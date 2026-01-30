from sqlalchemy.orm import Session
from campaign.campaign_store import CampaignStore
from campaign.campaign_models import Merchant

class DBCampaignStore(CampaignStore):
    """
    Database-backed campaign store.

    Handles:
    - Safe merchant pickup
    - Retry tracking
    - Failure recording
    """

    def __init__(self, session: Session, max_attempts: int = 3):
        self.session = session
        self.max_attempts = max_attempts

    def get_next_merchant(self):
        """
        Atomically fetch and lock the next merchant.
        Prevents double-pick in parallel workers.
        """
        merchant = (
            self.session.query(Merchant)
            .filter(
                Merchant.status == "pending",
                Merchant.attempts < self.max_attempts
            )
            .with_for_update(skip_locked=True)
            .first()
        )

        if not merchant:
            return None

        # Mark as in-progress immediately
        merchant.status = "in_progress"
        merchant.attempts += 1
        self.session.commit()

        return merchant

    def mark_completed(self, merchant_id: str):
        merchant = self.session.get(Merchant, merchant_id)
        if not merchant:
            return

        merchant.status = "completed"
        self.session.commit()

    def mark_failed(self, merchant_id: str, reason: str):
        merchant = self.session.get(Merchant, merchant_id)
        if not merchant:
            return

        merchant.status = "failed"
        merchant.result = reason
        self.session.commit()