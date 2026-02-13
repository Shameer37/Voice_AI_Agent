from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from campaign.campaign_store import CampaignStore
from campaign.campaign_models import Merchant


class DBCampaignStore(CampaignStore):
    """
    Database-backed campaign store.
    Safe for parallel workers.
    """

    def __init__(self, session: Session, max_attempts: int = 3):
        self.session = session
        self.max_attempts = max_attempts

    def get_next_merchant(self) -> Optional[Merchant]:
        merchant = (
            self.session.query(Merchant)
            .filter(
                Merchant.status == "pending",
                Merchant.attempts < self.max_attempts,
                Merchant.is_active == True,
            )
            .with_for_update(skip_locked=True)
            .first()
        )

        if not merchant:
            return None

        merchant.status = "in_progress"
        merchant.attempts += 1
        self.session.commit()

        return merchant

    def mark_completed(self, merchant_id: str, call_result: dict):
        merchant = self.session.get(Merchant, merchant_id)
        if not merchant:
            return

        merchant.status = "completed"
        merchant.result = call_result.get("result")
        merchant.duration = call_result.get("duration")
        merchant.summary = call_result.get("summary")
        merchant.last_interacted = datetime.utcnow()

        self.session.commit()

    def mark_failed(self, merchant_id: str, call_result: dict):
        merchant = self.session.get(Merchant, merchant_id)
        if not merchant:
            return

        merchant.status = "failed"
        merchant.result = call_result.get("result")
        merchant.last_interacted = datetime.utcnow()

        self.session.commit()
