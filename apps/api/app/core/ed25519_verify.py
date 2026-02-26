import base64
import logging

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

logger = logging.getLogger("kya.ed25519")


def verify_ed25519_signature(
    *,
    public_key_b64: str,
    message: bytes,
    signature_b64: str,
) -> bool:
    try:
        public_key = base64.b64decode(public_key_b64, validate=True)
        signature = base64.b64decode(signature_b64, validate=True)
        VerifyKey(public_key).verify(message, signature)
        return True
    except BadSignatureError:
        # Normal invalid signature path.
        return False
    except ValueError:
        # Likely malformed key/signature inputs.
        logger.warning("invalid_input_in_ed25519_verify", exc_info=True)
        return False
    except Exception:
        logger.warning("unexpected_error_in_ed25519_verify", exc_info=True)
        return False
