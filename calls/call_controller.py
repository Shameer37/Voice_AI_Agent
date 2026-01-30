"""
call_controller.py
==================

PURPOSE
-------
Manages the lifecycle of a single outbound call to a merchant.

This file is responsible for:
- Initiating a call
- Connecting telephony to the voice agent
- Tracking call success or failure

WHY THIS FILE EXISTS
--------------------
Separates telephony complexity from campaign logic.
Campaigns should not care about SIP, WebRTC, or call signaling.

WHAT THIS FILE DOES
-------------------
- Places one outbound call
- Attaches agent WebSocket
- Waits for call completion
- Returns structured call result

WHAT THIS FILE MUST NOT DO
--------------------------
- ❌ Must not loop merchants
- ❌ Must not manage campaign state
- ❌ Must not persist data

DESIGN PRINCIPLE
----------------
One call = one responsibility.

EXPECTED EXTENSIONS
-------------------
- Retry signaling
- Call recording hooks
- Telephony provider switching
"""

import asyncio
import logging
from enum import Enum
from datetime import datetime

logger = logging.getLogger("call")

class CallResult(str, Enum):
    SUCCESS = "success"
    NO_ANSWER = "no_answer"
    FAILED = "failed"
    HANGUP = "hangup"


class CallController:
    """
    Responsible for placing outbound calls.
    This class does NOT know about campaign state.
    """

    async def place_call(self, merchant, timeout=60):
        logger.info(
            f"📞 Calling merchant id={merchant.id} phone={merchant.phone}"
        )

        start_ts = asyncio.get_event_loop().time()
        called_at = datetime.utcnow().isoformat()

        try:
            # TODO: integrate FreJun / Twilio here
            await asyncio.wait_for(self._simulate_call(), timeout=timeout)

            duration = int(asyncio.get_event_loop().time() - start_ts)

            return {
                "status": "completed",
                "result": CallResult.SUCCESS,
                "duration": duration,
                "agent_connected": True,
                "summary": "Merchant engaged, issue captured",
                "call_id": f"CALL-{merchant.id}-{int(start_ts)}",
                "called_at": called_at,
            }

        except asyncio.TimeoutError:
            logger.warning("⏰ Call timed out")

            return {
                "status": "failed",
                "result": CallResult.NO_ANSWER,
                "duration": timeout,
                "agent_connected": False,
                "summary": "Call not answered",
                "call_id": f"CALL-{merchant.id}-{int(start_ts)}",
                "called_at": called_at,
            }

        except Exception as e:
            logger.exception("❌ Call failed")

            return {
                "status": "failed",
                "result": CallResult.FAILED,
                "duration": 0,
                "agent_connected": False,
                "summary": str(e),
                "call_id": f"CALL-{merchant.id}-{int(start_ts)}",
                "called_at": called_at,
            }

    async def _simulate_call(self):
        """Temporary mock for local testing."""
        await asyncio.sleep(10)
