from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.logging import get_logger
from models.client import Client, ClientStatus

logger = get_logger(__name__)

router = APIRouter(prefix="/clients", tags=["Client Lifecycle"])


class ClientStatusEnum(str, Enum):
    """Enumeration of valid client statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class ClientBase(BaseModel):
    """Base schema for client data."""
    name: str = Field(..., min_length=1, max_length=255, description="Client's full name or company name")
    email: EmailStr = Field(..., description="Client's email address")
    phone: Optional[str] = Field(None, max_length=50, description="Client's phone number")
    address: Optional[str] = Field(None, max_length=500, description="Client's address")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional client metadata")

    @validator("name")
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip()


class ClientCreate(ClientBase):
    """Schema for creating a new client."""
    status: ClientStatusEnum = Field(default=ClientStatusEnum.PENDING, description="Initial client status")


class ClientUpdate(BaseModel):
    """Schema for updating an existing client. All fields are optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    status: Optional[ClientStatusEnum] = None
    metadata: Optional[dict] = None

    @validator("name")
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip() if v else None


class ClientResponse(ClientBase):
    """Schema for client response data."""
    id: UUID
    status: ClientStatusEnum
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClientListResponse(BaseModel):
    """Schema for paginated client list response."""
    items: list[ClientResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class StatusTransitionRequest(BaseModel):
    """Schema for requesting a client status transition."""
    status: ClientStatusEnum = Field(..., description="New status for the client")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for status change")


# Valid status transitions
VALID_TRANSITIONS: dict[ClientStatusEnum, set[ClientStatusEnum]] = {
    ClientStatusEnum.PENDING: {ClientStatusEnum.ACTIVE, ClientStatusEnum.INACTIVE, ClientStatusEnum.ARCHIVED},
    ClientStatusEnum.ACTIVE: {ClientStatusEnum.INACTIVE, ClientStatusEnum.SUSPENDED, ClientStatusEnum.ARCHIVED},
    ClientStatusEnum.INACTIVE: {ClientStatusEnum.ACTIVE, ClientStatusEnum.PENDING, ClientStatusEnum.ARCHIVED},
    ClientStatusEnum.SUSPENDED: {ClientStatusEnum.ACTIVE, ClientStatusEnum.ARCHIVED},
    ClientStatusEnum.ARCHIVED: set(),  # Terminal state
}


async def get_client_or_404(db: AsyncSession, client_id: UUID) -> Client:
    """Fetch a client by ID or raise 404."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        logger.warning("Client not found", client_id=str(client_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with id {client_id} not found"
        )
    return client


def validate_status_transition(current: ClientStatusEnum, new: ClientStatusEnum) -> None:
    """Validate that a status transition is allowed."""
    if new not in VALID_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from {current.value} to {new.value}"
        )


@router.post(
    "",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new client",
    description="Create a new client record with the provided information."
)
async def create_client(
    client_data: ClientCreate,
    db: AsyncSession = Depends(get_db)
) -> ClientResponse:
    """Create a new client."""
    logger.info("Creating new client", email=client_data.email)
    
    client = Client(
        id=uuid4(),
        name=client_data.name,
        email=client_data.email,
        phone=client_data.phone,
        address=client_data.address,
        status=ClientStatus(client_data.status.value),
        metadata=client_data.metadata,
    )
    
    db.add(client)
    try:
        await db.commit()
        await db.refresh(client)
    except IntegrityError as e:
        await db.rollback()
        logger.error("Failed to create client - duplicate email", email=client_data.email, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A client with this email already exists"
        )
    
    logger.info("Client created successfully", client_id=str(client.id))
    return ClientResponse.model_validate(client)


@router.get(
    "/{client_id}",
    response_model=ClientResponse,
    summary="Get client by ID",
    description="Retrieve a single client by their unique identifier."
)
async def get_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> ClientResponse:
    """Get a client by ID."""
    client = await get_client_or_404(db, client_id)
    return ClientResponse.model_validate(client)


@router.get(
    "",
    response_model=ClientListResponse,
    summary="List clients",
    description="Retrieve a paginated list of clients with optional filtering."
)
async def list_clients(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    status: Optional[ClientStatusEnum] = Query(None, description="Filter by client status"),
    search: Optional[str] = Query(None, description="Search in name or email"),
    db: AsyncSession = Depends(get_db)
) -> ClientListResponse:
    """List clients with pagination and filtering."""
    query = select(Client)
    
    if status:
        query = query.where(Client.status == ClientStatus(status.value))
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Client.name.ilike(search_term)) | (Client.email.ilike(search_term))
        )
    
    # Get total count
    count_query = select(Client.id)
    if status:
        count_query = count_query.where(Client.status == ClientStatus(status.value))
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            (Client.name.ilike(search_term)) | (Client.email.ilike(search_term))
        )
    
    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination
    query = query.order_by(Client.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    clients = result.scalars().all()
    
    total_pages = (total + page_size - 1) // page_size
    
    return ClientListResponse(
        items=[ClientResponse.model_validate(c) for c in clients],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.patch(
    "/{client_id}",
    response_model=ClientResponse,
    summary="Update client",
    description="Partially update a client's information."
)
async def update_client(
    client_id: UUID,
    client_data: ClientUpdate,
    db: AsyncSession = Depends(get_db)
) -> ClientResponse:
    """Update a client."""
    client = await get_client_or_404(db, client_id)
    
    logger.info("Updating client", client_id=str(client_id), fields=list(client_data.model_dump(exclude_unset=True).keys()))
    
    update_data = client_data.model_dump(exclude_unset=True)
    
    # Handle status conversion
    if "status" in update_data:
        update_data["status"] = ClientStatus(update_data["status"].value)
    
    for field, value in update_data.items():
        setattr(client, field, value)
    
    client.updated_at = datetime.utcnow()
    
    try:
        await db.commit()
        await db.refresh(client)
    except IntegrityError as e:
        await db.rollback()
        logger.error("Failed to update client - integrity error", client_id=str(client_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update would violate uniqueness constraint"
        )
    
    logger.info("Client updated successfully", client_id=str(client_id))
    return ClientResponse.model_validate(client)


@router.post(
    "/{client_id}/status",
    response_model=ClientResponse,
    summary="Transition client status",
    description="Transition a client to a new status with validation of allowed transitions."
)
async def transition_client_status(
    client_id: UUID,
    transition: StatusTransitionRequest,
    db: AsyncSession = Depends(get_db)
) -> ClientResponse:
    """Transition client status with validation."""
    client = await get_client_or_404(db, client_id)
    
    current_status = ClientStatusEnum(client.status.value)
    new_status = transition.status
    
    validate_status_transition(current_status, new_status)
    
    logger.info(
        "Transitioning client status",
        client_id=str(client_id),
        from_status=current_status.value,
        to_status=new_status.value,
        reason=transition.reason
    )
    
    client.status = ClientStatus(new_status.value)
    client.updated_at = datetime.utcnow()
    
    if transition.reason:
        client.metadata = client.metadata or {}
        client.metadata["status_change_reason"] = transition.reason
        client.metadata["previous_status"] = current_status.value
        client.metadata["status_changed_at"] = datetime.utcnow().isoformat()
    
    await db.commit()
    await db.refresh(client)
    
    logger.info("Client status transitioned successfully", client_id=str(client_id))
    return ClientResponse.model_validate(client)


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete client",
    description="Permanently delete a client record. This action cannot be undone."
)
async def delete_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a client."""
    client = await get_client_or_404(db, client_id)
    
    logger.info("Deleting client", client_id=str(client_id))
    
    await db.delete(client)
    await db.commit()
    
    logger.info("Client deleted successfully", client_id=str(client_id))


@router.post(
    "/{client_id}/archive",
    response_model=ClientResponse,
    summary="Archive client",
    description="Archive a client (soft delete). Archived clients are hidden from normal lists but retained for compliance."
)
async def archive_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> ClientResponse:
    """Archive a client."""
    client = await get_client_or_404(db, client_id)
    
    if client.status == ClientStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client is already archived"
        )
    
    logger.info("Archiving client", client_id=str(client_id))
    
    client.status = ClientStatus.ARCHIVED
    client.updated_at = datetime.utcnow()
    client.metadata = client.metadata or {}
    client.metadata["archived_at"] = datetime.utcnow().isoformat()
    
    await db.commit()
    await db.refresh(client)
    
    logger.info("Client archived successfully", client_id=str(client_id))
    return ClientResponse.model_validate(client)