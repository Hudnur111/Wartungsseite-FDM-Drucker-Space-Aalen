from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from . import config


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def session_expiry_iso() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=config.SESSION_DAYS)).replace(microsecond=0).isoformat()


def normalize_email(value: str) -> str:
    return value.strip().lower()


def hash_secret(secret: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, config.PASSWORD_ITERATIONS)
    return "pbkdf2_sha256$%d$%s$%s" % (config.PASSWORD_ITERATIONS, salt.hex(), digest.hex())


def verify_secret(secret: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def hash_password(password: str) -> str:
    return hash_secret(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return verify_secret(password, stored_hash)


def new_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def env_or_file_team_code() -> str:
    env_code = os.environ.get("TEAMLEITER_CODE", "").strip()
    if env_code:
        return env_code
    if config.TEAM_CODE_FILE.exists():
        return config.TEAM_CODE_FILE.read_text(encoding="utf-8").strip()
    return ""


def safe_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def allowed_role(role: str) -> bool:
    return role in config.ROLES


def is_admin(user: dict | None) -> bool:
    return bool(user and user.get("role") == config.ADMIN_ROLE)


def is_mentor_or_admin(user: dict | None) -> bool:
    return bool(user and user.get("role") in {config.ADMIN_ROLE, config.MENTOR_ROLE})


def can_log_level(user: dict | None, level: str) -> bool:
    if not user:
        return False
    role = user.get("role")
    if role in {config.ADMIN_ROLE, config.MENTOR_ROLE}:
        return True
    return level == "B"

