import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cacher import Cacher
from src.gpt_translator import GPTTranslator
from src.translation_processor import TranslationProcessor
from src.utils import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate missing strings in a Weblate project using GPT.")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="The model name to use for translation. If not provided, the default model will be used.",
    )
    parser.add_argument(
        "--cheap-translation",
        action="store_true",
        default=False,
        help="Use the cheap translation model if available. If not available, the expensive model will be used.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Answer yes to all prompts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    config = load_config("config/config.yml")

    if args.cheap_translation:
        model = args.model or config["gpt"]["model_cheap"]
    else:
        model = args.model or config["gpt"]["model_expensive"]

    for weblate in config["weblate"]:
        print(f"Processing {weblate['name']}...")
        target_lang = weblate["target_language"]
        cacher = Cacher(lang=target_lang)	
        gpt_translator = GPTTranslator(
            prompt=config["gpt"]["prompt"],
            prompt_extension_flags_max_length=config["gpt"].get(
                "prompt_extension_flags_max_length"
            ),
            prompt_glossary=config["gpt"].get("prompt_glossary"),
            prompt_plural=config["gpt"].get("prompt_plural"),
            prompt_remind_translate=config["gpt"].get("prompt_remind_translate"),
            target_lang=target_lang,
            api_key_expensive=config["gpt"].get("api_key_expensive"),
            api_key_cheap=config["gpt"].get("api_key_cheap"),
            cacher=cacher,
            model=model,
            use_cheap=args.cheap_translation,
        )
        processor = TranslationProcessor(
            weblate_name=weblate["name"],
            api_url=weblate["api_url"],
            projects=weblate["projects"],
            target_lang=target_lang,
            weblate_api_key=weblate["api_key"],
            gpt_translator=gpt_translator,
            cacher=cacher,
            use_cheap_translation=args.cheap_translation,
            answer_yes=args.yes,
        )

        print("Processing incomplete translations...")
        processor.process_incomplete_translations()

    print("Translation process completed.")


if __name__ == "__main__":
    main()
