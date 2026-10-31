import fnmatch
import json
import re
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


def test_security_expert_agent_is_defined_in_the_configuration(opencode_config):
    agent = opencode_config["agent"]["security-expert"]

    assert agent["mode"] == "subagent"
    assert "Security Expert" in agent["description"]
    assert agent["permission"]["skill"] == "allow"


@pytest.mark.parametrize(
    "rule",
    ["nmap*", "msfconsole*", "hashcat*", "john*", "tshark*", "gdb*", "docker run*--privileged*"],
)
def test_security_expert_cannot_run_security_tools_on_the_host(opencode_config, rule):
    bash_rules = opencode_config["agent"]["security-expert"]["permission"]["bash"]

    assert bash_rules[rule] == "deny"


def test_security_expert_definition_file_matches_the_configuration():
    definition = (OPENCODE_DIRECTORY / "agents" / "security-expert.md").read_text(encoding="utf-8")

    assert "name: security-expert" in definition
    assert "security-tools-catalog" in definition
    assert "Container-Only Testing" in definition


def read_security_tools_catalog():
    path = OPENCODE_DIRECTORY / "skills" / "security-tools-catalog" / "SKILL.md"
    return path.read_text(encoding="utf-8")


def test_security_tools_catalog_is_registered_and_documents_open_source_tools(opencode_config):
    skill = read_security_tools_catalog()

    assert opencode_config["skill"]["security-tools-catalog"]["enabled"] is True
    for tool in (
        "Wireshark", "Wazuh", "OpenSearch", "Snort", "Suricata", "Kali Linux", "Nmap",
        "Metasploit Framework", "OWASP ZAP", "mitmproxy", "Ghidra", "Rizin", "x64dbg", "GDB",
        "Hashcat", "John the Ripper",
    ):
        assert tool in skill


@pytest.mark.parametrize("proprietary_tool", ["Burp Suite", "IDA Pro", "Splunk", "Elastic Security"])
def test_security_tools_catalog_lists_proprietary_tools_only_as_not_allowed(proprietary_tool):
    skill = read_security_tools_catalog()
    licensing_policy, remaining_catalog = skill.split("## Ground rules (mandatory)")

    assert proprietary_tool in licensing_policy
    assert proprietary_tool not in remaining_catalog


@pytest.mark.parametrize("proprietary_tool", ["Burp Suite", "IDA Pro", "Splunk", "Elastic Security"])
def test_security_expert_definition_does_not_recommend_proprietary_tools(proprietary_tool):
    definition = (OPENCODE_DIRECTORY / "agents" / "security-expert.md").read_text(encoding="utf-8")
    guidelines = definition.split("## Guidelines")[1].split("## Ethics and Scope")[0]
    before_guidelines = definition.split("## Guidelines")[0]

    assert proprietary_tool not in before_guidelines
    assert "only open source tools" in guidelines


AGENTS_RUNNING_CODE = [
    "software-architect", "backend-developer", "database-expert", "security-expert",
    "web-developer", "devops-engineer", "qa-automation", "qa-manual", "ui-designer",
]
HARDENED_DOCKER_RULES = [
    "docker run*--privileged*",
    "docker run*--network=host*",
    "docker run*--net=host*",
    "docker run*--pid=host*",
    "docker run*--ipc host*",
    "docker run*--device*",
    "docker run*--security-opt*unconfined*",
    "docker run*--cap-add*SYS_ADMIN*",
    "docker run*--cap-add*ALL*",
    "docker run*-v /*",
    'docker run*-v "/*',
    "docker run*-v ~*",
    "docker run*-v $HOME*",
    "docker run*--volume=/*",
    "docker run*--mount*source=/*",
    "docker create*--privileged*",
    "docker create*-v /*",
    "docker exec*--privileged*",
    "docker compose*--privileged*",
    "docker-compose*--privileged*",
]


@pytest.mark.parametrize("agent_name", AGENTS_RUNNING_CODE)
@pytest.mark.parametrize("rule", HARDENED_DOCKER_RULES)
def test_agents_running_code_have_hardened_docker_rules(opencode_config, agent_name, rule):
    bash_rules = opencode_config["agent"][agent_name]["permission"]["bash"]

    assert bash_rules[rule] == "deny"


@pytest.mark.parametrize("agent_name", AGENTS_RUNNING_CODE)
def test_hardened_docker_rules_do_not_block_project_mounts_or_minimal_capabilities(
    opencode_config, agent_name
):
    denied = [
        fnmatch.translate(rule)
        for rule, action in opencode_config["agent"][agent_name]["permission"]["bash"].items()
        if action == "deny" and rule.startswith("docker run")
    ]
    allowed_commands = [
        'docker run --rm --cap-drop ALL --cap-add NET_RAW -v "$PROJECT_DIR":/work:ro img',
        "docker run --rm -v $(pwd)/results:/results -v my-volume:/data img",
        'docker run --rm --cap-drop ALL --cap-add CHOWN --tmpfs /tmp --network "$NET" img',
    ]

    for command in allowed_commands:
        assert not any(re.match(pattern, command) for pattern in denied), command


@pytest.mark.parametrize("agent_name", ["project-manager", "product-owner", "business-analyst"])
def test_planning_agents_cannot_run_shell_commands(opencode_config, agent_name):
    assert opencode_config["agent"][agent_name]["permission"]["bash"] == "deny"
