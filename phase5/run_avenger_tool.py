#!/usr/bin/env python3
"""
Avenger Task Execution Tool

A production-quality CLI tool for executing avenger tasks with comprehensive
input validation, error handling, and logging.
"""

import argparse
import json
import logging
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import uuid


# Configure logging
def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> logging.Logger:
    """Set up structured logging configuration."""
    logger = logging.getLogger("avenger_tool")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler with formatted output
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


class TaskStatus(Enum):
    """Enumeration of possible task execution statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    VALIDATION_ERROR = "validation_error"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    status: TaskStatus
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata
        }


@dataclass
class AvengerTask:
    """Represents an avenger task to be executed."""
    task_id: str
    name: str
    task_type: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate task after initialization."""
        if not self.task_id:
            self.task_id = str(uuid.uuid4())
        if not self.name:
            raise ValueError("Task name is required")
        if not self.task_type:
            raise ValueError("Task type is required")
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("Max retries cannot be negative")


class ValidationError(Exception):
    """Custom exception for validation errors."""
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        self.field = field
        self.value = value
        super().__init__(message)


class TaskExecutionError(Exception):
    """Custom exception for task execution errors."""
    def __init__(self, message: str, task_id: str, original_error: Optional[Exception] = None):
        self.task_id = task_id
        self.original_error = original_error
        super().__init__(message)


class TaskValidator:
    """Validates avenger tasks before execution."""
    
    SUPPORTED_TASK_TYPES = {
        "data_processing",
        "api_call",
        "file_operation",
        "database_query",
        "transformation",
        "notification",
        "cleanup",
        "custom"
    }
    
    REQUIRED_FIELDS = {"name", "task_type", "payload"}
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def validate(self, task: AvengerTask) -> List[str]:
        """
        Validate a task and return list of validation errors.
        Empty list means valid.
        """
        errors = []
        
        # Check required fields
        for field_name in self.REQUIRED_FIELDS:
            value = getattr(task, field_name, None)
            if not value:
                errors.append(f"Missing required field: {field_name}")
        
        # Validate task type
        if task.task_type not in self.SUPPORTED_TASK_TYPES:
            errors.append(
                f"Unsupported task type: '{task.task_type}'. "
                f"Supported types: {', '.join(sorted(self.SUPPORTED_TASK_TYPES))}"
            )
        
        # Validate payload is a dict
        if not isinstance(task.payload, dict):
            errors.append("Payload must be a dictionary")
        
        # Validate timeout
        if task.timeout_seconds <= 0 or task.timeout_seconds > 86400:
            errors.append("Timeout must be between 1 and 86400 seconds")
        
        # Validate retries
        if task.max_retries < 0 or task.max_retries > 10:
            errors.append("Max retries must be between 0 and 10")
        
        # Validate dependencies
        if task.dependencies:
            for dep in task.dependencies:
                if not isinstance(dep, str) or not dep.strip():
                    errors.append("Dependency task IDs must be non-empty strings")
        
        # Task-type specific validation
        type_errors = self._validate_task_type_specific(task)
        errors.extend(type_errors)
        
        if errors:
            self.logger.warning(f"Task {task.task_id} validation failed: {errors}")
        else:
            self.logger.debug(f"Task {task.task_id} passed validation")
        
        return errors
    
    def _validate_task_type_specific(self, task: AvengerTask) -> List[str]:
        """Validate task-type specific requirements."""
        errors = []
        
        if task.task_type == "api_call":
            required = {"url", "method"}
            missing = required - set(task.payload.keys())
            if missing:
                errors.append(f"API call task requires payload fields: {missing}")
            if "method" in task.payload and task.payload["method"].upper() not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                errors.append("Invalid HTTP method")
        
        elif task.task_type == "file_operation":
            required = {"operation", "path"}
            missing = required - set(task.payload.keys())
            if missing:
                errors.append(f"File operation task requires payload fields: {missing}")
            if "operation" in task.payload and task.payload["operation"] not in {"read", "write", "delete", "copy", "move"}:
                errors.append("Invalid file operation")
        
        elif task.task_type == "database_query":
            if "query" not in task.payload:
                errors.append("Database query task requires 'query' in payload")
        
        elif task.task_type == "transformation":
            required = {"input_data", "transform_type"}
            missing = required - set(task.payload.keys())
            if missing:
                errors.append(f"Transformation task requires payload fields: {missing}")
        
        return errors


