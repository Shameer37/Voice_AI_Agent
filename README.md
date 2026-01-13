Voice AI Agent for Merchant Re-engagement (Swift Money)

This project implements a production-ready Voice AI Agent that interacts with merchants using Speech-to-Text (STT) and Text-to-Speech (TTS) in real time.
The agent is designed to re-engage inactive merchants, understand their issues, and provide helpful responses using RAG (Retrieval-Augmented Generation).

✅ Key Features

> Real-time Voice Agent over WebSocket (FastAPI)

> Speech-to-Text (STT) using OpenAI transcription

> Text-to-Speech (TTS) in 8kHz streaming audio (FreJun-safe)

> Half-Duplex Mode (No overlap)
Agent speaks → user input ignored
User speaks → agent listens

> Turn Detection
Uses audio energy (RMS) to detect speech vs silence
Automatically ends turn when silence is detected

> RAG (Retrieval-Augmented Generation)
Retrieves relevant knowledge from FAISS vectorstore
Generates context-aware responses

✅ Technologies Used

Python
FastAPI + WebSocket
asyncio (concurrent processing)
OpenAI STT (transcription)
OpenAI / LLM (response generation via RAG)
LangChain (RAG + conversation memory)
FAISS (vector search)
SentenceTransformers (embeddings)
8kHz TTS streaming (FreJun safe playback)


✅ Project Structure
voice_ai_agent/
├── agent/
│   └── rag_engine.py
│       # RAG pipeline: embeddings + FAISS retrieval + conversational response logic
│
├── speech/
│   ├── stt_openai_batch_FIXED.py
│   │   # Buffered STT pipeline (chunks → OpenAI transcription)
│   └── tts_8khz.py
│       # Generates 8kHz FreJun-safe TTS streaming audio chunks
│
├── data/
│   └── fintech.txt
│       # Knowledge base used to build vectorstore
│
├── vectorstore/
│   ├── index.faiss
│   └── index.pkl
│       # Generated vectorstore files
│
├── build_vector.py
│   # Converts fintech.txt → FAISS vectorstore
│
├── agent_websocket_PROD.py
│   # ✅ Core production voice agent (WebSocket STT + RAG + TTS)
│
├── new_frejun_server.py
│   # ✅ Server that bridges FreJun call audio ↔ your WebSocket voice agent
│   # (FreJun hits this server when a call connects)
│
├── new_frejun_app.py
│   # ✅ Outbound call trigger script
│   # (starts a call using FreJun API and connects it to your server)
│
├── requirements.txt
├── .env
├── .gitignore
└── README.md

✅ Setup
1️⃣ Clone the Repository
git clone https://github.com/Shameer37/Voice-AI-Agent.git
cd voice_ai_agent

2️⃣ Install Dependencies
pip install -r requirements.txt

3️⃣ Environment Variables

Create a .env file:

OPENAI_API_KEY=your_openai_key_here

# FreJun credentials (example keys, adjust to your actual implementation)
FREJUN_API_KEY=your_frejun_key_here
FREJUN_CALLER_ID=your_registered_number_or_id
FREJUN_AGENT_SERVER_URL=http://YOUR_PUBLIC_URL:PORT


✅ Build Vector Store (For RAG)

Make sure data/fintech.txt exists, then run:

python build_vector.py


This will generate:

vectorstore/index.faiss

vectorstore/index.pkl

✅ How to Run the System (Correct Order)

Your system has 3 components:

✅ Voice Agent (WebSocket: STT + RAG + TTS)

✅ FreJun Bridge Server (accepts call audio + routes it to agent)

✅ FreJun Caller App (triggers outbound call)

✅ Step 1: Start the Voice Agent (WebSocket)

Run:

python agent_websocket_PROD.py


By default it runs here:

ws://0.0.0.0:8001/ws/agent

✅ Step 2: Start the FreJun Bridge Server

Run:

python new_frejun_server.py


This server should:

accept FreJun connection for call audio

forward merchant audio to your agent WebSocket

forward agent TTS back to FreJun call stream

Example server URL:

http://0.0.0.0:9000


✅ If FreJun requires a webhook/callback URL, this server must be reachable publicly.

✅ Step 3: Make a Test Outbound Call using FreJun App

