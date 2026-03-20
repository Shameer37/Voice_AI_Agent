from __future__ import annotations

# ============================================================================
# unknown_issue_store.py
# ============================================================================
# Handles everything related to issues the agent couldn't answer:
#
#   1. save_unknown_issue()
#      - Writes the full captured context to unknown_issues.json
#      - Auto-embeds it into the live FAISS vectorstore so future calls
#        can find it immediately (no server restart needed)
#
#   2. load_unknown_issues()
#      - Reads all saved issues from JSON (used at startup to rebuild
#        the vectorstore if needed)
#
#   3. search_unknown_issues()
#      - Searches only the unknown_issues portion of the vectorstore
#        (optional — main retriever already searches everything)
#
# JSON schema per entry:
# {
#   "id":               "uuid4 string",
#   "session_id":       "caller session",
#   "timestamp":        "ISO 8601 UTC",
#   "original_query":   "first thing merchant said about this issue",
#   "clarifications":   [ {"question": "...", "answer": "..."}, ... ],
#   "full_summary":     "LLM-generated one-paragraph summary of the issue",
#   "status":           "open" | "resolved",
#   "resolution":       null or "filled in by support team manually"
# }
# ============================================================================

import os
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain.schema import Document

load_dotenv()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
UNKNOWN_ISSUES_JSON = os.getenv("UNKNOWN_ISSUES_PATH", "unknown_issues.json")
VECTORSTORE_PATH    = os.getenv("VECTORSTORE_PATH", "vectorstore")
EMBED_MODEL         = "text-embedding-3-large"
OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")


# ─────────────────────────────────────────────
# INTERNAL: load/save JSON file
# ─────────────────────────────────────────────

def _load_json() -> list[dict]:
    path = Path(UNKNOWN_ISSUES_JSON)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        logger.exception("[UnknownStore] Failed to load JSON")
        return []


def _save_json(records: list[dict]) -> None:
    try:
        with open(UNKNOWN_ISSUES_JSON, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("[UnknownStore] Failed to write JSON")


# ─────────────────────────────────────────────
# INTERNAL: build the text that gets embedded
# into FAISS for future retrieval
# ─────────────────────────────────────────────

def _build_embedding_text(record: dict) -> str:
    """
    Constructs a rich text representation of the captured issue
    that will be embedded into the vectorstore.

    Format is designed to match how merchants actually describe
    problems — so semantic search finds it naturally.
    """
    lines = [
        f"Issue reported by merchant: {record['original_query']}",
    ]

    if record.get("clarifications"):
        lines.append("Additional details gathered:")
        for qa in record["clarifications"]:
            lines.append(f"  Q: {qa['question']}")
            lines.append(f"  A: {qa['answer']}")

    if record.get("full_summary"):
        lines.append(f"Summary: {record['full_summary']}")

    if record.get("resolution"):
        lines.append(f"Resolution: {record['resolution']}")
    else:
        lines.append("Resolution: Under investigation by support team.")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# INTERNAL: embed one record into live FAISS
# ─────────────────────────────────────────────

def _embed_into_vectorstore(record: dict) -> bool:
    """
    Adds the captured issue as a new Document into the existing
    FAISS vectorstore. The vectorstore is saved back to disk so
    it persists across restarts.

    Returns True on success, False on failure.
    """
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(model=EMBED_MODEL, api_key=OPENAI_API_KEY)

        # Load the existing vectorstore
        vectorstore = FAISS.load_local(
            VECTORSTORE_PATH,
            embeddings,
            allow_dangerous_deserialization=True
        )

        # Build the document
        text = _build_embedding_text(record)
        doc = Document(
            page_content=text,
            metadata={
                "source":       "unknown_issue_capture",
                "issue_id":     record["id"],
                "session_id":   record["session_id"],
                "timestamp":    record["timestamp"],
                "status":       record["status"],
            }
        )

        # Add and save back
        vectorstore.add_documents([doc])
        vectorstore.save_local(VECTORSTORE_PATH)

        logger.info(f"[UnknownStore] Embedded issue {record['id']} into vectorstore")
        return True

    except Exception:
        logger.exception(f"[UnknownStore] Failed to embed issue {record.get('id')} into vectorstore")
        return False


# ─────────────────────────────────────────────
# PUBLIC: save a new unknown issue
# ─────────────────────────────────────────────

def save_unknown_issue(
    session_id:     str,
    original_query: str,
    clarifications: list[dict],   # [{"question": "...", "answer": "..."}]
    full_summary:   str,
) -> dict:
    """
    Saves a captured unknown issue to JSON and embeds it into the
    vectorstore for future retrieval.

    Args:
        session_id:     The call session identifier
        original_query: The merchant's first message about this issue
        clarifications: List of Q&A pairs gathered during the call
        full_summary:   LLM-generated summary of the full issue context

    Returns:
        The saved record dict
    """
    record = {
        "id":             str(uuid.uuid4()),
        "session_id":     session_id,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "original_query": original_query,
        "clarifications": clarifications,
        "full_summary":   full_summary,
        "status":         "open",
        "resolution":     None,
    }

    # 1. Save to JSON (skipped in test mode)
    if os.getenv("RAG_TEST_MODE") == "1":
        logger.info(f"[UnknownStore] TEST MODE — skipping JSON write for issue {record['id']}")
        return record

    records = _load_json()
    records.append(record)
    _save_json(records)
    logger.info(f"[UnknownStore] Saved issue {record['id']} to {UNKNOWN_ISSUES_JSON}")

    # Auto-embedding disabled: case records should not pollute the KB vectorstore.
    # Unknown issues are stored in JSON only for human review and email reporting.

    return record


# ─────────────────────────────────────────────
# PUBLIC: load all saved issues (for inspection / email)
# ─────────────────────────────────────────────

def load_unknown_issues(status_filter: Optional[str] = None) -> list[dict]:
    """
    Returns all saved unknown issues.
    Pass status_filter='open' to get only unresolved issues.
    """
    records = _load_json()
    if status_filter:
        records = [r for r in records if r.get("status") == status_filter]
    return records


# ─────────────────────────────────────────────
# PUBLIC: mark an issue as resolved
# (called manually or by support team tooling)
# ─────────────────────────────────────────────

def resolve_unknown_issue(issue_id: str, resolution: str) -> bool:
    """
    Marks an issue as resolved and updates both the JSON file
    and the vectorstore embedding (with resolution text).
    """
    records = _load_json()
    for record in records:
        if record["id"] == issue_id:
            record["status"]     = "resolved"
            record["resolution"] = resolution
            _save_json(records)
            # Re-embed with the resolution text so future searches
            # can find the answer in this resolved case
            _embed_into_vectorstore(record)
            logger.info(f"[UnknownStore] Resolved issue {issue_id}")
            return True

    logger.warning(f"[UnknownStore] Issue {issue_id} not found for resolution")
    return False