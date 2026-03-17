# Voice AI Agent (Swift Money)

Production-grade voice agent for merchant re-engagement using:
- FastAPI WebSocket voice runtime
- OpenAI STT + TTS
- RAG with FAISS (OpenAI embeddings)
- FreJun/Teler bridge for outbound call flow

## 1) Run Modes

### Local Testing (recommended while developing)
Use these files:
1. `agent_websocket_PROD.py` -> voice runtime (`ws://localhost:8001/ws/agent`)
2. `new_frejun_app.py` -> API bridge (`http://localhost:8000`)


### Production Runtime
Use these files/services:
1. `agent_websocket_PROD.py` behind process manager (systemd/pm2/supervisor)
2. `new_frejun_app.py` behind reverse proxy (Nginx) + public TLS domain
3. ngrok is for local only; production should use stable public domain

## 2) File Structure and Responsibilities

```text
voice_ai_agent/
├── agent_websocket_PROD.py              # Main real-time voice loop (STT -> RAG -> TTS)
├── new_frejun_app.py                    # FastAPI app entrypoint for call APIs
├── new_frejun_server.py                 # Router/bridge logic for call flow + webhooks + media stream
├── build_vector.py                      # Build FAISS vector index from KB text
├── test_rag_engine.py                   # CLI test for RAG responses
├── requirements.txt                     # Python dependencies
├── README.md
│
├── agent/
│   ├── rag_engine.py                    # Retrieval + response generation
│   ├── hybrid_retriever.py              # BM25 + vector fallback retriever
│   ├── issue_schema.py                  # Issue categorization schema/rules
│   ├── semnatic_chunker.py              # Semantic chunk helper (experimental/optional)
│   ├── transcriptLogger.py              # Transcript helpers
│   └── utils/
│       ├── email_utils.py               # Post-call summary email
│       ├── language_utils.py            # Language/script helpers
│       └── time_utils.py                # UTC/IST formatting and time helpers
│
├── analysis/
│   ├── intent_extractor.py              # Post-call intent + summary extraction
│   ├── hinglish_normalizer.py           # Hinglish normalization before downstream processing
│   └── faq_context.py                   # FAQ context constants
│
├── speech/
│   ├── stt_openai_batch_FIXED.py        # Buffered STT pipeline
│   └── tts_8khz.py                      # FreJun-safe 8kHz TTS output
│
├── campaign/
│   ├── db.py                            # Campaign DB engine/session setup
│   ├── campaign_models.py               # Campaign DB models
│   ├── db_campaign_store.py             # Merchant/campaign persistence layer
│   ├── campaign_runner.py               # Campaign execution runner
│   └── campaign_service.py              # Campaign business service
│
├── calls/
│   └── call_controller.py               # Outbound call control abstraction
│
├── scripts/
│   ├── seed_merchants.py                # Seed test merchants in campaign DB
│   └── build_bm25.py                    # Build BM25 index file (optional hybrid retrieval)
│
├── data/
│   ├── combined_knowledge.txt           # Main RAG knowledge source
│   └── faqs.txt                         # FAQ source
│
└── vectorstore/
    ├── index.faiss                      # FAISS index
    ├── index.pkl                        # FAISS metadata/docstore
    └── bm25.pkl                         # BM25 index (optional)
```

## 3) Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4) Environment Variables (`.env`)

Minimum required:

```env
OPENAI_API_KEY=your_openai_key
TELER_API_KEY=your_teler_key
LOCAL_AGENT_WEBSOCKET_URL=ws://localhost:8001/ws/agent
SERVER_DOMAIN=your-public-domain.example.com
FROM_NUMBER=+91XXXXXXXXXX
TO_NUMBER=+91XXXXXXXXXX
```

Notes:
- `new_config.py` tries to auto-detect ngrok using `http://127.0.0.1:4040/api/tunnels`.
- If ngrok is not running, it falls back to `SERVER_DOMAIN`.

## 5) Build Retrieval Indexes

### Required: FAISS index

```powershell
.\.venv\Scripts\python.exe build_vector.py
```

Creates:
- `vectorstore/index.faiss`
- `vectorstore/index.pkl`

### Optional: BM25 index for hybrid retriever

```powershell
.\.venv\Scripts\python.exe -m scripts.build_bm25
```

Creates:
- `vectorstore/bm25.pkl`

## 6) Local Testing Runbook

### Terminal 1: Voice runtime

```powershell
.\.venv\Scripts\python.exe agent_websocket_PROD.py
```

### Terminal 2: Bridge/API runtime

```powershell
.\.venv\Scripts\python.exe new_frejun_app.py
or
python new_frejun_app.py
```

Open:
- `http://localhost:8000/docs`

Trigger call:
- `POST /api/v1/initiate-call`

Payload:

```json
{
  "from_number": "+91XXXXXXXXXX",
  "to_number": "+91XXXXXXXXXX"
}
```

### RAG-only test (no telephony)

```powershell
.\.venv\Scripts\python.exe test_rag_engine.py
```

## 7) Production Runbook (high level)

1. Build indexes (`build_vector.py`, optional `scripts/build_bm25.py`)
2. Deploy app with stable domain and TLS
3. Run both services with process manager:
   - `agent_websocket_PROD.py` on `8001`
   - `new_frejun_app.py` on `8000`
4. Put reverse proxy in front of `new_frejun_app.py`
5. Configure telephony provider callbacks to production domain

## 8) Common Failure Points

1. `POST .../calls/initiate` returns `502`
- upstream provider-side issue (account, trunk, number permissions, routing)

2. `Failed to create call: 'data'`
- code assumed success payload shape on an error response
- add defensive response parsing and error-body logging in call-init path

3. RAG answers too generic/fallback-heavy
- ensure `data/combined_knowledge.txt` has needed entries
- rebuild indexes after KB edits

4. ngrok URL not detected
- start ngrok and verify `http://127.0.0.1:4040/api/tunnels` is reachable

## 9) Quick Restart Sequence

```powershell
# 1) (optional) rebuild indexes if KB changed
.\.venv\Scripts\python.exe build_vector.py

# 2) start voice runtime
.\.venv\Scripts\python.exe agent_websocket_PROD.py

# 3) start bridge/api runtime
.\.venv\Scripts\python.exe new_frejun_app.py
```
