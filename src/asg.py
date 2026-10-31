import json
import logging
import os
from typing import Any, Callable, Iterable, Optional, Union

from src.errors import SessionTimeoutError, SolutionGenerationError
from src.project_repository import ProjectRepository
from src.sprint_planner import SprintPlanner
from src.sprint_report import SprintReport
from src.ticket_repository import TicketRepository
from src.ticket_status import (
    STATUS_BLOCKED,
    STATUS_TO_DO,
    is_closed,
    is_pending,
    is_to_do,
    normalize_status,
)
from src.ticket_workflow import TicketWorkflow
from utils.log_utils import LogUtils
from utils.opencode_api import OpencodeAPI

MODEL_REFERENCE_SEPARATOR = "/"
PRD_FILE_NAME = "prd.md"
TASKS_DIRECTORY_NAME = "tasks"
DEFAULT_TASKS_PER_SPRINT = 5
SESSION_FAILURE_FINISH = "error"
SESSION_FAILURE_OUTCOME = "failed"
SESSION_SUCCESS_OUTCOME = "succeeded"
DEFAULT_MAX_STALLED_SPRINTS = 3
DEFAULT_MAX_RETRIES_PER_TICKET = 3
DEFAULT_MAX_STATUS_HISTORY = 10
PROJECT_MANAGER_AGENT = "project-manager"
DEFAULT_GENERATION_FOLLOW_UPS = 2
TICKET_RESULT_FOLLOW_UPS = 1
DEFAULT_SESSION_TIMEOUT = 1800
WRITE_TOOL_HINT = "with the `write` tool (arguments: `path`, `content`)"


