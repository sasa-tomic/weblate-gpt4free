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

    def translate(self, text, previous_translation=None, flags=None):
        prompt_extension = ""
        if previous_translation:
            prompt_extension += f"{self.prompt_extension_previous_translation}:\n__PREV_BEGIN\n{previous_translation}\n__PREV_END\n"
        if flags and "max-length:" in flags:
            prompt_extension += f"{self.prompt_extension_flags_max_length}: {flags}"
        if prompt_extension:
            if "{}" in self.prompt:
                prompt = self.prompt.format(prompt_extension)
            else:
                prompt = self.prompt + " " + prompt_extension
        else:
            prompt = self.prompt.replace("{}", "")
        prompt += f":\n\n{text}"

        for attempt in range(3):
            try:
                if attempt > 0:
                    print("Retrying...")
                print(prompt)

                result, raw_response = self.translate_cheap(prompt)

                print(result)
                proceed = input("Proceed? [y/N] ")
                if not proceed.lower().startswith("y"):
                    result, raw_response = self.translate_expensive(prompt)
                    print(result)
                    proceed = input("Proceed? [y/N] ")
                    if not proceed.lower().startswith("y"):
                        return ""

                if result:
                    return result
                else:
                    if "EMPTY" in raw_response or not (
                        "BEGIN" in raw_response and "END" in raw_response
                    ):
                        return ""
                    print(prompt)
                    print(raw_response)
                    raise Exception(
                        f"Could not find translation in response: {raw_response}"
                    )

            except Exception as e:
                print(e)

        raise Exception(f"Could not translate: {text}")

    def translate_cheap(self, text):
        raw_response = g4f.ChatCompletion.create(
            # provider=g4f.Provider.OpenaiChat,
            # provider=g4f.Provider.Chatgpt4Online,
            # provider=g4f.Provider.You,
            provider=g4f.Provider.ChatgptFree,
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": text}],
        )

        result = (
            re.search(r"__\s*BEGIN__\s*(.*)\s*__END__", raw_response, re.DOTALL)
            .group(1)
            .strip()
        )
        return result, raw_response

    def translate_expensive(self, text):
        raw_response = g4f.ChatCompletion.create(
            provider=g4f.Provider.Openai,
            api_key=self.api_key,
            model="gpt-4o",
            messages=[{"role": "user", "content": text}],
        )

        result = (
            re.search(r"__\s*BEGIN__\s*(.*)\s*__END__", raw_response, re.DOTALL)
            .group(1)
            .strip()
        )
        return result, raw_response
