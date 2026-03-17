# CLAUDE.md — Swift Money Voice AI Agent (Swara)

## Project Overview

**Swara** is a Hindi/Hinglish phone-support voice agent for Swift Money merchants.
It handles inbound merchant queries (AEPS, DMT, BBPS, KYC, device issues) over a real-time WebSocket voice call, using RAG to answer from a curated knowledge base.

**Stack:** FastAPI · OpenAI (STT + TTS + LLM) · FAISS + BM25 (hybrid retrieval) · FreJun/Teler (telephony)

---

## Architecture

```
Incoming Call (Teler/FreJun, 8 kHz PCM16)
    ↓
new_frejun_app.py   (port 8000 — HTTP API bridge, call routing)
    ↓
agent_websocket_PROD.py   (port 8001 — WebSocket voice loop)
    ├─ STT: OpenAI batch transcription (16 kHz)
    ├─ Hinglish normalizer
    ├─ RAG: agent/rag_engine.py
    │      ├─ Query expansion (Hinglish → Hindi)
    │      ├─ Scored FAISS retrieval (threshold 0.35) → EnsembleRetriever fallback
    │      └─ gpt-4o-mini with tagged response format
    └─ TTS: OpenAI → ffmpeg (24 kHz → 8 kHz) → base64 chunks → WebSocket
    ↓
Post-call: intent extraction + email summary (analysis/)
```

---

## Key Files

| File | Role |
|------|------|
| `agent_websocket_PROD.py` | Main WebSocket voice loop (port 8001) |
| `new_frejun_app.py` | FastAPI HTTP bridge (port 8000) |
| `new_frejun_server.py` | Call routing, FreJun webhooks |
| `agent/rag_engine.py` | RAG engine — retrieval, LLM, session state |
| `agent/hybrid_retriever.py` | HybridRetriever (BM25 → FAISS fallback) |
| `agent/bm25_store.py` | BM25 index builder and loader |
| `speech/stt.py` | Faster-Whisper STT (large-v2, Hindi forced) |
| `speech/tts.py` | OpenAI TTS → 8 kHz PCM16 |
| `speech/tts_8khz.py` | FreJun-safe 8 kHz TTS wrapper |
| `build_vector.py` | Build FAISS + BM25 indexes (run once) |
| `config.py` | Greeting/farewell messages, exit keywords |
| `data/combined_knowledge.txt` | Main knowledge base (67 KB) |
| `vectorstore/` | FAISS index + BM25 pickle |
| `unknown_issues.json` | Auto-captured unknown merchant issues |
| `analysis/intent_extractor.py` | Post-call intent + summary extraction |
| `campaign/` | Campaign DB, runner, merchant seeding |

---

## How to Run Locally

```bash
# Terminal 1 — WebSocket voice runtime
python agent_websocket_PROD.py
# → ws://localhost:8001/ws/agent

# Terminal 2 — HTTP API bridge (FreJun webhooks)
python new_frejun_app.py
# → http://localhost:8000/docs
```

Both must be running for a complete call flow.

---

## Rebuild the Vector Store

Run this whenever `data/combined_knowledge.txt` changes:

```bash
python build_vector.py
```

Outputs:
- `vectorstore/index.faiss` — semantic index
- `vectorstore/index.pkl` — document store
- `vectorstore/bm25_index.pkl` — keyword index

**Chunk settings** (in `build_vector.py`): 500-char chunks, 100-char overlap, section-aware separators (`\n\n`, `\n`, `. `, `। `).

---

## RAG Engine Design

### Response tags
The LLM must start every response with one of these tags:

| Tag | Meaning |
|-----|---------|
| `[ANSWER]` | Direct KB-grounded answer (1–2 sentences) |
| `[CLARIFY]` | KB has answer but needs service/device clarification |
| `[UNKNOWN]` | Not in KB — starts capture mode (max 4 questions) |
| `[SILENT]` | Merchant confirmed ("theek hai") — return empty string |

If no tag is found in the LLM response, it is treated as `[UNKNOWN]` (safe fallback, never hallucinates).

### Retrieval flow
1. Expand Hinglish query to Hindi-mixed form (`_expand_query`)
2. Scored FAISS search — keep only docs with relevance score ≥ 0.35
3. If nothing passes the threshold → EnsembleRetriever fallback (BM25 + FAISS)
4. If still no docs → return `FALLBACK_UNKNOWN` immediately (no LLM call)

### Session state
- Per-call conversation memory (k=6 messages, auto-expires in 2 days)
- Capture mode state tracks original query, clarifications asked (max 4), and last question

---

## Environment Variables (`.env`)

```
OPENAI_API_KEY=...
TELER_API_KEY=...
FROM_NUMBER=...
TO_NUMBER=...
PUBLIC_DOMAIN=...          # ngrok or stable HTTPS domain
DB_HOST/DB_USER/DB_PASS/DB_NAME=...   # MySQL for campaigns
SMTP_HOST/SMTP_PORT/...   # email for post-call reports
```

---

## Known Gotchas

- **Audio format**: Teler sends 8 kHz PCM16. STT resamples to 16 kHz internally. TTS outputs 8 kHz.
- **Half-duplex**: The WebSocket loop discards incoming audio while TTS is playing (prevents echo collisions).
- **Hinglish gap**: The knowledge base is in Hindi/English. Merchant queries come in romanized Hinglish. The `_expand_query` map bridges this — if retrieval fails, extend the expansion map in `rag_engine.py`.
- **BM25 always returns results**: BM25 has no relevance threshold. Prefer the scored FAISS path which does. The ensemble fallback is a safety net only.
- **Relevance threshold**: `RELEVANCE_THRESHOLD = 0.35` in `rag_engine.py`. If valid queries are falling through to `[UNKNOWN]` incorrectly, lower this value. If hallucinations return, raise it.
- **`rag_engine.py` has 840+ lines of commented-out previous versions** at the top of the file (lines 1–841). The live code starts at line 842. Do not delete the comments without user confirmation.
- **Vectorstore rebuild required** after any change to `combined_knowledge.txt` or chunk settings in `build_vector.py`.
- **Port conflict**: Both services must run on separate ports (8000 + 8001). Nginx or a reverse proxy sits in front in production.
