import subprocess
from pathlib import Path

import pytest

from src.project_repository import ProjectRepository


def run_git(directory, *arguments):
    return subprocess.run(
        ["git", *arguments], cwd=directory, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def remote(tmp_path):
    remote_path = tmp_path / "remote.git"
    run_git(tmp_path, "init", "--bare", "--initial-branch", "main", str(remote_path))
    return remote_path


@pytest.fixture
def project_path(tmp_path):
    return tmp_path / "project"


@pytest.fixture
def project_repository(project_path, remote, logger):
    return ProjectRepository(str(project_path), str(remote), logger)


def test_is_not_configured_without_remote_url(project_path, logger):
    repository = ProjectRepository(str(project_path), None, logger)

    assert repository.is_configured() is False
    assert repository.get_agent_instructions() == ""
    assert repository.prepare() is False
    assert repository.publish("TASK-001", "message") is False
    assert not project_path.exists()


def test_prepare_initializes_repository_with_remote_and_gitignore(
    project_repository, project_path, remote
):
    assert project_repository.prepare() is True

    assert run_git(project_path, "remote", "get-url", "origin") == str(remote)
    assert "node_modules/" in (project_path / ".gitignore").read_text(encoding="utf-8")


def test_prepare_is_idempotent_and_updates_remote_url(project_path, remote, logger, tmp_path):
    ProjectRepository(str(project_path), "git@example.com:old/repo.git", logger).prepare()
    ProjectRepository(str(project_path), str(remote), logger).prepare()
    ProjectRepository(str(project_path), str(remote), logger).prepare()

    assert run_git(project_path, "remote", "get-url", "origin") == str(remote)
    gitignore_lines = (project_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert len(gitignore_lines) == len(set(gitignore_lines))


def test_agent_instructions_mention_repository_and_skill(project_repository, remote):
    instructions = project_repository.get_agent_instructions()

    assert str(remote) in instructions
    assert "trunk-based-development" in instructions
    assert "'main'" in instructions


def write_and_publish(repository, project_path, ticket_id, file_name, integrate=False):
    repository.start_ticket(ticket_id)
    (project_path / file_name).write_text(file_name, encoding="utf-8")
    return repository.publish(ticket_id, f"{ticket_id}: add {file_name}", integrate=integrate)


def list_branches(remote):
    return run_git(remote, "branch", "--format=%(refname:short)").splitlines()


def test_get_ticket_branch_is_sanitized():
    assert ProjectRepository.get_ticket_branch("TASK-001") == "ticket/TASK-001"
    assert ProjectRepository.get_ticket_branch("TASK 1/../x") == "ticket/TASK-1-.-x"


def test_agent_instructions_for_ticket_forbid_pushing_to_trunk(project_repository):
    instructions = project_repository.get_agent_instructions("TASK-001")

    assert "'ticket/TASK-001'" in instructions
    assert "Never push to or commit on 'main'" in instructions


def test_publish_pushes_ticket_branch_and_leaves_trunk_untouched(
    project_repository, project_path, remote
):
    project_repository.prepare()

    assert write_and_publish(project_repository, project_path, "TASK-001", "index.html") is True

    assert sorted(list_branches(remote)) == ["main", "ticket/TASK-001"]
    assert run_git(remote, "ls-tree", "--name-only", "main") == ".gitignore"
    assert run_git(remote, "log", "main..ticket/TASK-001", "--format=%s") == "TASK-001: add index.html"


def test_publish_integrates_into_trunk_only_when_requested_and_deletes_branch(
    project_repository, project_path, remote
):
    project_repository.prepare()
    write_and_publish(project_repository, project_path, "TASK-001", "a.txt")
    project_repository.start_ticket("TASK-001")
    (project_path / "b.txt").write_text("b", encoding="utf-8")

    assert project_repository.publish("TASK-001", "TASK-001: add b", integrate=True) is True

    assert list_branches(remote) == ["main"]
    files = run_git(remote, "ls-tree", "--name-only", "main").splitlines()
    assert sorted(files) == [".gitignore", "a.txt", "b.txt"]
    assert run_git(project_path, "branch", "--show-current") == "main"
    assert "ticket/TASK-001" not in run_git(project_path, "branch", "--format=%(refname:short)")


def test_publish_without_changes_does_not_create_empty_commit(
    project_repository, project_path, remote
):
    project_repository.prepare()
    write_and_publish(project_repository, project_path, "TASK-001", "index.html")

    assert project_repository.publish("TASK-001", "second") is True

    assert run_git(remote, "rev-list", "--count", "main..ticket/TASK-001") == "1"


def test_tickets_work_on_separate_branches_created_from_the_trunk(
    project_repository, project_path, remote
):
    project_repository.prepare()
    write_and_publish(project_repository, project_path, "TASK-001", "a.txt", integrate=True)

    write_and_publish(project_repository, project_path, "TASK-002", "b.txt")

    assert run_git(remote, "ls-tree", "--name-only", "ticket/TASK-002").splitlines() == [
        ".gitignore", "a.txt", "b.txt"
    ]
    assert run_git(remote, "ls-tree", "--name-only", "main").splitlines() == [".gitignore", "a.txt"]


def test_unfinished_work_is_kept_on_its_branch_when_switching_tickets(
    project_repository, project_path, remote
):
    project_repository.prepare()
    project_repository.start_ticket("TASK-001")
    (project_path / "unfinished.txt").write_text("wip", encoding="utf-8")

    project_repository.start_ticket("TASK-002")

    assert not (project_path / "unfinished.txt").exists()
    assert "unfinished.txt" in run_git(project_path, "ls-tree", "--name-only", "ticket/TASK-001")


def test_integration_rebases_on_top_of_remote_trunk_changes(
    project_repository, project_path, remote, tmp_path
):
    project_repository.prepare()
    write_and_publish(project_repository, project_path, "TASK-001", "a.txt", integrate=True)
    project_repository.start_ticket("TASK-002")
    colleague = tmp_path / "colleague"
    run_git(tmp_path, "clone", str(remote), str(colleague))
    (colleague / "b.txt").write_text("b", encoding="utf-8")
    run_git(colleague, "add", "b.txt")
    run_git(colleague, "-c", "user.name=c", "-c", "user.email=c@c", "commit", "-m", "add b")
    run_git(colleague, "push", "origin", "main")
    (project_path / "c.txt").write_text("c", encoding="utf-8")

    assert project_repository.publish("TASK-002", "add c", integrate=True) is True

    files = run_git(remote, "ls-tree", "--name-only", "main").splitlines()
    assert sorted(files) == [".gitignore", "a.txt", "b.txt", "c.txt"]
    assert run_git(remote, "rev-list", "--merges", "--count", "main") == "0"


def test_integration_with_conflict_keeps_branch_and_trunk_unchanged(
    project_repository, project_path, remote, tmp_path
):
    project_repository.prepare()
    write_and_publish(project_repository, project_path, "TASK-001", "a.txt", integrate=True)
    project_repository.start_ticket("TASK-002")
    colleague = tmp_path / "colleague"
    run_git(tmp_path, "clone", str(remote), str(colleague))
    (colleague / "a.txt").write_text("changed by colleague", encoding="utf-8")
    run_git(colleague, "-c", "user.name=c", "-c", "user.email=c@c", "commit", "-am", "edit a")
    run_git(colleague, "push", "origin", "main")
    trunk_head = run_git(remote, "rev-parse", "main")
    (project_path / "a.txt").write_text("changed by ticket", encoding="utf-8")

    assert project_repository.publish("TASK-002", "edit a", integrate=True) is False

    assert run_git(remote, "rev-parse", "main") == trunk_head
    assert "ticket/TASK-002" in list_branches(remote)


def test_publish_returns_false_when_remote_is_unreachable(project_path, logger, tmp_path):
    repository = ProjectRepository(str(project_path), str(tmp_path / "missing.git"), logger)
    repository.prepare()

    assert write_and_publish(repository, project_path, "TASK-001", "a.txt") is False


@pytest.fixture
def remote_with_master(tmp_path):
    remote_path = tmp_path / "remote-master.git"
    run_git(tmp_path, "init", "--bare", "--initial-branch", "master", str(remote_path))
    seed = tmp_path / "seed"
    run_git(tmp_path, "clone", str(remote_path), str(seed))
    (seed / "README.md").write_text("seed", encoding="utf-8")
    run_git(seed, "add", "README.md")
    run_git(seed, "-c", "user.name=s", "-c", "user.email=s@s", "commit", "-m", "seed")
    run_git(seed, "push", "origin", "HEAD:master")
    return remote_path


def test_detect_remote_default_branch_returns_none_for_empty_remote(project_repository, remote):
    project_repository.prepare()

    assert project_repository.detect_remote_default_branch() is None
    assert project_repository.trunk_branch == "main"


def test_prepare_adopts_remote_default_branch_when_trunk_is_not_configured(
    project_path, remote_with_master, logger
):
    repository = ProjectRepository(str(project_path), str(remote_with_master), logger)

    repository.prepare()

    assert repository.detect_remote_default_branch() == "master"
    assert repository.trunk_branch == "master"
    assert "'master'" in repository.get_agent_instructions()


def test_prepare_keeps_configured_trunk_when_it_differs_from_remote_default(
    project_path, remote_with_master, logger
):
    repository = ProjectRepository(str(project_path), str(remote_with_master), logger, "develop")

    repository.prepare()

    assert repository.trunk_branch == "develop"


def test_integration_reaches_remote_default_branch_without_creating_another_trunk(
    project_path, remote_with_master, logger
):
    repository = ProjectRepository(str(project_path), str(remote_with_master), logger)
    repository.prepare()

    assert write_and_publish(repository, project_path, "TASK-001", "index.html", integrate=True)

    assert list_branches(remote_with_master) == ["master"]
    files = run_git(remote_with_master, "ls-tree", "--name-only", "master").splitlines()
    assert "index.html" in files and "README.md" in files
