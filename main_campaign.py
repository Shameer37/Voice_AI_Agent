"""
main_campaign.py
================

PURPOSE
-------
Entry point for running outbound calling campaigns.

WHY THIS FILE EXISTS
--------------------
Separates campaign execution from the voice agent service.
Allows campaigns to be run as:
- CLI job
- Cron task
- Background worker

WHAT THIS FILE DOES
-------------------
- Initializes campaign components
- Loads merchant data
- Starts campaign execution

WHAT THIS FILE MUST NOT DO
--------------------------
- ❌ Must not contain business logic
- ❌ Must not modify agent behavior
- ❌ Must not handle telephony

DESIGN PRINCIPLE
----------------
Bootstrap only. No intelligence here.

EXPECTED EXTENSIONS
-------------------
- Command-line arguments
- Environment-based configs
"""

# main_campaign.py

import asyncio
from campaign.excel_campaign_store import ExcelCampaignStore
from campaign.campaign_runner import CampaignRunner
from calls.call_controller import CallController

async def main():
    store = ExcelCampaignStore(
        path="merchants.xlsx",
        max_attempts=3   # ✅ retry policy belongs to STORE
    )

    call_controller = CallController()

    runner = CampaignRunner(
        store=store,
        call_controller=call_controller
    )

    await runner.run()

if __name__ == "__main__":
    asyncio.run(main())



# #------------------------------------------------------------------------
# #IT IS RECOMMENDED WHEN WE GET DATA OF MERCHANT IN DATABASE 
# #------------------------------------------------------------------------ 

# import asyncio
# from sqlalchemy.orm import Session
# from campaign.db_campaign_store import DBCampaignStore
# from campaign.campaign_runner import CampaignRunner
# from calls.call_controller import CallController
# from db import SessionLocal

# async def main():
#     session: Session = SessionLocal()
#     store = DBCampaignStore(session)
#     call_controller = CallController()

#     runner = CampaignRunner(
#         store=store,
#         call_controller=call_controller,
#         max_attempts=3
#     )

#     await runner.run()

# if __name__ == "__main__":
#     asyncio.run(main())