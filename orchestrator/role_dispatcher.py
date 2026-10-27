# orchestrator/role_dispatcher.py
"""
Role Dispatcher Module

Provides intelligent routing of requests to specialized role handlers.
Each role encapsulates domain-specific logic, prompts, and behaviors.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Type

logger = logging.getLogger(__name__)


class RoleType(Enum):
    """Enumeration of supported role types."""
    SALES = "sales"
    DEV = "dev"
    SUPPORT = "support"
    FINANCE = "finance"
    CEO = "ceo"


@dataclass
class RoleContext:
    """Context passed to role handlers for request processing."""
    user_id: str
    session_id: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    user_tier: str = "standard"  # standard, premium, enterprise
    language: str = "en"


@dataclass
class RoleResponse:
    """Standardized response from a role handler."""
    content: str
    role: RoleType
    confidence: float = 1.0
    suggested_actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    escalate: bool = False
    escalation_reason: Optional[str] = None


class RoleHandler(Protocol):
    """Protocol defining the interface for role handlers."""
    
    def handle(self, context: RoleContext) -> RoleResponse:
        """Process the request and return a response."""
        ...
    
    def can_handle(self, context: RoleContext) -> float:
        """Return confidence score (0.0-1.0) for handling this request."""
        ...
    
    @property
    def role_type(self) -> RoleType:
        """Return the role type this handler represents."""
        ...


class BaseRoleHandler(ABC):
    """Abstract base class for role handlers with common functionality."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._system_prompt = self._build_system_prompt()
    
    @property
    @abstractmethod
    def role_type(self) -> RoleType:
        pass
    
    @abstractmethod
    def _build_system_prompt(self) -> str:
        """Build the system prompt for this role."""
        pass
    
    @abstractmethod
    def _get_keywords(self) -> List[str]:
        """Return keywords that indicate this role should handle the request."""
        pass
    
    def can_handle(self, context: RoleContext) -> float:
        """Calculate confidence based on keyword matching."""
        message_lower = context.message.lower()
        keywords = self._get_keywords()
        
        if not keywords:
            return 0.0
        
        matches = sum(1 for kw in keywords if kw.lower() in message_lower)
        base_confidence = matches / len(keywords)
        
        # Boost confidence for explicit role mentions
        role_mentions = [
            f"as a {self.role_type.value}",
            f"speak to {self.role_type.value}",
            f"talk to {self.role_type.value}",
            f"{self.role_type.value} team",
            f"{self.role_type.value} department",
        ]
        if any(mention in message_lower for mention in role_mentions):
            base_confidence = min(1.0, base_confidence + 0.3)
        
        return min(1.0, base_confidence)
    
    def handle(self, context: RoleContext) -> RoleResponse:
        """Main entry point for handling requests."""
        logger.debug(f"{self.role_type.value} handler processing request for user {context.user_id}")
        
        try:
            response_content = self._process_request(context)
            return RoleResponse(
                content=response_content,
                role=self.role_type,
                confidence=self.can_handle(context),
                suggested_actions=self._get_suggested_actions(context),
                metadata={"handler": self.role_type.value}
            )
        except Exception as e:
            logger.error(f"Error in {self.role_type.value} handler: {e}", exc_info=True)
            return RoleResponse(
                content=f"I apologize, but I encountered an issue processing your request. Please try again or contact support if the problem persists.",
                role=self.role_type,
                confidence=0.0,
                escalate=True,
                escalation_reason=f"Handler error: {str(e)}"
            )
    
    @abstractmethod
    def _process_request(self, context: RoleContext) -> str:
        """Process the request and generate response content."""
        pass
    
    def _get_suggested_actions(self, context: RoleContext) -> List[str]:
        """Return suggested follow-up actions."""
        return []


