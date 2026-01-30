"""
Tracks outbound campaign call_ids.
Prevents inbound / unknown calls from affecting campaign state.
"""

class CampaignCallRegistry:
    def __init__(self):
        self._active_calls = set()

    def register(self, call_id: str):
        self._active_calls.add(call_id)

    def unregister(self, call_id: str):
        self._active_calls.discard(call_id)

    def is_campaign_call(self, call_id: str) -> bool:
        return call_id in self._active_calls