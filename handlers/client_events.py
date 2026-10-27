import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from domain.events.client_events import (
    ClientCreatedEvent,
    ClientUpdatedEvent,
    ClientArchivedEvent,
    ClientEvent,
)
from domain.repositories.client_repository import ClientRepository
from domain.repositories.event_store import EventStore
from infrastructure.message_broker import MessageBroker
from infrastructure.notifications import NotificationService
from application.services.client_service import ClientService

logger = logging.getLogger(__name__)


@dataclass
class ClientEventHandlerConfig:
    """Configuration for client event handlers."""
    publish_to_message_broker: bool = True
    send_notifications: bool = True
    update_read_models: bool = True
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 1.0


class ClientEventHandler:
    """
    Handles domain events related to client lifecycle.
    
    This handler processes ClientCreatedEvent, ClientUpdatedEvent, and ClientArchivedEvent,
    performing side effects such as:
    - Publishing events to message broker for downstream services
    - Sending notifications to relevant parties
    - Updating read models / projections
    - Storing events in event store for audit trail
    """

    def __init__(
        self,
        client_repository: ClientRepository,
        event_store: EventStore,
        message_broker: Optional[MessageBroker] = None,
        notification_service: Optional[NotificationService] = None,
        client_service: Optional[ClientService] = None,
        config: Optional[ClientEventHandlerConfig] = None,
    ):
        self._client_repository = client_repository
        self._event_store = event_store
        self._message_broker = message_broker
        self._notification_service = notification_service
        self._client_service = client_service
        self._config = config or ClientEventHandlerConfig()

    async def handle(self, event: ClientEvent) -> None:
        """
        Route event to appropriate handler based on event type.
        
        Args:
            event: The client domain event to handle
            
        Raises:
            ValueError: If event type is not recognized
            EventHandlingError: If event processing fails after retries
        """
        logger.info(
            "Processing client event",
            extra={
                "event_type": type(event).__name__,
                "client_id": event.client_id,
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
            }
        )

        try:
            # Store event in event store for audit trail
            await self._event_store.append(event)

            # Route to specific handler
            if isinstance(event, ClientCreatedEvent):
                await self._handle_client_created(event)
            elif isinstance(event, ClientUpdatedEvent):
                await self._handle_client_updated(event)
            elif isinstance(event, ClientArchivedEvent):
                await self._handle_client_archived(event)
            else:
                raise ValueError(f"Unknown client event type: {type(event).__name__}")

            logger.info(
                "Successfully processed client event",
                extra={"event_type": type(event).__name__, "client_id": event.client_id}
            )

        except Exception as e:
            logger.error(
                "Failed to process client event",
                extra={
                    "event_type": type(event).__name__,
                    "client_id": event.client_id,
                    "error": str(e),
                },
                exc_info=True
            )
            raise

    async def _handle_client_created(self, event: ClientCreatedEvent) -> None:
        """
        Handle client creation event.
        
        Side effects:
        - Publish to message broker for downstream services (CRM, billing, etc.)
        - Send welcome notification to client
        - Notify account manager
        - Update read models
        """
        logger.debug("Handling client created event", extra={"client_id": event.client_id})

        # Publish to message broker for downstream consumers
        if self._config.publish_to_message_broker and self._message_broker:
            await self._publish_with_retry(
                topic="client.created",
                message={
                    "event_id": event.event_id,
                    "client_id": event.client_id,
                    "email": event.email,
                    "name": event.name,
                    "company": event.company,
                    "tier": event.tier.value,
                    "created_at": event.timestamp.isoformat(),
                    "metadata": event.metadata,
                }
            )

        # Send welcome notification to client
        if self._config.send_notifications and self._notification_service:
            await self._notification_service.send_welcome_email(
                email=event.email,
                name=event.name,
                client_id=event.client_id,
            )

        # Notify assigned account manager
        if self._config.send_notifications and self._notification_service and event.assigned_account_manager_id:
            await self._notification_service.notify_account_manager(
                account_manager_id=event.assigned_account_manager_id,
                client_id=event.client_id,
                action="assigned_new_client",
                client_name=event.name,
            )

        # Update read model / projection
        if self._config.update_read_models and self._client_service:
            await self._client_service.refresh_client_projection(event.client_id)

    async def _handle_client_updated(self, event: ClientUpdatedEvent) -> None:
        """
        Handle client update event.
        
        Side effects:
        - Publish to message broker for downstream services
        - Send change notification to client (for significant changes)
        - Notify account manager of changes
        - Update read models
        - Handle tier changes (upgrade/downgrade workflows)
        """
        logger.debug("Handling client updated event", extra={"client_id": event.client_id})

        # Determine what changed
        changed_fields = event.changed_fields or []
        is_tier_change = "tier" in changed_fields
        is_email_change = "email" in changed_fields
        is_status_change = "status" in changed_fields

        # Publish to message broker
        if self._config.publish_to_message_broker and self._message_broker:
            await self._publish_with_retry(
                topic="client.updated",
                message={
                    "event_id": event.event_id,
                    "client_id": event.client_id,
                    "changed_fields": changed_fields,
                    "previous_values": event.previous_values,
                    "new_values": event.new_values,
                    "updated_at": event.timestamp.isoformat(),
                    "updated_by": event.updated_by,
                    "metadata": event.metadata,
                }
            )

        # Send notification to client for significant changes
        if self._config.send_notifications and self._notification_service:
            if is_email_change:
                await self._notification_service.send_email_change_confirmation(
                    old_email=event.previous_values.get("email"),
                    new_email=event.new_values.get("email"),
                    client_id=event.client_id,
                )
            elif is_tier_change:
                await self._notification_service.send_tier_change_notification(
                    client_id=event.client_id,
                    old_tier=event.previous_values.get("tier"),
                    new_tier=event.new_values.get("tier"),
                )
            elif is_status_change:
                await self._notification_service.send_status_change_notification(
                    client_id=event.client_id,
                    old_status=event.previous_values.get("status"),
                    new_status=event.new_values.get("status"),
                )

        # Notify account manager of significant changes
        if self._config.send_notifications and self._notification_service and (
            is_tier_change or is_status_change
        ):
            client = await self._client_repository.get_by_id(event.client_id)
            if client and client.assigned_account_manager_id:
                await self._notification_service.notify_account_manager(
                    account_manager_id=client.assigned_account_manager_id,
                    client_id=event.client_id,
                    action="client_updated",
                    changed_fields=changed_fields,
                )

        # Handle tier change workflows
        if is_tier_change and self._client_service:
            await self._client_service.handle_tier_change(
                client_id=event.client_id,
                old_tier=event.previous_values.get("tier"),
                new_tier=event.new_values.get("tier"),
            )

        # Update read model
        if self._config.update_read_models and self._client_service:
            await self._client_service.refresh_client_projection(event.client_id)

    async def _handle_client_archived(self, event: ClientArchivedEvent) -> None:
        """
        Handle client archival event.
        
        Side effects:
        - Publish to message broker for downstream services
        - Send archival notification to client
        - Notify account manager
        - Cancel active subscriptions/services
        - Update read models (mark as archived)
        - Trigger data retention workflows
        """
        logger.debug("Handling client archived event", extra={"client_id": event.client_id})

        # Publish to message broker
        if self._config.publish_to_message_broker and self._message_broker:
            await self._publish_with_retry(
                topic="client.archived",
                message={
                    "event_id": event.event_id,
                    "client_id": event.client_id,
                    "reason": event.reason,
                    "archived_by": event.archived_by,
                    "archived_at": event.timestamp.isoformat(),
                    "metadata": event.metadata,
                }
            )

        # Send archival notification to client
        if self._config.send_notifications and self._notification_service:
            client = await self._client_repository.get_by_id(event.client_id)
            if client:
                await self._notification_service.send_account_archived_notification(
                    email=client.email,
                    name=client.name,
                    client_id=event.client_id,
                    reason=event.reason,
                )

        # Notify account manager
        if self._config.send_notifications and self._notification_service:
            client = await self._client_repository.get_by_id(event.client_id)
            if client and client.assigned_account_manager_id:
                await self._notification_service.notify_account_manager(
                    account_manager_id=client.assigned_account_manager_id,
                    client_id=event.client_id,
                    action="client_archived",
                    reason=event.reason,
                )

        # Cancel active subscriptions and services
        if self._client_service:
            await self._client_service.cancel_active_services(event.client_id, event.reason)

        # Update read model to reflect archived status
        if self._config.update_read_models and self._client_service:
            await self._client_service.refresh_client_projection(event.client_id)

        # Trigger data retention / GDPR workflow if needed
        if event.metadata and event.metadata.get("gdpr_deletion_requested"):
            if self._client_service:
                await self._client_service.schedule_data_deletion(
                    client_id=event.client_id,
                    deletion_date=datetime.utcnow(),
                )

    async def _publish_with_retry(self, topic: str, message: dict) -> None:
        """
        Publish message to broker with retry logic.
        
        Args:
            topic: Message topic/routing key
            message: Message payload
            
        Raises:
            MessagePublishError: If all retry attempts fail
        """
        last_error = None
        
        for attempt in range(self._config.max_retry_attempts):
            try:
                await self._message_broker.publish(topic, message)
                logger.debug(
                    "Successfully published message",
                    extra={"topic": topic, "attempt": attempt + 1}
                )
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    "Failed to publish message, retrying",
                    extra={
                        "topic": topic,
                        "attempt": attempt + 1,
                        "max_attempts": self._config.max_retry_attempts,
                        "error": str(e),
                    }
                )
                if attempt < self._config.max_retry_attempts - 1:
                    import asyncio
                    await asyncio.sleep(self._config.retry_delay_seconds * (attempt + 1))

        # All retries exhausted
        logger.error(
            "Failed to publish message after all retries",
            extra={"topic": topic, "error": str(last_error)}
        )
        raise MessagePublishError(f"Failed to publish to {topic} after {self._config.max_retry_attempts} attempts") from last_error


class MessagePublishError(Exception):
    """Raised when message publishing fails after all retries."""
    pass


class EventHandlingError(Exception):
    """Raised when event handling fails."""
    pass


# Factory function for dependency injection
def create_client_event_handler(
    client_repository: ClientRepository,
    event_store: EventStore,
    message_broker: Optional[MessageBroker] = None,
    notification_service: Optional[NotificationService] = None,
    client_service: Optional[ClientService] = None,
    config: Optional[ClientEventHandlerConfig] = None,
) -> ClientEventHandler:
    """
    Factory function to create a ClientEventHandler with all dependencies.
    
    This allows for easy testing and configuration via dependency injection containers.
    """
    return ClientEventHandler(
        client_repository=client_repository,
        event_store=event_store,
        message_broker=message_broker,
        notification_service=notification_service,
        client_service=client_service,
        config=config,
    )