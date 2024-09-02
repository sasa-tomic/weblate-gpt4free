from .weblate_client import WeblateClient
from .gpt_translator import GPTTranslator


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
        for trans_units in self.weblate_client.get_incomplete_translation_units():
            if not trans_units:
                continue
            self._process_translation(trans_units)

    def _process_translation(self, trans_units: list[dict]):
        for unit in trans_units:
            print("*" * 50)
            print("Translation unit: ", unit)
            previous_translation = ("\n".join(unit.get("target", []))).strip() or None
            del unit["target"]
            skip_translation = False
            for source in unit["source"]:
                translated_text = self.gpt_translator.translate(
                    text=source,
                    previous_translation=previous_translation,
                    flags=unit.get("flags"),
                )
                if translated_text:
                    unit["target"] = unit.get("target", []) + [translated_text]
                else:
                    print("Translation failed")
                    skip_translation = True
                    continue
            if not skip_translation:
                self.weblate_client.update_translation_unit(unit)
