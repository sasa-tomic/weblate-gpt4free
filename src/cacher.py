import itertools
import pathlib
import diskcache as dc


class Cacher:
    def __init__(self, lang: str):
        self.cache = dc.Cache(pathlib.Path(__file__).parent.parent / "cache" / lang)

    def cache_get_unit(self, unit: dict):
        """
        Check if all translations are in cache. If so, return translations.
        """
        translations = []
        for source_string in unit["source"]:
            translation = self.cache_get_string(source_string) or match_complex_case(
                source_string, self.cache_get_string(source_string.lower())
            )
            if translation is None:
                return None
            translations.append(translation)
        return translations

    def cache_update_unit(self, unit: dict):
        for s, t in zip(unit["source"], unit["target"]):
            self.cache_update_string(s, t)

    def cache_get_string(self, key: str):
        value = self.cache.get(key)
        if value is None:
            return None
        # print("Found cache %s --> %s" % (key, value))
        return value

    def cache_update_string(self, key: str, value: str):
        # print("Updating cache %s --> %s" % (key, value))
        self.cache[key] = value

    def cache_clear(self):
        self.cache.clear()


def match_complex_case(reference_str, target_str):
    if not reference_str or not target_str:
        return None

    def match_char_case(ref_char, target_char):
        if ref_char.isupper():
            return target_char.upper()
        else:
            return target_char.lower()

    # Iterate over both strings and apply case based on the reference string
    result = "".join(
        match_char_case(ref_char, target_char)
        for ref_char, target_char in zip(reference_str, itertools.cycle(target_str))
    )

    return result