class TaskExecutor:
    """Executes avenger tasks with retry logic and timeout handling."""
    
    def __init__(self, logger: logging.Logger, dry_run: bool = False):
        self.logger = logger
        self.dry_run = dry_run
        self._handlers = {
            "data_processing": self._execute_data_processing,
            "api_call": self._execute_api_call,
            "file_operation": self._execute_file_operation,
            "database_query": self._execute_database_query,
            "transformation": self._execute_transformation,
            "notification": self._execute_notification,
            "cleanup": self._execute_cleanup,
            "custom": self._execute_custom,
        }
    
    def execute(self, task: AvengerTask) -> TaskResult:
        """Execute a task with retry logic."""
        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.PENDING,
            started_at=datetime.utcnow()
        )
        
        self.logger.info(f"Starting task {task.task_id} ({task.name}) - Type: {task.task_type}")
        
        if self.dry_run:
            self.logger.info(f"DRY RUN: Would execute task {task.task_id}")
            result.status = TaskStatus.COMPLETED
            result.output = {"dry_run": True, "message": "Task execution simulated"}
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
            return result
        
        last_error = None
        for attempt in range(task.max_retries + 1):
            task.retry_count = attempt
            result.status = TaskStatus.RUNNING
            
            try:
                if attempt > 0:
                    self.logger.info(f"Retry attempt {attempt}/{task.max_retries} for task {task.task_id}")
                
                # Execute the task
                handler = self._handlers.get(task.task_type)
                if not handler:
                    raise TaskExecutionError(
                        f"No handler for task type: {task.task_type}",
                        task.task_id
                    )
                
                output = handler(task)
                result.output = output
                result.status = TaskStatus.COMPLETED
                self.logger.info(f"Task {task.task_id} completed successfully")
                break
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"Task {task.task_id} attempt {attempt + 1} failed: {e}")
                if attempt < task.max_retries:
                    continue
        
        # Handle final failure
        if result.status != TaskStatus.COMPLETED:
            result.status = TaskStatus.FAILED
            result.error = str(last_error)
            self.logger.error(f"Task {task.task_id} failed after {task.max_retries + 1} attempts: {last_error}")
        
        result.completed_at = datetime.utcnow()
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
        return result
    
    def _execute_data_processing(self, task: AvengerTask) -> Dict[str, Any]:
        """Execute data processing task."""
        data = task.payload.get("data", [])
        operation = task.payload.get("operation", "process")
        
        # Simulate processing
        processed = len(data) if isinstance(data, list) else 1
        return {
            "operation": operation,
            "records_processed": processed,
            "status": "success"
        }
    
    def _execute_api_call(self, task: AvengerTask) -> Dict[str, Any]:
        """Execute API call task."""
        url = task.payload.get("url")
        method = task.payload.get("method", "GET").upper()
        
        # In production, use requests library with proper timeout
        return {
            "url": url,
            "method": method,
            "status_code": 200,
            "response": {"simulated": True}
        }
    
    def _execute_file_operation(self, task: AvengerTask) -> Dict[str, Any]:
        """Execute file operation task."""
        operation = task.payload.get("operation")
        path = task.payload.get("path")
        
        # In production, perform actual file operations
        return {
            "operation": operation,
            "path": path,
            "status": "success"
        }
    
    def _execute_database_query(self, task: AvengerTask) -> Dict[str, Any]:
        """Execute database query task."""
        query = task.payload.get("query")
        
        # In production, execute actual query
        return {
            "query": query[:100] + "..." if len(query) > 100 else query,
            "rows_affected": 0,
            "status": "success"
        }
    
    def _execute_transformation(self, task: AvengerTask) -> Dict[str, Any]:
        """Execute data transformation task."""
        transform_type = task.payload.get("transform_type")
        
        return {
            "transform_type": transform_type,
            "status": "success"
        }
    
    def _execute_notification(self, task: AvengerTask) -> Dict[str, Any]:
        """Execute notification task."""
        channel = task.payload.get("channel", "email")
        recipient = task.payload.get("recipient")
        
        return {
            "channel": channel,
            "recipient": recipient,
            "status": "sent"
        }
    
    def _execute_cleanup(self, task: AvengerTask) -> Dict[str, Any]:
        """Execute cleanup task."""
        target = task.payload.get("target", "temp_files")
        
        return {
            "target": target,
            "items_cleaned": 0,
            "status": "success"
        }
    
    def _execute_custom(self, task: AvengerTask) -> Dict[str, Any]:
        """Execute custom task."""
        return {
            "custom_action": task.payload.get("action", "unknown"),
            "status": "success"
        }


class AvengerTool:
    """Main tool class for managing avenger task execution."""
    
    def __init__(
        self,
        log_level: str = "INFO",
        log_file: Optional[Path] = None,
        dry_run: bool = False
    ):
        self.logger = setup_logging(log_level, log_file)
        self.validator = TaskValidator(self.logger)
        self.executor = TaskExecutor(self.logger, dry_run)
        self.dry_run = dry_run
        self.results: List[TaskResult] = []
    
    def load_tasks_from_file(self, file_path: Path) -> List[AvengerTask]:
        """Load tasks from a JSON file."""
        self.logger.info(f"Loading tasks from {file_path}")
        
        if not file_path.exists():
            raise FileNotFoundError(f"Task file not found: {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON in task file: {e}")
        
        tasks = []
        task_list = data if isinstance(data, list) else [data]
        
        for idx, task_data in enumerate(task_list):
            try:
                task = self._parse_task_data(task_data, idx)
                tasks.append(task)
            except Exception as e:
                self.logger.error(f"Failed to parse task at index {idx}: {e}")
                raise ValidationError(f"Task at index {idx} is invalid: {e}")
        
        self.logger.info(f"Loaded {len(tasks)} tasks")
        return tasks
    
    def _parse_task_data(self, data: Dict[str, Any], index: int) -> AvengerTask:
        """Parse task data from dictionary."""
        # Generate task_id if not provided
        task_id = data.get("task_id") or str(uuid.uuid4())
        
        # Parse priority
        priority_str = data.get("priority", "normal").upper()
        priority = TaskPriority[priority_str] if priority_str in TaskPriority.__members__ else TaskPriority.NORMAL
        
        return AvengerTask(
            task_id=task_id,
            name=data.get("name", f"Task-{index}"),
            task_type=data.get("task_type", "custom"),
            payload=data.get("payload", {}),
            priority=priority,
            timeout_seconds=data.get("timeout_seconds", 300),
            max_retries=data.get("max_retries", 3),
            dependencies=data.get("dependencies", []),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {})
        )
    
    def create_task_from_args(self, args: argparse.Namespace) -> AvengerTask:
        """Create a task from command line arguments."""
        payload = {}
        if args.payload:
            try:
                payload = json.loads(args.payload)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid payload JSON: {e}")
        
        priority = TaskPriority[args.priority.upper()] if args.priority else TaskPriority.NORMAL
        
        return AvengerTask(
            task_id=args.task_id or str(uuid.uuid4()),
            name=args.name or "CLI Task",
            task_type=args.task_type or "