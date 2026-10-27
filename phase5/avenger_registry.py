"""Avenger Registry Module.

Provides a thread-safe registry for storing and managing Avenger definitions
and metadata with full CRUD operations, search capabilities, and persistence.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class AvengerRole(Enum):
    """Enumeration of possible Avenger roles."""

    LEADER = "leader"
    STRATEGIST = "strategist"
    COMBATANT = "combatant"
    SUPPORT = "support"
    INTEL = "intel"
    TECH = "tech"
    MYSTIC = "mystic"
    COSMIC = "cosmic"


class AvengerStatus(Enum):
    """Enumeration of Avenger operational statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    STANDBY = "standby"
    MISSION = "mission"
    RETIRED = "retired"
    DECEASED = "deceased"
    RECRUITING = "recruiting"


@dataclass
class AvengerAbility:
    """Represents a single ability or power of an Avenger."""

    name: str
    description: str
    power_level: int  # 1-100 scale
    energy_cost: int = 0
    cooldown_seconds: float = 0.0
    is_ultimate: bool = False
    tags: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Validate ability attributes after initialization."""
        if not 1 <= self.power_level <= 100:
            raise ValueError(f"power_level must be 1-100, got {self.power_level}")
        if self.energy_cost < 0:
            raise ValueError(f"energy_cost cannot be negative, got {self.energy_cost}")
        if self.cooldown_seconds < 0:
            raise ValueError(f"cooldown_seconds cannot be negative, got {self.cooldown_seconds}")


@dataclass
class AvengerStats:
    """Core statistics for an Avenger."""

    strength: int = 50
    agility: int = 50
    durability: int = 50
    intelligence: int = 50
    energy_projection: int = 50
    fighting_skill: int = 50
    speed: int = 50
    stamina: int = 50

    def __post_init__(self) -> None:
        """Validate stats are within valid range."""
        for field_name, value in asdict(self).items():
            if not 0 <= value <= 100:
                raise ValueError(f"{field_name} must be 0-100, got {value}")

    @property
    def overall_power(self) -> float:
        """Calculate overall power rating as average of all stats."""
        values = asdict(self).values()
        return sum(values) / len(values)

    def to_dict(self) -> dict[str, int]:
        """Convert stats to dictionary."""
        return asdict(self)


@dataclass
class AvengerMetadata:
    """Extended metadata for an Avenger."""

    real_name: str
    aliases: list[str] = field(default_factory=list)
    birth_date: Optional[str] = None  # ISO format
    origin: str = "Unknown"
    affiliation_history: list[str] = field(default_factory=lambda: ["Avengers"])
    notable_achievements: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    universe: str = "Marvel-616"
    first_appearance: Optional[str] = None
    created_by: list[str] = field(default_factory=list)
    custom_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return asdict(self)


@dataclass
class Avenger:
    """Complete Avenger definition with all attributes."""

    name: str
    role: AvengerRole
    status: AvengerStatus = AvengerStatus.ACTIVE
    stats: AvengerStats = field(default_factory=AvengerStats)
    abilities: list[AvengerAbility] = field(default_factory=list)
    metadata: AvengerMetadata = field(default_factory=lambda: AvengerMetadata(real_name="Unknown"))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1
    tags: set[str] = field(default_factory=set)
    is_active: bool = True

    def __post_init__(self) -> None:
        """Validate and normalize after initialization."""
        if not self.name or not self.name.strip():
            raise ValueError("Avenger name cannot be empty")
        self.name = self.name.strip()
        if isinstance(self.role, str):
            self.role = AvengerRole(self.role)
        if isinstance(self.status, str):
            self.status = AvengerStatus(self.status)
        if isinstance(self.stats, dict):
            self.stats = AvengerStats(**self.stats)
        if isinstance(self.metadata, dict):
            self.metadata = AvengerMetadata(**self.metadata)
        if isinstance(self.abilities, list):
            self.abilities = [
                AvengerAbility(**a) if isinstance(a, dict) else a for a in self.abilities
            ]

    def update_timestamp(self) -> None:
        """Update the modified timestamp and increment version."""
        self.updated_at = datetime.utcnow().isoformat()
        self.version += 1

    def add_ability(self, ability: AvengerAbility) -> None:
        """Add an ability to this Avenger."""
        if any(a.name == ability.name for a in self.abilities):
            raise ValueError(f"Ability '{ability.name}' already exists")
        self.abilities.append(ability)
        self.update_timestamp()

    def remove_ability(self, ability_name: str) -> bool:
        """Remove an ability by name. Returns True if removed."""
        for i, ability in enumerate(self.abilities):
            if ability.name == ability_name:
                self.abilities.pop(i)
                self.update_timestamp()
                return True
        return False

    def get_ability(self, name: str) -> Optional[AvengerAbility]:
        """Get an ability by name."""
        for ability in self.abilities:
            if ability.name == name:
                return ability
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to values
        data["role"] = self.role.value
        data["status"] = self.status.value
        # Convert sets to lists for JSON serialization
        data["tags"] = list(self.tags)
        # Convert abilities
        data["abilities"] = [asdict(a) for a in self.abilities]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Avenger:
        """Create Avenger from dictionary."""
        # Handle enum conversions
        if "role" in data and isinstance(data["role"], str):
            data["role"] = AvengerRole(data["role"])
        if "status" in data and isinstance(data["status"], str):
            data["status"] = AvengerStatus(data["status"])
        # Handle tags
        if "tags" in data and isinstance(data["tags"], list):
            data["tags"] = set(data["tags"])
        # Handle abilities
        if "abilities" in data:
            data["abilities"] = [
                AvengerAbility(**a) if isinstance(a, dict) else a for a in data["abilities"]
            ]
        # Handle stats
        if "stats" in data and isinstance(data["stats"], dict):
            data["stats"] = AvengerStats(**data["stats"])
        # Handle metadata
        if "metadata" in data and isinstance(data["metadata"], dict):
            data["metadata"] = AvengerMetadata(**data["metadata"])
        return cls(**data)


class AvengerRegistryError(Exception):
    """Base exception for registry errors."""

    pass


class AvengerNotFoundError(AvengerRegistryError):
    """Raised when an Avenger is not found in the registry."""

    pass


class AvengerAlreadyExistsError(AvengerRegistryError):
    """Raised when attempting to add a duplicate Avenger."""

    pass


class AvengerValidationError(AvengerRegistryError):
    """Raised when Avenger data fails validation."""

    pass


class AvengerRegistry:
    """Thread-safe registry for managing Avenger definitions.

    Provides CRUD operations, search/filter capabilities, persistence,
    and event hooks for integration with other systems.
    """

    def __init__(self, auto_save: bool = False, save_path: Optional[Path] = None) -> None:
        """Initialize the registry.

        Args:
            auto_save: If True, automatically persist changes to disk.
            save_path: Path to save/load registry data. Defaults to ./avengers.json.
        """
        self._avengers: dict[str, Avenger] = {}
        self._name_index: dict[str, str] = {}  # name -> id mapping
        self._lock = threading.RLock()
        self._auto_save = auto_save
        self._save_path = save_path or Path("avengers.json")
        self._hooks: dict[str, list[Callable]] = {
            "on_add": [],
            "on_update": [],
            "on_remove": [],
            "on_load": [],
            "on_save": [],
        }
        logger.info("AvengerRegistry initialized")

    # --------------------------------------------------------------------- #
    # Hook Management
    # --------------------------------------------------------------------- #
    def register_hook(self, event: str, callback: Callable) -> None:
        """Register a callback for registry events.

        Args:
            event: Event name ('on_add', 'on_update', 'on_remove', 'on_load', 'on_save')
            callback: Function to call when event occurs. Receives (registry, avenger_id, avenger).
        """
        if event not in self._hooks:
            raise ValueError(f"Unknown event: {event}. Valid: {list(self._hooks.keys())}")
        self._hooks[event].append(callback)
        logger.debug("Registered hook for %s", event)

    def _trigger_hooks(self, event: str, avenger_id: str, avenger: Optional[Avenger]) -> None:
        """Trigger all callbacks for an event."""
        for callback in self._hooks.get(event, []):
            try:
                callback(self, avenger_id, avenger)
            except Exception as e:
                logger.error("Hook %s failed: %s", event, e)

    # --------------------------------------------------------------------- #
    # Core CRUD Operations
    # --------------------------------------------------------------------- #
    def add(self, avenger: Avenger, overwrite: bool = False) -> str:
        """Add an Avenger to the registry.

        Args:
            avenger: The Avenger to add.
            overwrite: If True, replace existing Avenger with same name.

        Returns:
            The Avenger's unique ID.

        Raises:
            AvengerAlreadyExistsError: If Avenger with same name exists and overwrite=False.
            AvengerValidationError: If Avenger data is invalid.
        """
        with self._lock:
            # Validate
            if not isinstance(avenger, Avenger):
                raise AvengerValidationError("Provided object is not an Avenger instance")

            # Check for duplicate name
            existing_id = self._name_index.get(avenger.name)
            if existing_id and not overwrite:
                raise AvengerAlreadyExistsError(
                    f"Avenger '{avenger.name}' already exists (ID: {existing_id})"
                )

            # Handle overwrite
            if existing_id and overwrite:
                self._avengers[existing_id] = avenger
                avenger.id = existing_id
                avenger.update_timestamp()
                logger.info("Overwrote Avenger: %s (ID: %s)", avenger.name, existing_id)
                self._trigger_hooks("on_update", existing_id, avenger)
            else:
                # New Avenger
                self._avengers[avenger.id] = avenger
                self._name_index[avenger.name] = avenger.id
                logger.info("Added Avenger: %s (ID: %s)", avenger.name, avenger.id)
                self._trigger_hooks("on_add", avenger.id, avenger)

            if self._auto_save:
                self.save()

            return avenger.id

    def get(self, identifier: str) -> Avenger:
        """Get an Avenger by ID or name.

        Args:
            identifier: Avenger ID or name.

        Returns:
            The Avenger instance.

        Raises:
            AvengerNotFoundError: If not found.
        """
        with self._lock:
            # Try ID first
            if identifier in self._avengers:
                return self._avengers[identifier]

            # Try name
            avenger_id = self._name_index.get(identifier)
            if avenger_id and avenger_id in self._avengers:
                return self._avengers[avenger_id]

            raise AvengerNotFoundError(f"Avenger not found: {identifier}")

    def get_by_id(self, avenger_id: str) -> Avenger:
        """Get an Avenger by ID only.

        Args:
            avenger_id: The unique identifier.

        Returns:
            The Avenger instance.

        Raises:
            AvengerNotFoundError: If not found.
        """
        with self._lock:
            if avenger_id not in self._avengers:
                raise AvengerNotFoundError(f"Avenger not found: {avenger_id}")
            return self._avengers[avenger_id]

    def get_by_name(self, name: str) -> Avenger:
        """Get an Avenger by name only.

        Args:
            name: The Avenger's name.

        Returns:
            The Avenger instance.

        Raises:
            AvengerNotFoundError: If not found.
        """
        with self._lock:
            avenger_id = self._name_index.get(name)
            if not avenger_id or avenger_id not in self._avengers:
                raise AvengerNotFoundError(f"Avenger not found: {name}")
            return self._avengers[avenger_id]

    def update(self, avenger: Avenger) -> None:
        """Update an existing Avenger.

        Args:
            avenger: The Avenger with updated data.

        Raises:
            AvengerNotFoundError: If Avenger doesn't exist.
            AvengerValidationError: If data is invalid.
        """
        with self._lock:
            if avenger.id not in self._avengers:
                raise AvengerNotFoundError(f"Avenger not found: {avenger.id}")

            # Check name conflict
            existing = self._avengers[avenger.id]
            if existing.name != avenger.name:
                if avenger.name in self._name_index:
                    raise AvengerAlreadyExistsError(f"Name '{avenger.name}' already in use")
                del self._name_index[existing.name]
                self._name_index[avenger.name] = avenger.id

            avenger.update_timestamp()
            self._avengers[avenger.id] = avenger
            logger.info("Updated Avenger: %s (ID: %s)", avenger.name, avenger.id)
            self._trigger_hooks("on_update", avenger.id, avenger)

            if self._auto_save:
                self.save()

    def remove(self, identifier: str) -> Avenger:
        """Remove an Avenger from the registry.

        Args:
            identifier: Avenger ID or name.

        Returns:
            The removed Avenger.

        Raises:
            AvengerNotFoundError: If not found.
        """
        with self._lock:
            avenger = self.get(identifier)
            avenger_id = avenger.id
            name = avenger.name

            del self._avengers[avenger_id]
            del self._name_index[name]
            logger.info("Removed Avenger: %s (ID: %s)", name, avenger_id)
            self._trigger_hooks("on_remove", avenger_id, avenger)

            if self._auto_save:
                self.save()

            return avenger

    def exists(self, identifier: str) -> bool:
        """Check if an Avenger exists by ID or name."""
        with self._lock:
            if identifier in self._avengers:
                return True
            return identifier in self._name_index

    # --------------------------------------------------------------------- #
    # Query Operations
    # --------------------------------------------------------------------- #
    def list_all(self, include_inactive: bool = False) -> list[Avenger]:
        """Get all Avengers.

        Args:
            include_inactive: If True, include Avengers with is_active=False.

        Returns:
            List of all Avengers.
        """
        with self._lock:
            avengers = list(self._avengers.values())
            if not include_inactive:
                avengers = [a for a in avengers if a.is_active]
            return avengers

    def list_by_role(self, role: AvengerRole, include_inactive: bool = False) -> list[Avenger]:
        """Get all Avengers with a specific role."""
        with self._lock: