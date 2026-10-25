from src.sprint_report import SprintReport


def build_tickets():
    return [
        {"id": "EPIC-001", "type": "epic", "status": "in-progress"},
        {"id": "TASK-001", "type": "task", "status": "done", "sprint": 3},
        {"id": "TASK-002", "type": "task", "status": "in-review", "sprint": 3},
        {"id": "TASK-003", "type": "task", "status": "in-testing", "sprint": 3},
        {"id": "TASK-004", "type": "task", "status": "backlog"},
    ]


def build_report(planned_count=1):
    before = {
        "EPIC-001": "in-progress",
        "TASK-001": "in-testing",
        "TASK-002": "in-progress",
        "TASK-003": "in-testing",
        "TASK-004": "backlog",
    }
    return SprintReport(3, before, build_tickets(), planned_count)


def test_snapshot_normalizes_statuses():
    snapshot = SprintReport.snapshot([{"id": "TASK-001", "status": "In Progress"}])

    assert snapshot == {"TASK-001": "in-progress"}


def test_report_shows_overall_and_executable_progress():
    lines = build_report().lines()

    assert lines[0] == "Sprint 3 summary"
    assert "1/5 (20.0%) done" in lines[1]
    assert "executable 1/4 (25.0%)" in lines[1]


def test_report_shows_status_breakdown():
    status_line = build_report().lines()[2]

    assert "done 1" in status_line
    assert "in-review 1" in status_line
    assert "backlog 1" in status_line
    assert "blocked 0" in status_line


def test_report_lists_transitions_closed_and_stalled_tickets():
    lines = build_report(planned_count=2).lines()

    assert "2 planned, 2 transitions, 1 closed (TASK-001)" in lines[3]
    assert "TASK-001 in-testing->done" in lines[4]
    assert "TASK-002 in-progress->in-review" in lines[4]
    assert lines[5] == "  Without progress: TASK-003 (in-testing)"


def test_report_without_tickets_does_not_divide_by_zero():
    lines = SprintReport(0, {}, [], 0).lines()

    assert "0/0 (0.0%) done" in lines[1]
