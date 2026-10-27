"""
Orchestrator Loop Module

Core orchestration logic for parsing goals, generating tasks, and executing them
sequentially with full state tracking and observability.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
from contextlib import asynccontextmanager

import structlog
from pydantic import BaseModel, Field, validator

logger = structlog.get_logger(__name__)


class TaskStatus(str, Enum):
    """Task execution status states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class GoalStatus(str, Enum):
    """Goal execution status states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Task priority levels (higher = more important)."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class Task:
    """Represents a single task in the orchestration plan."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    action: str = ""  # The action/tool to execute
    params: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)  # Task IDs this depends on
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retries: int = 0
    max_retries: int = 3
    timeout_seconds: float = 300.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert task to dictionary for serialization."""
        data = asdict(self)
        data["status"] = self.status.value
        data["priority"] = self.priority.value
        data["started_at"] = self.started_at.isoformat() if self.started_at else None
        data["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create task from dictionary."""
        data = data.copy()
        data["status"] = TaskStatus(data["status"])
        data["priority"] = TaskPriority(data["priority"])
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        return cls(**data)


@dataclass
class Goal:
    """Represents a high-level goal to be orchestrated."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    context: dict = field(default_factory=dict)
    status: GoalStatus = GoalStatus.PENDING
    tasks: list[Task] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert goal to dictionary for serialization."""
        data = asdict(self)
        data["status"] = self.status.value
        data["tasks"] = [t.to_dict() for t in self.tasks]
        data["created_at"] = self.created_at.isoformat()
        data["started_at"] = self.started_at.isoformat() if self.started_at else None
        data["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Goal":
        """Create goal from dictionary."""
        data = data.copy()
        data["status"] = GoalStatus(data["status"])
        data["tasks"] = [Task.from_dict(t) for t in data.get("tasks", [])]
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        return cls(**data)


class ActionRegistry:
    """Registry for available actions/tools that tasks can execute."""

    def __init__(self):
        self._actions: dict[str, Callable] = {}
        self._action_schemas: dict[str, dict] = {}

    def register(self, name: str, func: Callable, schema: Optional[dict] = None) -> None:
        """Register an action with optional JSON schema for validation."""
        self._actions[name] = func
        if schema:
            self._action_schemas[name] = schema
        logger.debug("action_registered", name=name)

    def unregister(self, name: str) -> None:
        """Unregister an action."""
        self._actions.pop(name, None)
        self._action_schemas.pop(name, None)

    def get(self, name: str) -> Optional[Callable]:
        """Get action by name."""
        return self._actions.get(name)

    def get_schema(self, name: str) -> Optional[dict]:
        """Get action schema by name."""
        return self._action_schemas.get(name)

    def list_actions(self) -> list[str]:
        """List all registered action names."""
        return list(self._actions.keys())

    def validate_params(self, action_name: str, params: dict) -> tuple[bool, Optional[str]]:
        """Validate parameters against action schema if available."""
        schema = self._action_schemas.get(action_name)
        if not schema:
            return True, None
        # Simple validation - in production, use jsonschema library
        required = schema.get("required", [])
        for field_name in required:
            if field_name not in params:
                return False, f"Missing required parameter: {field_name}"
        return True, None


class StateStore:
    """Persistent state storage for goals and tasks."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._goals: dict[str, Goal] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all goals from storage."""
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)
                goal = Goal.from_dict(data)
                self._goals[goal.id] = goal
            except Exception as e:
                logger.warning("failed_to_load_goal", file=str(file_path), error=str(e))

    def save_goal(self, goal: Goal) -> None:
        """Save goal to persistent storage."""
        self._goals[goal.id] = goal
        file_path = self.storage_path / f"{goal.id}.json"
        try:
            with open(file_path, "w") as f:
                json.dump(goal.to_dict(), f, indent=2, default=str)
        except Exception as e:
            logger.error("failed_to_save_goal", goal_id=goal.id, error=str(e))
            raise

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Retrieve goal by ID."""
        return self._goals.get(goal_id)

    def list_goals(self, status: Optional[GoalStatus] = None) -> list[Goal]:
        """List all goals, optionally filtered by status."""
        goals = list(self._goals.values())
        if status:
            goals = [g for g in goals if g.status == status]
        return sorted(goals, key=lambda g: g.created_at, reverse=True)

    def delete_goal(self, goal_id: str) -> bool:
        """Delete goal from storage."""
        if goal_id in self._goals:
            del self._goals[goal_id]
            file_path = self.storage_path / f"{goal_id}.json"
            file_path.unlink(missing_ok=True)
            return True
        return False


class GoalParser:
    """Parses natural language goals into structured task plans."""

    def __init__(self, action_registry: ActionRegistry, llm_client: Optional[Callable] = None):
        self.action_registry = action_registry
        self.llm_client = llm_client

    def parse(self, goal_description: str, context: Optional[dict] = None) -> Goal:
        """Parse a goal description into a Goal with tasks."""
        goal = Goal(description=goal_description, context=context or {})

        if self.llm_client:
            tasks = self._parse_with_llm(goal_description, context)
        else:
            tasks = self._parse_heuristic(goal_description, context)

        goal.tasks = tasks
        return goal

    def _parse_with_llm(self, description: str, context: Optional[dict]) -> list[Task]:
        """Parse goal using LLM (placeholder for actual implementation)."""
        # This would call the LLM to generate a structured plan
        # For now, fall back to heuristic
        logger.info("llm_parsing_not_implemented_falling_back_to_heuristic")
        return self._parse_heuristic(description, context)

    def _parse_heuristic(self, description: str, context: Optional[dict]) -> list[Task]:
        """Heuristic-based parsing for common patterns."""
        tasks = []
        desc_lower = description.lower()
        available_actions = self.action_registry.list_actions()

        # Simple pattern matching for common task types
        if any(kw in desc_lower for kw in ["file", "read", "write", "create", "delete"]):
            if "read" in desc_lower or "load" in desc_lower:
                tasks.append(Task(
                    name="read_file",
                    description="Read file contents",
                    action="read_file",
                    params={"path": context.get("file_path", "")} if context else {}
                ))
            if "write" in desc_lower or "create" in desc_lower or "save" in desc_lower:
                tasks.append(Task(
                    name="write_file",
                    description="Write file contents",
                    action="write_file",
                    params={
                        "path": context.get("file_path", ""),
                        "content": context.get("content", "")
                    } if context else {}
                ))

        if any(kw in desc_lower for kw in ["search", "find", "query", "lookup"]):
            tasks.append(Task(
                name="search",
                description="Search for information",
                action="search",
                params={"query": description} if not context else context
            ))

        if any(kw in desc_lower for kw in ["analyze", "process", "transform", "compute"]):
            tasks.append(Task(
                name="analyze",
                description="Analyze or process data",
                action="analyze",
                params={"data": context.get("data", "")} if context else {}
            ))

        if any(kw in desc_lower for kw in ["api", "request", "call", "fetch"]):
            tasks.append(Task(
                name="api_call",
                description="Make API request",
                action="http_request",
                params=context or {}
            ))

        # If no patterns matched, create a generic task
        if not tasks:
            tasks.append(Task(
                name="execute_goal",
                description=description,
                action="generic_executor",
                params={"goal": description, "context": context or {}}
            ))

        # Set dependencies - sequential by default
        for i, task in enumerate(tasks):
            if i > 0:
                task.dependencies = [tasks[i-1].id]

        return tasks


class TaskExecutor:
    """Executes individual tasks with retry logic and timeout handling."""

    def __init__(
        self,
        action_registry: ActionRegistry,
        max_concurrent: int = 1,
        default_timeout: float = 300.0
    ):
        self.action_registry = action_registry
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def execute(self, task: Task, goal_context: dict) -> Any:
        """Execute a single task with retries and timeout."""
        action = self.action_registry.get(task.action)
        if not action:
            raise ValueError(f"Action not found: {task.action}")

        # Validate parameters
        valid, error = self.action_registry.validate_params(task.action, task.params)
        if not valid:
            raise ValueError(f"Invalid parameters for {task.action}: {error}")

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()

        last_error = None
        for attempt in range(task.max_retries + 1):
            task.retries = attempt
            try:
                logger.info("task_executing", task_id=task.id, action=task.action, attempt=attempt + 1)

                # Merge goal context with task params
                merged_params = {**goal_context, **task.params}

                # Execute with timeout
                if asyncio.iscoroutinefunction(action):
                    result = await asyncio.wait_for(
                        action(**merged_params),
                        timeout=task.timeout_seconds
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(action, **merged_params),
                        timeout=task.timeout_seconds
                    )

                task.result = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                logger.info("task_completed", task_id=task.id, duration_ms=self._duration_ms(task))
                return result

            except asyncio.TimeoutError:
                last_error = f"Task timed out after {task.timeout_seconds}s"
                logger.warning("task_timeout", task_id=task.id, timeout=task.timeout_seconds)
            except Exception as e:
                last_error = str(e)
                logger.warning("task_error", task_id=task.id, error=last_error, attempt=attempt + 1)

            if attempt < task.max_retries:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info("task_retrying", task_id=task.id, wait_seconds=wait_time)
                await asyncio.sleep(wait_time)

        # All retries exhausted
        task.status = TaskStatus.FAILED
        task.error = last_error
        task.completed_at = datetime.utcnow()
        logger.error("task_failed", task_id=task.id, error=last_error)
        raise RuntimeError(f"Task {task.name} failed after {task.max_retries + 1} attempts: {last_error}")

    def _duration_ms(self, task: Task) -> float:
        """Calculate task duration in milliseconds."""
        if task.started_at and task.completed_at:
            return (task.completed_at - task.started_at).total_seconds() * 1000
        return 0.0


class OrchestratorLoop:
    """
    Main orchestration loop that manages goal execution.

    Handles:
    - Goal parsing and task generation
    - Dependency resolution and topological ordering
    - Sequential/parallel task execution
    - State persistence and recovery
    - Progress tracking and callbacks
    """

    def __init__(
        self,
        action_registry: ActionRegistry,
        state_store: StateStore,
        goal_parser: GoalParser,
        task_executor: TaskExecutor,
        progress_callback: Optional[Callable[[Goal, Task], None]] = None
    ):
        self.action_registry = action_registry
        self.state_store = state_store
        self.goal_parser = goal_parser
        self.task_executor = task_executor
        self.progress_callback = progress_callback
        self._running_goals: dict[str, asyncio.Task] = {}
        self._shutdown = False

    async def submit_goal(self, description: str, context: Optional[dict] = None) -> Goal:
        """Submit a new goal for execution."""
        goal = self.goal_parser.parse(description, context)
        self.state_store.save_goal(goal)
        logger.info("goal_submitted", goal_id=goal.id, task_count=len(goal.tasks))
        return goal

    async def execute_goal(self, goal_id: str) -> Goal:
        """Execute a goal by ID."""
        goal = self.state_store.get_goal(goal_id)
        if not goal:
            raise ValueError(f"Goal not found: {goal_id}")

        if goal.status in (GoalStatus.IN_PROGRESS, GoalStatus.COMPLETED):
            logger.warning("goal_already_executed", goal_id=goal_id, status=goal.status.value)
            return goal

        goal.status = GoalStatus.IN_PROGRESS
        goal.started_at = datetime.utcnow()
        self.state_store.save_goal(goal)

        try:
            await self._execute_goal_tasks(goal)
            goal.status = GoalStatus.COMPLETED
            goal.completed_at = datetime.utcnow()
            logger.info("goal_completed", goal_id=goal.id, duration_ms=self._goal_duration_ms(goal))
        except Exception as e:
            goal.status = GoalStatus.FAILED
            goal.error = str(e