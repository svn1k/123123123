import json, os, secrets
from datetime import datetime
from pathlib import Path

STORAGE_DIR = Path("./data/history")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

class SpendingStorage:
    def __init__(self, user_id):
        self.file = STORAGE_DIR / f"{user_id}_history.json"

    def add_record(self, type, desc, amount, tx_id=""):
        recs = self.get_history()
        recs.insert(0, {
            "type": type, "description": desc, "amount": amount, 
            "tx_id": tx_id, "date": datetime.now().strftime("%d.%m %H:%M")
        })
        self.file.write_text(json.dumps(recs[:50], ensure_ascii=False))

    def get_history(self):
        if not self.file.exists(): return []
        return json.loads(self.file.read_text())

    def clear(self):
        if self.file.exists(): self.file.unlink()