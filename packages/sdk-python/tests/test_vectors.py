import json
from hashlib import sha256
from pathlib import Path

from limiq_sdk.canonical import canonicalize


def test_shared_verify_vectors_match_python_sdk() -> None:
    vectors_dir = Path(__file__).resolve().parents[3] / "shared-test-vectors" / "verify"
    vector_files = sorted(vectors_dir.glob("*.json"))
    assert vector_files

    for vector_file in vector_files:
        vector = json.loads(vector_file.read_text(encoding="utf-8"))
        canonical = canonicalize(vector["input"])
        digest = sha256(canonical.encode("utf-8")).hexdigest()

        assert canonical == vector["expected"]["canonical_json"]
        assert digest == vector["expected"]["sha256_hex"]
