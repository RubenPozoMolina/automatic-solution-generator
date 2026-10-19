import yaml


class ConfigUtils:

    config = None

    def __init__(self, config_path):
        self.config_path = config_path

    def load_config(self):
        with open(self.config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        return self.config