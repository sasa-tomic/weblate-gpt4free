import datetime
import re
import sys

import editor  # type: ignore

from .cacher import Cacher
from .gpt_translator import GPTTranslator, TranslationResponse
from .weblate_client import WeblateClient


class TranslationProcessor:
    def __init__(
        self,
        weblate_name: str,
        api_url: str,
        projects: list[str],
        target_lang: str,
        weblate_api_key: str,
        gpt_translator: GPTTranslator,
        cacher: Cacher,
        gpt_reliable: bool,
        answer_yes: bool,
    ) -> None:
        self.weblate_name = weblate_name
        self.api_url = api_url
        self.projects = projects
        self.target_lang = target_lang
        self.weblate_api_key = weblate_api_key
        self.weblate_client: WeblateClient | None = None
        self.gpt_translator: GPTTranslator = gpt_translator
        self.cacher = cacher
        self.gpt_reliable = gpt_reliable
        self.answer_yes = answer_yes

    def update_weblate_client(self, project: str) -> None:
        self.weblate_client = WeblateClient(
            api_url=self.api_url,
            project=project,
            target_lang=self.target_lang,
            weblate_api_key=self.weblate_api_key,
        )

    def process_incomplete_translations(self) -> None:
        for project in self.projects:
            if self._project_completed_recently(project):
                print("Skipping project since it was recently completed:", project)
                continue
            self.update_weblate_client(project)
            if self.weblate_client is None:
                print("ERROR: self.weblate_client is not set")
                return
            for component, trans_units, has_more in self.weblate_client.get_translation_units(
                self.weblate_client.components, only_incomplete=True
            ):
                print(f"Processing project: {project} and component {component}")
                if trans_units:
                    self._process_translation(trans_units)
                if self.answer_yes and not has_more:
                    # Notify user and ask for user input to continue
                    print("Completed component:", component)
                    # Example review URL:
                    # https://hosted.weblate.org/zen/tor/tor-browser/tb-android/sr/?offset=0&q=state%3Aneeds-editing&sort_by=last_updated&checksum=
                    base_url = re.sub(r"/translate/", "/zen/", trans_units[-1]["web_url"])
                    base_url = re.sub(r"\?checksum=[a-zA-Z0-9]+", "", base_url)
                    print(f"Review changes at: {base_url}?q=state%3Aneeds-editing&sort_by=last_updated")
                    input("Press enter to continue...")
            self._mark_project_completed(project)

    def _project_completed_recently(self, project: str) -> bool:
        cache_dir = self.cacher.cache_dir() / self.weblate_name
        cache_dir.mkdir(exist_ok=True, parents=True)
        path = cache_dir / (project + ".completed")
        if path.exists():
            filetime = datetime.datetime.fromtimestamp(path.stat().st_mtime)
            if filetime > datetime.datetime.now() - datetime.timedelta(days=1):
                return True
            else:
                print("Project completion expired:", project)
        return False

    def _mark_project_completed(self, project: str) -> None:
        cache_dir = self.cacher.cache_dir() / self.weblate_name
        cache_dir.mkdir(exist_ok=True, parents=True)
        path = cache_dir / (project + ".completed")
        print("Marking project as completed:", project)
        path.touch()

    def _process_translation(self, trans_units: list[dict]) -> None:
        print("Processing %d incomplete translations..." % len(trans_units))
        to_translate: list[dict] = []
        to_translate_total_len = 0  # Prompt length assumption
        to_commit: list[dict] = []
        if self.weblate_client is None:
            print("ERROR: self.weblate_client is not set")
            return
        if self.weblate_client.glossary:
            self.gpt_translator.set_glossary(self.weblate_client.glossary)
        for unit_to_update in trans_units:
            cached_translation_target = self.cacher.cache_get_unit(unit_to_update)
            if cached_translation_target:
                unit_to_update["target"] = cached_translation_target
                to_commit.append(unit_to_update)
                continue
            to_translate.append(unit_to_update)
            to_translate_total_len += len(unit_to_update["source"])
            if to_translate_total_len > 20000:  # batch size, in chars
                transl_part: TranslationResponse = self.gpt_translator.translate(to_translate)
                if transl_part.new_glossary:
                    print("New glossary:")
                    for k, v in transl_part.new_glossary.items():
                        print(f"  {k} --> {v}")
                    update_glossary = self.answer_yes or input("Update glossary [y/n]? ").lower()
                    if update_glossary == "y":
                        for k, v in transl_part.new_glossary.items():
                            if self.cacher.cache_get_string(k):
                                print(f"Glossary cache already has an entry for {k}")
                            else:
                                print(f"Updating glossary cache {k} --> {v}")
                                self.cacher.cache_update_string(k, v)
                for trans_unit in transl_part.translation_units.values():
                    if trans_unit.get("target"):
                        to_commit.append(trans_unit)
                to_translate.clear()
                to_translate_total_len = 0

        if to_translate:
            transl_final: TranslationResponse = self.gpt_translator.translate(to_translate)
            if transl_final.new_glossary:
                for k, v in transl_final.new_glossary.items():
                    print(f"  {k} --> {v}")
                update_glossary = self.answer_yes or input("Update glossary [y/n]? ").lower()
                if update_glossary == "y":
                    for k, v in transl_final.new_glossary.items():
                        if self.cacher.cache_get_string(k):
                            print(f"Glossary cache already has an entry for {k}")
                        else:
                            print(f"Updating glossary cache {k} --> {v}")
                            self.cacher.cache_update_string(k, v)
            for trans_unit in transl_final.translation_units.values():
                if trans_unit.get("target"):
                    to_commit.append(trans_unit)

        commit_count = 0
        if to_commit:
            accept_all = "y" if self.answer_yes else None
            print(">" * 80)
            print("> Here is the entire translation")
            print(">" * 80)
            for unit_to_update in to_commit:
                _print_one(unit_to_update)
            print("!" * 80)
            print("! Proceeding with the commit of translations")
            print("!" * 80)
            for unit in to_commit:
                cached_translation_target = self.cacher.cache_get_unit(unit)
                accept_all, unit_to_update = _ask_proceed(unit, accept_all)
                if not unit_to_update:
                    continue
                if self.gpt_reliable:
                    self.cacher.cache_update_unit(unit_to_update)
                self.weblate_client.update_translation_unit(
                    unit_to_update, gpt_reliable=self.gpt_reliable, auto_approved=self.answer_yes
                )
                commit_count += 1
            to_commit.clear()

        # Compensate for the skipped translations
        self.weblate_client.set_incomplete_page_size(
            self.weblate_client.default_incomplete_page_size
            + (self.weblate_client.default_incomplete_page_size - commit_count)
        )


def _print_one(unit: dict) -> None:
    print()
    print("*" * 80)
    print("Unit web URL:", unit["web_url"])
    print("*" * 80)
    print("\n".join(unit["source"]))
    print("-" * 40)
    print("\n".join(unit["target"]))


def _ask_proceed(unit: dict, accept_all: str | None) -> tuple[str | None, dict]:
    while True:
        _print_one(unit)
        if accept_all:
            proceed = accept_all
        else:
            proceed = input("Submit yes/no/edit/all/skip all/quit [y/n/e/all/skip/q]? ").lower()
        if proceed == "q":
            sys.exit(0)
        elif proceed == "e":
            s = "\n__EOU\n".join(unit["target"])
            unit["target"] = editor.edit(contents=s).decode("utf-8").strip().split("\n__EOU\n")
        elif proceed == "all":
            accept_all = "y"
            break
        elif proceed == "skip":
            accept_all = "n"
            break
        elif proceed == "y":
            break
        elif proceed == "n":
            return (accept_all, {})
    return (accept_all, unit)
