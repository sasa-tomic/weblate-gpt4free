import yaml


def load_config(config_path):
    with open(config_path, encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)
