import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.asg import AutomaticSolutionGenerator
from src.errors import SolutionGenerationError


@pytest.fixture
def config(tmp_path):
    return {
        "project_path": str(tmp_path / "project"),
        "customer_interview": str(tmp_path / "interview.md"),
        "tasks_per_sprint": 5,
        "opencode_base_url": "http://localhost:5000",
        "opencode_user": "user",
        "opencode_password": "password",
        "model": "nvidia-free/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    }


@pytest.fixture
def generator(config, logger):
    return AutomaticSolutionGenerator(config, logger)


def write_ticket(tasks_path, ticket):
    tasks_path = Path(tasks_path)
    tasks_path.mkdir(parents=True, exist_ok=True)
    path = tasks_path / f"{ticket['id']}.json"
    path.write_text(json.dumps(ticket), encoding="utf-8")
    return path


def test_get_model_dict_preserves_slash_in_model_id(generator):
    assert generator.get_model_dict() == {
        "providerID": "nvidia-free",
        "id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    }


def test_get_model_dict_rejects_reference_without_provider(tmp_path, logger, config):
    config["model"] = "invalid-model"
    generator = AutomaticSolutionGenerator(config, logger)

    with pytest.raises(SolutionGenerationError, match="Model reference"):
        generator.get_model_dict()


def test_prompts_use_absolute_project_paths(generator):
    assert generator.project_path in generator.get_requirements_analysis()
    assert generator.project_path in generator.get_generate_tasks()


def test_get_sprint_tickets_accepts_to_do_with_space(generator):
    write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "To Do", "title": "Ticket"}
    )

    sprint_tickets = generator.get_sprint_tickets(sprint=0)

    assert [ticket["id"] for ticket in sprint_tickets] == ["TASK-001"]
    assert sprint_tickets[0]["sprint"] == 0


def test_all_tickets_closed_returns_false_without_tickets(generator):
    assert generator.all_tickets_closed() is False


def test_all_tickets_closed_returns_true_when_all_tickets_are_closed(generator):
    write_ticket(generator.get_tasks_path(), {"id": "TASK-001", "status": "done"})
    write_ticket(generator.get_tasks_path(), {"id": "TASK-002", "status": "Closed"})

    assert generator.all_tickets_closed() is True


def test_all_tickets_closed_returns_false_when_a_ticket_is_pending(generator):
    write_ticket(generator.get_tasks_path(), {"id": "TASK-001", "status": "done"})
    write_ticket(generator.get_tasks_path(), {"id": "TASK-002", "status": "Backlog"})

    assert generator.all_tickets_closed() is False


def test_process_raises_when_attachment_is_missing(generator, tmp_path):
    missing_file = str(tmp_path / "missing.md")
    generator.opencode_api = MagicMock()

    with pytest.raises(SolutionGenerationError, match="Missing required files"):
        generator.process("product-manager", 0, "prompt", [missing_file])

    generator.opencode_api.get_session.assert_not_called()


def test_process_raises_when_session_message_has_error(generator):
    generator.opencode_api = MagicMock()
    generator.opencode_api.get_session.return_value = {"data": {"id": "session-1"}}
    generator.opencode_api.send_prompt.return_value = {"ok": True}
    generator.opencode_api.wait_session.return_value = True
    generator.opencode_api.get_session_messages.return_value = {
        "data": [
            {
                "id": "message-1",
                "type": "assistant",
                "finish": "error",
                "error": {"message": "Provider request failed with HTTP 404"},
            }
        ]
    }

    with pytest.raises(SolutionGenerationError, match="HTTP 404"):
        generator.process("product-manager", 0, "prompt", [])


def test_process_completes_when_session_succeeds(generator):
    generator.opencode_api = MagicMock()
    generator.opencode_api.get_session.return_value = {"data": {"id": "session-1"}}
    generator.opencode_api.send_prompt.return_value = {"ok": True}
    generator.opencode_api.wait_session.return_value = True
    generator.opencode_api.get_session_messages.return_value = {
        "data": [{"id": "message-1", "type": "assistant", "finish": "stop"}]
    }

    generator.process("product-manager", 0, "prompt", [])

    generator.opencode_api.send_prompt.assert_called_once()


def test_find_session_failure_detects_failed_idle_message():
    messages = {
        "data": [
            {"id": "message-1", "type": "idle", "outcome": "failed"},
        ]
    }

    failure = AutomaticSolutionGenerator._find_session_failure(messages)

    assert failure is not None
    assert failure["id"] == "message-1"


def configure_prd(generator, tmp_path):
    interview_path = tmp_path / "interview.md"
    interview_path.write_text("interview", encoding="utf-8")
    generator.config["customer_interview"] = str(interview_path)


def configure_tasks(generator, tmp_path):
    prd_path = tmp_path / "prd.md"
    prd_path.write_text("prd", encoding="utf-8")
    generator.config["project_path"] = str(tmp_path)
    generator.project_path = str(tmp_path)
    generator.ticket_repository.tasks_path = str(tmp_path / "tasks")


