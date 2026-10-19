import json
import logging
import os
import sys
from datetime import datetime


class LogUtils:

    _logger = None
    _path = None

    def __init__(self, path="logs", console=True):
        self._logger = logging.getLogger(__name__)
        self._path = path
        if not os.path.exists(self._path):
            os.makedirs(self._path)
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file_name = f"{path}{os.path.sep}{timestamp}-asg.log"
        log_format = f'%(asctime)s - %(levelname)s - %(message)s'
        
        file_handler = logging.FileHandler(log_file_name)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.basicConfig(
            level=logging.INFO,
            handlers=[file_handler],
            format=log_format
        )
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(log_format))
            self._logger.addHandler(console_handler)

    def log(self, level, message):
        self._logger.log(level, message)

    def save_dict(self, name, content):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_name = f"{self._path}{os.path.sep}{timestamp}-{name}.json"
        with open(file_name, 'w') as f:
            json.dump(content, f, indent=4)