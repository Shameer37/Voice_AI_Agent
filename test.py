from agent.utils.email_utils import send_support_summary_email
from dotenv import load_dotenv
import os
import os
os.environ["SUPPORT_TEAM_EMAIL"] = "support@example.com"

load_dotenv()
send_support_summary_email({
    "merchant_id": "M-TEST",
    "merchant_name": "Test Merchant",
    "merchant_phone": "+919999999999",
    "call_id": "CALL-TEST-1",
    "call_time": "2026-02-09T12:30:00Z",
    "duration": 10,
    "agent_connected": True,
    "call_result": "completed",
    "intent": "test",
    "summary": "This is a test email."
})
print("done")

# from dotenv import load_dotenv
# import os

# load_dotenv()
# print("ENV=", os.getenv("ENV"))
# print("SMTP_HOST=", os.getenv("SMTP_HOST"))
# print("SMTP_PORT=", os.getenv("SMTP_PORT"))
# print("SMTP_SENDER=", os.getenv("SMTP_SENDER"))
# print("SUPPORT_TEAM_EMAIL=", os.getenv("SUPPORT_TEAM_EMAIL"))
