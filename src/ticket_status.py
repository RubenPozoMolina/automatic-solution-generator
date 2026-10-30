from typing import Any

STATUS_BACKLOG = "backlog"
STATUS_TO_DO = "to-do"
STATUS_IN_PROGRESS = "in-progress"
STATUS_IN_REVIEW = "in-review"
STATUS_IN_TESTING = "in-testing"
STATUS_BLOCKED = "blocked"
STATUS_DONE = "done"
STATUS_CLOSED = "closed"
CLOSED_STATUSES = frozenset({STATUS_DONE, STATUS_CLOSED})
PENDING_STATUSES = frozenset({
    STATUS_TO_DO,
    STATUS_IN_PROGRESS,
    STATUS_IN_REVIEW,
    STATUS_IN_TESTING,
    STATUS_BLOCKED,
})

_STATUS_ALIASES = {
    "backlog": STATUS_BACKLOG,
    "backlock": STATUS_BACKLOG,
    "back log": STATUS_BACKLOG,
    "todo": STATUS_TO_DO,
    "to-do": STATUS_TO_DO,
    "to do": STATUS_TO_DO,
    "in progress": STATUS_IN_PROGRESS,
    "in-progress": STATUS_IN_PROGRESS,
    "inprogress": STATUS_IN_PROGRESS,
    "in review": STATUS_IN_REVIEW,
    "in-review": STATUS_IN_REVIEW,
    "inreview": STATUS_IN_REVIEW,
    "in testing": STATUS_IN_TESTING,
    "in-testing": STATUS_IN_TESTING,
    "intesting": STATUS_IN_TESTING,
    "blocked": STATUS_BLOCKED,
    "complete": STATUS_DONE,
    "completed": STATUS_DONE,
    "done": STATUS_DONE,
    "closed": STATUS_CLOSED,
}


def normalize_status(value: Any) -> str:
    text = " ".join(str(value or "").strip().lower().replace("_", " ").split())
    return _STATUS_ALIASES.get(text, text)


def is_backlog(ticket: dict[str, Any]) -> bool:
    return normalize_status(ticket.get("status")) == STATUS_BACKLOG


def is_to_do(ticket: dict[str, Any]) -> bool:
    return normalize_status(ticket.get("status")) == STATUS_TO_DO


def is_closed(ticket: dict[str, Any]) -> bool:
    return normalize_status(ticket.get("status")) in CLOSED_STATUSES


def is_pending(ticket: dict[str, Any]) -> bool:
    return normalize_status(ticket.get("status")) in PENDING_STATUSES
