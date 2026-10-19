import json
import logging
import os

from utils.log_utils import LogUtils
from utils.opencode_api import OpencodeAPI


class AutomaticSolutionGenerator:
    config = None
    logger = None
    opencode_api = None
    agents = None
    requirements = None
    project_path = None

    def __init__(self, config, logger: LogUtils):
        self.config = config
        self.logger = logger
        self.load_opencode_api()
        self.project_path = os.path.abspath(self.config["project_path"])

    def load_opencode_api(self):
        try:
            self.opencode_api = OpencodeAPI(
                self.logger,
                self.config["opencode_base_url"],
                self.config["opencode_user"],
                self.config["opencode_password"]
            )
        except Exception as e:
            self.logger.log(
                logging.ERROR,
                f"Failed to load Opencode API: {e}"
            )

    def is_opencode_running(self):
        return self.opencode_api.get_health()

    def save_opencode_openapi(self, output):
        openapi = self.opencode_api.get_openapi()
        with open(output, "w") as f:
            json.dump(openapi, f, indent=4)

    def get_public_agents(self):
        return_value = []
        for agent in self.agents["data"]:
            if not agent["hidden"] and agent["mode"] == "primary" and agent["id"] not in ["build", "plan"]:
                return_value.append(agent)
        return return_value

    def load_requirements(self):
        with open(self.config["project_requirements"], "r") as f:
            self.requirements = f.read()

    def get_model_dict(self):
        model_string = self.config["model"]
        model_array = model_string.split("/")
        return_value = {
            "id": model_array[1],
            "providerID": model_array[0]
        }
        return return_value

    def get_agent(self, agent_id):
        return_value = None
        for agent in self.agents["data"]:
            if agent["id"] == agent_id:
                return_value = agent
        return return_value

    def generate_solution(self):
        if self.is_opencode_running():
            config = self.opencode_api.get_config()
            self.logger.save_dict("config", config)
            if not os.path.exists(self.config["project_path"]):
                os.makedirs(self.config["project_path"])
            self.load_requirements()
            self.save_opencode_openapi("openapi/opencode.json")
            self.agents = self.opencode_api.get_agents()
            project_finished = False
            iteration = 0
            while not project_finished:
                self.logger.log(logging.INFO, f"Starting iteration {iteration}")
                # TODO
                self.logger.log(logging.INFO, f"Finished iteration {iteration}")
                iteration += 1

        else:
            self.logger.log(logging.ERROR, "Opencode is not running")
