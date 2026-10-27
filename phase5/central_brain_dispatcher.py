import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type
import weakref

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a task in the system."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """Priority levels for tasks."""
    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 200


class AvengerStatus(Enum):
    """Status of an avenger in the system."""
    IDLE = "idle"
    BUSY = "busy"
    STARTING = "starting"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    UNHEALTHY = "unhealthy"


@dataclass
class Task:
    """Represents a task to be executed by an avenger."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    required_capabilities: Set[str] = field(default_factory=set)
    assigned_avenger_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: float = 300.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: "Task") -> bool:
        """Enable priority queue ordering."""
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        return self.created_at < other.created_at


@dataclass
class AvengerInfo:
    """Information about a registered avenger."""
    id: str
    name: str
    capabilities: Set[str]
    status: AvengerStatus = AvengerStatus.IDLE
    current_task_id: Optional[str] = None
    max_concurrent_tasks: int = 1
    active_task_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AvengerBase(ABC):
    """Base class for all avengers (workers)."""
    
    def __init__(self, avenger_id: str, name: str, capabilities: Set[str], 
                 max_concurrent_tasks: int = 1):
        self.info = AvengerInfo(
            id=avenger_id,
            name=name,
            capabilities=capabilities,
            max_concurrent_tasks=max_concurrent_tasks
        )
        self._dispatcher_ref: Optional[weakref.ref] = None
        self._shutdown_event = asyncio.Event()
    
    def set_dispatcher(self, dispatcher: "CentralBrainDispatcher") -> None:
        """Set reference to dispatcher for callbacks."""
        self._dispatcher_ref = weakref.ref(dispatcher)
    
    @property
    def dispatcher(self) -> Optional["CentralBrainDispatcher"]:
        """Get dispatcher instance if still alive."""
        if self._dispatcher_ref:
            return self._dispatcher_ref()
        return None
    
    @abstractmethod
    async def execute_task(self, task: Task) -> Any:
        """Execute a task and return result."""
        pass
    
    async def on_task_assigned(self, task: Task) -> None:
        """Called when a task is assigned to this avenger."""
        pass
    
    async def on_task_completed(self, task: Task, result: Any) -> None:
        """Called when a task completes successfully."""
        pass
    
    async def on_task_failed(self, task: Task, error: Exception) -> None:
        """Called when a task fails."""
        pass
    
    async def start(self) -> None:
        """Start the avenger."""
        self.info.status = AvengerStatus.STARTING
        logger.info(f"Avenger {self.info.name} ({self.info.id}) starting")
        self.info.status = AvengerStatus.IDLE
    
    async def stop(self) -> None:
        """Stop the avenger gracefully."""
        self.info.status = AvengerStatus.STOPPING
        logger.info(f"Avenger {self.info.name} ({self.info.id}) stopping")
        self._shutdown_event.set()
        self.info.status = AvengerStatus.STOPPED
    
    async def health_check(self) -> bool:
        """Check if avenger is healthy."""
        return self.info.status not in (AvengerStatus.ERROR, AvengerStatus.UNHEALTHY, AvengerStatus.STOPPED)


