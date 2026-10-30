import argparse
import logging
import sys

from src.asg import AutomaticSolutionGenerator, SolutionGenerationError
from utils.config_utils import ConfigUtils
from utils.log_utils import LogUtils


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", "-c",
        help="Config file path",
        required=True
    )
    args = parser.parse_args()

    log_utils = LogUtils()
    log_utils.log(logging.INFO, "Started")
    config = ConfigUtils(args.config).load_config()

    try:
        AutomaticSolutionGenerator(config, log_utils).generate_solution()
    except SolutionGenerationError as error:
        log_utils.log(logging.ERROR, f"Solution generation failed: {error}")
        return 1

    log_utils.log(logging.INFO, "Finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
