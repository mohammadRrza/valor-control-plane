"""Governed Agent identity aggregate and value objects."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from valor.ai_asset_registry.domain.errors import InvalidAgentName

MAX_AGENT_NAME_LENGTH = 100


@dataclass(frozen=True, slots=True)
class AgentId:
    value: UUID


@dataclass(frozen=True, slots=True)
class OwningTenantId:
    """Local representation of tenant identity at the context boundary."""

    value: UUID


@dataclass(frozen=True, slots=True)
class AgentName:
    value: str
    normalized: str = field(init=False)

    def __post_init__(self) -> None:
        canonical = " ".join(self.value.split())
        if not canonical:
            raise InvalidAgentName("Agent name must not be empty.")
        if len(canonical) > MAX_AGENT_NAME_LENGTH:
            raise InvalidAgentName(
                f"Agent name must be at most {MAX_AGENT_NAME_LENGTH} characters."
            )
        object.__setattr__(self, "value", canonical)
        object.__setattr__(self, "normalized", canonical.casefold())


@dataclass(frozen=True, slots=True)
class Agent:
    """A governed workload identity; it contains no executable agent runtime."""

    id: AgentId
    tenant_id: OwningTenantId
    name: AgentName
    created_at: datetime

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("Agent registration time must be timezone-aware.")

    @classmethod
    def register(
        cls,
        agent_id: AgentId,
        tenant_id: OwningTenantId,
        name: str,
        created_at: datetime,
    ) -> "Agent":
        return cls(
            id=agent_id,
            tenant_id=tenant_id,
            name=AgentName(name),
            created_at=created_at,
        )