class CentralBrainDispatcher:
    """
    Central dispatcher that routes tasks to avengers, manages their lifecycle,
    and coordinates task delivery.
    """
    
    def __init__(
        self,
        max_queue_size: int = 10000,
        health_check_interval: float = 30.0,
        task_timeout_grace: float = 10.0,
        enable_metrics: bool = True
    ):
        self.max_queue_size = max_queue_size
        self.health_check_interval = health_check_interval
        self.task_timeout_grace = task_timeout_grace
        self.enable_metrics = enable_metrics
        
        # Task management
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._tasks: Dict[str, Task] = {}
        self._task_results: Dict[str, Any] = {}
        self._task_futures: Dict[str, asyncio.Future] = {}
        
        # Avenger management
        self._avengers: Dict[str, AvengerBase] = {}
        self._avenger_capabilities: Dict[str, Set[str]] = defaultdict(set)
        self._capability_to_avengers: Dict[str, Set[str]] = defaultdict(set)
        
        # Concurrency control
        self._avenger_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._dispatch_lock = asyncio.Lock()
        
        # Background tasks
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._timeout_monitor_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Metrics
        self._metrics = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "tasks_cancelled": 0,
            "avengers_registered": 0,
            "avengers_unregistered": 0,
        }
        self._metrics_lock = asyncio.Lock()
        
        # Callbacks
        self._task_submitted_callbacks: List[Callable[[Task], Any]] = []
        self._task_completed_callbacks: List[Callable[[Task], Any]] = []
        self._task_failed_callbacks: List[Callable[[Task, Exception], Any]] = []
        self._avenger_registered_callbacks: List[Callable[[AvengerBase], Any]] = []
        self._avenger_unregistered_callbacks: List[Callable[[str], Any]] = []
    
    async def start(self) -> None:
        """Start the dispatcher background tasks."""
        if self._dispatcher_task is not None:
            logger.warning("Dispatcher already started")
            return
        
        logger.info("Starting Central Brain Dispatcher")
        self._shutdown_event.clear()
        
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop(), name="dispatcher-loop")
        self._health_check_task = asyncio.create_task(self._health_check_loop(), name="health-check-loop")
        self._timeout_monitor_task = asyncio.create_task(self._timeout_monitor_loop(), name="timeout-monitor-loop")
        
        logger.info("Central Brain Dispatcher started")
    
    async def stop(self, graceful: bool = True, timeout: float = 30.0) -> None:
        """Stop the dispatcher and all avengers."""
        logger.info("Stopping Central Brain Dispatcher")
        self._shutdown_event.set()
        
        # Stop accepting new tasks
        if graceful:
            # Wait for queue to drain with timeout
            try:
                await asyncio.wait_for(self._wait_for_queue_empty(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Queue not empty after {timeout}s, forcing shutdown")
        
        # Cancel background tasks
        for task in [self._dispatcher_task, self._health_check_task, self._timeout_monitor_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Stop all avengers
        await self._stop_all_avengers(graceful, timeout)
        
        logger.info("Central Brain Dispatcher stopped")
    
    async def _wait_for_queue_empty(self) -> None:
        """Wait for task queue to become empty."""
        while not self._task_queue.empty():
            await asyncio.sleep(0.1)
    
    async def _stop_all_avengers(self, graceful: bool, timeout: float) -> None:
        """Stop all registered avengers."""
        stop_tasks = []
        for avenger in self._avengers.values():
            if graceful:
                stop_tasks.append(asyncio.create_task(avenger.stop()))
            else:
                avenger.info.status = AvengerStatus.STOPPED
        
        if stop_tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*stop_tasks, return_exceptions=True), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Some avengers did not stop gracefully")
    
    # =========================================================================
    # Avenger Registration & Management
    # =========================================================================
    
    async def register_avenger(self, avenger: AvengerBase) -> None:
        """Register an avenger with the dispatcher."""
        async with self._dispatch_lock:
            if avenger.info.id in self._avengers:
                raise ValueError(f"Avenger with id {avenger.info.id} already registered")
            
            avenger.set_dispatcher(self)
            await avenger.start()
            
            self._avengers[avenger.info.id] = avenger
            self._avenger_semaphores[avenger.info.id] = asyncio.Semaphore(avenger.info.max_concurrent_tasks)
            
            # Update capability indexes
            for cap in avenger.info.capabilities:
                self._capability_to_avengers[cap].add(avenger.info.id)
            
            self._avenger_capabilities[avenger.info.id] = avenger.info.capabilities.copy()
            
            async with self._metrics_lock:
                self._metrics["avengers_registered"] += 1
            
            logger.info(f"Registered avenger: {avenger.info.name} ({avenger.info.id}) with capabilities: {avenger.info.capabilities}")
            
            # Notify callbacks
            for callback in self._avenger_registered_callbacks:
                try:
                    await self._safe_call(callback, avenger)
                except Exception as e:
                    logger.error(f"Error in avenger registered callback: {e}")
    
    async def unregister_avenger(self, avenger_id: str, graceful: bool = True) -> bool:
        """Unregister an avenger from the dispatcher."""
        async with self._dispatch_lock:
            avenger = self._avengers.pop(avenger_id, None)
            if not avenger:
                return False
            
            # Remove from capability indexes
            for cap in avenger.info.capabilities:
                self._capability_to_avengers[cap].discard(avenger_id)
            self._avenger_capabilities.pop(avenger_id, None)
            self._avenger_semaphores.pop(avenger_id, None)
            
            if graceful:
                await avenger.stop()
            
            async with self._metrics_lock:
                self._metrics["avengers_unregistered"] += 1
            
            logger.info(f"Unregistered avenger: {avenger.info.name} ({avenger_id})")
            
            # Notify callbacks
            for callback in self._avenger_unregistered_callbacks:
                try:
                    await self._safe_call(callback, avenger_id)
                except Exception as e:
                    logger.error(f"Error in avenger unregistered callback: {e}")
            
            return True
    
    def get_avenger(self, avenger_id: str) -> Optional[AvengerBase]:
        """Get an avenger by ID."""
        return self._avengers.get(avenger_id)
    
    def get_avengers_by_capability(self, capability: str) -> List[AvengerBase]:
        """Get all avengers that have a specific capability."""
        avenger_ids = self._capability_to_avengers.get(capability, set())
        return [self._avengers[aid] for aid in avenger_ids if aid in self._avengers]
    
    def get_available_avengers(self, required_capabilities: Set[str]) -> List[AvengerBase]:
        """Get avengers that have all required capabilities and are available."""
        if not required_capabilities:
            # If no capabilities required, return all idle avengers
            candidates = set(self._avengers.keys())
        else:
            # Intersect avengers for each capability
            candidates = None
            for cap in required_capabilities:
                cap_avengers = self._capability_to_avengers.get(cap, set())
                if candidates is None:
                    candidates = cap_avengers.copy()
                else:
                    candidates &= cap_avengers
            
            if candidates is None:
                candidates = set()
        
        # Filter for available avengers
        available = []
        for avenger_id in candidates:
            avenger = self._avengers.get(avenger_id)
            if avenger and self._is_avenger_available(avenger):
                available.append(avenger)
        
        # Sort by load (least busy first)
        available.sort(key=lambda a: a.info.active_task_count / a.info.max_concurrent_tasks)
        return available
    
    def _is_avenger_available(self, avenger: AvengerBase) -> bool:
        """Check if an avenger can accept more tasks."""
        return (
            avenger.info.status == AvengerStatus.IDLE and
            avenger.info.active_task_count < avenger.info.max_concurrent_tasks
        )
    
    # =========================================================================
    # Task Submission & Management
    # =========================================================================
    
    async def submit_task(
        self,
        name: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        required_capabilities: Optional[Set[str]] = None,
        max_retries: int = 3,
        timeout_seconds: float = 300.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Submit a task for execution."""
        task = Task(
            name=name,
            payload=payload,
            priority=priority,
            required_capabilities=required_capabilities or set(),
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            metadata=metadata or {}
        )
        
        # Check queue capacity
        if self._task_queue.full():
            raise RuntimeError("Task queue is full")
        
        self._tasks[task.id] = task
        await self._task_queue.put(task)
        
        async with self._metrics_lock:
            self._metrics["tasks_submitted"] += 1
        
        logger.debug(f"Submitted task: {task.name} ({task.id}) with priority {priority.name}")
        
        # Notify callbacks
        for callback in self._task_submitted_callbacks:
            try:
                await self._safe_call(callback, task)
            except Exception as e:
                logger.error(f"Error in task submitted callback: {e}")
        
        return task
    
    async def submit_task_and_wait(
        self,
        name: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        required_capabilities: Optional[Set[str]] = None,
        max_retries: int = 3,
        timeout_seconds: float = 30