class SalesHandler(BaseRoleHandler):
    """Handles sales-related inquiries: pricing, demos, trials, upgrades."""
    
    @property
    def role_type(self) -> RoleType:
        return RoleType.SALES
    
    def _build_system_prompt(self) -> str:
        return """You are a knowledgeable Sales Representative for our platform.
Your goals:
- Understand customer needs and match them with appropriate solutions
- Provide clear pricing information and value propositions
- Schedule demos and trials when appropriate
- Identify upsell/cross-sell opportunities
- Be consultative, not pushy
- Always mention next steps clearly

Key information:
- Starter: $29/mo - up to 5 users, basic features
- Professional: $99/mo - up to 25 users, advanced analytics, integrations
- Enterprise: Custom pricing - unlimited users, SSO, dedicated support, SLA
- 14-day free trial available on all plans
- Annual billing saves 20%"""
    
    def _get_keywords(self) -> List[str]:
        return [
            "price", "pricing", "cost", "plan", "subscription", "billing",
            "demo", "trial", "demo", "try", "evaluate", "test",
            "upgrade", "downgrade", "renew", "cancel", "contract",
            "purchase", "buy", "quote", "proposal", "discount",
            "enterprise", "team", "users", "seats", "license",
            "sales", "account executive", "rep", "representative"
        ]
    
    def _process_request(self, context: RoleContext) -> str:
        message = context.message.lower()
        
        if any(kw in message for kw in ["price", "pricing", "cost", "how much"]):
            return self._handle_pricing_inquiry(context)
        elif any(kw in message for kw in ["demo", "trial", "try", "test"]):
            return self._handle_demo_trial_request(context)
        elif any(kw in message for kw in ["upgrade", "downgrade", "change plan"]):
            return self._handle_plan_change(context)
        elif any(kw in message for kw in ["enterprise", "custom", "sso", "sla"]):
            return self._handle_enterprise_inquiry(context)
        else:
            return self._handle_general_sales(context)
    
    def _handle_pricing_inquiry(self, context: RoleContext) -> str:
        tier_info = {
            "standard": "Our **Starter plan at $29/month** (or $278/year with 20% discount) includes up to 5 users and core features.",
            "premium": "Our **Professional plan at $99/month** (or $950/year) supports up to 25 users with advanced analytics and integrations.",
            "enterprise": "For **Enterprise**, we offer custom pricing with unlimited users, SSO, dedicated support, and SLA guarantees."
        }
        current = tier_info.get(context.user_tier, tier_info["standard"])
        
        return f"""{current}

**All plans include:** 14-day free trial, no credit card required.

Would you like me to:
1. Start a free trial for you?
2. Schedule a personalized demo?
3. Discuss which plan best fits your needs?

Just let me know your team size and primary use case, and I'll recommend the best fit."""
    
    def _handle_demo_trial_request(self, context: RoleContext) -> str:
        return """I'd be happy to set that up for you!

**Free Trial (14 days, no credit card):**
- Full access to all Professional features
- Up to 25 team members can join
- Dedicated onboarding support

**Live Demo (30 minutes):**
- Tailored to your use case
- Q&A with a product specialist
- See advanced features in action

Which would you prefer? If you'd like a demo, what days/times work best for you (and your timezone)?"""
    
    def _handle_plan_change(self, context: RoleContext) -> str:
        return """I can help you change your plan. A few quick questions:

1. **Current plan:** What plan are you on now?
2. **Target plan:** Starter ($29/mo), Professional ($99/mo), or Enterprise (custom)?
3. **Timing:** Immediate switch or at next billing cycle?
4. **Team size:** How many users will need access?

**Note:** Upgrades take effect immediately with prorated billing. Downgrades apply at the next billing cycle to avoid service disruption.

Would you like me to process this change, or do you have questions about the differences between plans?"""
    
    def _handle_enterprise_inquiry(self, context: RoleContext) -> str:
        return """Enterprise is our most comprehensive tier, designed for organizations with advanced requirements:

**Enterprise includes:**
- Unlimited users & workspaces
- SSO (SAML/OIDC) & SCIM provisioning
- 99.9% uptime SLA with credits
- Dedicated Customer Success Manager
- Custom contract terms & billing
- Advanced security & compliance (SOC2, HIPAA options)
- Priority support with 1-hour response time
- Professional services & custom integrations

**Next steps:**
1. Discovery call to understand your requirements
2. Custom proposal with pricing
3. Security review & legal review
4. Pilot program (typically 30-60 days)

What's driving your interest in Enterprise? (Team growth, compliance needs, security requirements, etc.)"""
    
    def _handle_general_sales(self, context: RoleContext) -> str:
        return """I'm here to help with any sales questions! Whether you're:
- Exploring our platform for the first time
- Comparing plans and features
- Ready to start a trial or schedule a demo
- Need a custom quote for your team

What can I help you with today?"""
    
    def _get_suggested_actions(self, context: RoleContext) -> List[str]:
        return [
            "Start free trial",
            "Schedule demo",
            "View pricing page",
            "Contact sales team",
            "Request enterprise quote"
        ]


