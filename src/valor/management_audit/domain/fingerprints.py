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
