import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.asg import AutomaticSolutionGenerator
from src.errors import SessionTimeoutError, SolutionGenerationError


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


@pytest.mark.parametrize("parent_field", ["parent", "parentId"])
def test_run_sprints_closes_epic_whose_children_are_done(generator, parent_field):
    write_ticket(
        generator.get_tasks_path(),
        {"id": "EPIC-001", "type": "epic", "status": "backlog"}
    )
    write_ticket(
        generator.get_tasks_path(),
        {"id": "STORY-001", "type": "story", "status": "done", parent_field: "EPIC-001"}
    )
    generator.process = MagicMock()

    generator._run_sprints()

    assert read_ticket(generator, "EPIC-001")["status"] == "done"
    generator.process.assert_not_called()


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


def test_process_interrupts_session_that_does_not_finish(generator):
    generator.session_timeout = 5
    generator.opencode_api = MagicMock()
    generator.opencode_api.get_session.return_value = {"data": {"id": "session-1"}}
    generator.opencode_api.send_prompt.return_value = {"ok": True}
    generator.opencode_api.wait_session.return_value = False

    with pytest.raises(SessionTimeoutError, match="5 seconds"):
        generator.process("qa-automation", 0, "prompt", [])

    generator.opencode_api.wait_session.assert_called_once_with({"data": {"id": "session-1"}}, 5)
    generator.opencode_api.interrupt_session.assert_called_once()
    generator.opencode_api.get_session_messages.assert_not_called()


def test_process_ticket_keeps_status_when_session_times_out(generator):
    write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "in-testing", "sprint": 0, "assignee": "qa-automation"}
    )
    generator.process = MagicMock(side_effect=SessionTimeoutError("did not finish"))

    assert generator._process_ticket(generator.load_tickets()[0], 0) is False
    assert read_ticket(generator, "TASK-001")["status"] == "in-testing"


def prepare_existing_project(generator):
    Path(generator.project_path).mkdir(parents=True, exist_ok=True)
    Path(generator.get_prd_path()).write_text("prd", encoding="utf-8")
    write_ticket(generator.get_tasks_path(), {"id": "TASK-001", "status": "done", "sprint": 3})
    write_ticket(generator.get_tasks_path(), {"id": "TASK-002", "status": "in-testing", "sprint": 7})
    write_ticket(generator.get_tasks_path(), {"id": "TASK-003", "status": "backlog"})
    generator.is_opencode_running = MagicMock(return_value=True)
    generator._prepare_project = MagicMock()
    generator._generate_prd = MagicMock()
    generator._generate_tasks = MagicMock()
    generator._run_sprints = MagicMock()


def test_generate_solution_resumes_existing_project(generator):
    prepare_existing_project(generator)

    generator.generate_solution()

    generator._generate_prd.assert_not_called()
    generator._generate_tasks.assert_not_called()
    generator._run_sprints.assert_called_once_with(7)


def test_generate_solution_regenerates_everything_without_resume(generator):
    prepare_existing_project(generator)
    generator.resume = False

    generator.generate_solution()

    generator._generate_prd.assert_called_once()
    generator._generate_tasks.assert_called_once()
    generator._run_sprints.assert_called_once_with(0)


def test_generate_solution_starts_at_sprint_zero_for_new_project(generator):
    generator.is_opencode_running = MagicMock(return_value=True)
    generator._prepare_project = MagicMock()
    generator._generate_prd = MagicMock()
    generator._generate_tasks = MagicMock(
        side_effect=lambda: write_ticket(generator.get_tasks_path(), {"id": "TASK-001"})
    )
    generator._run_sprints = MagicMock()

    generator.generate_solution()

    generator._generate_prd.assert_called_once()
    generator._run_sprints.assert_called_once_with(0)


def test_find_session_failure_ignores_error_recovered_by_retry():
    messages = {
        "data": [
            {"id": "message-1", "type": "assistant", "finish": "error",
             "error": {"message": "OpenAI Chat stream ended without finish_reason"}},
            {"id": "message-2", "type": "synthetic"},
            {"id": "message-3", "type": "assistant", "finish": "stop"},
            {"id": "message-4", "type": "idle", "outcome": "succeeded"},
        ]
    }

    assert AutomaticSolutionGenerator._find_session_failure(messages) is None


def test_find_session_failure_reports_error_that_ends_session():
    messages = {
        "data": [
            {"id": "message-1", "type": "assistant", "finish": "stop"},
            {"id": "message-2", "type": "assistant", "finish": "error"},
        ]
    }

    assert AutomaticSolutionGenerator._find_session_failure(messages)["id"] == "message-2"


def test_process_ticket_asks_agent_to_fix_broken_ticket_json(generator):
    path = write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "in-progress", "sprint": 0, "assignee": "web-developer"}
    )
    ticket = generator.load_tickets()[0]

    def agent_breaks_json(agent, sprint, prompt, files):
        path.write_text('{"id": "TASK-001", "result": "completed" "status": "in-progress"}',
                        encoding="utf-8")
        return {"data": {"id": "session-1"}}

    def agent_fixes_json(session, agent, sprint, prompt, files):
        payload = {"id": "TASK-001", "status": "in-progress", "sprint": 0,
                   "assignee": "web-developer", "result": "completed"}
        path.write_text(json.dumps(payload), encoding="utf-8")

    generator.process = MagicMock(side_effect=agent_breaks_json)
    generator._run_prompt = MagicMock(side_effect=agent_fixes_json)

    assert generator._process_ticket(ticket, 0) is True

    assert "no longer valid JSON" in generator._run_prompt.call_args.args[3]
    assert read_ticket(generator, "TASK-001")["status"] == "in-review"