Run:

python new_frejun_app.py


This script should:

pick a target phone number

create an outbound FreJun call

attach it to your new_frejun_server.py audio stream endpoint

✅ How a Call Works (End-to-End Flow)
✅ Call flow

new_frejun_app.py triggers outbound call

FreJun connects the call to your new_frejun_server.py server

new_frejun_server.py opens a WebSocket to your agent:

ws://localhost:8001/ws/agent


Merchant speaks → audio → STT

Transcript → RAG → LLM reply

Reply → TTS → audio back into FreJun call

✅ How to Make a Call Successfully (Requirements)

✅ You MUST ensure these things:

✅ 1) Your FreJun server must be publicly accessible

If you are running locally, use:

ngrok http 9000


Then set:

FREJUN_AGENT_SERVER_URL=https://xxxxx.ngrok-free.app

✅ 2) Your FreJun credentials must be correct

If FreJun rejects your request:

invalid API key

unregistered caller ID

restricted test environment

✅ 3) Your agent port must be reachable from FreJun server

Normally:

Agent runs at: localhost:8001

FreJun server runs at: localhost:9000


# File Descriptions
1.agent_websocket_PROD.py: Runs the production FastAPI WebSocket voice agent pipeline (STT → RAG/LLM → TTS) with turn-handling and half-duplex control.

2.agent/rag_engine.py: Loads the FAISS retriever and generates contextual responses using RAG + conversation memory.

3.speech/stt_openai_batch_FIXED.py: Buffers incoming audio and performs OpenAI-based speech-to-text transcription with filtering and reset logic.

4.speech/tts_8khz.py: Generates FreJun-safe 8kHz TTS audio chunks and supports caching for greeting/filler/farewell messages.

5.new_frejun_server.py: Bridges FreJun call audio streaming with the AI agent WebSocket for real-time two-way communication.

6.new_frejun_app.py: Starts outbound calls via FreJun and connects the call flow to your streaming server/agent.

7.build_vector.py: Builds and saves the FAISS vectorstore from knowledge files for retrieval-augmented generation.

8.data/fintech.txt: Contains Swift Money support knowledge used as the retrieval source for RAG responses.

9.vectorstore/: Stores the generated FAISS index files used for fast similarity search during retrieval.


✅ Database Integration (Optional / Future Enhancement)

Right now the agent runs fully in real-time using WebSocket streaming, and the conversation flow is handled live during the call.
For production-scale tracking, you can integrate a database (MySQL/PostgreSQL) to store:

>Call metadata (call_id, merchant_id, phone, start_time, end_time, duration)

>Conversation logs (STT text, agent replies, timestamps)

>Final outcome (resolved / not resolved / callback required)

>Failures (network drop, STT failure, API timeout, retry count)

>This helps in analytics, reporting, and running future re-engagement cycles reliably.

✅ Improving Real-Time Performance (Based on Current Flow)

>Your latency is mainly coming from STT + LLM + TTS network calls, so optimization must focus on these:

>Keep STT buffering small but stable (use silence-based cut + max turn length) to avoid large transcription payloads

>Use cached greeting/filler/farewell audio so calls start instantly without waiting for TTS generation

>Run LLM response generation asynchronously while filler plays (so user feels instant response)

>Avoid duplicate STT→LLM triggers by enforcing background_task cancellation + TURN_COOLDOWN_SECONDS

>Use strict half-duplex gating (tts_active) to stop STT from capturing your own agent voice

>Shorten TTS chunk size (120ms is good) to stream output faster and feel more “live”

✅ Future Enhancements (Realistic Next Upgrades)

>Once your core pipeline is stable, these are the upgrades that actually matter:

>Intent normalization layer (clean noisy Hinglish STT into a better query before sending to RAG/LLM)

>Better voice activity detection (VAD) to reduce false turns from noise or background speech

>Merchant-specific context injection (merchant name, last transaction status, last issue) into RAG prompt

>Call outcome classification (resolved / follow-up / escalation / wrong number) stored automatically

>Multi-turn policy rules (avoid repeating same reply, ask missing details intelligently)

>Campaign mode execution (outbound calls list → call → log → move to next merchant)
 
# License
This project is licensed under the MIT License.
