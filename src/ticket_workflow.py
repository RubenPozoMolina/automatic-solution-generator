from datetime import datetime, timezone
from typing import Any, Optional

from src.ticket_status import (
    STATUS_BLOCKED,
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_IN_REVIEW,
    STATUS_IN_TESTING,
    STATUS_TO_DO,
    is_closed,
    normalize_status,
)

DEFAULT_REVIEWER = "software-architect"
DEFAULT_QA = "qa-automation"
DEFAULT_IMPLEMENTER = "software-architect"
EPIC_OWNER = "product-owner"
PROJECT_MANAGER = "project-manager"

ASSIGNEE_KEYWORDS = (
    ("web-developer", (
        "frontend", "front-end", "ui", "web", "react", "component",
        "css", "html", "svg", "canvas", "browser", "localstorage",
    )),
    ("backend-developer", (
        "backend", "back-end", "api", "server", "database", "sql",
        "endpoint", "migration", "orm",
    )),
    ("devops-engineer", (
        "devops", "infrastructure", "docker", "kubernetes", "ci/cd",
        "pipeline", "deployment", "deploy", "scaffold", "environment",
    )),
    ("ui-designer", ("design", "ux", "figma", "wireframe", "mockup", "prototype")),
    ("qa-automation", ("test", "qa", "automation", "coverage", "cypress", "playwright")),
)

RESULT_COMPLETED = "completed"
RESULT_BLOCKED = "blocked"
RESULT_CHANGES_REQUESTED = "changes-requested"
RESULT_FAILED = "failed"
RESULT_PASSED = "passed"
RESULT_PASSED_WITH_SKIPS = "passed-with-skips"
RESULT_SKIPPED_UNSUPPORTED = "skipped-unsupported-platform"
RESULT_DONE = "done"
COMPLETED_RESULTS = frozenset({
    RESULT_COMPLETED,
    RESULT_PASSED,
    RESULT_PASSED_WITH_SKIPS,
    RESULT_SKIPPED_UNSUPPORTED,
    RESULT_DONE,
})
BLOCKING_RESULTS = frozenset({RESULT_BLOCKED})
REWORK_RESULTS = frozenset({RESULT_CHANGES_REQUESTED, RESULT_FAILED})
KNOWN_RESULTS = COMPLETED_RESULTS | BLOCKING_RESULTS | REWORK_RESULTS
IMPLEMENTATION_STATUSES = frozenset({STATUS_TO_DO, STATUS_IN_PROGRESS})
RESULT_INSTRUCTIONS = (
    "write a 'result' field in the ticket JSON "
    "(completed, blocked, changes-requested, failed, passed, passed-with-skips, "
    "skipped-unsupported-platform or done) and list your evidence "
    "(files, commits, test reports) in 'resultEvidence'. Do not change 'status', 'assignee' "
    "or 'statusHistory': the orchestrator applies the transition."
)

NEXT_PHASE = {
    STATUS_TO_DO: STATUS_IN_PROGRESS,
    STATUS_IN_PROGRESS: STATUS_IN_REVIEW,
    STATUS_IN_REVIEW: STATUS_IN_TESTING,
    STATUS_IN_TESTING: STATUS_DONE,
    STATUS_BLOCKED: STATUS_TO_DO,
}

PROMPT_BY_STATUS = {
    STATUS_TO_DO: "Start implementing the ticket.",
    STATUS_IN_PROGRESS: "Continue the implementation and finish the pending work.",
    STATUS_IN_REVIEW: "Review the implementation and decide: approve or request changes.",
    STATUS_IN_TESTING: (
        "Verify the acceptance criteria and decide: pass or fail. "
        "If certain criteria cannot be executed due to host platform or OS limitations "
        "(e.g., unsupported browsers or platform-specific tools), document them as "
        "skipped-unsupported-platform in resultEvidence and pass the executable criteria "
        "rather than blocking the ticket."
    ),
    STATUS_BLOCKED: "Check whether the blocking dependency is resolved before continuing.",
}


