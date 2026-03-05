# """
# campaign_models.py
# ==================

# PURPOSE
# -------
# Defines all data structures related to outbound calling campaigns.
# This file acts as the single contract for how merchant and campaign
# data is represented across the system.

# WHY THIS FILE EXISTS
# --------------------
# - Prevents passing loosely structured dicts across the codebase
# - Makes campaign state explicit and debuggable
# - Enables persistence, retries, and auditing
# - Allows schema evolution without breaking business logic

# WHAT THIS FILE CONTAINS
# -----------------------
# - Merchant record structure
# - Campaign-related enums or constants
# - Call status representation
# - Retry / attempt counters

# WHAT THIS FILE MUST NOT DO
# --------------------------
# - ❌ No API calls
# - ❌ No database access
# - ❌ No telephony logic
# - ❌ No loops or execution logic

# DESIGN PRINCIPLE
# ----------------
# This file is PURE DATA.
# If this file ever imports asyncio, requests, OpenAI, or telephony SDKs,
# it is a design violation.

# EXPECTED LIFETIME
# -----------------
# Very stable.
# Changes here should be rare and intentional, as they affect
# the entire campaign system.
# """

# from dataclasses import dataclass
# from typing import Optional

# @dataclass
# class Merchant:
#     """
#     Represents a merchant in a calling campaign.

#     This model is intentionally simple so it can be used with:
#     - Excel-based campaigns
#     - Database-backed campaigns
#     """
#     id: str
#     phone: str
#     status: str = "pending"       # pending | in_progress | completed | failed
#     attempts: int = 0
#     result: Optional[str] = None

# campaign/campaign_models.py

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from datetime import datetime

Base = declarative_base()


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=False, index=True)

    status = Column(String, default="pending")  
    attempts = Column(Integer, default=0)

    active = Column(Boolean, default=True)
    last_interacted = Column(DateTime, nullable=True)

    result = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)
    summary = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
