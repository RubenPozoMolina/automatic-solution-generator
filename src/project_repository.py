import logging
import os
import subprocess
from typing import Optional

from utils.log_utils import LogUtils

DEFAULT_TRUNK_BRANCH = "main"
DEFAULT_GIT_TIMEOUT = 120
REMOTE_NAME = "origin"
GITIGNORE_FILE_NAME = ".gitignore"
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
    """Prepares the generated project as a trunk-based Git repository and publishes it."""

    def __init__(
        self,
        project_path: str,
        remote_url: Optional[str],
        logger: LogUtils,
        trunk_branch: str = DEFAULT_TRUNK_BRANCH,
        timeout: float = DEFAULT_GIT_TIMEOUT
    ):
        self.project_path = project_path
        self.remote_url = (remote_url or "").strip()
        self.logger = logger
        self.trunk_branch = trunk_branch
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
        return self._ensure_remote()

    def get_agent_instructions(self) -> str:
        if not self.is_configured():
            return ""
        return (
            f"Version control: the project is the Git repository {self.remote_url} and "
            f"follows trunk-based development. Follow the trunk-based-development skill: "
            f"integrate small commits into the trunk branch '{self.trunk_branch}' "
            f"and push them as soon as your phase is complete."
        )

    def publish(self, message: str) -> bool:
        """Commits pending changes to the trunk and pushes them. Never raises."""
        if not self.is_configured():
            return False
        if not self._is_initialized() and not self.prepare():
            return False
        if not self._commit(message):
            return False
        return self._integrate_and_push()

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

    def _integrate_and_push(self) -> bool:
        self._run("checkout", "-B", self.trunk_branch, log_failure=False)
        if self._has_remote_branch():
            if not self._run("pull", "--rebase", REMOTE_NAME, self.trunk_branch):
                self._run("rebase", "--abort", log_failure=False)
                return False
        pushed = self._run("push", "--set-upstream", REMOTE_NAME, self.trunk_branch)
        if pushed:
            self.logger.log(
                logging.INFO,
                f"Pushed project changes to {self.remote_url} ({self.trunk_branch})"
            )
        return pushed

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
