"""
campaign_manager.py
===================

PURPOSE
-------
Controls campaign lifecycle and operational state.

WHY THIS FILE EXISTS
--------------------
In production, campaigns must be controllable without killing processes.

WHAT THIS FILE DOES
-------------------
- Start campaign
- Pause campaign
- Resume campaign
- Stop campaign gracefully

WHAT THIS FILE MUST NOT DO
--------------------------
- ❌ Must not place calls
- ❌ Must not loop merchants
- ❌ Must not perform business logic

DESIGN PRINCIPLE
----------------
Operational control is separate from execution logic.

EXPECTED EXTENSIONS
-------------------
- Admin APIs
- Dashboard integration
- Graceful shutdown hooks
"""
class CampaignManager:
    def __init__(self):
        self.active = True

    def pause(self):
        self.active = False

    def resume(self):
        self.active = True