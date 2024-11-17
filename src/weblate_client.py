from typing import Generator
from urllib.parse import urljoin

import requests


class WeblateClient:
    def __init__(self, api_url: str, project: str, target_lang: str, weblate_api_key: str) -> None:
        """Initialize the Weblate client

        Args:
            api_url (str): The Weblate API URL
            project (str): The project name
            target_lang (str): The target language
            weblate_api_key (str): The Weblate API key
        """
        self.api_url: str = api_url
        if "/" not in project:
            project += "/"
        self.project, component_str = project.split("/", 1)
        components = {component_str} if component_str else set()
        print("Parsed project and components:", self.project, components)
        self.target_lang = target_lang
        self.headers = {
            "Authorization": f"Token {weblate_api_key}",
            "Content-Type": "application/json",
        }
        self.glossary_components = sorted(self.get_project_components(filter_glossary=True))
        non_glossary_components = sorted(
            components or set(self.get_project_components()) - set(self.glossary_components)
        )
        self.default_incomplete_page_size = 50
        self._incomplete_page_size = self.default_incomplete_page_size
        # First translate the glossary
        self.components = self.glossary_components + non_glossary_components
        print(f"Translating project {project} and components {self.components}")
        self.glossary: dict[str, str] = {}
        self.rebuild_glossary()

    def _make_request(self, endpoint: str, req_type: str = "get", **kwargs: dict) -> dict:
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
            print(f"URL: {url}")
            print("!" * 80)
        # response.raise_for_status()
        return response.json()

    def rebuild_glossary(self) -> None:
        print("Rebuilding glossary...")
        self.glossary = {}
        # Get all the glossary units by converting them from an iterator to a list
        glossary_units = list(self.get_translation_units(self.glossary_components, only_translated=True))
        if glossary_units:
            for unit in glossary_units[0]:
                for src, tgt in zip(unit["source"], unit["target"]):
                    # Key is lowercased source, value is source + ": " + target
                    self.glossary[src.lower()] = f"{src}: {tgt or src}"
            print(f"Found {len(self.glossary)} glossary entries in {len(self.glossary_components)} components")

    def get_project_components(self, filter_glossary: bool = False) -> list[str]:
        endpoint = f"projects/{self.project}/components/"
        response = self._make_request(endpoint)
        # FIXME: pagination of components not yet implemented
        components = response.get("results", [])
        if filter_glossary:
            components = [c["slug"] for c in components if c.get("is_glossary", False)]
        else:
            components = [c["slug"] for c in components]
        return components

    def set_incomplete_page_size(self, size: int) -> None:
        print("Setting incomplete page size to %d" % size)
        self._incomplete_page_size = size

    @property
    def incomplete_page_size(self) -> int:
        return self._incomplete_page_size

    def get_translation_units(
        self, components: list[str], only_translated: bool = False, only_incomplete: bool = False
    ) -> Generator[list[dict], None, None]:
        for component in components:
            self._incomplete_page_size = self.default_incomplete_page_size
            has_more = True
            page = 0
            while has_more:
                endpoint = f"translations/{self.project}/{component}/{self.target_lang}/units/"
                if only_translated:
                    params = {
                        "q": "state:>=translated",
                        "page_size": 1000,
                    }
                    if page > 0:
                        params["page"] = page
                elif only_incomplete:
                    params = {
                        "q": "state:<translated AND (changed:<yesterday OR state:empty)",
                        "page_size": self._incomplete_page_size,
                    }
                else:
                    params = {"page_size": 200}
                res = self._make_request(endpoint, req_type="get", params=params)
                if res.get("next"):
                    page += 1
                else:
                    has_more = False
                results = res.get("results")
                if results:
                    yield results

    def update_translation_unit(self, translated_unit: dict, gpt_reliable: bool, auto_approved: bool) -> None:
        url = translated_unit["url"]
        # https://docs.weblate.org/en/latest/api.html#put--api-units-(int-id)-
        # state (int) – unit state:
        #   0 - untranslated
        #   10 - needs editing
        #   20 - translated
        #   30 - approved (need review workflow enabled, see Dedicated reviewers)
        # target (array) – target string
        data = {
            "state": 20 if gpt_reliable or not auto_approved else 10,
            "target": translated_unit["target"],
        }
        try:
            self._make_request(url, req_type="patch", json=data)
        except requests.exceptions.HTTPError as e:
            print("Failed to update translation unit: ", url)
            print(e)
