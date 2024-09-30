import pathlib
import diskcache as dc


class Cacher:
    def __init__(self):
        self.cache = dc.Cache(pathlib.Path(__file__).parent.parent / "cache")

    def cache_get_unit(self, unit: dict):
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
