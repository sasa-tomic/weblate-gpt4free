from .cacher import Cacher
from .weblate_client import WeblateClient
import editor
import sys


class TranslationProcessor:
    def __init__(
        self,
        api_url,
        projects,
        target_lang,
        weblate_api_key,
        gpt_translator,
        cacher: Cacher,
    ):
        self.api_url = api_url
        self.projects = projects
        self.target_lang = target_lang
        self.weblate_api_key = weblate_api_key
        self.weblate_client = None
        self.gpt_translator = gpt_translator
        self.cacher = cacher

    def update_weblate_client(self, project):
        self.weblate_client = WeblateClient(
            api_url=self.api_url,
            project=project,
            target_lang=self.target_lang,
            weblate_api_key=self.weblate_api_key,
        )

    def process_incomplete_translations(self):
        for project in self.projects:
            print("Processing project[/component]:", project)
            self.update_weblate_client(project)
            for trans_units in self.weblate_client.get_translation_units(
                self.weblate_client.components, only_incomplete=True
            ):
                if not trans_units:
                    continue
                self._process_translation(trans_units)

    def _process_translation(self, trans_units: list[dict]):
        print("Processing %d incomplete translations..." % len(trans_units))
        to_translate = []
        to_translate_total_len = 0  # Prompt length assumption
        to_commit = []
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
                transl_units, new_glossary = self.gpt_translator.translate(to_translate)
                for k, v in new_glossary.items():
                    if self.cacher.cache_get_string(k):
                        print("Glossary cache already has an entry for %s" % k)
                    else:
                        print("Updating glossary cache %s --> %s" % (k, v))
                        self.cacher.cache_update_string(k, v)
                for trans_unit in transl_units.values():
                    if trans_unit.get("target"):
                        to_commit.append(trans_unit)
                to_translate.clear()
                to_translate_total_len = 0

        if to_translate:
            transl_units, new_glossary = self.gpt_translator.translate(to_translate)
            for k, v in new_glossary.items():
                print("Updating glossary cache %s --> %s" % (k, v))
                self.cacher.cache_update_string(k, v)
            for trans_unit in transl_units.values():
                if trans_unit.get("target"):
                    to_commit.append(trans_unit)

        commit_count = 0
        if to_commit:
            accept_all = None
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
                if unit["target"] == cached_translation_target == unit["source"]:
                    # User confirmed that the source and target are the same
                    print("Skipping translation of unit with no changes")
                    continue
                accept_all, unit_to_update = _ask_proceed(unit, accept_all)
                if not unit_to_update:
                    continue
                self.cacher.cache_update_unit(unit_to_update)
                self.weblate_client.update_translation_unit(unit_to_update)
                commit_count += 1
            to_commit.clear()

        # Compensate for the skipped translations
        self.weblate_client.set_incomplete_page_size(
            self.weblate_client.default_incomplete_page_size
            + (self.weblate_client.default_incomplete_page_size - commit_count)
        )


def _print_one(unit: dict):
    print()
    print("*" * 80)
    print("Unit web URL:", unit["web_url"])
    print("*" * 80)
    print("\n".join(unit["source"]))
    print("-" * 40)
    print("\n".join(unit["target"]))


def _ask_proceed(unit: dict, accept_all: str) -> tuple[str, dict]:
    while True:
        _print_one(unit)
        if accept_all:
            proceed = accept_all
        else:
            proceed = input(
                "Submit yes/no/edit/all/skip all/quit [y/n/e/all/skip/q]? "
            ).lower()
        if proceed == "q":
            sys.exit(0)
        elif proceed == "e":
            s = "\n__EOU\n".join(unit["target"])
            unit["target"] = (
                editor.edit(contents=s).decode("utf-8").strip().split("\n__EOU\n")
            )
        elif proceed == "all":
            accept_all = "y"
            break
        elif proceed == "skip":
            accept_all = "n"
            break
        elif proceed == "y":
            break
        elif proceed == "n":
            return (accept_all, None)
    return (accept_all, unit)
