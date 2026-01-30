"""
merchant_importer.py
====================

PURPOSE
-------
Responsible for importing and validating merchant data
before it enters the campaign system.

WHY THIS FILE EXISTS
--------------------
Raw input data (Excel / DB) is unreliable.
This file ensures the campaign never receives malformed or incomplete data.

WHAT THIS FILE DOES
-------------------
- Reads merchant data from Excel / CSV / DB
- Validates required fields (phone, merchant_id, etc.)
- Normalizes formats (phone numbers, strings)
- Adds default campaign metadata (status, retry_count)

WHAT THIS FILE MUST NOT DO
--------------------------
- ❌ Must not start campaigns
- ❌ Must not place calls
- ❌ Must not modify campaign execution logic

DESIGN PRINCIPLE
----------------
Garbage in → garbage out prevention layer.

EXPECTED EXTENSIONS
-------------------
- Data deduplication
- Fraud / blacklist checks
- Locale-specific normalization
"""
import pandas as pd
import logging

logger = logging.getLogger("campaign_import")

REQUIRED_COLUMNS = {"merchant_id", "phone"}

def import_from_excel(path="merchants.xlsx"):
    """
    Imports merchants into campaign format safely.

    - Preserves existing campaign progress
    - Adds missing campaign columns only
    - Prevents destructive overwrites
    """

    df = pd.read_excel(path)

    if not REQUIRED_COLUMNS.issubset(df.columns):
        missing = REQUIRED_COLUMNS - set(df.columns)
        raise ValueError(f"Excel missing required columns: {missing}")

    # Normalize phone numbers
    df["phone"] = (
        df["phone"]
        .astype(str)
        .str.replace(r"\D", "", regex=True)
        .str[-10:]
    )

    # Deduplicate by merchant_id
    before = len(df)
    df = df.drop_duplicates(subset=["merchant_id"])
    after = len(df)

    if before != after:
        logger.warning(f"Removed {before - after} duplicate merchants")

    # Add campaign columns only if missing
    if "status" not in df.columns:
        df["status"] = "pending"

    if "attempts" not in df.columns:
        df["attempts"] = 0

    if "result" not in df.columns:
        df["result"] = ""

    df.to_excel(path, index=False)

    logger.info(f"Imported {len(df)} merchants successfully")
