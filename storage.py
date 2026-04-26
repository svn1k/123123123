"""
SpendingStorage — Local encrypted spending history.

Key principle: Your spending history stays YOURS.
- Stored locally, encrypted with your wallet key
- Never sent to advertisers, analytics, or third parties
- Only you (via your session) can read it
"""

import base64
import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import logging
import httpx

from wallet import UPSTASH_URL, UPSTASH_TOKEN, _get_cipher

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./data/history"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def utc_now() -> datetime:
    return datetime.utcnow()


def iso_now() -> str:
    return utc_now().isoformat()


def normalize_alias(value: str) -> str:
    cleaned = "".join(str(value or "").strip().split()).lower()
    return cleaned[1:] if cleaned.startswith("@") else cleaned


def period_cutoff(period: str) -> datetime:
    now = utc_now()
    return {
        "day": now - timedelta(days=1),
        "week": now - timedelta(days=7),
        "month": now - timedelta(days=30),
        "all": datetime.min,
    }.get(period, datetime.min)


def add_interval(dt: datetime, interval: str) -> datetime:
    if interval == "daily":
        return dt + timedelta(days=1)
    if interval == "weekly":
        return dt + timedelta(days=7)
    if interval == "monthly":
        return dt + timedelta(days=30)
    raise ValueError(f"Unsupported interval: {interval}")


def parse_iso_dt(value: str | None, default: datetime | None = None) -> datetime:
    if not value:
        return default or datetime.min
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return default or datetime.min


