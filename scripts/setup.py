"""Generate local credentials without overwriting existing secrets."""

import hashlib
import json
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / "runtime" / "credentials.json"
p.parent.mkdir(exist_ok=True)
(root / "runtime" / "state").mkdir(exist_ok=True)
if p.exists():
    print("Existing credentials preserved:", p)
else:
    values = {
        role: secrets.token_urlsafe(32) for role in ("analyst", "responder", "reviewer")
    }
    fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(values, f, indent=2)
    print("Created local credentials:", p)
print(
    "Open this local file to copy the appropriate token into the dashboard. Do not share or commit it."
)

values = json.loads(p.read_text())
hash_path = p.with_name("token-hashes.json")
hash_path.write_text(
    json.dumps(
        {
            role: hashlib.sha256(token.encode()).hexdigest()
            for role, token in values.items()
        },
        indent=2,
    )
)
# High-entropy tokens stay private; the gateway only needs verifier hashes.
hash_path.chmod(0o644)
print(
    "Gateway verifier hashes refreshed; bearer tokens remain in the private credentials file."
)
