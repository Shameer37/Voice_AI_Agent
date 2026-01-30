"""
campaign_store.py
=================

PURPOSE
-------
Provides persistent storage and retrieval for campaign and merchant data.

This file is the single source of truth for:
- Which merchants exist
- Which merchants have been called
- Which calls failed, succeeded, or need retry

WHY THIS FILE EXISTS
--------------------
Campaign execution must be crash-safe and restart-safe.
If the system restarts, campaign progress MUST NOT be lost.

WHAT THIS FILE DOES
-------------------
- Loads merchant data from Excel / CSV / Database
- Saves call outcomes and retry counts
- Updates merchant status atomically
- Provides safe read/write operations

WHAT THIS FILE MUST NOT DO
--------------------------
- ❌ Must not place calls
- ❌ Must not run loops
- ❌ Must not contain business decisions
- ❌ Must not depend on agent or telephony code

DESIGN PRINCIPLE
----------------
Persistence is isolated.
Campaign logic should never care *how* data is stored.

EXPECTED EXTENSIONS
-------------------
- Excel → Database migration
- Redis-based locking
- Distributed campaign coordination
"""
from abc import ABC, abstractmethod
from typing import Optional
from campaign.campaign_models import Merchant

class CampaignStore(ABC):
    """
    Abstract interface for campaign storage.

    Campaign runner depends ONLY on this interface,
    not on Excel, DB, or any concrete storage.
    """

    @abstractmethod
    def get_next_merchant(self) -> Optional[Merchant]:
        """Return next pending merchant or None"""
        pass
    @abstractmethod
    # def mark_completed(self, merchant_id: str, result: dict):
    #     pass
    def mark_completed(self, merchant_id: str, call_result: dict):
        pass
    @abstractmethod
    # def mark_failed(self, merchant_id: str, reason: str):
    def mark_failed(self, merchant_id: str, call_result: dict):
        pass