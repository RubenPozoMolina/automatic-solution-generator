import logging
import time

import curlify
import requests

from requests.auth import HTTPBasicAuth
from utils.log_utils import LogUtils


class OpencodeAPI:
    base_url: str
    _username: str
    _password: str
    logger: LogUtils

    def __init__(self, logger: LogUtils, base_url: str, username: str, password: str):
        self.logger = logger
        self.base_url = base_url
        self._username = username
        self._password = password

    def get_basic_auth(self):
        return HTTPBasicAuth(self._username, self._password)

    @staticmethod
    def get_headers():
        return_value = {
            "Accept": "application/json",
        }
        return return_value

    def get_health(self):
        return_value = False
        info = self.get_info()
        if info:
            return_value = True
        return return_value

    def get_info(self):
        url = self.base_url + "/api/info"
        payload = {}
        headers = self.get_headers()
        response = requests.get(
            url,
            headers=headers,
            data=payload,
            auth=self.get_basic_auth()
        )
        if response.status_code == 200:
            return response.json()
        else:
            self.logger.log(
                logging.ERROR,
                f"Error getting info: {response.text}"
            )
            return None

    def get_config(self):
        url = self.base_url + "/api/config"
        headers = self.get_headers()
        response = requests.get(
            url,
            headers=headers,
            auth=self.get_basic_auth()
        )
        if response.status_code == 200:
            return response.json()
        else:
            self.logger.log(
                logging.ERROR,
                f"Error getting config: {response.text}"
            )
            return None


    def get_openapi(self):
        return_value = None
        try:
            url = self.base_url + "/openapi.json"
            payload = {}
            headers = self.get_headers()
            response = requests.get(
                url=url,
                headers=headers,
                data=payload,
                auth=self.get_basic_auth()
            )
            response.raise_for_status()
            return_value = response.json()
        except Exception as e:
            self.logger.log(
                logging.ERROR,
                f"Error getting openapi spec: {e}"
            )
        return return_value

    def get_agents(self):
        return_value = []
        try:
            url = self.base_url + "/api/agent"
            payload = {}
            headers = self.get_headers()
            response = requests.get(
                url=url,
                headers=headers,
                data=payload,
                auth=self.get_basic_auth()
            )
            response.raise_for_status()
            return_value = response.json()
        except Exception as e:
            self.logger.log(
                logging.ERROR,
                f"Error getting agents: {e}"
            )
        return return_value

    def get_session(self, agent, model, directory):
        return_value = None
        try:
            url = self.base_url + "/api/session"
            payload = {
                "agent": agent,
                "model": model,
                "location": {
                    "directory": directory
                }
            }
            headers = self.get_headers()
            headers["Content-Type"] = "application/json"
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                auth=self.get_basic_auth()
            )
            if response.status_code != 200:
                self.logger.log(
                    logging.ERROR,
                    f"Error creating session: {response.text}"
                )
            else:
                return_value = response.json()
        except Exception as e:
            self.logger.log(
                logging.ERROR,
                f"Error creating session: {e}"
            )
        return return_value

    def send_prompt(self, session, message, files=None):
        return_value = None
        try:
            session_id = session["data"]["id"]
            url = self.base_url + f"/api/session/{session_id}/prompt"
            payload = {
                "text": message,
                "files": []
            }
            if files:
                for file in files:
                    payload["files"].append(
                        {
                            "uri": "file://" + file
                        }
                    )
            headers = self.get_headers()
            headers["Content-Type"] = "application/json"
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                auth=self.get_basic_auth()
            )
            self.logger.log(
                logging.INFO,
                f"Sent prompt: {curlify.to_curl(response.request)}"
            )
            response.raise_for_status()
            return_value = response.json()
        except Exception as e:
            self.logger.log(
                logging.ERROR,
                f"Error sending prompt: {e}"
            )
        return return_value

    def get_session_inbox(self, session):
        return_value = None
        try:
            session_id = session["data"]["id"]
            url = self.base_url + f"/api/session/{session_id}/inbox"
            headers = self.get_headers()
            response = requests.get(
                url,
                headers=headers,
                auth=self.get_basic_auth()
            )
            if response.status_code == 200:
                return_value = response.json()
        except Exception as e:
            self.logger.log(
                logging.ERROR,
                f"Error getting session inbox: {e}"
            )
        return return_value

    def wait_session(self, session):
        return_value = False
        try:
            session_id = session["data"]["id"]
            url = self.base_url + f"/api/experimental/session/{session_id}/wait"
            headers = self.get_headers()
            response = requests.post(
                url,
                headers=headers,
                auth=self.get_basic_auth(),
                timeout=None
            )
            if response.status_code == 204:
                return_value = True
        except Exception as e:
            self.logger.log(
                logging.ERROR,
                f"Error waiting session: {e}"
            )
        return return_value

    def get_active_sessions(self):
        return_value = []
        try:
            url = self.base_url + "/api/session/active"
            headers = self.get_headers()
            response = requests.get(
                url,
                headers=headers,
                auth=self.get_basic_auth(),
                timeout=None
            )
            if response.status_code == 200:
                return_value = response.json()
        except Exception as e:
            self.logger.log(
                logging.ERROR,
                f"Error getting active sessions: {e}"
            )
        return return_value

    def get_session_messages(self, session, message_type=None):
        return_value = None
        try:
            session_id = session["data"]["id"]
            url = self.base_url + f"/api/session/{session_id}/message"
            params = {"order": "asc"}
            if message_type:
                params["type"] = message_type
            response = requests.get(
                url,
                headers=self.get_headers(),
                params=params,
                auth=self.get_basic_auth()
            )
            if response.status_code == 200:
                return_value = response.json()
            else:
                self.logger.log(
                    logging.ERROR,
                    f"Error getting session messages {response.status_code}: {response.text}"
                )
        except Exception as e:
            self.logger.log(
                logging.ERROR,
                f"Error getting session messages: {e}"
            )
        return return_value

    def wait_session_messages(self, session, timeout=60):
        return_value = False
        start_time = time.time()
        last_count = -1
        while time.time() - start_time < timeout:
            messages = self.get_session_messages(session)
            if messages and "data" in messages:
                current_count = len(messages["data"])
                if current_count == last_count and current_count > 0:
                    all_finished = True
                    for msg in messages["data"]:
                        if "status" in msg and msg["status"] not in ["completed", "error"]:
                            all_finished = False
                            break
                    if all_finished:
                        return_value = True
                        break
                last_count = current_count
            time.sleep(1)
        return return_value

    def execute_command(self, session, command_name, text, files=None, agents=None, skills=None, delivery=None):
        return_value = False
        try:
            session_id = session["data"]["id"]
            url = self.base_url + f"/api/session/{session_id}/command"
            
            # Build the full command text with / prefix
            if text.startswith(f"/{command_name}"):
                full_text = text
            else:
                full_text = f"/{command_name} {text}"
            
            payload = {
                "name": command_name,
                "text": full_text.strip(),
                "files": [],
                "agents": [],
                "skills": [],
            }
            
            # Add optional parameters if provided
            if files:
                for file in files:
                    payload["files"].append(file)
            
            if agents:
                for agent in agents:
                    payload["agents"].append(agent)
            
            if skills:
                for skill in skills:
                    payload["skills"].append(skill)
            
            if delivery:
                payload["delivery"] = delivery
            
            headers = self.get_headers()
            headers["Content-Type"] = "application/json"
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                auth=self.get_basic_auth()
            )
            
            # Accept any status < 400 as success (204 or 200)
            if response.status_code < 400:
                return_value = True
            else:
                self.logger.log(
                    logging.ERROR,
                    f"Error executing command '{command_name}': {response.status_code} - {response.text}"
                )
        except Exception as e:
            self.logger.log(
                logging.ERROR,
                f"Error executing command: {e}"
            )
        return return_value

