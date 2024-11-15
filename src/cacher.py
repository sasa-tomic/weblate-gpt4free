import pathlib

import diskcache as dc  # type: ignore


class Cacher:
    def __init__(self, lang: str) -> None:
        self.cache = dc.Cache(pathlib.Path(__file__).parent.parent / "cache" / lang)

    def cache_dir(self) -> pathlib.Path:
        return self._cache_dir

    def cache_get_unit(self, unit: dict) -> list[str] | None:
        """
        Check if all translations are in cache. If so, return translations.
        """
        translations = []
        for source_string in unit["source"]:
            translation = self.cache_get_string(source_string)
            if translation is None:
                return None
            translations.append(translation)
        return translations

    def cache_update_unit(self, unit: dict) -> None:
        for s, t in zip(unit["source"], unit["target"]):
            self.cache_update_string(s, t)

    def cache_get_string(self, key: str) -> str | None:
        value = self.cache.get(key)
        if value is None and key != key.capitalize():
            value = match_complex_case(key, self.cache.get(key.capitalize()))
        if value is None and key != key.lower():
            value = match_complex_case(key, self.cache.get(key.lower()))
        if value is None:
            return None
        # print("Found cache %s --> %s" % (key, value))
        return value

    def cache_update_string(self, key: str, value: str) -> None:
        # print("Updating cache %s --> %s" % (key, value))
        self.cache[key] = value

    def cache_clear(self) -> None:
        self.cache.clear()


def match_complex_case(reference_str: str, target_str: str) -> str | None:
    if not reference_str or not target_str:
        return None

    def match_char_case(ref_char: str, target_char: str) -> str:
        if ref_char.isupper():
            return target_char.upper()
        else:
            return target_char.lower()

    if len(reference_str) < len(target_str):
        # target string is longer than the source string
        # ==> repeat the last char of the source string to match the length of the target string
        reference_str += reference_str[-1] * (len(target_str) - len(reference_str))
    # Iterate over both strings and apply case based on the reference string
    result = "".join(match_char_case(ref_char, target_char) for ref_char, target_char in zip(reference_str, target_str))

    return result
