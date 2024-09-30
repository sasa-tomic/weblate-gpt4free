import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gpt_translator import GPTTranslator
from src.translation_processor import TranslationProcessor
from src.utils import load_config
from src.cacher import Cacher


def main():
    config = load_config("config/config.yml")

    cacher = Cacher()
    gpt_translator = GPTTranslator(
        prompt=config["gpt"]["prompt"],
        prompt_extension_previous_translation=config["gpt"].get(
            "prompt_extension_previous_translation"
        ),
        prompt_extension_flags_max_length=config["gpt"].get(
            "prompt_extension_flags_max_length"
        ),
        prompt_glossary=config["gpt"].get("prompt_glossary"),
        prompt_remind_translate=config["gpt"].get("prompt_remind_translate"),
        target_lang=config["weblate"]["target_language"],
        api_key=config["gpt"].get("api_key"),
        cacher=cacher,
    )
    processor = TranslationProcessor(
        api_url=config["weblate"]["api_url"],
        projects=config["weblate"]["projects"],
        target_lang=config["weblate"]["target_language"],
        api_key=config["weblate"]["api_key"],
        gpt_translator=gpt_translator,
        cacher=cacher,
    )

    print("Processing incomplete translations...")
    processor.process_incomplete_translations()

    print("Translation process completed.")


if __name__ == "__main__":
    main()
