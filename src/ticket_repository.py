import json
import logging
import os
import tempfile
from typing import Any, Optional

from src.errors import SolutionGenerationError
from utils.log_utils import LogUtils

TICKET_FILE_EXTENSION = ".json"
TICKET_METADATA_FIELDS = frozenset({"filename", "filepath"})


class TicketRepository:

    def __init__(self, tasks_path: str, logger: LogUtils):
        self.tasks_path = tasks_path
        self.logger = logger

    def load_tickets(self) -> list[dict[str, Any]]:
        if not os.path.isdir(self.tasks_path):
            self.logger.log(logging.ERROR, f"Tasks directory does not exist: {self.tasks_path}")
            return []

        tickets = []
        for filename in sorted(os.listdir(self.tasks_path)):
            if not filename.endswith(TICKET_FILE_EXTENSION):
                continue
            ticket = self._load_ticket(filename)
            if ticket is not None:
                tickets.append(ticket)
        return tickets

    def _load_ticket(self, filename: str) -> Optional[dict[str, Any]]:
        filepath = os.path.join(self.tasks_path, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                ticket = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            self.logger.log(logging.ERROR, f"Error reading {filename}: {error}")
            return None
        ticket["filename"] = filename
        ticket["filepath"] = filepath
        return ticket

    def save_ticket(self, ticket: dict[str, Any]) -> None:
        filepath = ticket["filepath"]
        payload = {
            key: value
            for key, value in ticket.items()
            if key not in TICKET_METADATA_FIELDS
        }
        try:
            self._write_atomically(filepath, payload)
        except OSError as error:
            raise SolutionGenerationError(f"Error saving {filepath}: {error}") from error

    @staticmethod
    def _write_atomically(filepath: str, payload: dict[str, Any]) -> None:
        directory = os.path.dirname(filepath)
        file_descriptor, temporary_path = tempfile.mkstemp(
            dir=directory,
            prefix=".ticket-",
            suffix=TICKET_FILE_EXTENSION
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2, ensure_ascii=False)
                file.write("\n")
            os.replace(temporary_path, filepath)
        except OSError:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
            raise
