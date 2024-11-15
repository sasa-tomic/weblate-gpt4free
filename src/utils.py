import typing

import yaml


def load_config(config_path: str) -> typing.Any:  # noqa: ANN401
    with open(config_path, encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)
