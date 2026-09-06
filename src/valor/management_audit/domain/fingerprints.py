from hashlib import sha256
from uuid import UUID


def agent_model_permission_fingerprint(
    *, tenant_id: UUID, agent_id: UUID, model_id: UUID, effect: str
) -> str:
    canonical = "\n".join(
        (
            f"tenant_id={tenant_id}",
            f"agent_id={agent_id}",
            f"model_id={model_id}",
            f"effect={effect.strip().lower()}",
        )
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def management_principal_fingerprint(
    *,
    principal_id: UUID,
    display_name: str,
    tenant_ids: frozenset[UUID],
    can_manage_principals: bool,
    disabled: bool,
) -> str:
    canonical = "\n".join(
        (
            f"principal_id={principal_id}",
            f"display_name={' '.join(display_name.split())}",
            f"tenant_ids={','.join(str(value) for value in sorted(tenant_ids))}",
            f"can_manage_principals={str(can_manage_principals).lower()}",
            f"disabled={str(disabled).lower()}",
        )
    )
    return sha256(canonical.encode()).hexdigest()


def management_credential_fingerprint(
    *,
    credential_id: UUID,
    principal_id: UUID,
    label: str | None,
    created_at: str,
    expires_at: str | None,
    revoked: bool,
) -> str:
    canonical = "\n".join(
        (
            f"credential_id={credential_id}",
            f"principal_id={principal_id}",
            f"label={'' if label is None else ' '.join(label.split())}",
            f"created_at={created_at}",
            f"expires_at={expires_at or ''}",
            f"revoked={str(revoked).lower()}",
        )
    )
    return sha256(canonical.encode()).hexdigest()
