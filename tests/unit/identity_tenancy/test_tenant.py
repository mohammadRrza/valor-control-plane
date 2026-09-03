from datetime import UTC, datetime
from uuid import UUID

import pytest

from valor.identity_tenancy.domain.errors import InvalidTenantName
from valor.identity_tenancy.domain.tenant import Tenant, TenantId, TenantName

TENANT_ID = TenantId(UUID("11111111-1111-4111-8111-111111111111"))
CREATED_AT = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


def test_tenant_creation_canonicalizes_name() -> None:
    tenant = Tenant.create(TENANT_ID, "  Acme   Research  ", CREATED_AT)
    assert tenant.name.value == "Acme Research"
    assert tenant.name.normalized == "acme research"
    assert tenant.created_at == CREATED_AT


@pytest.mark.parametrize("name", ["", " ", "\t\n"])
def test_tenant_name_rejects_empty_content(name: str) -> None:
    with pytest.raises(InvalidTenantName, match="must not be empty"):
        TenantName(name)


def test_tenant_name_rejects_more_than_one_hundred_canonical_characters() -> None:
    with pytest.raises(InvalidTenantName, match="at most 100"):
        TenantName("a" * 101)


def test_tenant_requires_timezone_aware_creation_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Tenant.create(TENANT_ID, "Acme", datetime(2026, 1, 2))