class AutomaticSolutionGenerator:

    def __init__(self, config: dict[str, Any], logger: LogUtils):
        self.config = config
        self.logger = logger
        self.opencode_api: OpencodeAPI = self._create_opencode_api()
        self.agents: dict[str, Any] = {}
        self.project_path = os.path.abspath(str(config["project_path"]))
        self.ticket_repository = TicketRepository(self.get_tasks_path(), logger)
        self.project_repository = ProjectRepository(
            self.project_path,
            config.get("repository"),
            logger,
            str(config["repository_branch"]) if config.get("repository_branch") else None
        )
        self.max_retries_per_ticket = int(
            config.get(
                "max_retries_per_ticket",
                config.get("max_blocked_retries", DEFAULT_MAX_RETRIES_PER_TICKET)
            )
        )
        self.max_status_history = int(
            config.get(
                "max_status_history",
                config.get("max_history_entries", DEFAULT_MAX_STATUS_HISTORY)
            )
        )
        self.ticket_workflow = TicketWorkflow(
            max_retries_per_ticket=self.max_retries_per_ticket,
            max_status_history=self.max_status_history,
        )
        self.sprint_planner = SprintPlanner(
            self.ticket_repository,
            int(config.get("tasks_per_sprint", DEFAULT_TASKS_PER_SPRINT)),
            logger,
            self.ticket_workflow
        )
        self.max_stalled_sprints = int(
            config.get("max_stalled_sprints", DEFAULT_MAX_STALLED_SPRINTS)
        )
        self.generation_follow_ups = int(
            config.get("generation_follow_ups", DEFAULT_GENERATION_FOLLOW_UPS)
        )
        self.session_timeout = float(config.get("session_timeout", DEFAULT_SESSION_TIMEOUT))
        self.resume = bool(config.get("resume", True))

    def _create_opencode_api(self) -> OpencodeAPI:
        try:
            return OpencodeAPI(
                self.logger,
                self.config["opencode_base_url"],
                self.config["opencode_user"],
                self.config["opencode_password"]
            )
        except KeyError as error:
            raise SolutionGenerationError(
                f"Missing Opencode API configuration value: {error}"
            ) from error

    def is_opencode_running(self) -> bool:
        return bool(self.opencode_api.get_health())

    def save_opencode_openapi(self, output: str) -> None:
        output_directory = os.path.dirname(output)
        if output_directory:
            os.makedirs(output_directory, exist_ok=True)
        openapi = self.opencode_api.get_openapi()
        with open(output, "w", encoding="utf-8") as file:
            json.dump(openapi, file, indent=4)

    def get_public_agents(self) -> list[dict[str, Any]]:
        public_agents = []
        for agent in self.agents.get("data", []):
            if not agent["hidden"] and agent["mode"] == "primary" and agent["id"] not in ["build", "plan"]:
                public_agents.append(agent)
        return public_agents

    def get_model_dict(self) -> dict[str, str]:
        model_reference = str(self.config["model"])
        if MODEL_REFERENCE_SEPARATOR not in model_reference:
            raise SolutionGenerationError(
                f"Model reference must have the form "
                f"'<provider>{MODEL_REFERENCE_SEPARATOR}<model>': {model_reference}"
            )
        provider_id, model_id = model_reference.split(MODEL_REFERENCE_SEPARATOR, 1)
        return {
            "id": model_id,
            "providerID": provider_id
        }

    def get_agent(self, agent_id: str) -> Optional[dict[str, Any]]:
        for agent in self.agents.get("data", []):
            if agent["id"] == agent_id:
                return agent
        return None

    def get_prd_path(self) -> str:
        return os.path.join(self.project_path, PRD_FILE_NAME)

    def get_tasks_path(self) -> str:
        return os.path.join(self.project_path, TASKS_DIRECTORY_NAME)

    def get_requirements_analysis(self) -> str:
        return (
            f"Create PRD from interview in: {self.get_customer_interview()}. "
            f"Save the PRD in: {self.get_prd_path()}"
        )

    def get_generate_tasks(self) -> str:
        return (
            f"Analyze PRD at {self.get_prd_path()} and create all tasks using the create-ticket skill. "
            f"Each task must be saved as a separate JSON file in the {self.get_tasks_path()} directory. "
            f"If previous tasks exist, do not create tasks that have already been created"
        )

    def get_plan_sprint_prompt(
        self,
        sprint: int,
        open_tickets: list[dict[str, Any]],
        capacity: int
    ) -> str:
        open_summary = "; ".join(
            f"{ticket.get('id', ticket.get('filename'))} "
            f"({ticket.get('status')}, {ticket.get('assignee')})"
            for ticket in open_tickets
        ) or "none"
        return (
            f"Plan sprint {sprint}. Tickets are JSON files in {self.get_tasks_path()}. "
            f"There are {len(open_tickets)} open tickets: {open_summary}. "
            f"The free capacity for this sprint is {capacity} tickets. "
            f"Move at most {capacity} tickets from 'backlog' to 'to-do', set their 'sprint' "
            f"to {sprint} and their 'assignee' to the executing agent. Only choose tickets "
            f"whose dependencies are all done; respect priorities. Do not edit "
            f"'statusHistory', do not modify any other ticket and do not create new tickets."
        )

    def get_customer_interview(self) -> str:
        interview_path = self.config.get("customer_interview")
        if not interview_path:
            return ""
        return os.path.abspath(str(interview_path))

    def load_tickets(self) -> list[dict[str, Any]]:
        return self.ticket_repository.load_tickets()

    def get_sprint_tickets(self, sprint: Optional[int] = None) -> list[dict[str, Any]]:
        sprint_tickets = []
        for ticket in self.load_tickets():
            if not is_to_do(ticket):
                continue
            if sprint is not None:
                ticket["sprint"] = sprint
            sprint_tickets.append(ticket)
            self.logger.log(
                logging.INFO,
                f"Found sprint ticket: {ticket['filename']} with status '{ticket.get('status')}'"
            )
        return sprint_tickets

    def all_tickets_closed(self) -> bool:
        tickets = self.load_tickets()
        if not tickets:
            self.logger.log(
                logging.ERROR,
                "No tickets found. The project cannot be considered complete."
            )
            return False

        pending_tickets = [ticket for ticket in tickets if not is_closed(ticket)]
        if not pending_tickets:
            self.logger.log(logging.INFO, "All tickets are closed.")
            return True

        for ticket in pending_tickets:
            self.logger.log(
                logging.INFO,
                f"Pending task: {ticket.get('filename')} with status '{ticket.get('status')}'"
            )
        self.logger.log(logging.INFO, f"{len(pending_tickets)} tickets still pending.")
        return False

    def generate_solution(self) -> None:
        if not self.is_opencode_running():
            raise SolutionGenerationError("Opencode is not running")

        self._prepare_project()
        if self.resume and os.path.isfile(self.get_prd_path()):
            self.logger.log(logging.INFO, f"Resuming: PRD already exists at {self.get_prd_path()}")
        else:
            self._generate_prd()
        if self.resume and self.load_tickets():
            self.logger.log(
                logging.INFO,
                f"Resuming: tickets already exist in {self.get_tasks_path()}"
            )
        else:
            self._generate_tasks()
        self._run_sprints(self._get_start_sprint())

    def _get_start_sprint(self) -> int:
        if not self.resume:
            return 0
        sprints = [
            sprint for sprint in map(self._ticket_sprint, self.load_tickets())
            if sprint is not None
        ]
        start_sprint = max(sprints, default=0)
        if start_sprint:
            self.logger.log(logging.INFO, f"Resuming sprints from sprint {start_sprint}")
        return start_sprint

    def _prepare_project(self) -> None:
        config = self.opencode_api.get_config()
        self.logger.save_dict("config", config)
        os.makedirs(self.project_path, exist_ok=True)
        self.project_repository.prepare()
        self.save_opencode_openapi("openapi/opencode.json")
        self.agents = self.opencode_api.get_agents()

    def _generate_prd(self) -> None:
        interview_path = self.get_customer_interview()
        if not interview_path:
            raise SolutionGenerationError("Customer interview path is not configured")

        prd_path = self.get_prd_path()
        created = self._process_until(
            "product-manager",
            0,
            self.get_requirements_analysis(),
            [interview_path],
            lambda: os.path.isfile(prd_path),
            f"The PRD file {prd_path} does not exist yet. Continue now: write the complete "
            f"PRD to that path {WRITE_TOOL_HINT}.",
            self.generation_follow_ups
        )
        if not created:
            raise SolutionGenerationError(
                f"The product manager did not create the PRD: {prd_path}"
            )

    def _generate_tasks(self) -> None:
        tasks_path = self.get_tasks_path()
        os.makedirs(tasks_path, exist_ok=True)
        created = self._process_until(
            PROJECT_MANAGER_AGENT,
            0,
            self.get_generate_tasks(),
            [self.get_prd_path()],
            lambda: bool(self.load_tickets()),
            f"The tasks directory {tasks_path} still contains no ticket JSON files. Continue "
            f"now: create every ticket as a separate JSON file in that directory "
            f"{WRITE_TOOL_HINT}.",
            self.generation_follow_ups
        )
        if not created:
            raise SolutionGenerationError(
                f"The project manager did not create any tickets in {tasks_path}"
            )

    def _run_sprints(self, start_sprint: int = 0) -> None:
        sprint = start_sprint
        stalled_sprints = 0
        while True:
            self.logger.log(logging.INFO, f"Starting sprint {sprint}")
            self.sprint_planner.remove_ancestor_dependencies()
            statuses_before = SprintReport.snapshot(self.load_tickets())
            self.sprint_planner.release_unready_tickets(sprint)
            planned_tickets = self._plan_sprint(sprint)
            self._log_sprint_tickets(sprint, planned_tickets)
            self._carry_over_pending_tickets(sprint)
            self._close_completed_epics()

            if (
                not self.sprint_planner.get_open_tickets()
                and not self.sprint_planner.get_backlog_tickets()
            ):
                if self.all_tickets_closed():
                    self.logger.log(logging.INFO, f"Finished sprint {sprint}")
                    self._log_sprint_report(sprint, statuses_before, planned_tickets)
                    return
                raise SolutionGenerationError(
                    f"No backlog tickets available for sprint {sprint} while open tickets remain"
                )

            progress = self._advance_sprint_tickets(sprint)
            self._close_completed_epics()
            self.logger.log(logging.INFO, f"Finished sprint {sprint}")
            self._log_sprint_report(sprint, statuses_before, planned_tickets)

            stalled_sprints = 0 if progress or planned_tickets else stalled_sprints + 1
            if stalled_sprints >= self.max_stalled_sprints:
                raise SolutionGenerationError(
                    f"No ticket progressed during {stalled_sprints} consecutive sprints"
                )
            sprint += 1

    def _log_sprint_report(
        self,
        sprint: int,
        statuses_before: dict[str, str],
        planned_tickets: list[dict[str, Any]]
    ) -> None:
        report = SprintReport(sprint, statuses_before, self.load_tickets(), len(planned_tickets))
        for line in report.lines():
            self.logger.log(logging.INFO, line)

    def _plan_sprint(self, sprint: int) -> list[dict[str, Any]]:
        open_tickets = self.sprint_planner.get_open_tickets()
        backlog_tickets = self.sprint_planner.get_backlog_tickets()
        capacity = self.sprint_planner.get_capacity()
        self.logger.log(
            logging.INFO,
            f"Sprint {sprint} load: {len(open_tickets)} open tickets, "
            f"{len(backlog_tickets)} in backlog, capacity {capacity}"
        )
        if capacity == 0 or not backlog_tickets:
            return []

        self.process(
            PROJECT_MANAGER_AGENT,
            sprint,
            self.get_plan_sprint_prompt(sprint, open_tickets, capacity),
            [self.get_prd_path()]
        )
        planned_tickets = self.sprint_planner.enforce_plan(sprint, backlog_tickets, capacity)
        if planned_tickets or open_tickets:
            return planned_tickets

        self.logger.log(
            logging.WARNING,
            f"Project manager planned no tickets for sprint {sprint}; "
            f"using the deterministic planner"
        )
        return self.sprint_planner.plan(sprint, limit=capacity)

    def _close_completed_epics(self) -> None:
        tickets = self.load_tickets()
        children_by_parent = self._group_children_by_parent(tickets)
        for ticket in tickets:
            if not self.ticket_workflow.is_epic(ticket):
                continue
            children = children_by_parent.get(str(ticket.get("id")), [])
            if self.ticket_workflow.close_epic_if_complete(ticket, children):
                self.ticket_repository.save_ticket(ticket)
                self.logger.log(
                    logging.INFO,
                    f"Closed epic {ticket.get('filename')} because all children are done"
                )

    @staticmethod
    def _group_children_by_parent(
        tickets: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        children_by_parent: dict[str, list[dict[str, Any]]] = {}
        for ticket in tickets:
            parent = ticket.get("parent") or ticket.get("parentId")
            if parent:
                children_by_parent.setdefault(str(parent), []).append(ticket)
        return children_by_parent

    def _carry_over_pending_tickets(self, sprint: int) -> None:
        for ticket in self.load_tickets():
            if is_closed(ticket) or not is_pending(ticket):
                continue
            if self.ticket_workflow.is_epic(ticket):
                continue
            if self._ticket_sprint(ticket) != sprint:
                ticket["sprint"] = sprint
                self.ticket_repository.save_ticket(ticket)
                self.logger.log(
                    logging.INFO,
                    f"Carried over ticket {ticket.get('filename')} to sprint {sprint}"
                )

    def _get_pending_sprint_tickets(self, sprint: int) -> list[dict[str, Any]]:
        all_tickets = self.load_tickets()
        closed_ticket_ids = {
            str(ticket.get("id")) for ticket in all_tickets if is_closed(ticket)
        }
        return [
            ticket for ticket in all_tickets
            if self._ticket_sprint(ticket) == sprint
            and is_pending(ticket)
            and self.ticket_workflow.is_processing_ready(ticket, closed_ticket_ids)
        ]

    def _advance_sprint_tickets(self, sprint: int) -> bool:
        """Performs one agent action, and therefore one status change, per ready ticket."""
        pending_tickets = self._get_pending_sprint_tickets(sprint)
        if not pending_tickets:
            return False
        progress = self._process_pending_tickets(pending_tickets, sprint)
        if not progress:
            self._log_stalled_tickets(pending_tickets)
        return progress

    def _process_pending_tickets(
        self,
        pending_tickets: list[dict[str, Any]],
        sprint: int
    ) -> bool:
        progress = False
        for ticket in pending_tickets:
            if self._unblock_ready_ticket(ticket, sprint):
                continue
            if self._process_ticket(ticket, sprint):
                progress = True
        return progress

    def _unblock_ready_ticket(
        self,
        ticket: dict[str, Any],
        sprint: int
    ) -> bool:
        if normalize_status(ticket.get("status")) != STATUS_BLOCKED:
            return False
        closed_ticket_ids = {
            str(loaded.get("id")) for loaded in self.load_tickets() if is_closed(loaded)
        }
        if not self.ticket_workflow.can_unblock(ticket, closed_ticket_ids):
            return False
        if not self.ticket_workflow.unblock(ticket):
            return False
        self.ticket_repository.save_ticket(ticket)
        self.logger.log(
            logging.INFO,
            f"Unblocked ticket {ticket.get('filename')} in sprint {sprint}"
        )
        return True

    def _process_ticket(self, ticket: dict[str, Any], sprint: int) -> bool:
        previous_status = normalize_status(ticket.get("status"))
        agent = self.ticket_workflow.get_assigned_agent(ticket)
        if not agent:
            self.logger.log(
                logging.WARNING,
                f"Ticket {ticket.get('filename')} has no assignee for status "
                f"'{previous_status}'"
            )
            return False

        self._persist_inferred_assignee(ticket, agent)
        ticket_id = self._get_ticket_identifier(ticket)
        self.project_repository.start_ticket(ticket_id)
        try:
            self._process_until(
                agent,
                sprint,
                self._build_ticket_prompt(ticket, sprint),
                [ticket["filepath"]],
                lambda: self._ticket_has_result(ticket),
                lambda: self._build_ticket_reminder(ticket),
                TICKET_RESULT_FOLLOW_UPS
            )
        except SessionTimeoutError as error:
            self.logger.log(
                logging.WARNING,
                f"Ticket {ticket.get('filename')} keeps status '{previous_status}' "
                f"in sprint {sprint}: {error}"
            )
            return False
        updated_ticket = self._reload_ticket(ticket)
        if updated_ticket is None:
            return False
        moved = self._save_ticket_transition(updated_ticket, sprint, previous_status)
        if moved:
            self.project_repository.publish(
                ticket_id,
                f"{ticket_id}: {previous_status} -> {updated_ticket.get('status')}",
                integrate=is_closed(updated_ticket)
            )
        return moved

    @staticmethod
    def _get_ticket_identifier(ticket: dict[str, Any]) -> str:
        return str(ticket.get("id") or ticket.get("filename"))

    def _build_ticket_prompt(self, ticket: dict[str, Any], sprint: int) -> str:
        prompt = self.ticket_workflow.build_prompt(ticket, sprint)
        repository_instructions = self.project_repository.get_agent_instructions(
            self._get_ticket_identifier(ticket)
        )
        if not repository_instructions:
            return prompt
        return f"{prompt} {repository_instructions}"

    def _persist_inferred_assignee(
        self,
        ticket: dict[str, Any],
        agent: str
    ) -> None:
        if ticket.get("assignee"):
            return
        ticket["assignee"] = agent
        self.ticket_repository.save_ticket(ticket)
        self.logger.log(
            logging.INFO,
            f"Assigned ticket {ticket.get('filename')} to '{agent}'"
        )

    def _save_ticket_transition(
        self,
        ticket: dict[str, Any],
        sprint: int,
        previous_status: Optional[str] = None
    ) -> bool:
        previous_status = previous_status or normalize_status(ticket.get("status"))
        closed_ticket_ids = {
            str(loaded.get("id")) for loaded in self.load_tickets() if is_closed(loaded)
        }
        if not self.ticket_workflow.apply_completion(
            ticket, previous_status, closed_ticket_ids=closed_ticket_ids
        ):
            self._discard_unregistered_status(ticket, previous_status)
            self.logger.log(
                logging.WARNING,
                f"Ticket {ticket.get('filename')} was not completed in sprint {sprint}"
            )
            return False

        self.ticket_repository.save_ticket(ticket)
        self.logger.log(
            logging.INFO,
            f"Ticket {ticket.get('filename')} moved from '{previous_status}' "
            f"to '{ticket.get('status')}' assigned to '{ticket.get('assignee')}'"
        )
        return self._is_forward_progress(previous_status, normalize_status(ticket.get("status")))

    @staticmethod
    def _is_forward_progress(previous_status: str, new_status: str) -> bool:
        if new_status == STATUS_BLOCKED:
            return False
        return previous_status != new_status

    def _ticket_has_result(self, ticket: dict[str, Any]) -> bool:
        if self.ticket_repository.get_parse_error(ticket["filepath"]):
            return False
        reloaded_ticket = self._reload_ticket(ticket)
        return reloaded_ticket is not None and self.ticket_workflow.has_result(reloaded_ticket)

    def _build_ticket_reminder(self, ticket: dict[str, Any]) -> str:
        parse_error = self.ticket_repository.get_parse_error(ticket["filepath"])
        if parse_error:
            return (
                f"The ticket file {ticket['filepath']} is no longer valid JSON ({parse_error}). "
                f"Fix the syntax now, keeping your changes, so the file parses again. "
                f"{self.ticket_workflow.build_result_reminder(ticket)}"
            )
        return self.ticket_workflow.build_result_reminder(ticket)

    def _discard_unregistered_status(
        self,
        ticket: dict[str, Any],
        previous_status: str
    ) -> None:
        written_status = normalize_status(ticket.get("status"))
        if written_status == previous_status:
            return
        ticket["status"] = previous_status
        self.ticket_repository.save_ticket(ticket)
        self.logger.log(
            logging.WARNING,
            f"Ignored status '{written_status}' written by an agent without a result on "
            f"{ticket.get('filename')}; restored '{previous_status}'"
        )

    def _reload_ticket(self, ticket: dict[str, Any]) -> Optional[dict[str, Any]]:
        for loaded_ticket in self.load_tickets():
            if loaded_ticket.get("filepath") == ticket.get("filepath"):
                return loaded_ticket
        return None

    def _log_stalled_tickets(self, pending_tickets: list[dict[str, Any]]) -> None:
        for ticket in pending_tickets:
            self.logger.log(
                logging.WARNING,
                f"Ticket {ticket.get('filename')} is stalled in status "
                f"'{ticket.get('status')}' assigned to '{ticket.get('assignee')}'"
            )

    @staticmethod
    def _ticket_sprint(ticket: dict[str, Any]) -> Optional[int]:
        try:
            return int(ticket.get("sprint"))
        except (TypeError, ValueError):
            return None

    def _log_sprint_tickets(self, sprint: int, sprint_tickets: list[dict[str, Any]]) -> None:
        if not sprint_tickets:
            return
        self.logger.log(logging.INFO, f"Tickets in sprint {sprint}:")
        for ticket in sprint_tickets:
            self.logger.log(
                logging.INFO,
                f"  - {ticket.get('filename')}: {ticket.get('title', 'No title')}"
            )

    def process(
        self,
        agent: str,
        sprint: int,
        prompt: str,
        files: Iterable[str]
    ) -> dict[str, Any]:
        self._validate_existing_files(files)
        session = self.opencode_api.get_session(
            agent,
            self.get_model_dict(),
            self.project_path
        )
        if not session:
            raise SolutionGenerationError(f"Failed to create session for agent {agent}")

        self._run_prompt(session, agent, sprint, prompt, files)
        return session

    def _process_until(
        self,
        agent: str,
        sprint: int,
        prompt: str,
        files: Iterable[str],
        is_done: Callable[[], bool],
        reminder: Union[str, Callable[[], str]],
        max_follow_ups: int
    ) -> bool:
        """Runs a prompt and keeps the same session going until the expected artifact exists.

        Models sometimes end a session after a failed or dropped tool call; a short follow-up
        in the same session is cheaper than starting over because the context is preserved.
        """
        session = self.process(agent, sprint, prompt, files)
        for follow_up in range(1, max_follow_ups + 1):
            if is_done():
                return True
            self.logger.log(
                logging.WARNING,
                f"Agent {agent} ended without the expected result; "
                f"follow-up {follow_up}/{max_follow_ups}"
            )
            message = reminder() if callable(reminder) else reminder
            self._run_prompt(session, agent, sprint, message, [])
        return is_done()

    def _run_prompt(
        self,
        session: dict[str, Any],
        agent: str,
        sprint: int,
        prompt: str,
        files: Iterable[str]
    ) -> None:
        response = self.opencode_api.send_prompt(
            session=session,
            message=prompt,
            files=files
        )
        if response is None:
            raise SolutionGenerationError(f"Failed to send prompt to agent {agent}")

        self.logger.log(
            logging.INFO,
            f"agent {agent} sprint {sprint} prompt {prompt[0:100]}"
        )

        if not self.opencode_api.wait_session(session, self.session_timeout):
            interrupted = self.opencode_api.interrupt_session(session)
            self.logger.log(
                logging.WARNING,
                f"Session for agent {agent} did not finish within {self.session_timeout:g} "
                f"seconds; interrupted: {interrupted}"
            )
            raise SessionTimeoutError(
                f"Agent {agent} session did not finish within {self.session_timeout:g} seconds"
            )

        session_messages = self.opencode_api.get_session_messages(session)
        if not session_messages or "data" not in session_messages:
            raise SolutionGenerationError(
                f"Failed to retrieve session messages for agent {agent}"
            )

        self._log_session_messages(session_messages)

        failure = self._find_session_failure(session_messages)
        if failure is not None:
            raise SolutionGenerationError(
                f"Agent {agent} session failed: {self._describe_session_failure(failure)}"
            )

        self.logger.log(logging.INFO, f"Session completed for agent {agent}")

    @staticmethod
    def _validate_existing_files(files: Iterable[str]) -> None:
        missing_files = [path for path in files if path and not os.path.isfile(path)]
        if missing_files:
            raise SolutionGenerationError(
                f"Missing required files: {', '.join(missing_files)}"
            )

    def _log_session_messages(self, session_messages: dict[str, Any]) -> None:
        for message in session_messages["data"]:
            message_id = message.get("id", "unknown")
            self.logger.log(logging.INFO, f"Message {message_id}: {message}")
            self.logger.save_dict(message_id, message)

    @staticmethod
    def _find_session_failure(session_messages: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Returns the failure that ended the session, ignoring errors it recovered from.

        Opencode retries provider errors (e.g. a stream cut by the model server) inside the
        same session, so an earlier failed message followed by a successful one is not fatal.
        """
        failure = None
        for message in session_messages.get("data", []):
            if AutomaticSolutionGenerator._is_failure_message(message):
                failure = message
            elif AutomaticSolutionGenerator._is_success_message(message):
                failure = None
        return failure

    @staticmethod
    def _is_failure_message(message: dict[str, Any]) -> bool:
        if message.get("finish") == SESSION_FAILURE_FINISH:
            return True
        return message.get("type") == "idle" and message.get("outcome") == SESSION_FAILURE_OUTCOME

    @staticmethod
    def _is_success_message(message: dict[str, Any]) -> bool:
        if message.get("type") == "idle":
            return message.get("outcome") == SESSION_SUCCESS_OUTCOME
        return message.get("type") == "assistant" and message.get("finish") is not None

    @staticmethod
    def _describe_session_failure(failure: dict[str, Any]) -> str:
        error = failure.get("error") or {}
        return str(
            error.get("message")
            or failure.get("outcome")
            or "unknown error"
        )
