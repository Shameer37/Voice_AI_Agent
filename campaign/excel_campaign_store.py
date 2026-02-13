import pandas as pd
from datetime import datetime
from typing import Optional
from campaign.campaign_store import CampaignStore
from campaign.campaign_models import Merchant

# ---------------------------------
# Column alias mapping (CRITICAL)
# ---------------------------------
COLUMN_ALIASES = {
    "merchant_id": ["merchant_id", "MerchantID", "mid", "id"],
    "merchant_name": ["merchant_name", "MerchantName", "name"],
    "phone": ["phone", "phone_no", "mobile", "Phonenumber"],
    "is_active": ["is_active", "active", "status"],
    "last_interacted": ["last_interacted", "last_call", "last_contacted"],
    "status": ["status"],
    "attempts": ["attempts"],
}


def _get_value(row, keys, default=None):
    for k in keys:
        if k in row and pd.notna(row[k]):
            return row[k]
    return default


class ExcelCampaignStore(CampaignStore):
    """
    Excel-backed campaign store.
    Handles unknown column names safely.
    """

    def __init__(self, path: str, max_attempts: int = 3):
        self.path = path
        self.max_attempts = max_attempts

    def _load_df(self) -> pd.DataFrame:
        return pd.read_excel(self.path)

    def _save_df(self, df: pd.DataFrame):
        df.to_excel(self.path, index=False)

    def get_next_merchant(self) -> Optional[Merchant]:
        df = self._load_df()

        # Ensure required operational columns exist
        for col, default in {
            "status": "pending",
            "attempts": 0,
            "is_active": True,
        }.items():
            if col not in df.columns:
                df[col] = default

        # Pick next eligible merchant
        eligible = df[
            (df["status"] == "pending") &
            (df["attempts"] < self.max_attempts) &
            (df["is_active"] == True)
        ].head(1)

        if eligible.empty:
            return None

        idx = eligible.index[0]

        df.loc[idx, "status"] = "in_progress"
        df.loc[idx, "attempts"] += 1
        self._save_df(df)

        row = df.loc[idx]

        return Merchant(
            id=str(_get_value(row, COLUMN_ALIASES["merchant_id"])),
            phone=str(_get_value(row, COLUMN_ALIASES["phone"])),
            name=_get_value(row, COLUMN_ALIASES["merchant_name"]),
            is_active=bool(_get_value(row, COLUMN_ALIASES["is_active"], True)),
            last_interacted=_get_value(row, COLUMN_ALIASES["last_interacted"]),
            status="in_progress",
            attempts=int(row["attempts"]),
        )

    def mark_completed(self, merchant_id: str, call_result: dict):
        df = self._load_df()

        df.loc[df["merchant_id"] == merchant_id, "status"] = "completed"
        df.loc[df["merchant_id"] == merchant_id, "result"] = call_result.get("result")
        df.loc[df["merchant_id"] == merchant_id, "duration"] = call_result.get("duration")
        df.loc[df["merchant_id"] == merchant_id, "summary"] = call_result.get("summary")
        df.loc[df["merchant_id"] == merchant_id, "last_interacted"] = datetime.utcnow()

        self._save_df(df)

    def mark_failed(self, merchant_id: str, call_result: dict):
        df = self._load_df()

        df.loc[df["merchant_id"] == merchant_id, "status"] = "failed"
        df.loc[df["merchant_id"] == merchant_id, "result"] = call_result.get("result")
        df.loc[df["merchant_id"] == merchant_id, "last_interacted"] = datetime.utcnow()

        self._save_df(df)
