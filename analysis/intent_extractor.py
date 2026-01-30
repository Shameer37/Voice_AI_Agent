# analysis/intent_extractor.py

from openai import OpenAI
from analysis.intent_schema import INTENT_LABELS as INTENT_CATEGORIES
from analysis.faq_context import FAQ_CONTEXT
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_intent_and_summary(text: str) -> dict:
    prompt = f"""
You are an internal support classifier.

FAQ Context:
{FAQ_CONTEXT}

From the merchant conversation below:
1. Choose ONE intent from:
{INTENT_CATEGORIES}

2. Write a 2–3 line actionable summary.

Conversation:
{text}

Return JSON only:
{{
  "intent": "...",
  "summary": "..."
}}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        return eval(res.choices[0].message.content)
    except Exception:
        return {
            "intent": "Other / Unclear",
            "summary": "Unable to confidently classify merchant issue."
        }

