from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from database import get_session_factory
from models.client import Client, ClientStatus
from models.node import Node
from models.subscription import Subscription, SubscriptionStatus
from models.payment import Payment, PaymentStatus
from repositories.client_repository import ClientRepository
from repositories.node_repository import NodeRepository
from repositories.subscription_repository import SubscriptionRepository
from repositories.payment_repository import PaymentRepository
from services.panel import PanelServiceFactory, PanelService
from services.traffic import TrafficService
from services.notification import NotificationService
from utils.exceptions import (
    ClientNotFoundError,
    NodeNotFoundError,
    SubscriptionNotFoundError,
    InsufficientBalanceError,
    BusinessRuleViolationError,
    PanelOperationError,
    ValidationError,
)
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ClientLifecycleService:
    """
    Orchestrates client lifecycle operations and enforces business rules.
    
    This service handles the complete client lifecycle from creation to deletion,
    including activation, renewal, suspension, and traffic management.
    All operations are wrapped in transactions using Unit of Work pattern.
    """

    def __init__(
        self,
        session_factory=None,
        panel_factory: Optional[PanelServiceFactory] = None,
        traffic_service: Optional[TrafficService] = None,
        notification_service: Optional[NotificationService] = None,
    ):
        self._session_factory = session_factory or get_session_factory()
        self._panel_factory = panel_factory or PanelServiceFactory()
        self._traffic_service = traffic_service or TrafficService()
        self._notification_service = notification_service or NotificationService()

    # ==================== Client Creation ====================

    async def create_client(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: str = "en",
        referrer_id: Optional[int] = None,
    ) -> Client:
        """
        Create a new client with default settings.
        
        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            last_name: User's last name
            language_code: Language preference
            referrer_id: Optional referrer's telegram ID
            
        Returns:
            Created Client instance
            
        Raises:
            BusinessRuleViolationError: If client already exists
        """
        async with self._session_factory() as session:
            client_repo = ClientRepository(session)
            
            # Check if client already exists
            existing = await client_repo.get_by_telegram_id(telegram_id)
            if existing:
                raise BusinessRuleViolationError(
                    f"Client with telegram_id {telegram_id} already exists",
                    rule="unique_telegram_id"
                )
            
            # Create client with defaults from settings
            client = Client(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                referrer_id=referrer_id,
                status=ClientStatus.ACTIVE,
                traffic_limit_bytes=settings.default_traffic_limit_gb * 1024**3,
                traffic_used_bytes=0,
                expiry_date=None,  # No expiry until subscription purchased
                is_banned=False,
                settings={
                    "auto_renew": False,
                    "notify_expiry_days": [7, 3, 1],
                    "notify_traffic_percent": [80, 90, 95],
                }
            )
            
            await client_repo.add(client)
            await session.commit()
            await session.refresh(client)
            
            logger.info(f"Created new client: {client.id} (telegram_id: {telegram_id})")
            
            # Send welcome notification
            await self._notification_service.send_welcome(client)
            
            return client

    async def get_or_create_client(self, telegram_id: int, **kwargs) -> Client:
        """Get existing client or create new one."""
        async with self._session_factory() as session:
            client_repo = ClientRepository(session)
            client = await client_repo.get_by_telegram_id(telegram_id)
            
            if not client:
                client = await self.create_client(telegram_id, **kwargs)
                
            return client

    # ==================== Client Status Management ====================

    async def activate_client(self, client_id: UUID, admin_id: Optional[UUID] = None) -> Client:
        """
        Activate a client account.
        
        Args:
            client_id: Client UUID
            admin_id: Optional admin who performed the action
            
        Returns:
            Updated Client instance
        """
        return await self._update_client_status(
            client_id, 
            ClientStatus.ACTIVE, 
            admin_id,
            "Client activated"
        )

    async def suspend_client(
        self, 
        client_id: UUID, 
        reason: str,
        admin_id: Optional[UUID] = None
    ) -> Client:
        """
        Suspend a client account.
        
        Args:
            client_id: Client UUID
            reason: Suspension reason
            admin_id: Optional admin who performed the action
            
        Returns:
            Updated Client instance
        """
        client = await self._update_client_status(
            client_id,
            ClientStatus.SUSPENDED,
            admin_id,
            f"Client suspended: {reason}"
        )
        
        # Disable VPN access on all nodes
        await self._disable_client_on_all_nodes(client)
        
        await self._notification_service.send_suspension_notice(client, reason)
        
        return client

    async def ban_client(
        self, 
        client_id: UUID, 
        reason: str,
        admin_id: Optional[UUID] = None
    ) -> Client:
        """
        Ban a client permanently.
        
        Args:
            client_id: Client UUID
            reason: Ban reason
            admin_id: Optional admin who performed the action
            
        Returns:
            Updated Client instance
        """
        async with self._session_factory() as session:
            client_repo = ClientRepository(session)
            client = await client_repo.get_by_id(client_id)
            
            if not client:
                raise ClientNotFoundError(str(client_id))
            
            client.is_banned = True
            client.status = ClientStatus.BANNED
            client.ban_reason = reason
            client.banned_at = datetime.utcnow()
            client.banned_by = admin_id
            
            await client_repo.update(client)
            await session.commit()
            
            # Disable VPN access and cleanup
            await self._disable_client_on_all_nodes(client)
            await self._cleanup_client_resources(client)
            
            await self._notification_service.send_ban_notice(client, reason)
            
            logger.warning(f"Client banned: {client_id}, reason: {reason}")
            
            return client

    async def unban_client(self, client_id: UUID, admin_id: Optional[UUID] = None) -> Client:
        """Unban a previously banned client."""
        return await self._update_client_status(
            client_id,
            ClientStatus.ACTIVE,
            admin_id,
            "Client unbanned"
        )

    async def _update_client_status(
        self,
        client_id: UUID,
        new_status: ClientStatus,
        admin_id: Optional[UUID],
        reason: str
    ) -> Client:
        """Internal method to update client status."""
        async with self._session_factory() as session:
            client_repo = ClientRepository(session)
            client = await client_repo.get_by_id(client_id)
            
            if not client:
                raise ClientNotFoundError(str(client_id))
            
            if client.is_banned and new_status != ClientStatus.BANNED:
                raise BusinessRuleViolationError(
                    "Cannot change status of banned client. Unban first.",
                    rule="banned_client_immutable"
                )
            
            old_status = client.status
            client.status = new_status
            client.status_changed_at = datetime.utcnow()
            client.status_changed_by = admin_id
            client.status_change_reason = reason
            
            await client_repo.update(client)
            await session.commit()
            await session.refresh(client)
            
            logger.info(f"Client {client_id} status changed: {old_status} -> {new_status}")
            
            return client

    # ==================== Subscription Management ====================

    async def create_subscription(
        self,
        client_id: UUID,
        plan_id: str,
        duration_days: int,
        node_id: Optional[UUID] = None,
        payment_id: Optional[UUID] = None,
        promo_code: Optional[str] = None,
    ) -> Subscription:
        """
        Create a new subscription for a client.
        
        Args:
            client_id: Client UUID
            plan_id: Subscription plan identifier
            duration_days: Subscription duration in days
            node_id: Optional specific node (auto-assigned if not provided)
            payment_id: Optional associated payment
            promo_code: Optional promo code applied
            
        Returns:
            Created Subscription instance
        """
        async with self._session_factory() as session:
            client_repo = ClientRepository(session)
            node_repo = NodeRepository(session)
            sub_repo = SubscriptionRepository(session)
            
            client = await client_repo.get_by_id(client_id)
            if not client:
                raise ClientNotFoundError(str(client_id))
            
            if client.is_banned:
                raise BusinessRuleViolationError(
                    "Cannot create subscription for banned client",
                    rule="banned_no_subscription"
                )
            
            # Get or assign node
            if node_id:
                node = await node_repo.get_by_id(node_id)
                if not node:
                    raise NodeNotFoundError(str(node_id))
                if not node.is_active:
                    raise BusinessRuleViolationError(
                        "Selected node is not active",
                        rule="node_not_active"
                    )
            else:
                node = await self._assign_optimal_node(session, client)
                if not node:
                    raise BusinessRuleViolationError(
                        "No available nodes for subscription",
                        rule="no_available_nodes"
                    )
            
            # Calculate dates
            now = datetime.utcnow()
            starts_at = now
            ends_at = now + timedelta(days=duration_days)
            
            # Get plan details (in production, fetch from plans config)
            plan_config = settings.subscription_plans.get(plan_id)
            if not plan_config:
                raise ValidationError(f"Unknown plan: {plan_id}")
            
            traffic_limit_gb = plan_config.get("traffic_gb", settings.default_traffic_limit_gb)
            
            # Create subscription
            subscription = Subscription(
                client_id=client_id,
                node_id=node.id,
                plan_id=plan_id,
                status=SubscriptionStatus.PENDING,
                starts_at=starts_at,
                ends_at=ends_at,
                traffic_limit_bytes=traffic_limit_gb * 1024**3,
                traffic_used_bytes=0,
                payment_id=payment_id,
                promo_code=promo_code,
                auto_renew=plan_config.get("auto_renew", False),
                metadata={}
            )
            
            await sub_repo.add(subscription)
            
            # Update client expiry to match subscription
            client.expiry_date = ends_at
            if client.status == ClientStatus.EXPIRED:
                client.status = ClientStatus.ACTIVE
            await client_repo.update(client)
            
            await session.commit()
            await session.refresh(subscription)
            
            # Provision on panel
            try:
                await self._provision_subscription_on_panel(subscription, client, node)
                subscription.status = SubscriptionStatus.ACTIVE
                await sub_repo.update(subscription)
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to provision subscription {subscription.id}: {e}")
                subscription.status = SubscriptionStatus.FAILED
                subscription.failure_reason = str(e)
                await sub_repo.update(subscription)
                await session.commit()
                raise PanelOperationError(f"Failed to provision VPN: {e}")
            
            logger.info(f"Created subscription {subscription.id} for client {client_id}")
            
            await self._notification_service.send_subscription_created(client, subscription)
            
            return subscription

    async def renew_subscription(
        self,
        subscription_id: UUID,
        duration_days: int,
        payment_id: Optional[UUID] = None,
        promo_code: Optional[str] = None,
    ) -> Subscription:
        """
        Renew an existing subscription.
        
        Args:
            subscription_id: Subscription UUID
            duration_days: Additional days to add
            payment_id: Optional associated payment
            promo_code: Optional promo code
            
        Returns:
            Updated Subscription instance
        """
        async with self._session_factory() as session:
            sub_repo = SubscriptionRepository(session)
            client_repo = ClientRepository(session)
            
            subscription = await sub_repo.get_by_id(subscription_id)
            if not subscription:
                raise SubscriptionNotFoundError(str(subscription_id))
            
            client = await client_repo.get_by_id(subscription.client_id)
            if not client:
                raise ClientNotFoundError(str(subscription.client_id))
            
            if client.is_banned:
                raise BusinessRuleViolationError(
                    "Cannot renew subscription for banned client",
                    rule="banned_no_renewal"
                )
            
            # Extend subscription
            new_ends_at = (subscription.ends_at or datetime.utcnow()) + timedelta(days=duration_days)
            subscription.ends_at = new_ends_at
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.renewal_count += 1
            subscription.last_renewed_at = datetime.utcnow()
            subscription.last_payment_id = payment_id
            if promo_code:
                subscription.promo_code = promo_code
            
            # Update client expiry
            client.expiry_date = new_ends_at
            if client.status == ClientStatus.EXPIRED:
                client.status = ClientStatus.ACTIVE
            await client_repo.update(client)
            
            # Update panel with new expiry
            node_repo = NodeRepository(session)
            node = await node_repo.get_by_id(subscription.node_id)
            if node:
                panel = self._panel_factory.create(node.panel_type, node.panel_url, node.panel_username, node.panel_password)
                await panel.update_client_expiry(subscription.panel_client_id, new_ends_at)
            
            await sub_repo.update(subscription)
            await session.commit()
            await session.refresh(subscription)
            
            logger.info(f"Renewed subscription {subscription_id} for {duration_days} days")
            
            await self._notification_service.send_renewal_notice(client, subscription)
            
            return subscription

    async def cancel_subscription(
        self,
        subscription_id: UUID,
        reason: str = "Cancelled by user",
        admin_id: Optional[UUID] = None,
    ) -> Subscription:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Subscription UUID
            reason: Cancellation reason
            admin_id: Optional admin who performed the action
            
        Returns:
            Updated Subscription instance
        """
        async with self._session_factory() as session:
            sub_repo = SubscriptionRepository(session)
            client_repo = ClientRepository(session)
            
            subscription = await sub_repo.get_by_id(subscription_id)
            if not subscription:
                raise SubscriptionNotFoundError(str(subscription_id))
            
            client = await client_repo.get_by_id(subscription.client_id)
            
            # Disable on panel
            if subscription.panel_client_id:
                node_repo = NodeRepository(session)
                node = await node_repo.get_by_id(subscription.node_id)
                if node:
                    panel = self._panel_factory.create(node.panel_type, node.panel_url, node.panel_username, node.panel_password)
                    await panel.disable_client(subscription.panel_client_id)
            
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancelled_at = datetime.utcnow()
            subscription.cancellation_reason = reason
            subscription.cancelled_by = admin_id
            
            await sub_repo.update(subscription)
            
            # Check if client has other active subscriptions
            active_subs = await sub_repo.get_active_by_client(client.id)
            if not active_subs:
                client.status = ClientStatus.EXPIRED
                await client_repo.update(client)
            
            await session.commit()
            await session.refresh(subscription)
            
            logger.info(f"Cancelled subscription {subscription_id}: {reason}")
            
            if client:
                await self._notification_service.send_cancellation_notice(client, subscription, reason)
            
            return subscription

    # ==================== Traffic Management ====================

    async def add_traffic(
        self,
        client_id: UUID,
        additional_gb: float,
        admin_id: Optional[UUID] = None,
        reason: str = "Manual traffic addition",
    ) -> Client:
        """
        Add traffic quota to a client.
        
        Args:
            client_id: Client UUID
            additional_gb: GB to add
            admin_id: Optional admin who performed the action
            reason: Reason for addition
            
        Returns:
            Updated Client instance
        """
        async with self._session_factory() as session