class DevHandler(BaseRoleHandler):
    """Handles technical/development inquiries: APIs, SDKs, integrations, debugging."""
    
    @property
    def role_type(self) -> RoleType:
        return RoleType.DEV
    
    def _build_system_prompt(self) -> str:
        return """You are a Senior Developer Advocate / Technical Support Engineer.
Your expertise:
- REST APIs, GraphQL, Webhooks
- SDKs: Python, JavaScript/TypeScript, Go, Java
- Authentication: OAuth2, JWT, API Keys
- Webhooks, event streaming, real-time features
- Debugging: error codes, rate limits, latency
- CI/CD integration, deployment, infrastructure

Style: Technical, precise, code-first. Provide snippets, links to docs, and actionable debugging steps."""
    
    def _get_keywords(self) -> List[str]:
        return [
            "api", "endpoint", "rest", "graphql", "webhook",
            "sdk", "library", "package", "npm", "pip", "maven", "go get",
            "auth", "authentication", "oauth", "jwt", "token", "api key",
            "error", "exception", "bug", "issue", "fail", "timeout", "429", "500", "401",
            "rate limit", "throttle", "quota",
            "integrate", "integration", "webhook", "callback",
            "deploy", "deployment", "ci/cd", "pipeline", "docker", "kubernetes",
            "documentation", "docs", "reference", "schema", "openapi", "swagger",
            "python", "javascript", "typescript", "go", "java", "node",
            "sandbox", "test", "mock", "staging", "production"
        ]
    
    def _process_request(self, context: RoleContext) -> str:
        message = context.message.lower()
        
        if any(kw in message for kw in ["api", "endpoint", "rest", "graphql"]):
            return self._handle_api_inquiry(context)
        elif any(kw in message for kw in ["sdk", "library", "install", "import"]):
            return self._handle_sdk_question(context)
        elif any(kw in message for kw in ["auth", "oauth", "token", "jwt", "api key"]):
            return self._handle_auth_question(context)
        elif any(kw in message for kw in ["error", "exception", "bug", "fail", "429", "500", "401"]):
            return self._handle_debugging(context)
        elif any(kw in message for kw in ["webhook", "event", "callback", "stream"]):
            return self._handle_webhooks(context)
        else:
            return self._handle_general_dev(context)
    
    def _handle_api_inquiry(self, context: RoleContext) -> str:
        return """**API Reference:** https://docs.example.com/api/reference

**Base URL:** `https://api.example.com/v1`

**Authentication:** Bearer token (OAuth2) or API Key header

```bash
# Example: List resources
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://api.example.com/v1/resources
```

**Key endpoints:**
- `GET /v1/resources` - List with pagination (`?page=1&limit=50`)
- `POST /v1/resources` - Create new
- `GET /v1/resources/{id}` - Get by ID
- `PATCH /v1/resources/{id}` - Partial update
- `DELETE /v1/resources/{id}` - Delete

**Rate limits:** 1000 req/min (Standard), 5000 req/min (Pro), Custom (Enterprise)

What specific endpoint or operation are you working with?"""
    
    def _handle_sdk_question(self, context: RoleContext) -> str:
        return """**Official SDKs:**

| Language | Package | Install Command |
|----------|---------|-----------------|
| Python | `example-sdk` | `pip install example-sdk` |
| JavaScript/TS | `@example/sdk` | `npm install @example/sdk` |
| Go | `github.com/example/go-sdk` | `go get github.com/example/go-sdk` |
| Java | `com.example:sdk` | Maven/Gradle |

**Quick start (Python):**
```python
from example_sdk import Client

client = Client(api_key="sk_live_...")
resources = client.resources.list(limit=10)
for r in resources:
    print(r.name, r.id)
```

**TypeScript:**
```typescript
import { ExampleClient } from '@example/sdk';

const client = new ExampleClient({ apiKey: 'sk_live_...' });
const resources = await client.resources.list({ limit: 10 });
```

Which language are you using? I can share more specific examples.""" 
    
    def _handle_auth_question(self, context: RoleContext) -> str:
        return """**Authentication Methods:**

1. **API Keys** (simplest, server-to-server)
   ```bash
   curl -H "X-API-Key: sk_live_..." https://api.example.com/v1/resources
   ```

2. **OAuth2 / Bearer Tokens** (user-facing apps)
   - Authorization Code flow for web apps
   - PKCE for SPAs/mobile
   - Client Credentials for machine-to-machine

3. **JWT** (for service-to-service with short-lived tokens)

**Common issues:**
- `401 Unauthorized`: Token expired or invalid → Refresh or regenerate
- `403 Forbidden`: Valid token but insufficient scopes → Check permissions
- `429 Too Many Requests`: Rate limited → Implement exponential backoff

**Token refresh:**
```python
# Python SDK handles auto-refresh
client = Client(client_id="...", client_secret="...")
# Token refreshed automatically on 401
```

What auth flow are you implementing?"""
    
    def _handle_debugging(self, context: RoleContext) -> str:
        message = context.message
        # Extract error codes if present
        import re
        error_codes = re.findall(r'\b(4\d{2}|5\d{2})\b', message)
        
        response = """**Debugging Checklist:**

1. **Check the error response body** - It usually contains:
   ```json
   {
     "error": {
       "code": "RATE_LIMIT_EXCEEDED",
       "message": "Too