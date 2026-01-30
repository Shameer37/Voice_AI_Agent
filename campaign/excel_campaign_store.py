import pandas as pd
from campaign.campaign_store import CampaignStore
from campaign.campaign_models import Merchant

class ExcelCampaignStore(CampaignStore):
    """
    Campaign store backed by an Excel file.

    Suitable for:
    - Small campaigns
    - Manual uploads
    - Offline workflows
    """

    def __init__(self, path: str, max_attempts: int = 3):
        self.path = path
        self.max_attempts = max_attempts

    def _load_df(self):
        return pd.read_excel(self.path)

    def _save_df(self, df):
        df.to_excel(self.path, index=False)

    def get_next_merchant(self):
        df = self._load_df()

        row = df[
            (df["status"] == "pending") &
            (df["attempts"] < self.max_attempts)
        ].head(1)

        if row.empty:
            return None

        idx = row.index[0]
        df.loc[idx, "status"] = "in_progress"
        df.loc[idx, "attempts"] += 1
        self._save_df(df)

        return Merchant(
            id=str(df.loc[idx, "merchant_id"]),
            phone=str(df.loc[idx, "phone"]),
            status="in_progress",
            attempts=int(df.loc[idx, "attempts"])
        )

    def mark_completed(self, merchant_id: str, result: str = ""):
        df = self._load_df()
        df.loc[df["merchant_id"] == merchant_id, "status"] = "completed"
        df.loc[df["merchant_id"] == merchant_id, "result"] = result["result"]
        df.loc[df["merchant_id"] == merchant_id, "duration"] = result["duration"]
        df.loc[df["merchant_id"] == merchant_id, "summary"] = result["summary"]
        self._save_df(df)

    def mark_failed(self, merchant_id: str, reason: str):
        df = self._load_df()
        df.loc[df["merchant_id"] == merchant_id, "status"] = "failed"
        df.loc[df["merchant_id"] == merchant_id, "result"] = reason
        self._save_df(df)