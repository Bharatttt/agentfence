"""Password verifiers for local accounts (also usable by Python 3.9 setup)."""
import hashlib
import hmac
import secrets


def password_record(password):
    salt = secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return {"salt": salt.hex(), "hash": value.hex()}


def verify_password(password, record):
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(record["salt"]),
                           n=16384, r=8, p=1)
    return hmac.compare_digest(value.hex(), record["hash"])
