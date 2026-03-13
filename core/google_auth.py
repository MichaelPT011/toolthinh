"""Safe local account/profile storage used by the desktop app.

This module intentionally does not accept exported browser cookies or session
tokens. It stores local profiles that can later be mapped to a supported
backend such as an official API key or a demo backend.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from core.config import ACCOUNTS_FILE

logger = logging.getLogger(__name__)


class GoogleAuth:
    """Manage local backend profiles and round-robin account selection."""

    def __init__(self) -> None:
        self._accounts: list[dict] = self._load_accounts()
        self._rotation_index = 0

    def add_account(
        self,
        nickname: str,
        api_key: str = "",
        email: str = "",
        user_name: str = "",
        proxy: str | None = None,
        notes: str = "",
    ) -> dict:
        account = {
            "account_id": str(uuid.uuid4()),
            "nickname": nickname.strip() or f"Profile {len(self._accounts) + 1}",
            "api_key": api_key.strip() or None,
            "status": "active",
            "proxy": proxy.strip() if proxy else None,
            "credits": None,
            "added_at": datetime.now().isoformat(),
            "error_count": 0,
            "email": email.strip() or None,
            "user_name": user_name.strip() or None,
            "notes": notes.strip() or None,
        }
        self._accounts.append(account)
        self._save_accounts()
        logger.info("Added profile %s", account["nickname"])
        return account

    def import_account_from_file(self, file_path: str) -> dict:
        with open(file_path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            raise ValueError("Profile file must contain a JSON object")
        return self.add_account(
            nickname=str(raw.get("nickname") or raw.get("name") or "").strip(),
            api_key=str(raw.get("api_key") or "").strip(),
            email=str(raw.get("email") or "").strip(),
            user_name=str(raw.get("user_name") or raw.get("name") or "").strip(),
            proxy=str(raw.get("proxy") or "").strip(),
            notes=str(raw.get("notes") or "").strip(),
        )

    def update_account(self, account_id: str, **changes: object) -> bool:
        account = self.get_account(account_id)
        if not account:
            return False
        for key in ["nickname", "api_key", "email", "user_name", "proxy", "notes", "status", "credits"]:
            if key in changes:
                value = changes[key]
                account[key] = value.strip() if isinstance(value, str) else value
        self._save_accounts()
        return True

    def set_plan_label(self, plan_label: str) -> None:
        for account in self._accounts:
            account["credits"] = plan_label
        self._save_accounts()

    def remove_account(self, account_id: str) -> bool:
        before = len(self._accounts)
        self._accounts = [item for item in self._accounts if item["account_id"] != account_id]
        if len(self._accounts) < before:
            self._save_accounts()
            return True
        return False

    def get_accounts(self) -> list[dict]:
        return list(self._accounts)

    def get_active_accounts(self) -> list[dict]:
        return [account for account in self._accounts if account.get("status") == "active"]

    def get_account(self, account_id: str) -> dict | None:
        for account in self._accounts:
            if account["account_id"] == account_id:
                return account
        return None

    def get_next_active_account(self) -> dict | None:
        active = self.get_active_accounts()
        if not active:
            return None
        account = active[self._rotation_index % len(active)]
        self._rotation_index += 1
        return account

    async def validate_session(self, account_id: str) -> dict:
        account = self.get_account(account_id)
        if not account:
            return {"status": "error", "email": None, "user_name": None}

        nickname = account.get("nickname") or "profile"
        slug = nickname.lower().replace(" ", "_")
        account["status"] = "active"
        account["error_count"] = 0
        account["email"] = account.get("email") or f"{slug}@local.demo"
        account["user_name"] = account.get("user_name") or nickname
        account["credits"] = account.get("credits") or "Chưa kiểm tra"
        self._save_accounts()
        return {
            "status": "active",
            "email": account["email"],
            "user_name": account["user_name"],
        }

    def get_auth_headers(self, account_id: str) -> dict:
        account = self.get_account(account_id)
        if not account:
            return {}
        headers = {
            "X-Profile-Id": account_id,
            "X-Profile-Name": account.get("nickname") or "Profile",
        }
        if account.get("api_key"):
            headers["Authorization"] = f"Bearer {account['api_key']}"
        return headers

    def set_proxy(self, account_id: str, proxy: str | None) -> None:
        account = self.get_account(account_id)
        if account:
            account["proxy"] = proxy.strip() if isinstance(proxy, str) and proxy.strip() else None
            self._save_accounts()

    async def check_credits(self, account_id: str) -> str | None:
        account = self.get_account(account_id)
        if not account:
            return None
        credits = str(account.get("credits") or "Chưa kiểm tra")
        account["credits"] = credits
        self._save_accounts()
        return credits

    def _save_accounts(self) -> None:
        ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as handle:
            json.dump(self._accounts, handle, indent=2, ensure_ascii=False)

    def _load_accounts(self) -> list[dict]:
        if not ACCOUNTS_FILE.exists():
            return []
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, list):
                return []
            if len(data) == 1:
                first = data[0] if isinstance(data[0], dict) else {}
                if (
                    first.get("nickname") == "Default profile"
                    and not first.get("api_key")
                    and not first.get("email")
                    and not first.get("user_name")
                    and not first.get("notes")
                ):
                    return []
            return data
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load accounts: %s", exc)
            return []