class TicketWorkflow:
    """Applies the ticket lifecycle transitions owned by the orchestrator."""

    def __init__(self, project_manager: str = PROJECT_MANAGER):
        self.project_manager = project_manager

    def get_assigned_agent(self, ticket: dict[str, Any]) -> Optional[str]:
        assignee = ticket.get("assignee") or ticket.get("implementedBy")
        if assignee:
            return str(assignee)
        status = normalize_status(ticket.get("status"))
        if status == STATUS_IN_REVIEW:
            return str(ticket.get("reviewedBy") or DEFAULT_REVIEWER)
        if status == STATUS_IN_TESTING:
            return str(ticket.get("testedBy") or DEFAULT_QA)
        if status in (STATUS_TO_DO, STATUS_IN_PROGRESS, STATUS_BLOCKED):
            return self.infer_assignee(ticket)
        return None

    def infer_assignee(self, ticket: dict[str, Any]) -> str:
        ticket_type = str(ticket.get("type", "")).strip().lower()
        if ticket_type == "epic":
            return EPIC_OWNER
        searchable_text = " ".join(
            str(ticket.get(field, ""))
            for field in ("title", "description", "technicalNotes")
        ).lower()
        for agent, keywords in ASSIGNEE_KEYWORDS:
            if any(keyword in searchable_text for keyword in keywords):
                return agent
        return DEFAULT_IMPLEMENTER

    def build_prompt(self, ticket: dict[str, Any], sprint: int) -> str:
        status = normalize_status(ticket.get("status"))
        instruction = PROMPT_BY_STATUS.get(status, "Work on the ticket.")
        return (
            f"Work on ticket {ticket.get('id', ticket.get('filename'))} for sprint {sprint}. "
            f"Read {ticket.get('filepath')} and follow the ticket-workflow skill. "
            f"Current status: {status}. Assignee: {ticket.get('assignee')}. "
            f"{instruction} "
            "Perform only the work of the current phase in this sprint; the next phase "
            "will happen in a later sprint. "
            f"When your phase is complete, {RESULT_INSTRUCTIONS}"
        )

    @staticmethod
    def build_result_reminder(ticket: dict[str, Any]) -> str:
        return (
            f"Your work on ticket {ticket.get('id', ticket.get('filename'))} is not registered. "
            f"Edit {ticket.get('filepath')} now and {RESULT_INSTRUCTIONS}"
        )

    @staticmethod
    def has_result(ticket: dict[str, Any]) -> bool:
        return str(ticket.get("result") or "").strip().lower() in KNOWN_RESULTS

    def apply_completion(self, ticket: dict[str, Any], previous_status: str) -> bool:
        target_status = self._resolve_target_status(ticket, previous_status)
        if target_status is None or target_status == previous_status:
            return False

        actor = ticket.get("assignee") or "orchestrator"
        if previous_status in IMPLEMENTATION_STATUSES and not ticket.get("implementedBy"):
            ticket["implementedBy"] = ticket.get("assignee")
        self.record_transition(ticket, previous_status, target_status, actor)
        ticket["status"] = target_status
        ticket["assignee"] = self._assignee_for_status(target_status, ticket)
        ticket.pop("result", None)
        ticket["updatedAt"] = self._now()
        return True

    def unblock(self, ticket: dict[str, Any]) -> bool:
        if normalize_status(ticket.get("status")) != STATUS_BLOCKED:
            return False
        self.record_transition(ticket, STATUS_BLOCKED, STATUS_TO_DO, self.project_manager)
        ticket["status"] = STATUS_TO_DO
        ticket["assignee"] = (
            ticket.get("implementedBy") or ticket.get("assignee")
        )
        ticket["updatedAt"] = self._now()
        return True

    def is_processing_ready(
        self,
        ticket: dict[str, Any],
        closed_ticket_ids: set[str]
    ) -> bool:
        if is_closed(ticket) or self.is_epic(ticket):
            return False
        return self._dependencies_are_closed(ticket, closed_ticket_ids)

    @staticmethod
    def is_epic(ticket: dict[str, Any]) -> bool:
        return str(ticket.get("type", "")).strip().lower() == "epic"

    def close_epic_if_complete(
        self,
        epic: dict[str, Any],
        children: list[dict[str, Any]]
    ) -> bool:
        if not self.is_epic(epic) or is_closed(epic) or not children:
            return False
        if not all(is_closed(child) for child in children):
            return False
        self.record_transition(
            epic,
            normalize_status(epic.get("status")),
            STATUS_DONE,
            self.project_manager
        )
        epic["status"] = STATUS_DONE
        epic["assignee"] = None
        epic["updatedAt"] = self._now()
        return True

    def _resolve_target_status(
        self,
        ticket: dict[str, Any],
        previous_status: str
    ) -> Optional[str]:
        result = str(ticket.get("result") or "").strip().lower()
        if result in BLOCKING_RESULTS:
            return STATUS_BLOCKED
        if result in REWORK_RESULTS:
            return STATUS_IN_PROGRESS
        if result in COMPLETED_RESULTS:
            return self._next_status_after_completion(ticket, previous_status)
        return None

    def _next_status_after_completion(
        self,
        ticket: dict[str, Any],
        previous_status: str
    ) -> str:
        if previous_status == STATUS_IN_TESTING:
            return STATUS_DONE
        if previous_status in (STATUS_TO_DO, STATUS_IN_PROGRESS):
            if self._requires_review(ticket):
                return STATUS_IN_REVIEW
            return STATUS_IN_TESTING
        return NEXT_PHASE.get(previous_status, previous_status)

    @staticmethod
    def _requires_review(ticket: dict[str, Any]) -> bool:
        return bool(ticket.get("requiresReview", True))

    def _assignee_for_status(
        self,
        status: str,
        ticket: dict[str, Any]
    ) -> Optional[str]:
        if status == STATUS_IN_REVIEW:
            return str(ticket.get("reviewedBy") or DEFAULT_REVIEWER)
        if status == STATUS_IN_TESTING:
            return str(ticket.get("testedBy") or DEFAULT_QA)
        if status in (STATUS_TO_DO, STATUS_IN_PROGRESS, STATUS_BLOCKED):
            return str(
                ticket.get("implementedBy")
                or ticket.get("assignee")
                or ""
            ) or None
        if status == STATUS_DONE:
            return None
        return ticket.get("assignee")

    @staticmethod
    def _dependencies_are_closed(
        ticket: dict[str, Any],
        closed_ticket_ids: set[str]
    ) -> bool:
        dependencies = ticket.get("dependencies") or []
        return all(str(dependency) in closed_ticket_ids for dependency in dependencies)

    def record_transition(
        self,
        ticket: dict[str, Any],
        previous_status: Optional[str],
        target_status: str,
        actor: str,
        reason: Optional[str] = None
    ) -> None:
        history = list(ticket.get("statusHistory") or [])
        history.append(
            {
                "from": previous_status,
                "to": target_status,
                "actor": actor,
                "timestamp": self._now(),
                "reason": reason or str(ticket.get("result") or "Phase completed"),
                "evidence": list(ticket.get("resultEvidence") or []),
            }
        )
        ticket["statusHistory"] = history

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
