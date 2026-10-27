import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


class AvengerStatus(str, Enum):
    """Enumeration of possible avenger execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class AvengerPriority(str, Enum):
    """Priority levels for avenger executions."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AvengerExecution:
    """Represents a single avenger execution with full metadata."""
    execution_id: str
    avenger_id: str
    avenger_name: str
    mission_id: str
    status: AvengerStatus
    priority: AvengerPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    current_step: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """Convert execution to dictionary for serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        data['created_at'] = self.created_at.isoformat()
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        # Convert enum values to strings
        data['status'] = self.status.value
        data['priority'] = self.priority.value
        # Convert set to list
        data['tags'] = list(self.tags)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AvengerExecution':
        """Create execution from dictionary."""
        # Convert string dates back to datetime
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('started_at'):
            data['started_at'] = datetime.fromisoformat(data['started_at'])
        if data.get('completed_at'):
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        # Convert enum strings back to enums
        data['status'] = AvengerStatus(data['status'])
        data['priority'] = AvengerPriority(data['priority'])
        # Convert list back to set
        data['tags'] = set(data.get('tags', []))
        return cls(**data)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return None

    @property
    def is_terminal(self) -> bool:
        """Check if execution is in a terminal state."""
        return self.status in {AvengerStatus.COMPLETED, AvengerStatus.FAILED, 
                               AvengerStatus.CANCELLED, AvengerStatus.TIMEOUT}


class AvengerStatusStore:
    """
    Thread-safe storage for avenger executions with persistence support.
    
    Uses a combination of in-memory storage with optional file-based persistence
    for durability across restarts.
    """
    
    def __init__(self, persistence_path: Optional[Path] = None, 
                 auto_save_interval: float = 30.0):
        """
        Initialize the status store.
        
        Args:
            persistence_path: Optional path to JSON file for persistence
            auto_save_interval: Seconds between auto-saves (0 to disable)
        """
        self._executions: Dict[str, AvengerExecution] = {}
        self._lock = asyncio.Lock()
        self._persistence_path = persistence_path
        self._auto_save_interval = auto_save_interval
        self._save_task: Optional[asyncio.Task] = None
        self._indexes: Dict[str, Set[str]] = {
            'by_avenger': {},
            'by_mission': {},
            'by_status': {},
            'by_priority': {}
        }

    async def start(self) -> None:
        """Start the store and load any persisted data."""
        await self._load()
        if self._auto_save_interval > 0:
            self._save_task = asyncio.create_task(self._auto_save_loop())

    async def stop(self) -> None:
        """Stop the store and persist final state."""
        if self._save_task:
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
        await self._save()

    async def _load(self) -> None:
        """Load executions from persistence file."""
        if not self._persistence_path or not self._persistence_path.exists():
            return
        
        try:
            async with self._lock:
                content = await asyncio.to_thread(self._persistence_path.read_text)
                data = json.loads(content)
                for exec_data in data.get('executions', []):
                    execution = AvengerExecution.from_dict(exec_data)
                    self._executions[execution.execution_id] = execution
                    self._update_indexes(execution)
            logger.info(f"Loaded {len(self._executions)} executions from {self._persistence_path}")
        except Exception as e:
            logger.error(f"Failed to load executions: {e}")

    async def _save(self) -> None:
        """Save executions to persistence file."""
        if not self._persistence_path:
            return
            
        try:
            async with self._lock:
                data = {
                    'executions': [exec.to_dict() for exec in self._executions.values()],
                    'saved_at': datetime.now(timezone.utc).isoformat()
                }
                # Write atomically using temp file
                temp_path = self._persistence_path.with_suffix('.tmp')
                await asyncio.to_thread(temp_path.write_text, json.dumps(data, indent=2))
                await asyncio.to_thread(temp_path.replace, self._persistence_path)
        except Exception as e:
            logger.error(f"Failed to save executions: {e}")

    async def _auto_save_loop(self) -> None:
        """Background task for periodic auto-saving."""
        while True:
            try:
                await asyncio.sleep(self._auto_save_interval)
                await self._save()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-save error: {e}")

    def _update_indexes(self, execution: AvengerExecution) -> None:
        """Update internal indexes for fast queries."""
        # By avenger
        self._indexes['by_avenger'].setdefault(execution.avenger_id, set()).add(execution.execution_id)
        # By mission
        self._indexes['by_mission'].setdefault(execution.mission_id, set()).add(execution.execution_id)
        # By status
        self._indexes['by_status'].setdefault(execution.status.value, set()).add(execution.execution_id)
        # By priority
        self._indexes['by_priority'].setdefault(execution.priority.value, set()).add(execution.execution_id)

    def _remove_from_indexes(self, execution: AvengerExecution) -> None:
        """Remove execution from all indexes."""
        for index in self._indexes.values():
            for key_set in index.values():
                key_set.discard(execution.execution_id)

    async def create_execution(self, 
                              avenger_id: str,
                              avenger_name: str,
                              mission_id: str,
                              priority: AvengerPriority = AvengerPriority.NORMAL,
                              metadata: Optional[Dict[str, Any]] = None,
                              tags: Optional[Set[str]] = None) -> AvengerExecution:
        """
        Create a new avenger execution record.
        
        Args:
            avenger_id: Unique identifier for the avenger
            avenger_name: Human-readable name of the avenger
            mission_id: Mission this execution belongs to
            priority: Execution priority level
            metadata: Additional metadata
            tags: Optional tags for categorization
            
        Returns:
            The created AvengerExecution
        """
        execution = AvengerExecution(
            execution_id=str(uuid4()),
            avenger_id=avenger_id,
            avenger_name=avenger_name,
            mission_id=mission_id,
            status=AvengerStatus.PENDING,
            priority=priority,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {},
            tags=tags or set()
        )
        
        async with self._lock:
            self._executions[execution.execution_id] = execution
            self._update_indexes(execution)
        
        logger.info(f"Created execution {execution.execution_id} for avenger {avenger_id}")
        return execution

    async def update_status(self, 
                           execution_id: str, 
                           status: AvengerStatus,
                           progress: Optional[float] = None,
                           current_step: Optional[str] = None,
                           error_message: Optional[str] = None) -> Optional[AvengerExecution]:
        """
        Update the status of an execution.
        
        Args:
            execution_id: ID of execution to update
            status: New status
            progress: Optional progress percentage (0-100)
            current_step: Optional current step description
            error_message: Optional error message if failed
            
        Returns:
            Updated execution or None if not found
        """
        async with self._lock:
            execution = self._executions.get(execution_id)
            if not execution:
                return None
            
            # Remove from old status index
            self._indexes['by_status'][execution.status.value].discard(execution_id)
            
            # Update fields
            old_status = execution.status
            execution.status = status
            
            if status == AvengerStatus.RUNNING and not execution.started_at:
                execution.started_at = datetime.now(timezone.utc)
            elif status.is_terminal() and not execution.completed_at:
                execution.completed_at = datetime.now(timezone.utc)
            
            if progress is not None:
                execution.progress = max(0.0, min(100.0, progress))
            if current_step is not None:
                execution.current_step = current_step
            if error_message is not None:
                execution.error_message = error_message
            
            # Add to new status index
            self._indexes['by_status'].setdefault(status.value, set()).add(execution_id)
            
            logger.debug(f"Execution {execution_id} status: {old_status.value} -> {status.value}")
            return execution

    async def update_progress(self, 
                             execution_id: str,
                             progress: float,
                             current_step: str,
                             completed_steps: Optional[int] = None) -> Optional[AvengerExecution]:
        """Update execution progress."""
        async with self._lock:
            execution = self._executions.get(execution_id)
            if not execution:
                return None
            
            execution.progress = max(0.0, min(100.0, progress))
            execution.current_step = current_step
            if completed_steps is not None:
                execution.completed_steps = completed_steps
            
            return execution

    async def complete_execution(self, 
                                execution_id: str,
                                result: Optional[Dict[str, Any]] = None) -> Optional[AvengerExecution]:
        """Mark execution as completed with optional result."""
        return await self.update_status(
            execution_id, 
            AvengerStatus.COMPLETED,
            progress=100.0,
            current_step="Completed"
        )

    async def fail_execution(self, 
                            execution_id: str,
                            error_message: str) -> Optional[AvengerExecution]:
        """Mark execution as failed with error message."""
        return await self.update_status(
            execution_id,
            AvengerStatus.FAILED,
            error_message=error_message
        )

    async def cancel_execution(self, execution_id: str) -> Optional[AvengerExecution]:
        """Cancel a running execution."""
        async with self._lock:
            execution = self._executions.get(execution_id)
            if not execution or execution.is_terminal:
                return None
        return await self.update_status(execution_id, AvengerStatus.CANCELLED)

    async def get_execution(self, execution_id: str) -> Optional[AvengerExecution]:
        """Get execution by ID."""
        async with self._lock:
            return self._executions.get(execution_id)

    async def get_executions(self, 
                            avenger_id: Optional[str] = None,
                            mission_id: Optional[str] = None,
                            status: Optional[AvengerStatus] = None,
                            priority: Optional[AvengerPriority] = None,
                            tags: Optional[Set[str]] = None,
                            limit: int = 100,
                            offset: int = 0) -> List[AvengerExecution]:
        """
        Query executions with filters.
        
        Args:
            avenger_id: Filter by avenger ID
            mission_id: Filter by mission ID
            status: Filter by status
            priority: Filter by priority
            tags: Filter by tags (must have all specified tags)
            limit: Maximum results to return
            offset: Pagination offset
            
        Returns:
            List of matching executions
        """
        async with self._lock:
            # Start with all executions or filtered by index
            if avenger_id:
                candidate_ids = self._indexes['by_avenger'].get(avenger_id, set())
            elif mission_id:
                candidate_ids = self._indexes['by_mission'].get(mission_id, set())
            elif status:
                candidate_ids = self._indexes['by_status'].get(status.value, set())
            elif priority:
                candidate_ids = self._indexes['by_priority'].get(priority.value, set())
            else:
                candidate_ids = set(self._executions.keys())
            
            # Apply additional filters
            results = []
            for exec_id in candidate_ids:
                execution = self._executions.get(exec_id)
                if not execution:
                    continue
                    
                if mission_id and execution.mission_id != mission_id:
                    continue
                if status and execution.status != status:
                    continue
                if priority and execution.priority != priority:
                    continue
                if tags and not tags.issubset(execution.tags):
                    continue
                    
                results.append(execution)
            
            # Sort by creation time (newest first)
            results.sort(key=lambda e: e.created_at, reverse=True)
            
            # Apply pagination
            return results[offset:offset + limit]

    async def get_running_executions(self) -> List[AvengerExecution]:
        """Get all currently running executions."""
        return await self.get_executions(status=AvengerStatus.RUNNING)

    async def get_pending_executions(self) -> List[AvengerExecution]:
        """Get all pending executions."""
        return await self.get_executions(status=AvengerStatus.PENDING)

    async def get_failed_executions(self, mission_id: Optional[str] = None) -> List[AvengerExecution]:
        """Get all failed executions, optionally filtered by mission."""
        return await self.get_executions(mission_id=mission_id, status=AvengerStatus.FAILED)

    async def get_avenger_summary(self, avenger_id: str) -> Dict[str, Any]:
        """Get summary statistics for an avenger."""
        async with self._lock:
            exec_ids = self._indexes['by_avenger'].get(avenger_id, set())
            executions = [self._executions[eid] for eid in exec_ids if eid in self._executions]
            
            if not executions:
                return {
                    'avenger_id': avenger_id,
                    'total_executions': 0,
                    'status_counts': {},
                    'success_rate': 0.0,
                    'avg_duration_seconds': None
                }
            
            status_counts = {}
            completed_durations = []
            
            for exec in executions:
                status_counts[exec.status.value] = status_counts.get(exec.status.value, 0) + 1
                if exec.duration_seconds is not None:
                    completed_durations.append(exec.duration_seconds)
            
            completed = status_counts.get('completed', 0)
            total = len(executions)
            
            return {
                'avenger_id': avenger_id,
                'total_executions': total,
                'status_counts': status_counts,
                'success_rate': completed / total if total > 0 else 0.0,
                'avg_duration_seconds': sum(completed_durations) / len(completed_durations) if completed_durations else None,
                'last_execution': max(executions, key=lambda e: e.created_at).to_dict() if executions else None
            }

    async def get_mission_summary(self, mission_id: str) -> Dict[str, Any]:
        """Get summary statistics for a mission."""
        async with self._lock