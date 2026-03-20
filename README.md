# Swara — Hindi Voice AI Agent for Swift Money

> A production-grade, real-time voice support agent that handles inbound merchant calls in Hindi/Hinglish — powered by RAG, OpenAI, and FAISS.

---

## Overview

**Swara** is an AI-powered phone support agent built for Swift Money merchants. It handles live inbound calls over WebSocket, understands Hindi and Hinglish speech, retrieves answers from a curated knowledge base (AEPS, DMT, BBPS, KYC, device issues), and responds with natural-sounding voice — entirely without a human agent.

```
Merchant calls → STT (Whisper) → Hinglish query → RAG (FAISS + BM25)
     → gpt-4o-mini → TTS (OpenAI) → 8 kHz audio → Merchant hears answer
```

---

## Features

- **Real-time voice loop** — WebSocket-based, half-duplex audio handling
- **Hybrid RAG retrieval** — Scored FAISS (inner product) with BM25 ensemble fallback
- **Hinglish understanding** — Query expansion maps Romanized Hindi to Devanagari for better retrieval
- **Structured response tagging** — `[ANSWER]` / `[CLARIFY]` / `[UNKNOWN]` / `[SILENT]` prevent hallucination
- **Unknown issue capture** — Automatically gathers merchant context through guided questions, saves for human review
- **Post-call analytics** — Intent extraction and email summaries after every call
- **Campaign engine** — Outbound merchant re-engagement campaigns with MySQL backend

---

## Architecture

```
Incoming Call (Teler/FreJun — 8 kHz PCM16)
    │
    ▼
new_frejun_app.py          HTTP API bridge        (port 8000)
    │
    ▼
agent_websocket_PROD.py    WebSocket voice loop   (port 8001)
    ├── STT      →  OpenAI Whisper (batched, 16 kHz)
    ├── Normalize →  Hinglish → Hindi query expansion
    ├── RAG      →  agent/rag_engine.py
    │               ├── Scored FAISS (threshold: inner product ≥ -0.25)
    │               └── BM25 ensemble fallback
    └── TTS      →  OpenAI → ffmpeg (24 kHz → 8 kHz) → base64 chunks
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI |
| Speech-to-Text | OpenAI Whisper (batch) |
| Text-to-Speech | OpenAI TTS → ffmpeg |
| LLM | gpt-4o-mini |
| Vector Store | FAISS (inner product, `text-embedding-3-large`) |
| Keyword Retrieval | BM25 (rank-bm25) |
| Telephony | FreJun / Teler (8 kHz PCM16 WebSocket) |
| Campaign DB | MySQL (SQLAlchemy) |
| Language | Python 3.11+ |

---

## Project Structure

```
voice_ai_agent/
├── agent_websocket_PROD.py       # Main real-time voice loop (STT → RAG → TTS)
├── new_frejun_app.py             # FastAPI HTTP bridge (port 8000)
├── new_frejun_server.py          # Call routing + FreJun webhooks
├── build_vector.py               # Build FAISS + BM25 indexes from knowledge base
├── test_rag_engine.py            # CLI tool to test RAG responses interactively
├── unknown_issue_store.py        # Unknown issue capture + JSON persistence
│
├── agent/
│   ├── rag_engine.py             # Core RAG: retrieval, LLM call, session state
│   ├── hybrid_retriever.py       # HybridRetriever (BM25 → FAISS fallback)
│   └── bm25_store.py             # BM25 index builder and loader
│
├── speech/
│   ├── stt_openai_batch_FIXED.py # Batched Whisper STT pipeline
│   └── tts_8khz.py               # FreJun-safe 8 kHz TTS wrapper
│
├── analysis/
│   ├── intent_extractor.py       # Post-call intent + summary extraction
│   └── hinglish_normalizer.py    # Pre-processing for Hinglish queries
│
├── campaign/
│   ├── campaign_runner.py        # Outbound campaign execution
│   ├── campaign_service.py       # Campaign business logic
│   └── db_campaign_store.py      # MySQL persistence layer
│
├── data/
│   └── combined_knowledge.txt    # Knowledge base (FAQs, AEPS scripts, product info)
│
└── vectorstore/
    ├── index.faiss               # FAISS semantic index
    ├── index.pkl                 # FAISS document store
    └── bm25_index.pkl            # BM25 keyword index
```

---

## Quick Start

### 1. Clone and set up environment

```bash
git clone <your-repo-url>
cd voice_ai_agent

