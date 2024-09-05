import os.path
import re
import g4f
import g4f.debug
from g4f.cookies import set_cookies_dir, read_cookie_files

g4f.debug.logging = True

cookies_dir = os.path.join(os.path.dirname(__file__), "har_and_cookies")
set_cookies_dir(cookies_dir)
read_cookie_files(cookies_dir)


class GPTTranslator:
    def __init__(
        self,
        model="gpt-3.5-turbo",
        prompt=None,
        prompt_extension_previous_translation=None,
        prompt_extension_flags_max_length=None,
        target_lang="NONE. STOP TRANSLATION - UNSET LANGUAGE!",
        api_key=None,
    ):
        self.model = model
        self.prompt = (
            prompt
            or f"Completely translate the following text to {target_lang}, not leaving any of the original text in the output, and return only the translated text. Make sure to keep the same formatting that the original text has"
        )
        self.prompt_extension_previous_translation = (
            prompt_extension_previous_translation
        )
        self.prompt_extension_flags_max_length = prompt_extension_flags_max_length
        self.api_key = api_key

    def _prepare_one(self, unit):
        result = ""
        previous_translation = [t for t in unit.get("target", []) if t.strip()]
        if previous_translation:
            print(previous_translation)
            result = """
Previous translation:
__PREV_BEGIN
{previous_translation}
__PREV_END
""".format(
                previous_translation=previous_translation,
            )

        flags = unit.get("flags", None)
        if flags and "max-length:" in flags:
            result += f"{self.prompt_extension_flags_max_length}: {flags}"
        unit_id = unit["id"]
        text = "\n__EOU\n".join(unit["source"])
        result += f"\n/>>B\n{unit_id}: {text}\nE<</"
        return result

    def translate(self, units=list[dict]):
        input_text = self.prompt + "\n\n".join(
            [self._prepare_one(unit) for unit in units]
        )

        transl_units = {}
        for unit in units:
            del unit["target"]
            transl_units[unit["id"]] = unit

        for attempt in range(3):
            try:
                if attempt > 0:
                    print("Retrying...")
                print(input_text)

                try_expensive = 1
                while True:
                    if try_expensive:
                        result, raw_response = self.translate_expensive(input_text)
                    else:
                        result, raw_response = self.translate_cheap(input_text)

                    for r in result:
                        print(r)

                    proceed = input(
                        "Retry cheap | retry expensive | done? [c/e/d] "
                    ).lower()
                    if proceed == "d":
                        break
                    elif proceed == "c":
                        try_expensive = 0
                    elif proceed == "e":
                        try_expensive = 1

                for r in result:
                    unit_id, translation = r.split(":", 1)
                    unit_id = int(unit_id.strip())
                    unit = transl_units.get(unit_id)
                    if unit:
                        unit["target"] = [t.strip() for t in translation.split("__EOU")]
                        transl_units[unit_id] = unit
                if transl_units:
                    return transl_units
                else:
                    if "EMPTY" in raw_response or not (
                        "/>>B" in raw_response and "E<</" in raw_response
                    ):
                        return ""
                    print(input_text)
                    print(raw_response)
                    raise Exception(
                        f"Could not find translations in response: {raw_response}"
                    )

            except Exception as e:
                print(e)

        raise Exception(f"Could not translate: {input_text}")

    def translate_cheap(self, text):
        raw_response = g4f.ChatCompletion.create(
            # provider=g4f.Provider.OpenaiChat,
            # provider=g4f.Provider.Chatgpt4Online,
            # provider=g4f.Provider.You,
            # provider=g4f.Provider.ChatgptFree,
            # model="gpt-3.5-turbo",
            provider=g4f.Provider.Openai,
            api_key=self.api_key,
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[{"role": "user", "content": text}],
        )

        results = re.findall(r"/>>B(.+?)E<</", raw_response, re.DOTALL)
        if not results:
            print("Could not find translations in the response")
            print(text)
            print(raw_response)
            results, raw_response = "", ""
        return results, raw_response

    def translate_expensive(self, text):
        raw_response = g4f.ChatCompletion.create(
            provider=g4f.Provider.Openai,
            api_key=self.api_key,
            model="gpt-4o",
            temperature=0.1,
            messages=[{"role": "user", "content": text}],
        )

        results = re.findall(r"/>>B(.+?)E<</", raw_response, re.DOTALL)
        if not results:
            print("Could not find translations in the response")
            print(text)
            print(raw_response)
            results, raw_response = "", ""
        return results, raw_response
