#!/usr/bin/env python3
import json
import os.path
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import g4f  # type: ignore
import g4f.debug  # type: ignore
from g4f.cookies import read_cookie_files, set_cookies_dir  # type: ignore

from .cacher import Cacher

g4f.debug.logging = True

cookies_dir = os.path.join(os.path.dirname(__file__), "har_and_cookies")
set_cookies_dir(cookies_dir)
read_cookie_files(cookies_dir)


@dataclass
class TranslationResponse:
    translation_units: Dict[str, dict] = field(default_factory=dict)
    new_glossary: Dict[str, str] = field(default_factory=dict)
    is_reliable: bool = False


class GPTTranslator:
    def __init__(
        self,
        provider_name: str = "Openai",
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        reliable: bool = False,
        prompt: Optional[str] = None,
        prompt_extension_flags_max_length: Optional[str] = None,
        prompt_remind_translate: Optional[str] = None,
        prompt_glossary: Optional[str] = None,
        prompt_plural: Optional[str] = None,
        target_lang: str = "NONE. STOP TRANSLATION - UNSET LANGUAGE!",
        cacher: Optional[Cacher] = None,
        glossary: Optional[Dict[str, str]] = None,
    ) -> None:
        self.provider_name = provider_name
        self.model = model
        self.api_key = api_key
        self.reliable = reliable
        self.prompt = prompt or (
            f"Completely translate the following text to {target_lang}, not leaving any of the original "
            "text in the output, and return only the translated text. Make sure to keep the same "
            "formatting that the original text has"
        )
        self.prompt_extension_flags_max_length = prompt_extension_flags_max_length
        self.prompt_remind_translate = prompt_remind_translate or "Please fully translate"
        self.prompt_glossary = prompt_glossary or "Glossary"
        self.prompt_plural = prompt_plural
        self.glossary = glossary or {}
        self.cacher = cacher or Cacher(lang="unknown")

    def set_glossary(self, glossary: Dict[str, str]) -> None:
        """Set glossary (dict of word -> translation) for all translations, will be used in the prompt."""
        self.glossary = glossary

    def get_glossary_prompt(self, units: List[Dict]) -> str:
        used_glossary: Dict[str, str] = {}
        for unit in units:
            unit_source = " ".join(unit["source"]).lower()
            for term in self.glossary:
                # Search each weblate glossary item in input text to build relevant glossary items
                if term in unit_source:
                    used_glossary[term] = self.glossary[term]
            for term in unit_source.split():
                # Split source item text into terms and (inverse) search in persistent cacher glossary
                # Remove any leading or trailing non-alphanumerics
                term = re.sub(r"\W*(.+?)\W*$", r"\1", term, flags=re.UNICODE)
                if term in used_glossary:
                    continue
                cached_translation = self.cacher.cache_get_string(term)
                if cached_translation:
                    used_glossary[term] = f"{term}: {cached_translation}"
        if used_glossary:
            return self.prompt_glossary + ": " + "; ".join(used_glossary.values()) + "\n"
        return ""

    def _prepare_one(self, unit: Dict) -> str:
        result = ""
        result += (self.prompt_remind_translate.strip() + " ") or ""

        flags = unit.get("flags")
        if flags and "max-length:" in flags:
            result += f"{self.prompt_extension_flags_max_length}: {flags}"
        if len(unit["source"]) > 1:
            result += f" {self.prompt_plural}."
        unit_id = unit["id"]
        text = "\n__EOU\n".join(unit["source"])
        result += f"\n/>>B\n{unit_id}: {text}\nE<</"
        return result

    def translate(self, units: list[dict]) -> TranslationResponse:
        glossary_prompt = self.get_glossary_prompt(units) or ""
        input_text = (
            self.prompt + "\n\n" + glossary_prompt + "\n\n" + "\n\n".join([self._prepare_one(unit) for unit in units])
        )

        transl_units = {}
        for unit in units:
            del unit["target"]
            transl_units[unit["id"]] = unit

        print(input_text)
        print("Waiting before submission...")
        time.sleep(5)
        print("Submitting...")
        for attempt in range(3):
            try:
                if attempt > 0:
                    print("Retrying...")

                result, raw_response = self.get_translation(input_text)

                if result:
                    (result, raw_response) = self.get_grammar_checked(result)
                print(raw_response)

                if self.reliable:
                    new_glossary: dict[str, str] = {}
                else:
                    new_glossary_match = re.search(r"NEW_GLOSSARY: ({.+?})", raw_response, re.DOTALL)
                    new_glossary = {}
                    if new_glossary_match:
                        new_glossary_str = new_glossary_match.group(1)
                        try:
                            new_glossary = json.loads(new_glossary_str)
                        except ValueError:  # includes simplejson.decoder.JSONDecodeError:
                            print("Failed to parse new glossary:", new_glossary_str)
                for r in result:
                    if ":" not in r:
                        continue
                    unit_id_str, translation = r.split(":", 1)
                    unit_id = int(unit_id_str.strip())
                    transl_unit = transl_units.get(unit_id)
                    if transl_unit:
                        transl_unit["target"] = [t.strip() for t in translation.split("__EOU")]
                        transl_units[unit_id] = transl_unit
                if transl_units:
                    return TranslationResponse(transl_units, new_glossary, self.reliable)
                else:
                    print(input_text)
                    print(raw_response)
                    raise Exception(f"Could not find translations in response: {raw_response}")

            except Exception as e:
                print(e)

        raise Exception(f"Could not translate: {input_text}")

    def get_translation(self, text: str) -> Tuple[List[str], str]:
        raw_response = g4f.ChatCompletion.create(
            provider=self.provider_name,
            api_key=self.api_key,
            model=self.model,
            temperature=0.1,
            messages=[{"role": "user", "content": text}],
        )

        results = re.findall(r"/>>B(.+?)E<</", raw_response, re.DOTALL)
        if not results:
            print("Could not find translations in the response")
            print(text)
            print(raw_response)
            sys.exit(1)
            results, raw_response = [], ""
        return results, raw_response

    def get_grammar_checked(self, results: list[str]) -> Tuple[List[str], str]:
        text = (
            "Please fix grammar and typos in the following text and change word synonyms if needed to bring sentences "
            + "in line with the most commonly used modern forms of the language, but do not alter the language, alphabet, "
            + "whitespaces, newlines, and other special characters:\n\n"
            + "\n".join([f"\n/>>B\n{r}\nE<</" for r in results])
        )
        raw_response = g4f.ChatCompletion.create(
            provider=self.provider_name,
            api_key=self.api_key,
            model=self.model,
            temperature=0.1,
            messages=[{"role": "user", "content": text}],
        )

        results = re.findall(r"/>>B(.+?)E<</", raw_response, re.DOTALL)
        if not results:
            print("Could not find translations in the response")
            print(text)
            print(raw_response)
            sys.exit(1)
            results, raw_response = [], ""
        return results, raw_response