def test_generate_prd_raises_after_follow_ups_without_prd(generator, tmp_path):
    configure_prd(generator, tmp_path)
    generator.process = MagicMock(return_value={"data": {"id": "session-1"}})
    generator._run_prompt = MagicMock()

    with pytest.raises(SolutionGenerationError, match="did not create the PRD"):
        generator._generate_prd()

    assert generator._run_prompt.call_count == 2


def test_generate_prd_follow_up_recovers_interrupted_session(generator, tmp_path):
    configure_prd(generator, tmp_path)
    generator.process = MagicMock(return_value={"data": {"id": "session-1"}})

    def write_prd(session, agent, sprint, prompt, files):
        Path(generator.get_prd_path()).parent.mkdir(parents=True, exist_ok=True)
        Path(generator.get_prd_path()).write_text("prd", encoding="utf-8")

    generator._run_prompt = MagicMock(side_effect=write_prd)

    generator._generate_prd()

    session, agent, _, prompt, files = generator._run_prompt.call_args.args
    assert (session, agent, files) == ({"data": {"id": "session-1"}}, "product-manager", [])
    assert generator.get_prd_path() in prompt
    assert generator._run_prompt.call_count == 1


def test_generate_tasks_raises_after_follow_ups_without_tickets(generator, tmp_path):
    configure_tasks(generator, tmp_path)
    generator.process = MagicMock(return_value={"data": {"id": "session-1"}})
    generator._run_prompt = MagicMock()

    with pytest.raises(SolutionGenerationError, match="did not create any tickets"):
        generator._generate_tasks()

    assert generator._run_prompt.call_count == 2
    assert (tmp_path / "tasks").is_dir()


def test_generate_tasks_follow_up_recovers_interrupted_session(generator, tmp_path):
    configure_tasks(generator, tmp_path)
    generator.process = MagicMock(return_value={"data": {"id": "session-1"}})
    generator._run_prompt = MagicMock(
        side_effect=lambda *args: write_ticket(tmp_path / "tasks", {"id": "TASK-001"})
    )

    generator._generate_tasks()

    assert generator._run_prompt.call_count == 1
    assert "write" in generator._run_prompt.call_args.args[3]


def test_generate_tasks_skips_follow_up_when_tickets_exist(generator, tmp_path):
    configure_tasks(generator, tmp_path)
    generator.process = MagicMock(
        side_effect=lambda *args: write_ticket(tmp_path / "tasks", {"id": "TASK-001"})
    )
    generator._run_prompt = MagicMock()

    generator._generate_tasks()

    generator._run_prompt.assert_not_called()


def read_ticket(generator, ticket_id):
    path = Path(generator.get_tasks_path()) / f"{ticket_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def fake_process(generator, ticket_calls):
    def process(agent, sprint, prompt, files):
        if agent == "project-manager":
            for ticket in generator.load_tickets():
                if ticket.get("status") == "backlog":
                    ticket["status"] = "to-do"
                    generator.ticket_repository.save_ticket(ticket)
            return
        ticket_path = Path(files[0])
        ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
        ticket_calls.append((sprint, ticket["id"], ticket["status"]))
        ticket["result"] = "completed"
        ticket_path.write_text(json.dumps(ticket), encoding="utf-8")
    return process


def test_run_sprints_finishes_without_llm_when_all_tickets_are_closed(generator):
    write_ticket(generator.get_tasks_path(), {"id": "TASK-001", "status": "done"})
    generator.process = MagicMock()

    generator._run_sprints()

    generator.process.assert_not_called()


def test_run_sprints_raises_when_no_backlog_remains_and_tickets_are_open(generator):
    write_ticket(
        generator.get_tasks_path(),
        {"id": "EPIC-001", "type": "epic", "status": "in-progress"}
    )
    generator.process = MagicMock()

    with pytest.raises(SolutionGenerationError, match="No backlog tickets available"):
        generator._run_sprints()


def test_plan_sprint_skips_project_manager_without_capacity(generator):
    generator.sprint_planner.tasks_per_sprint = 1
    write_ticket(generator.get_tasks_path(), {"id": "TASK-001", "status": "in-progress"})
    write_ticket(generator.get_tasks_path(), {"id": "TASK-002", "status": "backlog"})
    generator.process = MagicMock()

    assert generator._plan_sprint(0) == []
    generator.process.assert_not_called()


def test_plan_sprint_asks_project_manager_with_free_capacity(generator):
    generator.sprint_planner.tasks_per_sprint = 2
    write_ticket(generator.get_tasks_path(), {"id": "TASK-001", "status": "in-progress"})
    write_ticket(generator.get_tasks_path(), {"id": "TASK-002", "status": "backlog"})
    write_ticket(generator.get_tasks_path(), {"id": "TASK-003", "status": "backlog"})
    generator.process = MagicMock(side_effect=fake_process(generator, []))

    planned = generator._plan_sprint(4)

    agent, sprint, prompt, _ = generator.process.call_args.args
    assert (agent, sprint) == ("project-manager", 4)
    assert "capacity for this sprint is 1" in prompt
    assert [ticket["id"] for ticket in planned] == ["TASK-002"]
    assert read_ticket(generator, "TASK-002")["sprint"] == 4
    assert read_ticket(generator, "TASK-003")["status"] == "backlog"


