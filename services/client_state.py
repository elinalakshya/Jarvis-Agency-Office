from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
import threading
import logging

logger = logging.getLogger(__name__)


class ClientLifecycleStage(Enum):
    """Enumeration of all possible client lifecycle stages."""
    PROSPECT = "prospect"
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFBOARDING = "offboarding"
    CLOSED = "closed"
    ARCHIVED = "archived"


# Define valid state transitions: current_state -> set of allowed next states
VALID_TRANSITIONS: Dict[ClientLifecycleStage, Set[ClientLifecycleStage]] = {
    ClientLifecycleStage.PROSPECT: {
        ClientLifecycleStage.ONBOARDING,
        ClientLifecycleStage.CLOSED,
    },
    ClientLifecycleStage.ONBOARDING: {
        ClientLifecycleStage.ACTIVE,
        ClientLifecycleStage.SUSPENDED,
        ClientLifecycleStage.CLOSED,
        ClientLifecycleStage.PROSPECT,  # revert if onboarding fails
    },
    ClientLifecycleStage.ACTIVE: {
        ClientLifecycleStage.SUSPENDED,
        ClientLifecycleStage.OFFBOARDING,
        ClientLifecycleStage.CLOSED,
    },
    ClientLifecycleStage.SUSPENDED: {
        ClientLifecycleStage.ACTIVE,
        ClientLifecycleStage.OFFBOARDING,
        ClientLifecycleStage.CLOSED,
    },
    ClientLifecycleStage.OFFBOARDING: {
        ClientLifecycleStage.CLOSED,
        ClientLifecycleStage.ACTIVE,  # cancel offboarding
        ClientLifecycleStage.SUSPENDED,
    },
    ClientLifecycleStage.CLOSED: {
        ClientLifecycleStage.ARCHIVED,
    },
    ClientLifecycleStage.ARCHIVED: set(),  # terminal state
}


@dataclass
class TransitionEvent:
    """Record of a state transition for audit trail."""
    from_state: ClientLifecycleStage
    to_state: ClientLifecycleStage
    timestamp: float
    reason: str
    metadata: Dict[str, str] = field(default_factory=dict)


class InvalidTransitionError(Exception):
    """Raised when attempting an invalid state transition."""
    def __init__(self, current: ClientLifecycleStage, target: ClientLifecycleStage):
        self.current = current
        self.target = target
        allowed = VALID_TRANSITIONS.get(current, set())
        super().__init__(
            f"Invalid transition from {current.value} to {target.value}. "
            f"Allowed: {[s.value for s in allowed]}"
        )


class ClientState:
    """
    Thread-safe state machine for managing client lifecycle stages.
    
    Provides validated state transitions with audit logging and event hooks.
    """

    def __init__(
        self,
        client_id: str,
        initial_state: ClientLifecycleStage = ClientLifecycleStage.PROSPECT,
    ):
        self.client_id = client_id
        self._state = initial_state
        self._lock = threading.RLock()
        self._history: List[TransitionEvent] = []
        self._transition_hooks: List[callable] = []

    @property
    def state(self) -> ClientLifecycleStage:
        """Current lifecycle stage (thread-safe read)."""
        with self._lock:
            return self._state

    @property
    def history(self) -> List[TransitionEvent]:
        """Immutable view of transition history."""
        with self._lock:
            return list(self._history)

    def can_transition(self, target_state: ClientLifecycleStage) -> bool:
        """Check if transition to target_state is valid from current state."""
        with self._lock:
            return target_state in VALID_TRANSITIONS.get(self._state, set())

    def get_allowed_transitions(self) -> Set[ClientLifecycleStage]:
        """Return set of valid next states from current state."""
        with self._lock:
            return VALID_TRANSITIONS.get(self._state, set()).copy()

    def add_transition_hook(self, hook: callable) -> None:
        """
        Register a callback to be invoked on every successful transition.
        
        Hook signature: hook(client_id: str, event: TransitionEvent) -> None
        """
        with self._lock:
            self._transition_hooks.append(hook)

    def remove_transition_hook(self, hook: callable) -> bool:
        """Remove a previously registered transition hook."""
        with self._lock:
            try:
                self._transition_hooks.remove(hook)
                return True
            except ValueError:
                return False

    def transition(
        self,
        target_state: ClientLifecycleStage,
        reason: str = "",
        metadata: Optional[Dict[str, str]] = None,
    ) -> TransitionEvent:
        """
        Attempt to transition to target_state.
        
        Args:
            target_state: Desired next lifecycle stage
            reason: Human-readable reason for transition
            metadata: Optional additional context
            
        Returns:
            TransitionEvent recording the successful transition
            
        Raises:
            InvalidTransitionError: If transition is not allowed
        """
        import time
        
        with self._lock:
            if not self.can_transition(target_state):
                raise InvalidTransitionError(self._state, target_state)

            from_state = self._state
            self._state = target_state
            
            event = TransitionEvent(
                from_state=from_state,
                to_state=target_state,
                timestamp=time.time(),
                reason=reason,
                metadata=metadata or {},
            )
            self._history.append(event)
            
            logger.info(
                "Client %s transitioned: %s -> %s (reason: %s)",
                self.client_id, from_state.value, target_state.value, reason
            )

        # Execute hooks outside lock to avoid deadlocks
        for hook in self._transition_hooks:
            try:
                hook(self.client_id, event)
            except Exception as e:
                logger.exception("Transition hook failed for client %s: %s", self.client_id, e)

        return event

    def force_transition(
        self,
        target_state: ClientLifecycleStage,
        reason: str = "forced",
        metadata: Optional[Dict[str, str]] = None,
    ) -> TransitionEvent:
        """
        Force transition bypassing validation (admin/emergency use only).
        
        Warning: This breaks state machine guarantees. Use sparingly.
        """
        import time
        
        with self._lock:
            from_state = self._state
            self._state = target_state
            
            event = TransitionEvent(
                from_state=from_state,
                to_state=target_state,
                timestamp=time.time(),
                reason=f"FORCED: {reason}",
                metadata=metadata or {},
            )
            self._history.append(event)
            
            logger.warning(
                "FORCED transition for client %s: %s -> %s (reason: %s)",
                self.client_id, from_state.value, target_state.value, reason
            )

        for hook in self._transition_hooks:
            try:
                hook(self.client_id, event)
            except Exception as e:
                logger.exception("Transition hook failed for client %s: %s", self.client_id, e)

        return event

    def is_terminal(self) -> bool:
        """Check if current state is terminal (no outgoing transitions)."""
        with self._lock:
            return len(VALID_TRANSITIONS.get(self._state, set())) == 0

    def __repr__(self) -> str:
        return f"ClientState(client_id={self.client_id!r}, state={self.state.value})"