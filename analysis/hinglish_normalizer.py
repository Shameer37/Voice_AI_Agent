# analysis/hinglish_normalizer.py
import re

# Very small, high-signal mapping
HINGLISH_MAP = {
    # verbs / helpers
    # Previous behavior (kept for reference):
    # "nahi": "à¤¨à¤¹à¥€à¤‚",
    # "nahin": "à¤¨à¤¹à¥€à¤‚",
    # "ho": "à¤¹à¥‹",
    # "raha": "à¤°à¤¹à¤¾",
    # "rahi": "à¤°à¤¹à¥€",
    # "ho raha": "à¤¹à¥‹ à¤°à¤¹à¤¾",
    # "ho rahi": "à¤¹à¥‹ à¤°à¤¹à¥€",
    #
    # CHANGE: replace mojibake with proper Devanagari
    "nahi": "नहीं",
    "nahin": "नहीं",
    "ho": "हो",
    "raha": "रहा",
    "rahi": "रही",
    "ho raha": "हो रहा",
    "ho rahi": "हो रही",

    # common fintech words spoken in English
    "withdrawal": "withdrawal",
    "settlement": "settlement",
    "transaction": "transaction",
    "pending": "pending",
    "failed": "failed",
    "balance": "balance",
    "machine": "machine",
    "device": "device",
    "portal": "portal",
    "login": "login",
}

WORD_RE = re.compile(r"\b[\w']+\b", re.IGNORECASE)

def normalize_hinglish(text: str) -> str:
    """
    Converts common Hinglish phrases into Hindi+English mixed text
    suitable for intent detection.

    Safe:
    - No translation
    - No guessing
    - Deterministic
    """
    if not text:
        return text

    def replace(match):
        word = match.group(0)
        key = word.lower()
        return HINGLISH_MAP.get(key, word)

    return WORD_RE.sub(replace, text)
