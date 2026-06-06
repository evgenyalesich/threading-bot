from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from app.core.settings import Settings
from app.services.telegram_service import TelegramService


@dataclass(slots=True)
class LoginCode:
    code_hash: str
    expires_at: float


class UiAuthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._codes: dict[str, LoginCode] = {}
        self._last_delivery_errors: dict[str, str] = {}

    def enabled(self) -> bool:
        return bool(self._settings.ui_auth_enabled)

    def _secret(self) -> bytes:
        secret = self._settings.ui_auth_secret or self._settings.telegram_bot_token or "dev-ui-auth-secret"
        return str(secret).encode("utf-8")

    def _chat_id(self) -> str:
        return str(self._settings.telegram_chat_id or "").strip()

    def _chat_ids(self) -> list[str]:
        return self._settings.telegram_allowed_chat_id_list()

    def _hash_code(self, code: str) -> str:
        return hmac.new(self._secret(), code.encode("utf-8"), hashlib.sha256).hexdigest()

    async def send_login_code(self) -> None:
        chat_ids = self._chat_ids()
        if not chat_ids:
            raise ValueError("telegram_chat_id_required")
        telegram = TelegramService(self._settings)
        expires_at = time.time() + 300
        sent = 0
        self._last_delivery_errors = {}
        for chat_id in chat_ids:
            code = f"{secrets.randbelow(1_000_000):06d}"
            self._codes[chat_id] = LoginCode(code_hash=self._hash_code(code), expires_at=expires_at)
            try:
                await telegram.send_message(
                    "Код входа в UI Threading Bot:\n"
                    f"{code}\n\n"
                    "Код живет 5 минут. Если это был не ты, просто игнорируй сообщение.",
                    chat_id=chat_id,
                )
                sent += 1
            except Exception as exc:
                self._last_delivery_errors[chat_id] = str(exc)[:180]
        if sent <= 0:
            raise ValueError("telegram_delivery_failed_for_all_allowed_chats")

    def last_delivery_errors(self) -> dict[str, str]:
        return dict(self._last_delivery_errors)

    def verify_code(self, code: str) -> bool:
        code_hash = self._hash_code(str(code).strip())
        for chat_id, entry in list(self._codes.items()):
            if entry.expires_at < time.time():
                self._codes.pop(chat_id, None)
                continue
            if hmac.compare_digest(entry.code_hash, code_hash):
                self._codes.pop(chat_id, None)
                return True
        return False

    def create_session_token(self) -> str:
        payload = {
            "scope": "telegram_allowed",
            "exp": int(time.time()) + 60 * 60 * 24 * 14,
            "nonce": secrets.token_hex(12),
        }
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        sig = hmac.new(self._secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{body}.{sig}"

    def verify_session_token(self, token: str | None) -> bool:
        if not token or "." not in token:
            return False
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(self._secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        try:
            padded = body + "=" * (-len(body) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        except Exception:
            return False
        legacy_chat_ok = payload.get("chat_id") in self._chat_ids()
        scope_ok = payload.get("scope") == "telegram_allowed"
        return (legacy_chat_ok or scope_ok) and int(payload.get("exp") or 0) >= int(time.time())


_ui_auth_service: UiAuthService | None = None


def get_ui_auth_service() -> UiAuthService:
    global _ui_auth_service
    if _ui_auth_service is None:
        _ui_auth_service = UiAuthService(Settings())
    return _ui_auth_service
