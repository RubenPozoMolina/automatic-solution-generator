import argparse
import logging

from src.asg import AutomaticSolutionGenerator
from utils.config_utils import ConfigUtils
from utils.log_utils import LogUtils


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", "-c",
        help="Config file path",
        required=True
    )
    args = parser.parse_args()

    log_utils = LogUtils()
    log_utils.log(logging.INFO, "Started")
    config_utils = ConfigUtils(args.config)
    config = config_utils.load_config()
    asg = AutomaticSolutionGenerator(config, log_utils)
    asg.generate_solution()
    log_utils.log(logging.INFO, "Finished")


if __name__ == "__main__":
    main()