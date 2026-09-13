import hmac
import secrets
from hashlib import sha256
from uuid import UUID


def generate_runtime_bearer_token(credential_id: UUID) -> tuple[str, str]:
    secret = secrets.token_urlsafe(32)
    return f"valor_runtime_{credential_id}_{secret}", secret


def runtime_secret_verifier(secret: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), secret.encode(), sha256).hexdigest()


def verify_runtime_secret(secret: str, pepper: str, expected_verifier: str) -> bool:
    return hmac.compare_digest(runtime_secret_verifier(secret, pepper), expected_verifier)
