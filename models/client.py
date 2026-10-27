from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Boolean,
    Index,
    event,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, declared_attr, validates

Base = declarative_base()


class TimestampMixin:
    """
    Mixin providing automatic timestamp management for model lifecycle.
    
    Fields:
        created_at: Set once on insert, never modified.
        updated_at: Updated on every modification.
        deleted_at: Set on soft delete; None means active record.
    """
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        comment="Record creation timestamp (UTC)"
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Last modification timestamp (UTC)"
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Soft delete timestamp (UTC); NULL = active"
    )

    @property
    def is_deleted(self) -> bool:
        """Return True if this record has been soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark record as deleted without removing from database."""
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None


class Client(Base, TimestampMixin):
    """
    Client model representing an API consumer or tenant.
    
    Lifecycle:
        - created_at: Set on INSERT
        - updated_at: Auto-updated on any column change
        - deleted_at: Set on soft_delete(), None while active
    
    Validation:
        - name: 1-255 chars, unique among active clients
        - api_key: Auto-generated UUID4, unique, immutable after creation
        - is_active: Boolean flag for quick enable/disable without deletion
    """
    __tablename__ = "clients"
    
    # Table-level constraints and indexes
    __table_args__ = (
        Index(
            "ix_clients_name_active",
            "name",
            unique=True,
            postgresql_where=(deleted_at.is_(None)),
            comment="Unique name among non-deleted clients"
        ),
        Index(
            "ix_clients_api_key",
            "api_key",
            unique=True,
            comment="Fast lookup by API key"
        ),
        {"comment": "API clients / tenants with soft-delete lifecycle"},
    )

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Primary key, UUID v4"
    )
    
    name = Column(
        String(255),
        nullable=False,
        comment="Human-readable client name; unique among active records"
    )
    
    api_key = Column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid4,
        comment="API authentication key; generated once, never changed"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Quick toggle to disable client without deletion"
    )
    
    description = Column(
        String(1000),
        nullable=True,
        default=None,
        comment="Optional free-text description"
    )

    # ---------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------
    @validates("name")
    def validate_name(self, key: str, value: str) -> str:
        """Ensure name is non-empty and within length limits."""
        if not value or not value.strip():
            raise ValueError("Client name cannot be empty")
        if len(value) > 255:
            raise ValueError("Client name cannot exceed 255 characters")
        return value.strip()

    @validates("description")
    def validate_description(self, key: str, value: Optional[str]) -> Optional[str]:
        """Trim description and enforce max length if provided."""
        if value is not None:
            value = value.strip()
            if len(value) > 1000:
                raise ValueError("Description cannot exceed 1000 characters")
            return value if value else None
        return None

    @validates("is_active")
    def validate_is_active(self, key: str, value: bool) -> bool:
        """Coerce to boolean for safety."""
        return bool(value)

    # ---------------------------------------------------------------------
    # ORM Events - prevent api_key mutation after insert
    # ---------------------------------------------------------------------
    @classmethod
    def _protect_api_key(cls, target, value, oldvalue, initiator):
        """Prevent api_key changes after initial persistence."""
        if oldvalue is not None and value != oldvalue:
            raise ValueError("api_key is immutable after creation")
        return value

    # Apply the validator as an ORM event for extra safety
    # (validates() only runs on attribute set, not on bulk updates)
    # This is attached at module load time after class definition.


# Attach immutable api_key protection after class is fully defined
event.listen(Client.api_key, "set", Client._protect_api_key, retval=True)


# -------------------------------------------------------------------------
# Helper functions for common queries
# -------------------------------------------------------------------------
def get_active_clients_query(session):
    """Return a query filtered to non-deleted, active clients."""
    return session.query(Client).filter(
        Client.deleted_at.is_(None),
        Client.is_active.is_(True)
    )


def get_client_by_api_key(session, api_key: UUID) -> Optional[Client]:
    """Fetch active client by API key, excluding soft-deleted."""
    return session.query(Client).filter(
        Client.api_key == api_key,
        Client.deleted_at.is_(None),
        Client.is_active.is_(True)
    ).first()


# -------------------------------------------------------------------------
# Example usage / sanity check (only runs when file executed directly)
# -------------------------------------------------------------------------
if __name__ == "__main__":
    # Quick self-test: ensure model compiles and validators work
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create valid client
    client = Client(name="Test Client", description="A test client")
    session.add(client)
    session.commit()
    assert client.id is not None
    assert client.api_key is not None
    assert client.created_at is not None
    assert client.updated_at is not None
    assert client.deleted_at is None
    assert client.is_active is True
    assert not client.is_deleted
    
    # Test validation: empty name
    try:
        bad = Client(name="")
        session.add(bad)
        session.commit()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "empty" in str(e).lower()
    session.rollback()
    
    # Test validation: name too long
    try:
        bad = Client(name="x" * 300)
        session.add(bad)
        session.commit()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "255" in str(e)
    session.rollback()
    
    # Test soft delete
    client.soft_delete()
    session.commit()
    assert client.is_deleted
    assert client.deleted_at is not None
    
    # Test restore
    client.restore()
    session.commit()
    assert not client.is_deleted
    assert client.deleted_at is None
    
    # Test api_key immutability
    original_key = client.api_key
    try:
        client.api_key = uuid4()
        session.commit()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "immutable" in str(e).lower()
    session.rollback()
    assert client.api_key == original_key
    
    print("All self-tests passed.")