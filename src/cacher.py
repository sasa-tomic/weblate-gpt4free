import pathlib
import json
import diskcache as dc


class Cacher:
    def __init__(self):
        self.cache = dc.Cache(pathlib.Path(__file__).parent / "cache")

    def cache_get_unit(self, unit: dict):
        unit_cache_key = json.dumps(unit["source"])
        unit_cache_value = self.cache.get(unit_cache_key)
        if unit_cache_value:
            print("Found cache %s --> %s" % (unit_cache_key, unit_cache_value))
            return json.loads(unit_cache_value)
        return None

    def cache_update_unit(self, unit: dict):
        unit_cache_key = json.dumps(unit["source"])
        unit_cache_value = json.dumps(unit["target"])
        print("Updating cache %s --> %s" % (unit_cache_key, unit_cache_value))
        self.cache[unit_cache_key] = unit_cache_value

    def cache_get_string(self, string: str):
        string_cache_key = json.dumps([string])  # unit expects a list as key/value
        string_cache_value = self.cache.get(string_cache_key)
        if string_cache_value:
            print("Found cache %s --> %s" % (string_cache_key, string_cache_value))
            return json.loads(string_cache_value)[0]
        return None

    def cache_update_string(self, string: str):
        string_cache_key = json.dumps([string])  # unit expects a list as key
        string_cache_value = json.dumps([string])  # unit expects a list as value
        print("Updating cache %s --> %s" % (string_cache_key, string_cache_value))
        self.cache[string_cache_key] = string_cache_value

    def cache_clear(self):
        self.cache.clear()