python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
# Required
OPENAI_API_KEY=sk-...

# Telephony (FreJun/Teler)
TELER_API_KEY=your_teler_key
FROM_NUMBER=+91XXXXXXXXXX
TO_NUMBER=+91XXXXXXXXXX
PUBLIC_DOMAIN=your-public-domain.com

# MySQL (campaigns)
DB_HOST=localhost
DB_USER=your_db_user
DB_PASS=your_db_password
DB_NAME=your_db_name

# Email (post-call summaries)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASS=your_app_password
```

### 3. Build the vector indexes

Run this once, and again whenever the knowledge base changes:

```bash
python build_vector.py
```

Outputs:
- `vectorstore/index.faiss`
- `vectorstore/index.pkl`
- `vectorstore/bm25_index.pkl`

### 4. Start the services

**Terminal 1 — Voice runtime:**
```bash
python agent_websocket_PROD.py
# → ws://localhost:8001/ws/agent
```

**Terminal 2 — HTTP API bridge:**
```bash
python new_frejun_app.py
# → http://localhost:8000/docs
```

---

## Testing RAG Without Telephony

```bash
python test_rag_engine.py
```

Interactive CLI to test queries directly against the RAG engine. Unknown issues are not written to disk in this mode.

Example:
```
Q: AEPS transaction fail ho gayi kya kare
A: AEPS transaction fail hone par Lader report check karein...

Q: KYC ke liye kya kya chahiye
A: Aadhaar card, PAN card, aapki dukaan par hona, aur device hona zaroori hai...
```

---

## Triggering a Call (API)

With both services running:

```bash
curl -X POST http://localhost:8000/api/v1/initiate-call \
  -H "Content-Type: application/json" \
  -d '{"from_number": "+91XXXXXXXXXX", "to_number": "+91XXXXXXXXXX"}'
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## RAG Design

### Response Tags

Every LLM response is prefixed with a tag that controls agent behavior:

| Tag | Behavior |
|-----|----------|
| `[ANSWER]` | Direct answer from knowledge base — spoken to merchant |
| `[CLARIFY]` | KB has an answer but needs more context — asks one question |
| `[UNKNOWN]` | Not in KB — enters guided capture mode (max 4 questions) |
| `[SILENT]` | Merchant confirmed ("theek hai") — returns empty string |

If no tag is found → treated as `[UNKNOWN]` (safe fallback, never hallucinates).

### Retrieval Flow

```
1. Expand Hinglish query → Hindi-mixed form
2. Scored FAISS search (inner product, threshold ≥ -0.25)
3. If no docs pass threshold → BM25 ensemble fallback
4. If still no docs → FALLBACK_UNKNOWN (no LLM call)
5. LLM call with top docs → tagged response
```

---

## Production Deployment

1. Build indexes: `python build_vector.py`
2. Use a stable public HTTPS domain (not ngrok)
3. Run both services under a process manager (systemd / supervisor / pm2)
4. Put Nginx in front of `new_frejun_app.py` (port 8000) with TLS termination
5. Point FreJun/Teler webhooks to your public domain

```
Internet → Nginx (443/TLS) → new_frejun_app.py (8000)
                           → agent_websocket_PROD.py (8001)
```

---

## Common Issues

| Symptom | Fix |
|---------|-----|
| All queries fall to ensemble fallback | Check FAISS threshold in `rag_engine.py` (`RELEVANCE_THRESHOLD`) |
| Agent gives wrong/hallucinated answers | Update `data/combined_knowledge.txt` and rebuild indexes |
| `502` on call initiate | Upstream telephony issue — check account/trunk/number permissions |
| TTS audio garbled | Verify ffmpeg is installed and in PATH |
| ngrok URL not detected | Start ngrok first; fallback uses `PUBLIC_DOMAIN` env var |

---

## Knowledge Base

The agent answers from `data/combined_knowledge.txt` — a curated file combining:
- `faqs.txt` — structured Q&A for common merchant issues
- `aeps_script.txt` — AEPS transaction handling scripts
- `call_handling_guidelines.txt` — agent call flow guidelines
- `fintech.txt` — Swift Money product and company information

To add new knowledge: edit the source files, re-combine into `combined_knowledge.txt`, then run `python build_vector.py`.

---

## License

Private — Swift Money / Quicksun Technologies Pvt. Ltd.
