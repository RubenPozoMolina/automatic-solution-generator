import pytest

from src.ticket_status import STATUS_BLOCKED, STATUS_IN_REVIEW, STATUS_IN_TESTING, STATUS_TO_DO
from src.ticket_workflow import TicketWorkflow


@pytest.fixture
def workflow():
    return TicketWorkflow()


def build_ticket(**overrides):
    ticket = {
        "id": "TASK-001",
        "type": "task",
        "title": "Ticket",
        "description": "",
        "status": "to-do",
        "assignee": None,
        "dependencies": [],
        "requiresReview": True,
        "statusHistory": [],
    }
    ticket.update(overrides)
    return ticket


@pytest.mark.parametrize(
    ("ticket", "expected_agent"),
    [
        ({"type": "epic", "title": "Project setup"}, "product-owner"),
        ({"type": "task", "title": "Build editor UI", "description": "svg canvas"}, "web-developer"),
        ({"type": "task", "title": "Create API", "description": "database server"}, "backend-developer"),
        ({"type": "task", "title": "Add pipeline", "description": "docker deploy"}, "devops-engineer"),
        ({"type": "task", "title": "Write tests", "description": "playwright coverage"}, "qa-automation"),
        ({"type": "task", "title": "Unknown work"}, "software-architect"),
    ],
)
def test_infer_assignee_uses_type_and_keywords(workflow, ticket, expected_agent):
    assert workflow.infer_assignee(build_ticket(**ticket)) == expected_agent


def test_get_assigned_agent_infers_assignee_when_missing(workflow):
    ticket = build_ticket(assignee=None, title="Build editor UI")

    assert workflow.get_assigned_agent(ticket) == "web-developer"


def test_completed_ticket_moves_to_review_and_assigns_reviewer(workflow):
    ticket = build_ticket(status="to-do", result="completed")

    assert workflow.apply_completion(ticket, STATUS_TO_DO) is True
    assert ticket["status"] == STATUS_IN_REVIEW
    assert ticket["assignee"] == "software-architect"
    assert ticket["statusHistory"][-1]["to"] == STATUS_IN_REVIEW


def test_completed_ticket_without_review_moves_to_testing(workflow):
    ticket = build_ticket(status="to-do", result="completed", requiresReview=False)

    assert workflow.apply_completion(ticket, STATUS_TO_DO) is True
    assert ticket["status"] == STATUS_IN_TESTING
    assert ticket["assignee"] == "qa-automation"


def test_completed_ticket_does_not_change_when_status_is_unchanged(workflow):
    ticket = build_ticket(status="to-do")

    assert workflow.apply_completion(ticket, STATUS_TO_DO) is False
    assert ticket["status"] == STATUS_TO_DO


def test_unblock_moves_blocked_ticket_to_to_do(workflow):
    ticket = build_ticket(status="blocked", assignee="backend-developer")

    assert workflow.unblock(ticket) is True
    assert ticket["status"] == STATUS_TO_DO
    assert ticket["assignee"] == "backend-developer"
    assert ticket["statusHistory"][-1]["from"] == STATUS_BLOCKED


def test_blocked_ticket_is_not_ready_until_dependencies_close(workflow):
    ticket = build_ticket(status="blocked", dependencies=["TASK-000"])

    assert workflow.is_processing_ready(ticket, set()) is False
    assert workflow.is_processing_ready(ticket, {"TASK-000"}) is True


def test_ticket_with_open_dependency_is_not_ready(workflow):
    ticket = build_ticket(status="to-do", dependencies=["TASK-000"])

    assert workflow.is_processing_ready(ticket, set()) is False
    assert workflow.is_processing_ready(ticket, {"TASK-000"}) is True


def test_epic_is_not_processing_ready(workflow):
    ticket = build_ticket(type="epic", status="to-do")

    assert workflow.is_processing_ready(ticket, set()) is False


def test_epic_closes_when_all_children_are_done(workflow):
    epic = build_ticket(id="EPIC-001", type="epic", status="in-progress")
    children = [
        build_ticket(id="TASK-001", status="done"),
        build_ticket(id="TASK-002", status="done"),
    ]

    assert workflow.close_epic_if_complete(epic, children) is True
    assert epic["status"] == "done"
    assert epic["assignee"] is None


def test_completion_records_implementer(workflow):
    ticket = build_ticket(status="in-progress", assignee="web-developer", result="completed")

    assert workflow.apply_completion(ticket, "in-progress") is True
    assert ticket["implementedBy"] == "web-developer"
    assert ticket["assignee"] == "software-architect"


def test_changes_requested_returns_ticket_to_implementer(workflow):
    ticket = build_ticket(status="in-progress", assignee="web-developer", result="completed")
    workflow.apply_completion(ticket, "in-progress")
    ticket["result"] = "changes-requested"

    assert workflow.apply_completion(ticket, STATUS_IN_REVIEW) is True
    assert ticket["status"] == "in-progress"
    assert ticket["assignee"] == "web-developer"


def test_status_written_without_result_is_not_a_transition(workflow):
    ticket = build_ticket(status="in-progress", assignee="web-developer")

    assert workflow.apply_completion(ticket, STATUS_TO_DO) is False
    assert workflow.has_result(ticket) is False


def test_prompt_does_not_ask_agent_to_change_status(workflow):
    prompt = workflow.build_prompt(build_ticket(filepath="/tmp/TASK-001.json"), 0)

    assert "move it to in progress" not in prompt
    assert "Do not change 'status'" in prompt


@pytest.mark.parametrize(
    "result_value",
    ["passed", "passed-with-skips", "skipped-unsupported-platform"],
)
def test_testing_phase_completion_moves_to_done(workflow, result_value):
    ticket = build_ticket(
        status=STATUS_IN_TESTING,
        assignee="qa-automation",
        result=result_value,
        resultEvidence=["Safari skipped due to Linux host; Chrome and Firefox passed"],
    )

    assert workflow.apply_completion(ticket, STATUS_IN_TESTING) is True
    assert ticket["status"] == "done"
    assert ticket["assignee"] is None
    assert ticket["statusHistory"][-1]["to"] == "done"
    assert ticket["statusHistory"][-1]["evidence"] == [
        "Safari skipped due to Linux host; Chrome and Firefox passed"
    ]