def test_process_ticket_restores_ticket_left_broken_by_agent(generator):
    path = write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "in-progress", "sprint": 0, "assignee": "web-developer"}
    )
    ticket = generator.load_tickets()[0]

    def agent_breaks_json(agent, sprint, prompt, files):
        path.write_text('{"id": "TASK-001" "status": "done"}', encoding="utf-8")
        return {"data": {"id": "session-1"}}

    generator.process = MagicMock(side_effect=agent_breaks_json)
    generator._run_prompt = MagicMock()

    assert generator._process_ticket(ticket, 0) is False
    assert read_ticket(generator, "TASK-001")["status"] == "in-progress"


def test_run_sprints_logs_summary_after_each_sprint(generator):
    write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "backlog", "title": "Build web component"}
    )
    generator.process = MagicMock(side_effect=fake_process(generator, []))

    generator._run_sprints()

    logged = [call.args[1] for call in generator.logger.log.call_args_list]
    summaries = [line for line in logged if line.startswith("Sprint ") and line.endswith("summary")]
    assert summaries == [f"Sprint {sprint} summary" for sprint in range(4)]
    assert any("1/1 (100.0%) done" in line for line in logged)


def test_unblock_does_not_count_as_sprint_progress(generator):
    write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "blocked", "sprint": 0, "dependencies": []}
    )

    # With no prior block history, unblock succeeds, but _advance_sprint_tickets reports no forward progress
    progress = generator._advance_sprint_tickets(0)

    assert progress is False
    assert read_ticket(generator, "TASK-001")["status"] == "to-do"


def test_process_ticket_blocking_does_not_count_as_progress(generator):
    path = write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "to-do", "sprint": 0, "assignee": "web-developer"}
    )
    ticket = generator.load_tickets()[0]

    def agent_blocks(agent, sprint, prompt, files):
        payload = {"id": "TASK-001", "status": "to-do", "sprint": 0,
                   "assignee": "web-developer", "result": "blocked"}
        path.write_text(json.dumps(payload), encoding="utf-8")
        return {"data": {"id": "session-1"}}

    generator.process = MagicMock(side_effect=agent_blocks)
    generator._run_prompt = MagicMock()

    assert generator._process_ticket(ticket, 0) is False
    assert read_ticket(generator, "TASK-001")["status"] == "blocked"


def test_run_sprints_halts_when_ticket_cannot_unblock(generator):
    generator.max_stalled_sprints = 2
    write_ticket(
        generator.get_tasks_path(),
        {
            "id": "TASK-001",
            "status": "blocked",
            "sprint": 0,
            "statusHistory": [
                {"from": "to-do", "to": "blocked", "closedTicketsAtBlock": []}
            ]
        }
    )
    generator.process = MagicMock()

    with pytest.raises(SolutionGenerationError, match="2 consecutive sprints"):
        generator._run_sprints(0)


def test_generator_configures_max_status_history():
    logger = MagicMock()
    config = {
        "project_path": "/tmp/test-project",
        "opencode_base_url": "http://localhost:4096",
        "opencode_user": "user",
        "opencode_password": "pwd",
        "max_status_history": 5,
    }
    with patch("src.asg.OpencodeAPI"):
        gen = AutomaticSolutionGenerator(config, logger)
        assert gen.max_status_history == 5
        assert gen.ticket_workflow.max_status_history == 5


def test_ticket_prompt_includes_repository_instructions_when_configured(
    tmp_path, logger, config
):
    config["repository"] = "git@example.com:team/app.git"
    generator = AutomaticSolutionGenerator(config, logger)
    ticket = {"id": "TASK-001", "status": "to-do", "filepath": "/tmp/TASK-001.json"}

    prompt = generator._build_ticket_prompt(ticket, 0)

    assert "git@example.com:team/app.git" in prompt
    assert "trunk-based-development" in prompt


def test_ticket_prompt_omits_repository_instructions_without_repository(generator):
    ticket = {"id": "TASK-001", "status": "to-do", "filepath": "/tmp/TASK-001.json"}

    assert "trunk-based-development" not in generator._build_ticket_prompt(ticket, 0)


def test_completed_ticket_phase_is_published_to_the_repository(generator):
    write_ticket(
        generator.get_tasks_path(),
        {"id": "TASK-001", "status": "to-do", "sprint": 0, "assignee": "web-developer"}
    )
    generator.process = MagicMock(side_effect=fake_process(generator, []))
    generator.project_repository = MagicMock()
    generator.project_repository.get_agent_instructions.return_value = ""

    assert generator._advance_sprint_tickets(0) is True

    generator.project_repository.publish.assert_called_once_with("TASK-001: to-do -> in-review")
