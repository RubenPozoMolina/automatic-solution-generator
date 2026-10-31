import logging
import os
import re
import subprocess
from typing import Optional

from utils.log_utils import LogUtils

DEFAULT_TRUNK_BRANCH = "main"
DEFAULT_GIT_TIMEOUT = 120
REMOTE_NAME = "origin"
GITIGNORE_FILE_NAME = ".gitignore"
HEAD_REFERENCE_PREFIX = "ref: refs/heads/"
TICKET_BRANCH_PREFIX = "ticket/"
GITIGNORE_ENTRIES = (
    "node_modules/",
    "*.log",
    "*.pid",
    "*.deb",
    ".ticket-*.json",
    "test-results/",
    "qa-artifacts/",
)
GIT_ENVIRONMENT = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new",
}


class ProjectRepository:
    """Prepares the generated project as a trunk-based Git repository and publishes it.

    Each ticket works on a short-lived branch that is merged into the trunk once it is done.
    """

    def __init__(
        self,
        project_path: str,
        remote_url: Optional[str],
        logger: LogUtils,
        trunk_branch: Optional[str] = None,
        timeout: float = DEFAULT_GIT_TIMEOUT
    ):
        self.project_path = project_path
        self.remote_url = (remote_url or "").strip()
        self.logger = logger
        self.trunk_branch = trunk_branch or DEFAULT_TRUNK_BRANCH
        self.is_trunk_configured = bool(trunk_branch)
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.remote_url)

    def prepare(self) -> bool:
        """Initializes the repository and its remote. Returns False when it cannot be used."""
        if not self.is_configured():
            return False
        os.makedirs(self.project_path, exist_ok=True)
        if not self._is_initialized() and not self._run("init", "--initial-branch", self.trunk_branch):
            return False
        self._ensure_gitignore()
        if not self._ensure_remote():
            return False
        self._adopt_remote_default_branch()
        return True

    def get_agent_instructions(self, ticket_id: Optional[str] = None) -> str:
        if not self.is_configured():
            return ""
        instructions = (
            f"Version control: the project is the Git repository {self.remote_url} and "
            f"follows trunk-based development with the trunk branch '{self.trunk_branch}'. "
            f"Follow the trunk-based-development skill. "
        )
        if ticket_id is None:
            return instructions + "Integrate small commits and push them as soon as your phase is complete."
        branch = self.get_ticket_branch(ticket_id)
        return (
            f"{instructions}The project is already checked out on the short-lived branch '{branch}' "
            f"for this ticket: commit small, meaningful changes on it and do not switch branches. "
            f"Never push to or commit on '{self.trunk_branch}': the orchestrator pushes '{branch}' "
            f"after each phase and merges it into '{self.trunk_branch}' only when the ticket is done."
        )

    @staticmethod
    def get_ticket_branch(ticket_id: str) -> str:
        safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", str(ticket_id))
        safe_id = re.sub(r"\.{2,}", ".", safe_id).strip("-.") or "ticket"
        return f"{TICKET_BRANCH_PREFIX}{safe_id}"

    def start_ticket(self, ticket_id: str) -> bool:
        """Checks out the short-lived branch of the ticket, creating it from the trunk."""
        if not self.is_configured():
            return False
        if not self._is_initialized() and not self.prepare():
            return False
        return self._switch_to_branch(self.get_ticket_branch(ticket_id))

    def publish(self, ticket_id: str, message: str, integrate: bool = False) -> bool:
        """Commits pending changes to the ticket branch and pushes it. Never raises.

        With `integrate`, the branch is then rebased onto the trunk, fast-forwarded into it and
        deleted. The trunk only ever receives finished tickets.
        """
        if not self.is_configured():
            return False
        if not self._is_initialized() and not self.prepare():
            return False
        branch = self.get_ticket_branch(ticket_id)
        if not self._switch_to_branch(branch) or not self._commit(message):
            return False
        if not self._push_branch(branch):
            return False
        return self._integrate_into_trunk(branch) if integrate else True

    def _switch_to_branch(self, branch: str) -> bool:
        current_branch = self._read("symbolic-ref", "--short", "HEAD")
        if current_branch == branch:
            return True
        if current_branch and current_branch != self.trunk_branch:
            self._commit(f"WIP: unfinished work left on {current_branch}")
        if self._ref_exists(f"refs/heads/{branch}"):
            return self._run("checkout", branch)
        start_point = self._get_trunk_start_point()
        return self._run("checkout", "-b", branch, *([start_point] if start_point else []))

    def _get_trunk_start_point(self) -> Optional[str]:
        if self._has_remote_branch() and self._run("fetch", REMOTE_NAME, self.trunk_branch):
            return f"{REMOTE_NAME}/{self.trunk_branch}"
        if not self._ref_exists(f"refs/heads/{self.trunk_branch}"):
            self._bootstrap_trunk()
        if self._ref_exists(f"refs/heads/{self.trunk_branch}"):
            return self.trunk_branch
        return None

    def _bootstrap_trunk(self) -> None:
        """Creates the first trunk commit (only `.gitignore`) so every ticket branches from it."""
        if self._read("symbolic-ref", "--short", "HEAD") != self.trunk_branch:
            return
        if not self._run("add", GITIGNORE_FILE_NAME, log_failure=False):
            return
        if self._run(
            "-c", "user.name=ASG", "-c", "user.email=asg@localhost",
            "commit", "--message", "Initialize trunk"
        ):
            self._run("push", "--set-upstream", REMOTE_NAME, self.trunk_branch)

    def _ref_exists(self, reference: str) -> bool:
        return self._run("rev-parse", "--verify", "--quiet", reference, log_failure=False)

    def _commit(self, message: str) -> bool:
        if not self._run("add", "--all"):
            return False
        if self._run("diff", "--cached", "--quiet", log_failure=False):
            self.logger.log(logging.DEBUG, "No changes to commit in the project repository")
            return True
        return self._run(
            "-c", "user.name=ASG", "-c", "user.email=asg@localhost",
            "commit", "--message", message
        )

    def _push_branch(self, branch: str) -> bool:
        if not self._ref_exists(f"refs/heads/{branch}"):
            self.logger.log(logging.DEBUG, f"Branch '{branch}' has no commits to push yet")
            return True
        pushed = self._run("push", "--set-upstream", REMOTE_NAME, branch)
        if pushed:
            self.logger.log(logging.INFO, f"Pushed branch '{branch}' to {self.remote_url}")
        return pushed

    def _integrate_into_trunk(self, branch: str) -> bool:
        if not self._ref_exists(f"refs/heads/{branch}"):
            return True
        if self._has_remote_branch() and not self._rebase_onto_remote_trunk():
            return False
        if not self._run("push", REMOTE_NAME, f"{branch}:{self.trunk_branch}"):
            return False
        self._run("checkout", "-B", self.trunk_branch, branch)
        self._run("branch", "--set-upstream-to", f"{REMOTE_NAME}/{self.trunk_branch}", log_failure=False)
        self._run("branch", "-D", branch, log_failure=False)
        self._run("push", REMOTE_NAME, "--delete", branch, log_failure=False)
        self.logger.log(
            logging.INFO,
            f"Merged '{branch}' into trunk '{self.trunk_branch}' of {self.remote_url}"
        )
        return True

    def _rebase_onto_remote_trunk(self) -> bool:
        if not self._run("fetch", REMOTE_NAME, self.trunk_branch):
            return False
        if self._run("rebase", f"{REMOTE_NAME}/{self.trunk_branch}"):
            return True
        self._run("rebase", "--abort", log_failure=False)
        return False

    def detect_remote_default_branch(self) -> Optional[str]:
        """Returns the default branch of the remote, or None when it has none or is unreachable."""
        output = self._read("ls-remote", "--symref", REMOTE_NAME, "HEAD")
        for line in (output or "").splitlines():
            if line.startswith(HEAD_REFERENCE_PREFIX):
                return line[len(HEAD_REFERENCE_PREFIX):].split("\t")[0].strip() or None
        return None

    def _adopt_remote_default_branch(self) -> None:
        remote_default_branch = self.detect_remote_default_branch()
        if remote_default_branch is None:
            self.logger.log(
                logging.DEBUG,
                f"Remote has no default branch yet; using trunk '{self.trunk_branch}'"
            )
            return
        if remote_default_branch == self.trunk_branch:
            return
        if self.is_trunk_configured:
            self.logger.log(
                logging.WARNING,
                f"Remote default branch is '{remote_default_branch}' but the configured trunk is "
                f"'{self.trunk_branch}'; keeping the configured trunk"
            )
            return
        self.logger.log(
            logging.INFO,
            f"Using the remote default branch '{remote_default_branch}' as trunk"
        )
        self.trunk_branch = remote_default_branch

    def _has_remote_branch(self) -> bool:
        return self._run(
            "ls-remote", "--exit-code", "--heads", REMOTE_NAME, self.trunk_branch,
            log_failure=False
        )

    def _is_initialized(self) -> bool:
        return os.path.isdir(os.path.join(self.project_path, ".git"))

    def _ensure_remote(self) -> bool:
        current_url = self._read("remote", "get-url", REMOTE_NAME)
        if current_url is None:
            return self._run("remote", "add", REMOTE_NAME, self.remote_url)
        if current_url != self.remote_url:
            return self._run("remote", "set-url", REMOTE_NAME, self.remote_url)
        return True

    def _ensure_gitignore(self) -> None:
        path = os.path.join(self.project_path, GITIGNORE_FILE_NAME)
        existing_entries = set()
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as file:
                existing_entries = {line.strip() for line in file}
        missing_entries = [entry for entry in GITIGNORE_ENTRIES if entry not in existing_entries]
        if not missing_entries:
            return
        with open(path, "a", encoding="utf-8") as file:
            file.write("\n".join(missing_entries) + "\n")

    def _run(self, *arguments: str, log_failure: bool = True) -> bool:
        completed = self._execute(arguments)
        if completed is not None and completed.returncode == 0:
            return True
        if log_failure:
            detail = completed.stderr.strip() if completed is not None else "timeout or git missing"
            self.logger.log(
                logging.WARNING,
                f"git {' '.join(arguments[:3])} failed in {self.project_path}: {detail}"
            )
        return False

    def _read(self, *arguments: str) -> Optional[str]:
        completed = self._execute(arguments)
        if completed is None or completed.returncode != 0:
            return None
        return completed.stdout.strip()

    def _execute(self, arguments: tuple[str, ...]) -> Optional[subprocess.CompletedProcess]:
        try:
            return subprocess.run(
                ["git", *arguments],
                cwd=self.project_path,
                env={**os.environ, **GIT_ENVIRONMENT},
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
