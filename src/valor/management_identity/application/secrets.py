import hmac
import secrets
from hashlib import sha256
from uuid import UUID

BEARER_PREFIX = "valor_mgmt"


def generate_bearer_token(credential_id: UUID) -> tuple[str, str]:
    secret = secrets.token_urlsafe(32)
    return f"{BEARER_PREFIX}_{credential_id}_{secret}", secret


def parse_bearer_token(token: str) -> tuple[UUID, str] | None:
    prefix = f"{BEARER_PREFIX}_"
    if not token.startswith(prefix):
        return None
    value = token[len(prefix) :]
    credential_text, separator, secret = value.partition("_")
    if not separator or not secret:
        return None
    try:
        return UUID(credential_text), secret
    except ValueError:
        return None


def secret_verifier(secret: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), secret.encode(), sha256).hexdigest()


def verifier_matches(secret: str, pepper: str, expected: str) -> bool:
    return hmac.compare_digest(secret_verifier(secret, pepper), expected)
