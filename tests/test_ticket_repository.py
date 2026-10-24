import json

import pytest

from src.errors import SolutionGenerationError
from src.ticket_repository import TicketRepository


@pytest.fixture
def tasks_path(tmp_path):
    path = tmp_path / "tasks"
    path.mkdir()
    return path


@pytest.fixture
def repository(tasks_path, logger):
    return TicketRepository(str(tasks_path), logger)


def write_ticket(tasks_path, ticket, filename=None):
    filename = filename or f"{ticket['id']}.json"
    path = tasks_path / filename
    path.write_text(json.dumps(ticket), encoding="utf-8")
    return path


def test_load_tickets_returns_empty_list_when_directory_is_missing(tmp_path, logger):
    repository = TicketRepository(str(tmp_path / "missing"), logger)

    assert repository.load_tickets() == []


def test_load_tickets_adds_metadata_and_sorts_by_filename(tasks_path, repository):
    write_ticket(tasks_path, {"id": "TASK-002", "status": "Backlog"})
    write_ticket(tasks_path, {"id": "TASK-001", "status": "Backlog"})

    tickets = repository.load_tickets()

    assert [ticket["id"] for ticket in tickets] == ["TASK-001", "TASK-002"]
    assert tickets[0]["filename"] == "TASK-001.json"
    assert tickets[0]["filepath"] == str(tasks_path / "TASK-001.json")


def test_load_tickets_ignores_non_json_files(tasks_path, repository):
    write_ticket(tasks_path, {"id": "TASK-001", "status": "Backlog"})
    (tasks_path / "notes.md").write_text("not a ticket", encoding="utf-8")

    tickets = repository.load_tickets()

    assert len(tickets) == 1


def test_load_tickets_skips_invalid_json_and_logs_error(tasks_path, repository, logger):
    (tasks_path / "broken.json").write_text("{not json", encoding="utf-8")

    tickets = repository.load_tickets()

    assert tickets == []
    logger.log.assert_called()


def test_save_ticket_persists_changes_without_metadata(tasks_path, repository):
    path = write_ticket(tasks_path, {"id": "TASK-001", "status": "Backlog"})
    ticket = repository.load_tickets()[0]
    ticket["status"] = "to-do"
    ticket["sprint"] = 2

    repository.save_ticket(ticket)

    saved_ticket = json.loads(path.read_text(encoding="utf-8"))
    assert saved_ticket == {"id": "TASK-001", "status": "to-do", "sprint": 2}


def test_save_ticket_wraps_write_errors(tmp_path, logger, monkeypatch):
    repository = TicketRepository(str(tmp_path), logger)

    def fail_write(_filepath, _payload):
        raise OSError("disk full")

    monkeypatch.setattr(repository, "_write_atomically", fail_write)

    with pytest.raises(SolutionGenerationError, match="Error saving"):
        repository.save_ticket({"filepath": str(tmp_path / "TASK-001.json")})
