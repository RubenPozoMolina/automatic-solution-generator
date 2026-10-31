import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from src.ticket_repository import TicketRepository
from src.ticket_status import (
    STATUS_BACKLOG,
    STATUS_TO_DO,
    is_backlog,
    is_closed,
    is_pending,
    is_to_do,
)
from src.ticket_workflow import TicketWorkflow
from utils.log_utils import LogUtils

PRIORITY_RANKS = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
DEFAULT_PRIORITY_RANK = len(PRIORITY_RANKS)
TICKET_TYPE_RANKS = {"task": 0, "subtask": 1, "story": 2, "epic": 3}
DEFAULT_TYPE_RANK = len(TICKET_TYPE_RANKS)
NON_EXECUTABLE_TICKET_TYPES = frozenset({"epic"})
PARENT_FIELDS = ("parent", "parentId")


class SprintPlanner:
    """Measures sprint load and validates or selects backlog tickets for a sprint."""

    def __init__(
        self,
        repository: TicketRepository,
        tasks_per_sprint: int,
        logger: LogUtils,
        workflow: Optional[TicketWorkflow] = None
    ):
        self.repository = repository
        self.tasks_per_sprint = tasks_per_sprint
        self.logger = logger
        self.workflow = workflow or TicketWorkflow()

    def get_open_tickets(self) -> list[dict[str, Any]]:
        return [
            ticket for ticket in self.repository.load_tickets()
            if is_pending(ticket) and not self._is_non_executable(ticket)
        ]

    def get_backlog_tickets(self) -> list[dict[str, Any]]:
        return [
            ticket for ticket in self.repository.load_tickets()
            if is_backlog(ticket) and not self._is_non_executable(ticket)
        ]

    def get_capacity(self) -> int:
        return max(self.tasks_per_sprint - len(self.get_open_tickets()), 0)

    def remove_ancestor_dependencies(self) -> list[dict[str, Any]]:
        """Drops dependencies on a ticket's own parent chain.

        A parent only closes when all its children are done, so a child that depends on its
        own parent (or grandparent) can never start.
        """
        tickets = self.repository.load_tickets()
        tickets_by_id = {str(ticket.get("id")): ticket for ticket in tickets}
        fixed_tickets = []
        for ticket in tickets:
            ancestor_ids = self._get_ancestor_ids(ticket, tickets_by_id)
            dependencies = ticket.get("dependencies") or []
            kept = [dependency for dependency in dependencies if str(dependency) not in ancestor_ids]
            if len(kept) == len(dependencies):
                continue
            ticket["dependencies"] = kept
            self.repository.save_ticket(ticket)
            fixed_tickets.append(ticket)
            self.logger.log(
                logging.WARNING,
                f"Removed dependencies of {self.ticket_key(ticket)} on its own parents "
                f"({sorted(set(map(str, dependencies)) - set(map(str, kept)))}): "
                f"a parent cannot close before its children"
            )
        return fixed_tickets

    @staticmethod
    def _get_parent_id(ticket: dict[str, Any]) -> Optional[str]:
        for field in PARENT_FIELDS:
            if ticket.get(field):
                return str(ticket[field])
        return None

    @staticmethod
    def _get_ancestor_ids(
        ticket: dict[str, Any],
        tickets_by_id: dict[str, dict[str, Any]]
    ) -> set[str]:
        ancestor_ids: set[str] = set()
        parent_id = SprintPlanner._get_parent_id(ticket)
        while parent_id and parent_id not in ancestor_ids:
            ancestor_ids.add(parent_id)
            parent = tickets_by_id.get(parent_id)
            parent_id = SprintPlanner._get_parent_id(parent) if parent else None
        return ancestor_ids

    def release_unready_tickets(self, sprint: int) -> list[dict[str, Any]]:
        """Returns to backlog the to-do tickets that cannot start because of open dependencies."""
        closed_ticket_ids = self._get_closed_ticket_ids()
        released_tickets = [
            ticket for ticket in self.get_open_tickets()
            if is_to_do(ticket)
            and not self._is_ready(ticket, closed_ticket_ids)
        ]
        for ticket in released_tickets:
            self.workflow.record_transition(
                ticket,
                STATUS_TO_DO,
                STATUS_BACKLOG,
                self.workflow.project_manager,
                "Dependencies not done; slot released for ready work"
            )
            ticket["status"] = STATUS_BACKLOG
            ticket.pop("sprint", None)
            ticket["updatedAt"] = self._now()
            self.repository.save_ticket(ticket)
            self.logger.log(
                logging.INFO,
                f"Returned ticket {self.ticket_key(ticket)} to backlog before sprint {sprint}: "
                f"dependencies are not done"
            )
        return released_tickets

    def plan(self, sprint: int, limit: Optional[int] = None) -> list[dict[str, Any]]:
        limit = self.tasks_per_sprint if limit is None else limit
        closed_ticket_ids = self._get_closed_ticket_ids()
        ready_tickets = [
            ticket for ticket in self.get_backlog_tickets()
            if self._is_ready(ticket, closed_ticket_ids)
        ]
        selected_tickets = sorted(
            ready_tickets,
            key=lambda ticket: self._get_sort_key(ticket, closed_ticket_ids)
        )[:limit]

        for ticket in selected_tickets:
            self._mark_as_to_do(ticket, sprint)
            self._record_planning(ticket, sprint)
            self.repository.save_ticket(ticket)
            self.logger.log(
                logging.INFO,
                f"Planned ticket {ticket.get('id', ticket['filename'])} for sprint {sprint}"
            )
        return selected_tickets

    def enforce_plan(
        self,
        sprint: int,
        backlog_before: Iterable[dict[str, Any]],
        capacity: int
    ) -> list[dict[str, Any]]:
        """Validates the tickets the project manager moved out of backlog.

        Only ready tickets (all dependencies done) within the sprint capacity are kept; the
        rest are restored to their backlog snapshot. The planning transition is recorded by
        the orchestrator so the history has real timestamps.
        """
        snapshots = {self.ticket_key(ticket): ticket for ticket in backlog_before}
        moved_tickets = [
            ticket for ticket in self.repository.load_tickets()
            if self.ticket_key(ticket) in snapshots
            and not is_backlog(ticket)
            and not is_closed(ticket)
        ]
        closed_ticket_ids = self._get_closed_ticket_ids()
        moved_tickets.sort(key=lambda ticket: self._get_sort_key(ticket, closed_ticket_ids))

        planned_tickets = []
        for ticket in moved_tickets:
            snapshot = snapshots[self.ticket_key(ticket)]
            rejection = self._get_rejection_reason(
                ticket, closed_ticket_ids, len(planned_tickets), capacity
            )
            if rejection:
                self._restore_snapshot(snapshot)
                self.logger.log(
                    logging.WARNING,
                    f"Returned ticket {self.ticket_key(ticket)} to backlog in sprint {sprint}: "
                    f"{rejection}"
                )
                continue
            ticket["status"] = STATUS_TO_DO
            ticket["sprint"] = sprint
            ticket["statusHistory"] = list(snapshot.get("statusHistory") or [])
            self._record_planning(ticket, sprint)
            ticket["updatedAt"] = self._now()
            self.repository.save_ticket(ticket)
            planned_tickets.append(ticket)
            self.logger.log(
                logging.INFO,
                f"Project manager planned ticket {self.ticket_key(ticket)} for sprint {sprint}"
            )
        return planned_tickets

    def _get_rejection_reason(
        self,
        ticket: dict[str, Any],
        closed_ticket_ids: set[str],
        planned_count: int,
        capacity: int
    ) -> Optional[str]:
        if not self._is_ready(ticket, closed_ticket_ids):
            return "dependencies are not done"
        if planned_count >= capacity:
            return f"sprint capacity is {capacity}"
        return None

    def _restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.repository.save_ticket(dict(snapshot))

    def _record_planning(self, ticket: dict[str, Any], sprint: int) -> None:
        self.workflow.record_transition(
            ticket,
            STATUS_BACKLOG,
            STATUS_TO_DO,
            self.workflow.project_manager,
            f"Planned for sprint {sprint}"
        )

    def _is_ready(self, ticket: dict[str, Any], closed_ticket_ids: set[str]) -> bool:
        return self._get_unmet_dependency_count(ticket, closed_ticket_ids) == 0

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _get_closed_ticket_ids(self) -> set[str]:
        return {
            str(ticket.get("id"))
            for ticket in self.repository.load_tickets()
            if is_closed(ticket)
        }

    @staticmethod
    def ticket_key(ticket: dict[str, Any]) -> str:
        return str(ticket.get("id", ticket.get("filename")))

    @staticmethod
    def _mark_as_to_do(ticket: dict[str, Any], sprint: int) -> None:
        ticket["status"] = STATUS_TO_DO
        ticket["sprint"] = sprint
        if "updatedAt" in ticket:
            ticket["updatedAt"] = SprintPlanner._now()

    @staticmethod
    def _get_sort_key(
        ticket: dict[str, Any],
        closed_ticket_ids: set[str]
    ) -> tuple[int, int, int, str]:
        return (
            SprintPlanner._get_priority_rank(ticket),
            SprintPlanner._get_type_rank(ticket),
            SprintPlanner._get_unmet_dependency_count(ticket, closed_ticket_ids),
            str(ticket.get("id", ticket.get("filename", "")))
        )

    @staticmethod
    def _is_non_executable(ticket: dict[str, Any]) -> bool:
        ticket_type = str(ticket.get("type", "")).strip().lower()
        return ticket_type in NON_EXECUTABLE_TICKET_TYPES

    @staticmethod
    def _get_priority_rank(ticket: dict[str, Any]) -> int:
        priority = str(ticket.get("priority", "")).strip().upper()
        return PRIORITY_RANKS.get(priority, DEFAULT_PRIORITY_RANK)

    @staticmethod
    def _get_type_rank(ticket: dict[str, Any]) -> int:
        ticket_type = str(ticket.get("type", "")).strip().lower()
        return TICKET_TYPE_RANKS.get(ticket_type, DEFAULT_TYPE_RANK)

    @staticmethod
    def _get_unmet_dependency_count(
        ticket: dict[str, Any],
        closed_ticket_ids: set[str]
    ) -> int:
        dependencies = ticket.get("dependencies") or []
        return sum(
            1 for dependency in dependencies
            if str(dependency) not in closed_ticket_ids
        )
