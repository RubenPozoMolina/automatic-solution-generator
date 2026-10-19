import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.log_utils import LogUtils
from utils.opencode_api import OpencodeAPI


def main():
    logger = LogUtils(console=True)

    base_url = os.getenv("OPENCODE_BASE_URL", "http://localhost:8000")
    username = os.getenv("OPENCODE_USERNAME", "user")
    password = os.getenv("OPENCODE_PASSWORD", "password")
    agent = os.getenv("OPENCODE_AGENT", "build")
    model_string = os.getenv("OPENCODE_MODEL", "opencode/big-pickle")
    model_array = model_string.split("/")
    model = {
        "id": model_array[1],
        "providerID": model_array[0]
    }
    message = os.getenv(
        "OPENCODE_MESSAGE",
        "Create a Python script called hello_world.py that prints 'Hello World' in build/test directory"
    )

    api = OpencodeAPI(logger, base_url, username, password)

    logger.log(logging.INFO, "Checking API health...")
    if not api.get_health():
        logger.log(logging.ERROR, "API is not healthy")
        return

    build_dir = os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)
                            )
        ), "build", "test"
    )
    os.makedirs(build_dir, exist_ok=True)

    session = api.get_session(agent, model, os.path.abspath(build_dir))
    if not session:
        logger.log(logging.ERROR, "Failed to create session")
        return

    api.send_prompt(session, message)
    api.wait_session(session)
    session_messages = api.get_session_messages(session)
    for message in session_messages["data"]:
        logger.log(logging.INFO, f"Message {message['id']}: {message}")
        logger.save_dict(message["id"], message)
    logger.log(logging.INFO, "Session completed")


if __name__ == "__main__":
    import logging

    main()
