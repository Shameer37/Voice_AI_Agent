# import os
# import smtplib
# import time
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# import anthropic
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()
# anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
# SUPPORT_TEAM_EMAIL = os.getenv("SUPPORT_TEAM_EMAIL", "support@example.com") # Default email
# ENV = os.getenv("ENV", "dev")
# SMTP_SENDER = os.getenv("SMTP_SENDER", "noreply@example.com")
# SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
# SMTP_PORT = int(os.getenv("SMTP_PORT", 1025))
# SMTP_USER = os.getenv("SMTP_USER")
# SMTP_PASS = os.getenv("SMTP_PASS")


# anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)

# def summarize_with_llm(full_transcript: str):
#     """Summarizes a full conversation transcript using an LLM."""
#     prompt = f"""
#     Please summarize the following conversation between an AI agent and a retail merchant.
#     Focus on the merchant's reason for inactivity and the final outcome of the call.
#     The summary should be concise (2-3 sentences) for a customer support team.

#     Conversation Transcript:
#     {full_transcript}
#     """

#     # Try Anthropic with 2 retries
#     for attempt in range(2):
#         try:
#             response = anthropic_client.messages.create(
#                 model="claude-3-5-sonnet-20240620", # Using a recommended model
#                 max_tokens=150,
#                 temperature=0.5,
#                 messages=[{"role": "user", "content": prompt}]
#             )
#             return response.content[0].text.strip()
#         except Exception as e:
#             print(f"⚠️ Anthropic failed (attempt {attempt+1}): {e}")
#             time.sleep(2)

#     return "Conversation could not be summarized due to an API error."


# def summarize_conversation_from_log(session_id: str) -> str | None:
#     """Reads a log file and returns an LLM-generated summary."""
#     log_path = os.path.join("logs", f"{session_id}.txt")

#     if not os.path.exists(log_path):
#         print(f"⚠️ Log file missing, cannot summarize: {log_path}")
#         return "Log file was not found for this session."

#     with open(log_path, "r", encoding="utf-8") as f:
#         transcript = f.read()

#     if not transcript:
#         return "Log file was empty."

#     summary = summarize_with_llm(transcript)
#     print(f"[✅] Summarized: {summary}")
#     return summary


# def send_conversation_summary_email(session_id: str, user_name: str, summarized_response: str, merchant_phone: str | None = None):
#     """
#     Sends a call summary email to the internal support team.
#     """
#     if not summarized_response:
#         summarized_response = "The conversation summary was empty or could not be generated."

#     # --- Subject line reframed for internal team ---
#     subject = f"[AI Agent Report] Call with {user_name} (Session: {session_id})"

#     # --- Body reframed for internal team ---
#     body = f"""
#     Hello Support Team,

#     The AI agent completed a call with the following merchant:

#     - Name/ID: {user_name}
#     - Phone: {merchant_phone if merchant_phone else 'N/A'}
#     - Session ID: {session_id}

#     📋 Conversation Summary:
#     {summarized_response}

#     Please review and take further action if necessary.

#     Regards,
#     SwiftMoney AI Agent
#     """

#     msg = MIMEMultipart()
#     msg["From"] = SMTP_SENDER
#     msg["To"] = SUPPORT_TEAM_EMAIL
#     msg["Subject"] = subject
#     msg.attach(MIMEText(body, "plain"))

#     try:
#         if ENV == "dev":
#             # For local testing with MailHog
#             with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
#                 server.send_message(msg)
#         else:
#             # For production email sending
#             with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
#                 server.starttls()
#                 server.login(SMTP_USER, SMTP_PASS)
#                 server.send_message(msg)

#         print(f"[📧] Summary email sent to Support Team ({SUPPORT_TEAM_EMAIL}) for session {session_id}")
#     except Exception as e:
#         print(f"[⚠️] Failed to send support email: {e}")

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", 1025))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_SENDER = os.getenv("SMTP_SENDER", "noreply@swiftmoney.ai")
SUPPORT_TEAM_EMAIL = os.getenv("SUPPORT_TEAM_EMAIL")
ENV = os.getenv("ENV", "dev")


def send_support_summary_email(post_call_data: dict):
    """
    Sends a clean post-call summary to support team.
    This file does ZERO intelligence.
    """

    subject = f"[AI Call Report] {post_call_data['intent']} | Merchant {post_call_data.get('merchant_id')}"

    body = f"""
Hello Support Team,

An outbound AI call has been completed.

Merchant ID   : {post_call_data.get('merchant_id')}
Merchant Name : {post_call_data.get('merchant_name', 'N/A')}
Phone Number  : {post_call_data.get('merchant_phone', 'N/A')}

Call ID       : {post_call_data.get('call_id')}
Call Time     : {post_call_data.get('call_time')}
Duration      : {post_call_data.get('duration')} seconds
Agent Joined  : {"Yes" if post_call_data.get('agent_connected') else "No"}
Call Result   : {post_call_data.get('call_result')}

Detected Intent:
- {post_call_data.get('intent')}

Summary:
{post_call_data.get('summary')}

You may use the Call ID to retrieve recordings if required.

— SwiftMoney Voice AI
"""

    msg = MIMEMultipart()
    msg["From"] = SMTP_SENDER
    msg["To"] = SUPPORT_TEAM_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        if ENV == "dev":
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)


        print(f"[📧] Summary email sent to Support Team ({SUPPORT_TEAM_EMAIL})")
    except Exception as e:
        print(f"[⚠️] Failed to send support email: {e}")
