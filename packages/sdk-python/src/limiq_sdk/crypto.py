import base64
import hashlib
import json
from collections.abc import Mapping
from typing import Any

from nacl.signing import SigningKey, VerifyKey

from limiq_sdk.canonical import canonicalize
from limiq_sdk.types import SignActionResult


def _b64_decode(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except Exception as exc:  # pragma: no cover
        raise ValueError("Invalid base64 input") from exc


def _b64_encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def generate_keys() -> dict[str, str]:
    signing_key = SigningKey.generate()
    seed32 = bytes(signing_key)
    public32 = bytes(signing_key.verify_key)
    private64 = seed32 + public32
    return {
        "public_key_base64": _b64_encode(public32),
        "private_key_base64": _b64_encode(private64),
    }


def sha256_hex(message: bytes) -> str:
    return hashlib.sha256(message).hexdigest()


def _signing_key_from_private64(private_key_base64: str) -> SigningKey:
    private_key = _b64_decode(private_key_base64)
    if len(private_key) != 64:
        raise ValueError("private_key_base64 must decode to 64 bytes")
    seed32 = private_key[:32]
    return SigningKey(seed32)


def sign_action(
    *,
    agent_id: str,
    workspace_id: str,
    action_type: str,
    target_service: str,
    payload: Mapping[str, Any],
    capability_jti: str,
    private_key_base64: str,
) -> SignActionResult:
    envelope: dict[str, Any] = {
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "action_type": action_type,
        "target_service": target_service,
        "payload": dict(payload),
        "capability_jti": capability_jti,
    }
    canonical_json = canonicalize(envelope)
    digest = hashlib.sha256(canonical_json.encode("utf-8")).digest()

    signing_key = _signing_key_from_private64(private_key_base64)
    signature = signing_key.sign(digest).signature

    return {
        "signature_base64": _b64_encode(signature),
        "canonical_json": canonical_json,
        "sha256_hex": digest.hex(),
    }


def verify_signature(*, public_key_base64: str, signature_base64: str, canonical_json: str) -> bool:
    try:
        public_key = _b64_decode(public_key_base64)
        signature = _b64_decode(signature_base64)
    except ValueError:
        return False

    if len(public_key) != 32 or len(signature) != 64:
        return False

    digest = hashlib.sha256(canonical_json.encode("utf-8")).digest()
    try:
        VerifyKey(public_key).verify(digest, signature)
        return True
    except Exception:
        return False


def extract_capability_jti(capability_token: str) -> str:
    parts = capability_token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid capability token format")

    payload_raw = parts[1]
    padding = "=" * ((4 - len(payload_raw) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_raw + padding).decode("utf-8")
        payload = json.loads(decoded)
    except Exception as exc:  # pragma: no cover
        raise ValueError("Invalid capability token payload") from exc

    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti:
        raise ValueError("Capability token has no valid jti")
    return jti
