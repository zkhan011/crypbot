"""Authenticated control-plane services for the local MOCK deployment.

The in-memory implementation is deliberately restricted to demonstration and
test environments.  It keeps the authorization, audit, and AI-draft rules in
one place so a database-backed repository can replace it without changing API
authorization semantics.  It is not a substitute for durable production
identity storage or a production secret manager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from secrets import token_urlsafe
from typing import Literal
from uuid import uuid4

from app.core.security import hash_password, verify_password
from app.services.durable_security import AuditHashChain


class Role(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    TRADER = "TRADER"
    VIEWER = "VIEWER"


class AuthorizationError(PermissionError):
    """Raised when a caller is not allowed to perform a control-plane action."""


class AuthenticationError(PermissionError):
    """Raised for an invalid, expired, or locked demonstration session."""


ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.SUPER_ADMIN: frozenset({"users:manage", "bots:control", "ai:request", "ai:approve", "audit:read"}),
    Role.ADMIN: frozenset({"users:create", "bots:control", "ai:request", "ai:approve", "audit:read"}),
    Role.TRADER: frozenset({"bots:view", "bots:control", "ai:request"}),
    Role.VIEWER: frozenset({"bots:view"}),
}


@dataclass
class User:
    id: str
    email: str
    display_name: str
    role: Role
    password_hash: str
    active: bool = True
    failed_logins: int = 0
    locked_until: datetime | None = None
    last_login_at: datetime | None = None
    force_password_change: bool = False

    def public(self) -> dict[str, object]:
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role.value,
            "active": self.active,
            "failed_logins": self.failed_logins,
            "locked": self.locked_until is not None and self.locked_until > datetime.now(UTC),
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "force_password_change": self.force_password_change,
        }


@dataclass(frozen=True)
class Session:
    token: str
    user_id: str
    expires_at: datetime


@dataclass(frozen=True)
class AuditRecord:
    id: str
    timestamp: datetime
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str
    outcome: str
    detail: str

    def public(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "outcome": self.outcome,
            "detail": self.detail,
        }


@dataclass
class StrategyDraft:
    id: str
    prompt: str
    strategy_name: str
    strategy_type: Literal["COPY", "VOLUME", "HYBRID"]
    description: str
    allowed_pairs: list[str]
    leverage: str
    max_daily_loss: str
    max_drawdown: str
    stop_loss: str
    take_profit: str
    required_mock_scenarios: list[str]
    risk_explanation: str
    activation_status: Literal["DRAFT", "APPROVED", "REJECTED", "ACTIVE"] = "DRAFT"
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def public(self) -> dict[str, object]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "strategyName": self.strategy_name,
            "strategyType": self.strategy_type,
            "description": self.description,
            "allowedPairs": self.allowed_pairs,
            "timeframe": "5m",
            "entryRules": ["volume above moving average", "confirmed directional candle"],
            "exitRules": ["stop-loss", "take-profit", "trailing stop"],
            "riskRules": ["shared hard risk limits always apply"],
            "stopLoss": self.stop_loss,
            "takeProfit": self.take_profit,
            "trailingStop": "1.0%",
            "leverage": self.leverage,
            "maxDailyLoss": self.max_daily_loss,
            "maxDrawdown": self.max_drawdown,
            "copyFilters": ["avoid high leverage signals"],
            "volumeFilters": ["minimum liquidity", "maximum spread"],
            "conflictRules": "REJECT_NEW_SIGNAL",
            "requiredMockScenarios": self.required_mock_scenarios,
            "riskExplanation": self.risk_explanation,
            "activationStatus": self.activation_status,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat(),
        }


class MockAIProviderAdapter:
    """Deterministic, non-executing strategy assistant for mock demonstrations."""

    def create_draft(self, prompt: str, actor_id: str) -> StrategyDraft:
        normalized = prompt.lower()
        risky = "aggressive" in normalized or "risky" in normalized
        strategy_type: Literal["COPY", "VOLUME", "HYBRID"] = (
            "HYBRID" if "hybrid" in normalized else ("COPY" if "copy" in normalized else "VOLUME")
        )
        return StrategyDraft(
            id=str(uuid4()),
            prompt=prompt,
            strategy_name="Mock conservative momentum draft" if not risky else "Mock risky draft for rejection testing",
            strategy_type=strategy_type,
            description="A draft only. It cannot submit orders until authorized approval and mock validation are complete.",
            allowed_pairs=["BTC-USDT", "ETH-USDT"],
            leverage="2" if not risky else "50",
            max_daily_loss="2%" if not risky else "20%",
            max_drawdown="8%" if not risky else "40%",
            stop_loss="1.0%" if not risky else "0%",
            take_profit="2.0%",
            required_mock_scenarios=["BULLISH_VOLUME_BREAKOUT", "HIGH_SPREAD_NO_TRADE", "STOP_LOSS_HIT"],
            risk_explanation=(
                "Conservative values are proposed; shared hard risk rules still validate activation."
                if not risky
                else "Intentionally unsafe values demonstrate validation rejection; this draft cannot be activated."
            ),
            created_by=actor_id,
        )


class ControlPlane:
    """In-memory authenticated control plane used only by the runnable MOCK demo."""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.sessions: dict[str, Session] = {}
        self.audit_records: list[AuditRecord] = []
        self.audit_chain = AuditHashChain()
        self.drafts: dict[str, StrategyDraft] = {}
        self.ai_provider = MockAIProviderAdapter()
        self._seed_users()

    def _seed_users(self) -> None:
        for email, name, role in (
            ("superadmin@example.local", "Demo Super Admin", Role.SUPER_ADMIN),
            ("admin@example.local", "Demo Admin", Role.ADMIN),
            ("trader@example.local", "Demo Trader", Role.TRADER),
            ("viewer@example.local", "Demo Viewer", Role.VIEWER),
        ):
            user = User(str(uuid4()), email, name, role, hash_password("ChangeMe123!"), force_password_change=True)
            self.users[user.id] = user

    def audit(self, actor_id: str | None, action: str, resource_type: str, resource_id: str, outcome: str, detail: str) -> None:
        record = AuditRecord(str(uuid4()), datetime.now(UTC), actor_id, action, resource_type, resource_id, outcome, detail)
        self.audit_records.append(record)
        self.audit_chain.append(record.public())

    def authenticate(self, email: str, password: str) -> tuple[str, User]:
        user = next((candidate for candidate in self.users.values() if candidate.email.lower() == email.lower()), None)
        now = datetime.now(UTC)
        if user is None or not user.active:
            self.audit(None, "LOGIN_FAILED", "user", email, "DENIED", "Unknown or inactive user")
            raise AuthenticationError("invalid credentials")
        if user.locked_until and user.locked_until > now:
            self.audit(user.id, "LOGIN_FAILED", "user", user.id, "DENIED", "Account is temporarily locked")
            raise AuthenticationError("account locked")
        if not verify_password(password, user.password_hash):
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = now + timedelta(minutes=15)
            self.audit(user.id, "LOGIN_FAILED", "user", user.id, "DENIED", "Invalid password")
            raise AuthenticationError("invalid credentials")
        user.failed_logins = 0
        user.locked_until = None
        user.last_login_at = now
        token = token_urlsafe(32)
        self.sessions[token] = Session(token, user.id, now + timedelta(hours=8))
        self.audit(user.id, "LOGIN_SUCCEEDED", "session", user.id, "SUCCESS", "Demo session issued")
        return token, user

    def session_user(self, token: str | None) -> User:
        session = self.sessions.get(token or "")
        if session is None or session.expires_at <= datetime.now(UTC):
            raise AuthenticationError("invalid or expired session")
        user = self.users[session.user_id]
        if not user.active:
            raise AuthenticationError("user is inactive")
        return user

    def require(self, user: User, permission: str) -> None:
        if permission not in ROLE_PERMISSIONS[user.role]:
            self.audit(user.id, "AUTHORIZATION_DENIED", "permission", permission, "DENIED", f"Role {user.role.value} lacks permission")
            raise AuthorizationError("insufficient permission")

    def list_users(self, actor: User) -> list[dict[str, object]]:
        self.require(actor, "users:manage")
        return [user.public() for user in self.users.values()]

    def create_user(self, actor: User, email: str, display_name: str, role: Role, password: str) -> dict[str, object]:
        if actor.role == Role.SUPER_ADMIN:
            self.require(actor, "users:manage")
        else:
            self.require(actor, "users:create")
            if role in {Role.SUPER_ADMIN, Role.ADMIN}:
                raise AuthorizationError("admins may only create trader or viewer accounts")
        if any(user.email.lower() == email.lower() for user in self.users.values()):
            raise ValueError("email already exists")
        user = User(str(uuid4()), email, display_name, role, hash_password(password), force_password_change=True)
        self.users[user.id] = user
        self.audit(actor.id, "USER_CREATED", "user", user.id, "SUCCESS", f"Created role {role.value}")
        return user.public()

    def request_ai_draft(self, actor: User, prompt: str) -> dict[str, object]:
        self.require(actor, "ai:request")
        draft = self.ai_provider.create_draft(prompt, actor.id)
        self.drafts[draft.id] = draft
        self.audit(actor.id, "AI_STRATEGY_GENERATED", "strategy_draft", draft.id, "SUCCESS", "Draft created; activation is blocked")
        return draft.public()

    def list_drafts(self, actor: User) -> list[dict[str, object]]:
        self.require(actor, "ai:request")
        return [draft.public() for draft in self.drafts.values()]

    def approve_draft(self, actor: User, draft_id: str) -> dict[str, object]:
        self.require(actor, "ai:approve")
        draft = self.drafts[draft_id]
        if draft.leverage == "50" or draft.stop_loss == "0%":
            draft.activation_status = "REJECTED"
            self.audit(actor.id, "AI_STRATEGY_REJECTED", "strategy_draft", draft_id, "DENIED", "Draft violates hard risk limits")
            raise ValueError("draft violates hard risk limits")
        draft.activation_status = "APPROVED"
        self.audit(actor.id, "AI_STRATEGY_APPROVED", "strategy_draft", draft_id, "SUCCESS", "Approved for mock validation only")
        return draft.public()

    def audit_log(self, actor: User) -> list[dict[str, str | None]]:
        self.require(actor, "audit:read")
        return [record.public() for record in reversed(self.audit_records[-100:])]

    def verify_audit_log(self, actor: User) -> dict[str, object]:
        self.require(actor, "audit:read")
        return {"valid": self.audit_chain.verify(), "entries": len(self.audit_records)}
