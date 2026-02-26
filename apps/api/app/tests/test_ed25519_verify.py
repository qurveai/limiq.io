import base64
from hashlib import sha256

from nacl.signing import SigningKey

from app.core.ed25519_verify import verify_ed25519_signature


def test_verify_ed25519_signature_valid() -> None:
    keypair = SigningKey.generate()
    message = sha256(b"hello").digest()
    signature = keypair.sign(message).signature

    ok = verify_ed25519_signature(
        public_key_b64=base64.b64encode(bytes(keypair.verify_key)).decode(),
        message=message,
        signature_b64=base64.b64encode(signature).decode(),
    )

    assert ok is True


def test_verify_ed25519_signature_bad_signature_returns_false() -> None:
    keypair = SigningKey.generate()
    message = sha256(b"hello").digest()
    wrong_message = sha256(b"bye").digest()
    signature = keypair.sign(message).signature

    ok = verify_ed25519_signature(
        public_key_b64=base64.b64encode(bytes(keypair.verify_key)).decode(),
        message=wrong_message,
        signature_b64=base64.b64encode(signature).decode(),
    )

    assert ok is False


def test_verify_ed25519_signature_invalid_input_returns_false() -> None:
    ok = verify_ed25519_signature(
        public_key_b64="not-base64",
        message=b"msg",
        signature_b64="not-base64",
    )

    assert ok is False
