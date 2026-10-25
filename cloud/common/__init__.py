"""Small shared types for the serving code: session records, the provider error and content hashing."""
import hashlib
import json


class ProviderFailure(RuntimeError):
    def __init__(self, reason, telemetry=None):
        super().__init__(reason)
        self.telemetry = telemetry


def content_hash(value):
    """Canonical JSON SHA-256; unchanged, because ledger nonces and work hashes store its output."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()
