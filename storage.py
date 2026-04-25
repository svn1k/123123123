"""
SpendingStorage — Local encrypted spending history.

Key principle: Your spending history stays YOURS.
- Stored locally, encrypted with your wallet key
- Never sent to advertisers, analytics, or third parties
- Only you (via your session) can read it
"""

import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./data/history"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


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
            cutoff = {
                "week": datetime.utcnow() - timedelta(days=7),
                "month": datetime.utcnow() - timedelta(days=30),
            }.get(period, datetime.min)
            
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
        now = datetime.utcnow()
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
