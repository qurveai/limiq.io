import base64

from limiq_sdk.client import build_signed_request
from limiq_sdk.crypto import (
    extract_capability_jti,
    generate_keys,
    sign_action,
    verify_signature,
)


def _fake_token(jti: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').decode("ascii").rstrip("=")
    payload = (
        base64.urlsafe_b64encode(f'{{"jti":"{jti}"}}'.encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{header}.{payload}.sig"


def test_generate_keys_lengths() -> None:
    keys = generate_keys()
    assert len(base64.b64decode(keys["public_key_base64"], validate=True)) == 32
    assert len(base64.b64decode(keys["private_key_base64"], validate=True)) == 64


def test_sign_and_verify_signature() -> None:
    keys = generate_keys()
    signed = sign_action(
        agent_id="11111111-1111-1111-1111-111111111111",
        workspace_id="22222222-2222-2222-2222-222222222222",
        action_type="purchase",
        target_service="stripe_proxy",
        payload={"amount": 18, "currency": "EUR", "tool": "purchase"},
        capability_jti="33333333-3333-3333-3333-333333333333",
        private_key_base64=keys["private_key_base64"],
    )
    assert verify_signature(
        public_key_base64=keys["public_key_base64"],
        signature_base64=signed["signature_base64"],
        canonical_json=signed["canonical_json"],
    )


def test_extract_capability_jti() -> None:
    assert extract_capability_jti(_fake_token("jti-123")) == "jti-123"


def test_build_signed_request_shape() -> None:
    keys = generate_keys()
    request = build_signed_request(
        workspace_id="22222222-2222-2222-2222-222222222222",
        agent_id="11111111-1111-1111-1111-111111111111",
        action_type="purchase",
        target_service="stripe_proxy",
        payload={"amount": 18, "currency": "EUR", "tool": "purchase"},
        capability_token=_fake_token("jti-456"),
        private_key_base64=keys["private_key_base64"],
    )

    assert request["signature"]
    assert request["request_context"] == {}
