import requests
import time
from urllib.parse import urljoin


class WeblateClient:
    def __init__(self, api_url, project, components, target_lang, api_key):
        self.api_url = api_url
        self.project = project
        self.target_lang = target_lang
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }
        self.components = sorted(components or self.get_project_components())
        self.glossary_components = sorted(
            self.get_project_components(filter_glossary=True)
        )
        units = list(
            self.get_translation_units(self.glossary_components, only_translated=True)
        )[0]
        self.glossary = {}
        for unit in units:
            for s, t in zip(unit["source"], unit["target"]):
                self.glossary[s] = t

    def _make_request(self, endpoint, req_type="get", **kwargs):
        url = urljoin(self.api_url, endpoint)
        request_with_type = getattr(requests, req_type.lower())
        headers = self.headers.copy()
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
            del kwargs["headers"]
        response = request_with_type(url, headers=headers, **kwargs)
        if response.status_code > 299:
            print("!" * 80)
            print("ERROR Response (%d): " % response.status_code, response.text)
            print("URL: %s" % url)
            print("!" * 80)
        # response.raise_for_status()
        return response.json()

    def get_project_components(self, filter_glossary=False):
        endpoint = f"projects/{self.project}/components/"
        response = self._make_request(endpoint)
        # FIXME: pagination of components needs to be implemented
        components = response.get("results", [])
        if filter_glossary:
            components = [c["slug"] for c in components if c.get("is_glossary", False)]
        else:
            components = [c["slug"] for c in components]
        return components

    def get_translation_units(
        self, components, only_translated=False, only_incomplete=False
    ):
        for component in components:
            has_more = True
            page = 0
            while has_more:
                endpoint = (
                    f"translations/{self.project}/{component}/{self.target_lang}/units/"
                )
                if only_translated:
                    params = {
                        "q": "state:>=translated",
                        "page_size": 1000,
                    }
                elif only_incomplete:
                    params = {
                        "q": "state:<translated OR state:needs-editing",
                        "page_size": 200,
                    }
                else:
                    params = {"page_size": 200}
                if page > 0:
                    params["page"] = page
                res = self._make_request(endpoint, req_type="get", params=params)
                if res.get("next"):
                    page += 1
                else:
                    has_more = False
                res = res.get("results")
                if res:
                    yield res

    def update_translation_unit(self, translated_unit):
        url = translated_unit["url"]
        # https://docs.weblate.org/en/latest/api.html#put--api-units-(int-id)-
        # state (int) – unit state, 0 - untranslated, 10 - needs editing, 20 - translated, 30 - approved (need review workflow enabled, see Dedicated reviewers)
        # target (array) – target string
        data = {
            "state": 20,
            "target": translated_unit["target"],
        }
        try:
            self._make_request(url, req_type="patch", json=data)
        except requests.exceptions.HTTPError as e:
            print("Failed to update translation unit: ", url)
            print(e)
        # time.sleep(5)