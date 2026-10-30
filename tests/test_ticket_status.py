import pytest

from src.ticket_status import (
    STATUS_BACKLOG,
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_TO_DO,
    is_backlog,
    is_closed,
    is_to_do,
    normalize_status,
)


@pytest.mark.parametrize(
    ("raw_status", "expected_status"),
    [
        ("to-do", STATUS_TO_DO),
        ("To Do", STATUS_TO_DO),
        ("TODO", STATUS_TO_DO),
        ("backlog", STATUS_BACKLOG),
        ("Backlog", STATUS_BACKLOG),
        ("in progress", STATUS_IN_PROGRESS),
        ("In_Progress", STATUS_IN_PROGRESS),
        ("done", STATUS_DONE),
        ("completed", STATUS_DONE),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_status_handles_aliases(raw_status, expected_status):
    assert normalize_status(raw_status) == expected_status


def test_is_to_do_accepts_status_with_space():
    assert is_to_do({"status": "To Do"}) is True


def test_is_backlog_is_case_insensitive():
    assert is_backlog({"status": "BACKLOG"}) is True


@pytest.mark.parametrize("status", ["done", "closed", "Completed"])
def test_is_closed_accepts_closed_aliases(status):
    assert is_closed({"status": status}) is True


def test_is_closed_rejects_open_ticket():
    assert is_closed({"status": "to-do"}) is False
