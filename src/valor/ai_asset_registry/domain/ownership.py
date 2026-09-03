"""Tenant ownership identity within the AI Asset Registry boundary."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OwningTenantId:
    """Local representation of tenant identity at the context boundary."""

    value: UUID
