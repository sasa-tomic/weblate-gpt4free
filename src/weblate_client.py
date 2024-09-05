import requests
import time
from urllib.parse import urljoin


class WeblateClient:
    def __init__(self, api_url, project, components, target_lang, api_key):
        self.api_url = api_url
        self.project = project
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }
        self.components = sorted(
            components
            or [c["slug"] for c in self.get_project_components().get("results", [])]
        )
        self.target_lang = target_lang

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

    def get_project_components(self):
        endpoint = f"projects/{self.project}/components/"
        return self._make_request(endpoint)

    def get_incomplete_translation_units(self):
        for component in self.components:
            endpoint = (
                f"translations/{self.project}/{component}/{self.target_lang}/units/"
            )
            params = {
                "q": "state:<translated OR state:needs-editing",
            }
            yield self._make_request(endpoint, req_type="get", params=params).get(
                "results"
            )

    def update_translation_unit(self, translated_unit):
        url = translated_unit["url"]
        # https://docs.weblate.org/en/latest/api.html#put--api-units-(int-id)-
        # state (int) – unit state, 0 - untranslated, 10 - needs editing, 20 - translated, 30 - approved (need review workflow enabled, see Dedicated reviewers)
        # target (array) – target string
        data = {
            "state": 20,
            "target": translated_unit["target"],
        }
        print("# Translate from:\n", "\n---\n".join(translated_unit["source"]))
        print("# Translate to:\n", "\n---\n".join(translated_unit["target"]))
        try:
            self._make_request(url, req_type="patch", json=data)
        except requests.exceptions.HTTPError as e:
            print("Failed to update translation unit: ", url)
            print(e)
        # time.sleep(5)
