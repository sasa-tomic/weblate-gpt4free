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
        "--provider",
        type=str,
        default="default",
        const="default",
        nargs="?",
        help="The provider name from the config.yml file to use for translation.",
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

    gpt_provider = config["gpt"]["providers"].get(args.provider)
    if not gpt_provider:
        print(f"Unknown GPT provider: {args.provider}. Available providers:")
        for provider in config["gpt"]["providers"]:
            print(provider)
        print()
        raise ValueError(f"Unknown GPT provider: {args.provider}")

    gpt_provider_name = gpt_provider.get("provider")
    gpt_model = gpt_provider["model"]
    gpt_api_key = gpt_provider.get("api_key")
    gpt_reliable = gpt_provider.get("reliable", False)

    for weblate in config["weblate"]:
        print(f"Processing {weblate['name']}...")
        target_lang = weblate["target_language"]
        cacher = Cacher(lang=target_lang)
        gpt_translator = GPTTranslator(
            prompt=config["gpt"]["prompt"],
            prompt_extension_flags_max_length=config["gpt"].get("prompt_extension_flags_max_length"),
            prompt_glossary=config["gpt"].get("prompt_glossary"),
            prompt_plural=config["gpt"].get("prompt_plural"),
            prompt_remind_translate=config["gpt"].get("prompt_remind_translate"),
            target_lang=target_lang,
            cacher=cacher,
            provider_name=gpt_provider_name,
            model=gpt_model,
            api_key=gpt_api_key,
            reliable=gpt_reliable,
        )
        processor = TranslationProcessor(
            weblate_name=weblate["name"],
            username=weblate["username"],
            api_url=weblate["api_url"],
            projects=weblate["projects"],
            target_lang=target_lang,
            weblate_api_key=weblate["api_key"],
            gpt_translator=gpt_translator,
            cacher=cacher,
            gpt_reliable=gpt_reliable,
            answer_yes=args.yes,
        )

        print("Processing incomplete translations...")
        processor.process_incomplete_translations()

    print("Translation process completed.")


if __name__ == "__main__":
    main()
