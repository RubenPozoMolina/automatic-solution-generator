import json
from pathlib import Path

import pytest

OPENCODE_DIRECTORY = Path(__file__).resolve().parent.parent / ".opencode"


@pytest.fixture(scope="module")
def opencode_config():
    return json.loads((OPENCODE_DIRECTORY / "opencode.json").read_text(encoding="utf-8"))


def test_database_expert_agent_is_defined_in_the_configuration(opencode_config):
    agent = opencode_config["agent"]["database-expert"]

    assert agent["mode"] == "subagent"
    assert "PostgreSQL" in agent["description"]
    assert agent["permission"]["skill"] == "allow"


def test_database_expert_cannot_run_database_clients_on_the_host(opencode_config):
    bash_rules = opencode_config["agent"]["database-expert"]["permission"]["bash"]

    assert bash_rules["psql*"] == "deny"
    assert bash_rules["pg_dump*"] == "deny"
    assert bash_rules["docker run*--network host*"] == "deny"


def test_database_expert_definition_file_matches_the_configuration():
    definition = (OPENCODE_DIRECTORY / "agents" / "database-expert.md").read_text(encoding="utf-8")

    assert "name: database-expert" in definition
    assert "docker-test-runner" in definition
    assert "Container-Only Testing" in definition


def test_docker_test_runner_documents_postgresql_containers():
    skill = (OPENCODE_DIRECTORY / "skills" / "docker-test-runner" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "postgres:16-alpine" in skill
    assert "Database services" in skill
