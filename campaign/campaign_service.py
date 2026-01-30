from campaign.campaign_runner import CampaignRunner
from campaign.excel_campaign_store import ExcelCampaignStore
# OR
# from campaign.db_campaign_store import DBCampaignStore

async def run_excel_campaign(excel_path: str, call_handler):
    """
    Entry point for Excel-based campaigns.
    """
    store = ExcelCampaignStore(excel_path)
    runner = CampaignRunner(store, call_handler)
    await runner.run()