import json
import logging
import os
from time import sleep

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
        if not os.path.exists("openapi"):
            os.makedirs("openapi")
        openapi = self.opencode_api.get_openapi()
        with open(output, "w") as f:
            json.dump(openapi, f, indent=4)

    def get_public_agents(self):
        return_value = []
        for agent in self.agents["data"]:
            if not agent["hidden"] and agent["mode"] == "primary" and agent["id"] not in ["build", "plan"]:
                return_value.append(agent)
        return return_value

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

    def get_requirements_analysis(self):
        return_value = f"Create PRD from interview in: {self.config['customer_interview']}"
        return_value += f" Save the PRD in: {self.config['project_path']}/prd.md"
        return return_value

    def get_generate_tasks(self):
        return_value = f"Analyze PRD at {self.config['project_path']}/prd.md and create all tasks using the create-ticket skill"
        return_value += f". Each task must be saved as a separate markdown file in the {self.config['project_path']}/tasks/ directory"
        return_value += f". If previous tasks exist, do not create tasks that have already been created"
        return return_value

    def get_customer_interview(self):
        return_value = ""
        if "customer_interview" in self.config:
            try:
                abs_path = os.path.abspath(self.config["customer_interview"])
                return_value = abs_path
            except Exception as e:
                self.logger.log(
                    logging.ERROR,
                    f"Failed to get customer interview: {e}"
                )
        return return_value

    def generate_solution(self):
        if self.is_opencode_running():
            config = self.opencode_api.get_config()
            self.logger.save_dict("config", config)
            if not os.path.exists(self.config["project_path"]):
                os.makedirs(self.config["project_path"])
            self.save_opencode_openapi("openapi/opencode.json")
            self.agents = self.opencode_api.get_agents()
            project_finished = False
            iteration = 0
            requirements_analysis = self.get_requirements_analysis()
            self.process(
                "product-manager",
                iteration,
                requirements_analysis,
                [self.get_customer_interview()]
            )
            # Project Manager genera las tareas desde el PRD
            tasks_prompt = self.get_generate_tasks()
            prd_abs_path = os.path.abspath(self.config['project_path'] + "/prd.md")
            self.process(
                "project-manager",
                iteration,
                tasks_prompt,
                [prd_abs_path]
            )
            # while not project_finished:
            #     self.logger.log(logging.INFO, f"Starting iteration {iteration}")
            #     self.logger.log(logging.INFO, f"Finished iteration {iteration}")
            #     iteration += 1
        else:
            self.logger.log(logging.ERROR, "Opencode is not running")

    def process(self, agent, iteration, prompt, files):
        session = self.opencode_api.get_session(
            agent,
            self.get_model_dict(),
            self.project_path
        )
        if session:
            success = self.opencode_api.send_prompt(
                session=session,
                message=prompt,
                files=files
            )

            if success:
                self.logger.log(
                    logging.INFO,
                    f"agent {agent} iteration {iteration} prompt {prompt[0:100]}"
                )
                # Wait for session completion
                self.opencode_api.wait_session(session)

                # Retrieve and log session messages
                session_messages = self.opencode_api.get_session_messages(session)
                if session_messages and "data" in session_messages:
                    for message in session_messages["data"]:
                        self.logger.log(logging.INFO, f"Message {message['id']}: {message}")
                        self.logger.save_dict(message["id"], message)
                self.logger.log(logging.INFO, f"Session completed for agent {agent}")
            else:
                self.logger.log(logging.ERROR, f"Failed to execute command for agent {agent}")
        else:
            self.logger.log(logging.ERROR, f"Failed to create session for agent {agent}")