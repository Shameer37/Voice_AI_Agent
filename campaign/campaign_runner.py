"""
campaign_runner.py
==================

PURPOSE
-------
Executes an outbound calling campaign by iterating merchants
and triggering calls in a controlled, fault-tolerant manner.

WHY THIS FILE EXISTS
--------------------
Campaign execution logic must be:
- Deterministic
- Restart-safe
- Easy to pause or resume

WHAT THIS FILE DOES
-------------------
- Selects next eligible merchant
- Enforces delays and cooldowns
- Applies retry policies
- Moves campaign forward cleanly

WHAT THIS FILE MUST NOT DO
--------------------------
- ❌ Must not place calls directly
- ❌ Must not talk to STT / TTS
- ❌ Must not handle storage details

DESIGN PRINCIPLE
----------------
This is the campaign brain, not the hands.

EXPECTED EXTENSIONS
-------------------
- Parallel campaigns
- Rate limiting
- Priority-based calling
"""
# campaign/campaign_runner.py
import logging
from campaign.campaign_store import CampaignStore

logger = logging.getLogger("campaign")


class CampaignRunner:
    """
    Orchestrates merchant calling flow.
    """

    def __init__(self, store: CampaignStore, call_controller):
        self.store = store
        self.call_controller = call_controller

    async def run(self):
        """
        Runs campaign until no merchants remain.
        """
        while True:
            merchant = self.store.get_next_merchant()

            if not merchant:
                logger.info("🏁 Campaign completed – no merchants left")
                break

            try:
                logger.info(f"📞 Calling merchant {merchant.id}")

                call_result = await self.call_controller.place_call(merchant)

                if call_result["status"] == "completed":
                    self.store.mark_completed(
                        merchant_id=merchant.id,
                        call_result=call_result
                    )
                    logger.info(f"✅ Merchant {merchant.id} completed")

                else:
                    self.store.mark_failed(
                        merchant_id=merchant.id,
                        call_result=call_result
                    )
                    logger.warning(
                        f"⚠️ Merchant {merchant.id} failed: {call_result['result']}"
                    )

            except Exception as e:
                logger.exception(f"❌ Merchant {merchant.id} crashed")

                self.store.mark_failed(
                    merchant_id=merchant.id,
                    call_result={
                        "status": "failed",
                        "result": "internal_error",
                        "summary": str(e),
                        "agent_connected": False,
                    }
                )
