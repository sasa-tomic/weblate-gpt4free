from .weblate_client import WeblateClient
from .gpt_translator import GPTTranslator
import editor
import sys


class TranslationProcessor:
    def __init__(
        self,
        api_url,
        project,
        components,
        target_lang,
        api_key,
        gpt_translator=GPTTranslator(),
    ):
        self.weblate_client = WeblateClient(
            api_url=api_url,
            project=project,
            components=components,
            target_lang=target_lang,
            api_key=api_key,
        )
        self.gpt_translator = gpt_translator

    def process_incomplete_translations(self):
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
        for unit in trans_units:
            to_translate.append(unit)
            to_translate_total_len += len(unit["source"])
            if to_translate_total_len > 20000:  # batch size, in chars
                trans_units = self.gpt_translator.translate(to_translate)
                for trans_unit in trans_units.values():
                    if trans_unit.get("target"):
                        to_commit.append(trans_unit)
                to_translate.clear()
                to_translate_total_len = 0

        if to_translate:
            trans_units = self.gpt_translator.translate(to_translate)
            for trans_unit in trans_units.values():
                if trans_unit.get("target"):
                    to_commit.append(trans_unit)

        if to_commit:
            accept_all = False
            for unit in to_commit:
                accept_all, unit = _ask_proceed(unit, accept_all)
                if not unit:
                    continue
                self.weblate_client.update_translation_unit(unit)
            to_commit.clear()


def _ask_proceed(unit: dict, accept_all: bool) -> tuple[bool, dict]:
    while True:
        print()
        print("*" * 80)
        print("\n".join(unit["source"]))
        print("\n".join(unit["target"]))
        if accept_all:
            proceed = "y"
        else:
            proceed = input("Submit yes/no/edit/all/quit [y/N/e/all/q]? ").lower()
        if proceed == "q":
            sys.exit(0)
        elif proceed == "e":
            s = "\n__EOU\n".join(unit["target"])
            unit["target"] = editor.edit(contents=s).decode("utf-8").split("\n__EOU\n")
        elif proceed == "all":
            accept_all = True
            break
        elif proceed == "y":
            break
        elif proceed == "n":
            return (accept_all, None)
    return (accept_all, unit)
