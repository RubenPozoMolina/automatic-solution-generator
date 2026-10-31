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
    assert repository.publish("message") is False
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


def test_publish_pushes_changes_to_trunk(project_repository, project_path, remote):
    project_repository.prepare()
    (project_path / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")

    assert project_repository.publish("TASK-001: to-do -> in-review") is True

    assert run_git(remote, "log", "main", "--format=%s") == "TASK-001: to-do -> in-review"
    assert "index.html" in run_git(remote, "ls-tree", "--name-only", "main")


def test_publish_without_changes_does_not_create_empty_commit(
    project_repository, project_path, remote
):
    project_repository.prepare()
    (project_path / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")
    project_repository.publish("first")

    assert project_repository.publish("second") is True

    assert run_git(remote, "rev-list", "--count", "main") == "1"


def test_publish_rebases_on_top_of_remote_changes(
    project_repository, project_path, remote, tmp_path
):
    project_repository.prepare()
    (project_path / "a.txt").write_text("a", encoding="utf-8")
    project_repository.publish("add a")
    colleague = tmp_path / "colleague"
    run_git(tmp_path, "clone", str(remote), str(colleague))
    (colleague / "b.txt").write_text("b", encoding="utf-8")
    run_git(colleague, "add", "b.txt")
    run_git(colleague, "-c", "user.name=c", "-c", "user.email=c@c", "commit", "-m", "add b")
    run_git(colleague, "push", "origin", "main")
    (project_path / "c.txt").write_text("c", encoding="utf-8")

    assert project_repository.publish("add c") is True

    files = run_git(remote, "ls-tree", "--name-only", "main").splitlines()
    assert sorted(files) == [".gitignore", "a.txt", "b.txt", "c.txt"]


def test_publish_returns_false_when_remote_is_unreachable(project_path, logger, tmp_path):
    repository = ProjectRepository(str(project_path), str(tmp_path / "missing.git"), logger)
    repository.prepare()
    Path(project_path / "a.txt").write_text("a", encoding="utf-8")

    assert repository.publish("add a") is False