class SpendingStorage:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.file = STORAGE_DIR / f"{user_id}_history.json"
        self._cache: Optional[list] = None

    def add_record(
        self,
        type: str,       # "send", "receive", "booking", "purchase", "deposit", "withdraw"
        description: str,
        amount: float,
        tx_id: str = "",
        metadata: dict = None
    ):
        records = self._load()
        record = {
            "id": secrets.token_hex(8),
            "type": type,
            "description": description,
            "amount": float(amount),
            "tx_id": tx_id,
            "date": datetime.utcnow().strftime("%d.%m.%Y %H:%M"),
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        records.insert(0, record)
        self._save(records)
        self._cache = records
        logger.info(f"[{self.user_id}] Recorded: {type} {amount} USDC — {description}")

    def get_history(
        self,
        limit: int = 20,
        period: str = "all",
        category: str = None
    ) -> List[dict]:
        records = self._load()
        
        # Filter by period
        if period != "all":
            cutoff = period_cutoff(period)
            
            records = [
                r for r in records
                if datetime.fromisoformat(r.get("timestamp", "2000-01-01")) >= cutoff
            ]
        
        # Filter by category
        if category:
            records = [r for r in records if r.get("type") == category]
        
        return records[:limit]

    def get_stats(self) -> dict:
        records = self._load()
        now = utc_now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        def ts(r):
            try:
                return datetime.fromisoformat(r.get("timestamp", "2000-01-01"))
            except Exception:
                return datetime.min

        total_sent = sum(r["amount"] for r in records if r["type"] in ("send", "booking", "purchase"))
        total_received = sum(r["amount"] for r in records if r["type"] == "receive")
        purchases = sum(1 for r in records if r["type"] == "purchase")
        bookings = sum(1 for r in records if r["type"] == "booking")
        transfers = sum(1 for r in records if r["type"] == "send")
        week_spent = sum(r["amount"] for r in records if ts(r) >= week_ago and r["type"] in ("send", "booking", "purchase"))
        month_spent = sum(r["amount"] for r in records if ts(r) >= month_ago and r["type"] in ("send", "booking", "purchase"))

        return {
            "total_sent": total_sent,
            "total_received": total_received,
            "purchases": purchases,
            "bookings": bookings,
            "transfers": transfers,
            "week_spent": week_spent,
            "month_spent": month_spent,
            "total_records": len(records)
        }

    def get_spent_amount(
        self,
        period: str = "month",
        record_types: Optional[list[str]] = None,
        budget_category: Optional[str] = None
    ) -> float:
        records = self.get_history(limit=100000, period=period)
        total = 0.0
        for record in records:
            if record_types and record.get("type") not in record_types:
                continue
            metadata = record.get("metadata") or {}
            record_category = str(metadata.get("budget_category") or record.get("type") or "").lower()
            if budget_category and record_category != str(budget_category).lower():
                continue
            total += float(record.get("amount", 0.0) or 0.0)
        return round(total, 6)

    def clear_history(self):
        self._save([])
        self._cache = []

    def _load(self) -> list:
        if self._cache is not None:
            return self._cache
        
        if not self.file.exists():
            return []
        
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            self._cache = data
            return data
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return []

    def _save(self, records: list):
        self.file.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


class UserProfileStorage:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.file = STORAGE_DIR / f"{user_id}_profile.json"
        self.db_key = f"profile_{user_id}"
        self._cache: Optional[dict] = None
        self.cipher = _get_cipher()

    def _default_profile(self) -> dict:
        return {
            "contacts": [],
            "merchants": [],
            "invoices": [],
            "recurring": [],
            "budgets": [],
            "risk_rules": {
                "max_single_payment": None,
                "daily_spend_limit": None,
                "monthly_spend_limit": None,
                "require_known_contact_over": None,
                "block_new_recipient_over": None,
            },
        }

    def _load(self) -> dict:
        if self._cache is not None:
            return self._cache
        profile_from_db = self._load_from_db()
        if profile_from_db is not None:
            self._cache = self._normalize_profile(profile_from_db)
            self._save_local_only(self._cache)
            return self._cache
        if not self.file.exists():
            self._cache = self._default_profile()
            return self._cache
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            profile = self._normalize_profile(data)
            self._cache = profile
            self._save_to_db(profile)
            return profile
        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            self._cache = self._default_profile()
            return self._cache

    def _save(self, profile: dict):
        self._save_local_only(profile)
        self._save_to_db(profile)
        self._cache = profile

    def _normalize_profile(self, data: dict | None) -> dict:
        profile = self._default_profile()
        if isinstance(data, dict):
            profile.update(data)
            profile["risk_rules"] = {
                **self._default_profile()["risk_rules"],
                **(data.get("risk_rules") or {}),
            }
        return profile

    def _save_local_only(self, profile: dict):
        self.file.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _headers(self):
        return {"Authorization": f"Bearer {UPSTASH_TOKEN}"}

    def _load_from_db(self) -> Optional[dict]:
        if not UPSTASH_URL:
            return None
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"{UPSTASH_URL}/get/{self.db_key}", headers=self._headers())
                if resp.status_code != 200:
                    return None
                result = resp.json().get("result")
                if not result:
                    return None
                decrypted = self.cipher.decrypt(result.encode()).decode("utf-8")
                return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Failed to load profile from Upstash: {e}")
            return None

    def _save_to_db(self, profile: dict):
        if not UPSTASH_URL:
            return
        try:
            encrypted = self.cipher.encrypt(json.dumps(profile).encode()).decode("utf-8")
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    f"{UPSTASH_URL}/set/{self.db_key}",
                    headers=self._headers(),
                    json=encrypted,
                )
                resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to save profile to Upstash: {e}")

    def _next_id(self, prefix: str) -> str:
        return f"{prefix}-{secrets.token_hex(4).upper()}"

    def get_contacts(self) -> List[dict]:
        return list(self._load().get("contacts", []))

    def save_contact(
        self,
        alias: str,
        address: str,
        note: str = "",
        wallet_user_id: str = "",
        wallet_username: str = "",
        wallet_display_name: str = "",
        is_internal_wallet: bool = False,
    ) -> dict:
        alias_key = normalize_alias(alias)
        if not alias_key:
            raise ValueError("Contact alias cannot be empty.")
        profile = self._load()
        contacts = profile["contacts"]
        existing = next((c for c in contacts if c.get("alias_key") == alias_key), None)
        payload = {
            "alias": alias.strip(),
            "alias_key": alias_key,
            "address": address.strip(),
            "note": note.strip(),
            "wallet_user_id": str(wallet_user_id or "").strip(),
            "wallet_username": str(wallet_username or "").strip(),
            "wallet_display_name": str(wallet_display_name or "").strip(),
            "is_internal_wallet": bool(is_internal_wallet),
            "updated_at": iso_now(),
        }
        if existing:
            existing.update(payload)
            record = existing
        else:
            record = {
                "id": self._next_id("CNT"),
                "created_at": iso_now(),
                **payload,
            }
            contacts.append(record)
        self._save(profile)
        return record

    def get_contact(self, alias: str) -> Optional[dict]:
        alias_key = normalize_alias(alias)
        return next((c for c in self._load()["contacts"] if c.get("alias_key") == alias_key), None)

    def remove_contact(self, alias: str) -> bool:
        alias_key = normalize_alias(alias)
        profile = self._load()
        before = len(profile["contacts"])
        profile["contacts"] = [c for c in profile["contacts"] if c.get("alias_key") != alias_key]
        changed = len(profile["contacts"]) != before
        if changed:
            self._save(profile)
        return changed

    def get_merchants(self) -> List[dict]:
        return list(self._load().get("merchants", []))

    def save_merchant(
        self,
        alias: str,
        address: str,
        category: str = "general",
        note: str = "",
        default_amount: float = 0.0,
        wallet_user_id: str = "",
        wallet_username: str = "",
        wallet_display_name: str = "",
        is_internal_wallet: bool = False,
    ) -> dict:
        alias_key = normalize_alias(alias)
        if not alias_key:
            raise ValueError("Merchant alias cannot be empty.")
        profile = self._load()
        merchants = profile["merchants"]
        existing = next((m for m in merchants if m.get("alias_key") == alias_key), None)
        payload = {
            "alias": alias.strip(),
            "alias_key": alias_key,
            "address": address.strip(),
            "category": (category or "general").strip().lower(),
            "note": note.strip(),
            "default_amount": float(default_amount or 0.0),
            "wallet_user_id": str(wallet_user_id or "").strip(),
            "wallet_username": str(wallet_username or "").strip(),
            "wallet_display_name": str(wallet_display_name or "").strip(),
            "is_internal_wallet": bool(is_internal_wallet),
            "updated_at": iso_now(),
        }
        if existing:
            existing.update(payload)
            record = existing
        else:
            record = {
                "id": self._next_id("MRC"),
                "created_at": iso_now(),
                **payload,
            }
            merchants.append(record)
        self._save(profile)
        return record

    def get_merchant(self, alias: str) -> Optional[dict]:
        alias_key = normalize_alias(alias)
        return next((m for m in self._load()["merchants"] if m.get("alias_key") == alias_key), None)

    def remove_merchant(self, alias: str) -> bool:
        alias_key = normalize_alias(alias)
        profile = self._load()
        before = len(profile["merchants"])
        profile["merchants"] = [m for m in profile["merchants"] if m.get("alias_key") != alias_key]
        changed = len(profile["merchants"]) != before
        if changed:
            self._save(profile)
        return changed

    def resolve_alias(self, value: str) -> Optional[dict]:
        alias_key = normalize_alias(value)
        if not alias_key:
            return None
        contact = self.get_contact(alias_key)
        if contact:
            return {"kind": "contact", **contact}
        merchant = self.get_merchant(alias_key)
        if merchant:
            return {"kind": "merchant", **merchant}
        return None

    @staticmethod
    def encode_payment_request(payload: dict) -> str:
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        return f"PERPAY:{token}"

    @staticmethod
    def decode_payment_request(code: str) -> dict:
        raw = str(code or "").strip()
        if not raw.upper().startswith("PERPAY:"):
            raise ValueError("Payment request must start with PERPAY:")
        token = raw.split(":", 1)[1].strip()
        if not token:
            raise ValueError("Payment request code is empty.")
        padding = "=" * (-len(token) % 4)
        try:
            decoded = base64.urlsafe_b64decode((token + padding).encode("ascii")).decode("utf-8")
            data = json.loads(decoded)
        except Exception as e:
            raise ValueError(f"Invalid payment request code: {e}") from e
        if not isinstance(data, dict):
            raise ValueError("Payment request payload is invalid.")
        return data

    def create_invoice(
        self,
        amount: float,
        description: str,
        recipient_address: str,
        recipient_alias: str = "",
        due_date: str = "",
        note: str = ""
    ) -> dict:
        profile = self._load()
        invoice_id = self._next_id("INV")
        invoice = {
            "id": invoice_id,
            "amount": float(amount),
            "description": description.strip(),
            "recipient_address": recipient_address.strip(),
            "recipient_alias": recipient_alias.strip(),
            "due_date": due_date.strip(),
            "note": note.strip(),
            "status": "open",
            "created_at": iso_now(),
            "paid_at": "",
            "paid_tx_id": "",
            "payer": "",
        }
        payload = {
            "invoice_id": invoice_id,
            "amount": float(amount),
            "description": description.strip(),
            "recipient_address": recipient_address.strip(),
            "recipient_alias": recipient_alias.strip(),
            "due_date": due_date.strip(),
            "note": note.strip(),
            "created_at": invoice["created_at"],
        }
        invoice["share_code"] = self.encode_payment_request(payload)
        profile["invoices"].insert(0, invoice)
        self._save(profile)
        return invoice

    def get_invoices(self, status: Optional[str] = None) -> List[dict]:
        invoices = list(self._load().get("invoices", []))
        if status:
            invoices = [i for i in invoices if i.get("status") == status]
        return invoices

    def get_invoice(self, invoice_id: str) -> Optional[dict]:
        key = str(invoice_id or "").strip().upper()
        return next((i for i in self._load()["invoices"] if i.get("id") == key), None)

    def update_invoice_status(
        self,
        invoice_id: str,
        status: str,
        paid_tx_id: str = "",
        payer: str = ""
    ) -> Optional[dict]:
        profile = self._load()
        invoice = next((i for i in profile["invoices"] if i.get("id") == str(invoice_id).strip().upper()), None)
        if not invoice:
            return None
        invoice["status"] = status
        invoice["updated_at"] = iso_now()
        if status == "paid":
            invoice["paid_at"] = iso_now()
            invoice["paid_tx_id"] = paid_tx_id
            invoice["payer"] = payer
        self._save(profile)
        return invoice

    def cancel_invoice(self, invoice_id: str) -> bool:
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            return False
        self.update_invoice_status(invoice_id, "cancelled")
        return True

    def create_recurring_payment(
        self,
        target_address: str,
        amount: float,
        interval: str,
        memo: str = "",
        target_alias: str = "",
        target_kind: str = "address",
        category: str = "transfer",
        start_at: str = "",
    ) -> dict:
        start_dt = parse_iso_dt(start_at, default=utc_now())
        if start_dt < utc_now():
            start_dt = utc_now()
        recurring = {
            "id": self._next_id("REC"),
            "target_address": target_address.strip(),
            "target_alias": target_alias.strip(),
            "target_kind": target_kind.strip() or "address",
            "amount": float(amount),
            "interval": interval,
            "memo": memo.strip(),
            "category": (category or "transfer").strip().lower(),
            "active": True,
            "created_at": iso_now(),
            "start_at": start_dt.isoformat(),
            "next_run_at": start_dt.isoformat(),
            "last_run_at": "",
            "last_tx_id": "",
            "runs": 0,
        }
        profile = self._load()
        profile["recurring"].insert(0, recurring)
        self._save(profile)
        return recurring

    def get_recurring_payments(self, active_only: bool = False) -> List[dict]:
        recurring = list(self._load().get("recurring", []))
        if active_only:
            recurring = [r for r in recurring if r.get("active")]
        return recurring

    def get_recurring_payment(self, recurring_id: str) -> Optional[dict]:
        key = str(recurring_id or "").strip().upper()
        return next((r for r in self._load()["recurring"] if r.get("id") == key), None)

    def set_recurring_active(self, recurring_id: str, active: bool) -> Optional[dict]:
        profile = self._load()
        recurring = next((r for r in profile["recurring"] if r.get("id") == str(recurring_id).strip().upper()), None)
        if not recurring:
            return None
        recurring["active"] = bool(active)
        recurring["updated_at"] = iso_now()
        self._save(profile)
        return recurring

    def delete_recurring_payment(self, recurring_id: str) -> bool:
        key = str(recurring_id or "").strip().upper()
        profile = self._load()
        before = len(profile["recurring"])
        profile["recurring"] = [r for r in profile["recurring"] if r.get("id") != key]
        changed = len(profile["recurring"]) != before
        if changed:
            self._save(profile)
        return changed

    def get_due_recurring_payments(self, now: Optional[datetime] = None) -> List[dict]:
        now = now or utc_now()
        due = []
        for item in self.get_recurring_payments(active_only=True):
            if parse_iso_dt(item.get("next_run_at"), default=datetime.max) <= now:
                due.append(item)
        return due

    def mark_recurring_executed(self, recurring_id: str, tx_id: str) -> Optional[dict]:
        profile = self._load()
        recurring = next((r for r in profile["recurring"] if r.get("id") == str(recurring_id).strip().upper()), None)
        if not recurring:
            return None
        executed_at = utc_now()
        recurring["last_run_at"] = executed_at.isoformat()
        recurring["last_tx_id"] = tx_id
        recurring["runs"] = int(recurring.get("runs", 0)) + 1
        recurring["next_run_at"] = add_interval(executed_at, recurring.get("interval", "monthly")).isoformat()
        recurring["updated_at"] = iso_now()
        self._save(profile)
        return recurring

    def set_budget(self, category: str, period: str, amount: float, strict: bool = False) -> dict:
        category_key = str(category or "all").strip().lower()
        period_key = str(period or "month").strip().lower()
        profile = self._load()
        budgets = profile["budgets"]
        existing = next(
            (b for b in budgets if b.get("category") == category_key and b.get("period") == period_key),
            None,
        )
        payload = {
            "category": category_key,
            "period": period_key,
            "amount": float(amount),
            "strict": bool(strict),
            "updated_at": iso_now(),
        }
        if existing:
            existing.update(payload)
            budget = existing
        else:
            budget = {
                "id": self._next_id("BDG"),
                "created_at": iso_now(),
                **payload,
            }
            budgets.append(budget)
        self._save(profile)
        return budget

    def get_budgets(self) -> List[dict]:
        return list(self._load().get("budgets", []))

    def remove_budget(self, budget_id: str) -> bool:
        key = str(budget_id or "").strip().upper()
        profile = self._load()
        before = len(profile["budgets"])
        profile["budgets"] = [b for b in profile["budgets"] if b.get("id") != key]
        changed = len(profile["budgets"]) != before
        if changed:
            self._save(profile)
        return changed

    def get_risk_rules(self) -> dict:
        return dict(self._load().get("risk_rules", {}))

    def update_risk_rules(self, updates: dict) -> dict:
        profile = self._load()
        rules = profile.get("risk_rules", {})
        for key, value in updates.items():
            if key not in self._default_profile()["risk_rules"]:
                continue
            if value in ("", None):
                rules[key] = None
            else:
                rules[key] = float(value)
        profile["risk_rules"] = rules
        self._save(profile)
        return dict(rules)