def test_plan_sprint_falls_back_when_project_manager_plans_nothing(generator):
    write_ticket(generator.get_tasks_path(), {"id": "TASK-001", "status": "backlog"})
    generator.process = MagicMock()

    planned = generator._plan_sprint(0)

    assert [ticket["id"] for ticket in planned] == ["TASK-001"]
    assert read_ticket(generator, "TASK-001")["status"] == "to-do"


def test_advance_sprint_tickets_changes_status_once_per_ticket(generator):
    write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "to-do", "sprint": 0, "assignee": "web-developer"}
    )
    ticket_calls = []
    generator.process = MagicMock(side_effect=fake_process(generator, ticket_calls))

    assert generator._advance_sprint_tickets(0) is True

    assert ticket_calls == [(0, "TASK-001", "to-do")]
    assert read_ticket(generator, "TASK-001")["status"] == "in-review"


def test_run_sprints_moves_ticket_one_status_per_sprint_until_done(generator):
    write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "backlog", "title": "Build web component"}
    )
    ticket_calls = []
    generator.process = MagicMock(side_effect=fake_process(generator, ticket_calls))

    generator._run_sprints()

    assert ticket_calls == [
        (0, "TASK-001", "to-do"),
        (1, "TASK-001", "in-review"),
        (2, "TASK-001", "in-testing"),
    ]
    assert read_ticket(generator, "TASK-001")["status"] == "done"


def test_run_sprints_raises_after_consecutive_stalled_sprints(generator):
    generator.max_stalled_sprints = 2
    write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "to-do", "assignee": "web-developer"}
    )
    generator.process = MagicMock()
    generator._run_prompt = MagicMock()

    with pytest.raises(SolutionGenerationError, match="2 consecutive sprints"):
        generator._run_sprints()


def test_process_ticket_asks_for_missing_result_once(generator):
    path = write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "in-progress", "sprint": 0, "assignee": "web-developer"}
    )
    generator.process = MagicMock(return_value={"data": {"id": "session-1"}})

    def register_result(session, agent, sprint, prompt, files):
        ticket = json.loads(path.read_text(encoding="utf-8"))
        ticket["result"] = "completed"
        path.write_text(json.dumps(ticket), encoding="utf-8")

    generator._run_prompt = MagicMock(side_effect=register_result)

    assert generator._process_ticket(generator.load_tickets()[0], 0) is True

    session, agent, _, prompt, _ = generator._run_prompt.call_args.args
    assert generator._run_prompt.call_count == 1
    assert (session, agent) == ({"data": {"id": "session-1"}}, "web-developer")
    assert "not registered" in prompt
    saved = read_ticket(generator, "TASK-001")
    assert saved["status"] == "in-review"
    assert saved["implementedBy"] == "web-developer"


def test_process_ticket_restores_status_written_without_result(generator):
    path = write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "to-do", "sprint": 0, "assignee": "web-developer"}
    )

    def agent_moves_status(agent, sprint, prompt, files):
        ticket = json.loads(path.read_text(encoding="utf-8"))
        ticket["status"] = "in-progress"
        path.write_text(json.dumps(ticket), encoding="utf-8")
        return {"data": {"id": "session-1"}}

    generator.process = MagicMock(side_effect=agent_moves_status)
    generator._run_prompt = MagicMock()

    assert generator._process_ticket(generator.load_tickets()[0], 0) is False
    assert read_ticket(generator, "TASK-001")["status"] == "to-do"


def test_run_sprints_does_not_fill_sprint_with_dependent_tickets(generator):
    tasks_path = generator.get_tasks_path()
    write_ticket(tasks_path, {"id": "TASK-001", "status": "backlog", "priority": "P0"})
    write_ticket(tasks_path, {"id": "TASK-003", "status": "backlog", "priority": "P0",
                              "dependencies": ["TASK-001"]})
    write_ticket(tasks_path, {"id": "TASK-007", "status": "backlog", "priority": "P0",
                              "dependencies": ["TASK-001", "TASK-003"]})
    write_ticket(tasks_path, {"id": "TASK-020", "status": "backlog", "priority": "P2"})
    ticket_calls = []
    generator.process = MagicMock(side_effect=fake_process(generator, ticket_calls))

    planned = generator._plan_sprint(0)

    assert sorted(ticket["id"] for ticket in planned) == ["TASK-001", "TASK-020"]
    assert read_ticket(generator, "TASK-003")["status"] == "backlog"
    assert read_ticket(generator, "TASK-007")["status"] == "backlog"
