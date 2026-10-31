import json

import pytest

from src.sprint_planner import SprintPlanner
from src.ticket_repository import TicketRepository
from src.ticket_status import is_to_do


@pytest.fixture
def tasks_path(tmp_path):
    path = tmp_path / "tasks"
    path.mkdir()
    return path


@pytest.fixture
def repository(tasks_path, logger):
    return TicketRepository(str(tasks_path), logger)


@pytest.fixture
def planner(repository, logger):
    return SprintPlanner(repository, tasks_per_sprint=5, logger=logger)


def write_ticket(tasks_path, ticket):
    path = tasks_path / f"{ticket['id']}.json"
    path.write_text(json.dumps(ticket), encoding="utf-8")
    return path


def build_ticket(
    ticket_id,
    priority="P0",
    ticket_type="TASK",
    status="Backlog",
    dependencies=None
):
    return {
        "id": ticket_id,
        "type": ticket_type,
        "title": f"Title for {ticket_id}",
        "priority": priority,
        "status": status,
        "dependencies": dependencies or [],
    }


def test_plan_marks_selected_tickets_as_to_do(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001"))
    planner = SprintPlanner(repository, tasks_per_sprint=1, logger=logger)

    planned_tickets = planner.plan(sprint=0)

    assert [ticket["id"] for ticket in planned_tickets] == ["TASK-001"]
    saved_ticket = json.loads((tasks_path / "TASK-001.json").read_text(encoding="utf-8"))
    assert saved_ticket["status"] == "to-do"
    assert saved_ticket["sprint"] == 0


def test_plan_respects_tasks_per_sprint(tasks_path, repository, logger):
    for index in range(1, 5):
        write_ticket(tasks_path, build_ticket(f"TASK-00{index}"))
    planner = SprintPlanner(repository, tasks_per_sprint=2, logger=logger)

    planned_tickets = planner.plan(sprint=1)

    assert len(planned_tickets) == 2


def test_plan_prioritizes_higher_priority_tickets(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001", priority="P1"))
    write_ticket(tasks_path, build_ticket("TASK-002", priority="P0"))
    planner = SprintPlanner(repository, tasks_per_sprint=1, logger=logger)

    planned_tickets = planner.plan(sprint=0)

    assert [ticket["id"] for ticket in planned_tickets] == ["TASK-002"]


def test_plan_prefers_actionable_types_before_epics(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("EPIC-001", ticket_type="EPIC"))
    write_ticket(tasks_path, build_ticket("TASK-001", ticket_type="TASK"))
    planner = SprintPlanner(repository, tasks_per_sprint=1, logger=logger)

    planned_tickets = planner.plan(sprint=0)

    assert [ticket["id"] for ticket in planned_tickets] == ["TASK-001"]


def test_plan_uses_unmet_dependencies_as_tie_breaker(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001", dependencies=["TASK-000"]))
    write_ticket(tasks_path, build_ticket("TASK-002", dependencies=[]))
    planner = SprintPlanner(repository, tasks_per_sprint=1, logger=logger)

    planned_tickets = planner.plan(sprint=0)

    assert [ticket["id"] for ticket in planned_tickets] == ["TASK-002"]


def test_plan_ignores_closed_dependencies(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-000", status="done"))
    write_ticket(tasks_path, build_ticket("TASK-001", dependencies=["TASK-000"]))
    write_ticket(tasks_path, build_ticket("TASK-002", dependencies=[]))
    planner = SprintPlanner(repository, tasks_per_sprint=1, logger=logger)

    planned_tickets = planner.plan(sprint=0)

    assert [ticket["id"] for ticket in planned_tickets] == ["TASK-001"]


def test_plan_ignores_tickets_that_are_not_in_backlog(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001", status="to-do"))
    write_ticket(tasks_path, build_ticket("TASK-002", status="done"))
    planner = SprintPlanner(repository, tasks_per_sprint=5, logger=logger)

    assert planner.plan(sprint=0) == []


def test_plan_returns_empty_list_when_there_is_no_backlog(tasks_path, repository, logger):
    planner = SprintPlanner(repository, tasks_per_sprint=5, logger=logger)

    assert planner.plan(sprint=0) == []


def test_planned_ticket_is_detected_as_to_do(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001"))
    planner = SprintPlanner(repository, tasks_per_sprint=1, logger=logger)

    planner.plan(sprint=0)

    assert is_to_do(repository.load_tickets()[0]) is True


def test_plan_ignores_epics_because_they_are_containers(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("EPIC-001", ticket_type="EPIC"))
    planner = SprintPlanner(repository, tasks_per_sprint=5, logger=logger)

    assert planner.plan(sprint=0) == []


def read_ticket(tasks_path, ticket_id):
    return json.loads((tasks_path / f"{ticket_id}.json").read_text(encoding="utf-8"))


def test_get_capacity_subtracts_open_tickets(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001", status="in-progress"))
    write_ticket(tasks_path, build_ticket("TASK-002", status="blocked"))
    write_ticket(tasks_path, build_ticket("TASK-003", status="done"))
    write_ticket(tasks_path, build_ticket("EPIC-001", ticket_type="EPIC", status="in-progress"))
    write_ticket(tasks_path, build_ticket("TASK-004"))
    planner = SprintPlanner(repository, tasks_per_sprint=3, logger=logger)

    assert [ticket["id"] for ticket in planner.get_open_tickets()] == ["TASK-001", "TASK-002"]
    assert planner.get_capacity() == 1


def test_get_capacity_is_never_negative(tasks_path, repository, logger):
    for index in range(1, 4):
        write_ticket(tasks_path, build_ticket(f"TASK-00{index}", status="to-do"))
    planner = SprintPlanner(repository, tasks_per_sprint=2, logger=logger)

    assert planner.get_capacity() == 0


def test_plan_accepts_limit(tasks_path, repository, logger):
    for index in range(1, 4):
        write_ticket(tasks_path, build_ticket(f"TASK-00{index}"))
    planner = SprintPlanner(repository, tasks_per_sprint=5, logger=logger)

    assert len(planner.plan(sprint=0, limit=1)) == 1


def simulate_project_manager(tasks_path, repository, moves):
    backlog_before = repository.load_tickets()
    for ticket_id in moves:
        ticket = read_ticket(tasks_path, ticket_id)
        ticket["status"] = "to-do"
        ticket["statusHistory"] = [{"from": "backlog", "to": "to-do", "timestamp": "invented"}]
        write_ticket(tasks_path, ticket)
    return backlog_before


def test_enforce_plan_sets_sprint_and_records_real_transition(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001"))
    write_ticket(tasks_path, build_ticket("TASK-002"))
    planner = SprintPlanner(repository, tasks_per_sprint=5, logger=logger)
    backlog_before = simulate_project_manager(tasks_path, repository, ["TASK-001"])

    planned = planner.enforce_plan(2, backlog_before, capacity=5)

    assert [ticket["id"] for ticket in planned] == ["TASK-001"]
    saved = read_ticket(tasks_path, "TASK-001")
    assert saved["sprint"] == 2
    assert len(saved["statusHistory"]) == 1
    assert saved["statusHistory"][0]["actor"] == "project-manager"
    assert saved["statusHistory"][0]["timestamp"] != "invented"
    assert read_ticket(tasks_path, "TASK-002")["status"] == "Backlog"


def test_enforce_plan_returns_extra_tickets_to_backlog(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001", priority="P2"))
    write_ticket(tasks_path, build_ticket("TASK-002", priority="P0"))
    planner = SprintPlanner(repository, tasks_per_sprint=5, logger=logger)
    backlog_before = simulate_project_manager(tasks_path, repository, ["TASK-001", "TASK-002"])

    planned = planner.enforce_plan(0, backlog_before, capacity=1)

    assert [ticket["id"] for ticket in planned] == ["TASK-002"]
    restored = read_ticket(tasks_path, "TASK-001")
    assert restored["status"] == "Backlog"
    assert "statusHistory" not in restored


def test_enforce_plan_returns_tickets_with_open_dependencies(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001"))
    write_ticket(tasks_path, build_ticket("TASK-002", dependencies=["TASK-001"]))
    planner = SprintPlanner(repository, tasks_per_sprint=5, logger=logger)
    backlog_before = simulate_project_manager(tasks_path, repository, ["TASK-001", "TASK-002"])

    planned = planner.enforce_plan(0, backlog_before, capacity=5)

    assert [ticket["id"] for ticket in planned] == ["TASK-001"]
    assert read_ticket(tasks_path, "TASK-002")["status"] == "Backlog"


def test_enforce_plan_ignores_tickets_that_were_not_in_backlog(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001", status="in-progress"))
    planner = SprintPlanner(repository, tasks_per_sprint=5, logger=logger)

    assert planner.enforce_plan(0, [], capacity=5) == []


def test_plan_ignores_tickets_with_open_dependencies(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001", priority="P1"))
    write_ticket(tasks_path, build_ticket("TASK-002", priority="P0", dependencies=["TASK-001"]))
    planner = SprintPlanner(repository, tasks_per_sprint=5, logger=logger)

    assert [ticket["id"] for ticket in planner.plan(sprint=0)] == ["TASK-001"]


def test_release_unready_tickets_frees_only_unstarted_tickets(tasks_path, repository, logger):
    write_ticket(tasks_path, build_ticket("TASK-001", status="in-progress"))
    write_ticket(tasks_path, build_ticket("TASK-002", status="to-do", dependencies=["TASK-001"]))
    write_ticket(tasks_path, build_ticket("TASK-003", status="blocked", dependencies=["TASK-001"]))
    write_ticket(tasks_path, build_ticket("TASK-004", status="to-do"))
    planner = SprintPlanner(repository, tasks_per_sprint=5, logger=logger)

    released = planner.release_unready_tickets(sprint=1)

    assert [ticket["id"] for ticket in released] == ["TASK-002"]
    assert read_ticket(tasks_path, "TASK-002")["status"] == "backlog"
    assert read_ticket(tasks_path, "TASK-002")["statusHistory"][-1]["to"] == "backlog"
    assert read_ticket(tasks_path, "TASK-003")["status"] == "blocked"
    assert read_ticket(tasks_path, "TASK-004")["status"] == "to-do"
    assert planner.get_capacity() == 2


def read_ticket(tasks_path, ticket_id):
    return json.loads((tasks_path / f"{ticket_id}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("parent_field", ["parent", "parentId"])
def test_remove_ancestor_dependencies_drops_dependencies_on_own_parents(
    repository, tasks_path, planner, parent_field
):
    write_ticket(tasks_path, build_ticket("EPIC-001", ticket_type="epic"))
    write_ticket(tasks_path, build_ticket("EPIC-002", ticket_type="epic", dependencies=["EPIC-001"]))
    story = build_ticket("STORY-001", ticket_type="story", dependencies=["EPIC-001", "EPIC-002"])
    story[parent_field] = "EPIC-002"
    write_ticket(tasks_path, story)
    task = build_ticket("TASK-001", dependencies=["STORY-001", "EPIC-002", "EPIC-001"])
    task[parent_field] = "STORY-001"
    write_ticket(tasks_path, task)

    fixed_tickets = planner.remove_ancestor_dependencies()

    assert len(fixed_tickets) == 2
    assert read_ticket(tasks_path, "EPIC-002")["dependencies"] == ["EPIC-001"]
    assert read_ticket(tasks_path, "STORY-001")["dependencies"] == ["EPIC-001"]
    assert read_ticket(tasks_path, "TASK-001")["dependencies"] == ["EPIC-001"]


def test_remove_ancestor_dependencies_keeps_unrelated_dependencies(
    repository, tasks_path, planner
):
    write_ticket(tasks_path, build_ticket("TASK-001"))
    task = build_ticket("TASK-002", dependencies=["TASK-001"])
    task["parentId"] = "EPIC-001"
    write_ticket(tasks_path, task)

    assert planner.remove_ancestor_dependencies() == []
    assert read_ticket(tasks_path, "TASK-002")["dependencies"] == ["TASK-001"]


def test_remove_ancestor_dependencies_survives_parent_cycles(repository, tasks_path, planner):
    first = build_ticket("TASK-001", dependencies=["TASK-002"])
    first["parentId"] = "TASK-002"
    second = build_ticket("TASK-002", dependencies=["TASK-001"])
    second["parentId"] = "TASK-001"
    write_ticket(tasks_path, first)
    write_ticket(tasks_path, second)

    assert len(planner.remove_ancestor_dependencies()) == 2


def test_planner_plans_children_after_removing_dependencies_on_their_epic(
    repository, tasks_path, planner
):
    write_ticket(tasks_path, build_ticket("EPIC-001", ticket_type="epic"))
    story = build_ticket("STORY-001", ticket_type="story", dependencies=["EPIC-001"])
    story["parentId"] = "EPIC-001"
    write_ticket(tasks_path, story)
    assert planner.plan(0) == []

    planner.remove_ancestor_dependencies()

    assert [ticket["id"] for ticket in planner.plan(0)] == ["STORY-001"]
