# Voice AI Agent for Merchant Re-engagement
This project implements a Voice AI agent that can interact with merchants using text-to-speech (TTS) and speech-to-text (STT) technologies. The system aims to re-engage inactive merchants, resolve their issues, and persuade them to resume using the Swift Money services.


# Technologies Used 
Python (Programming Language)
Edge TTS (Text-to-Speech API for speech synthesis)
Vosk API / Whisper AI / Faster Whisper (for Speech-to-Text functionality)
LangChain (for RAG and NLP processing)
FAISS (for vector search and embedding retrieval)
MySQL (for database management)
asyncio (for asynchronous task handling)


# Project Structure
voice-ai-agent/
├── agent/
│   └── rag_engine.py       # Loads RAG and context retriever logic
├── recordings/             # Folder for storing recorded audio files (TTS and STT)
├── logs/                   # Folder for session logs (user input and agent responses)
├── .env                    # Environment variables for sensitive keys (e.g., ANTHROPIC_API_KEY)
├── .gitignore              # Git ignore file to exclude unnecessary files
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation
├── data/                   # Folder for documents and text data (e.g., fintech.txt)
│   └── fintech.txt         # Example text file for building vector store
├── speech/                 # Folder for TTS and STT functionality
│   ├── tts.py              # Handles Text-to-Speech generation
│   └── stt.py              # Handles Speech-to-Text conversion
├── build_vector.py         # Script for building vector store from text data (fintech.txt)
└── main.py                 # Main entry point for running the agent
└── vectorstore/
    └── index.faiss         # Handles vector store creation and retrieval logic
    └── index.pkl            # Pickle file for storing vector embeddings

# Setup
Clone the repository:
git clone https://github.com/Shameer37/Voice-AI-Agent.git
cd voice-ai-agent

Install dependencies:
pip install -r requirements.txt

Set up environment variables:
Create a .env file to store sensitive keys like Anthropic API Key for the AI agent:
ANTHROPIC_API_KEY=your_anthropic_api_key_here

Prepare the data:
Ensure you have your text files (e.g., fintech.txt) placed in the data/ folder. This file will be used to build the vector store for context retrieval.

Build the vector store:
Use build_vector.py to convert the fintech.txt file into a vector store.
python build_vector.py

Run the agent:
You can run the main agent using:
python main.py


# How It Works
1. Speech-to-Text (STT)
The agent listens to the merchant using Vosk (or Whisper AI) for real-time transcription.
The transcribed speech is converted into text, which is passed on to the agent for processing.

2. Text-to-Speech (TTS)
The agent generates responses based on the merchant's input using Edge TTS.
The responses are converted to speech (audio) and played back to the merchant.

3. RAG (Retrieval-Augmented Generation)
The system loads a vector store containing the context (e.g., fintech.txt).
The agent uses LangChain's RAG to retrieve relevant information and generate context-based responses to the merchant's inquiries.

4. Session Management
Every session is logged into a logs/ folder, including both user input (STT) and agent responses (TTS).
The recordings/ folder stores audio files of both user speech and agent responses.
Each session has a unique session_id that ensures the responses and recordings are stored in an organized manner.


# File Descriptions
1. main.py: The main entry point for running the agent. Handles the initialization of the conversation and integrates STT, TTS, and RAG functionality and contains logic for processing merchant messages and generating AI responses using LangChain’s RAG model.

2. conversation_handler.py: Manages the conversation flow, such as greeting the merchant, handling interactions, and saving session logs.

3. rag_engine.py: Handles the loading of the vector store and uses RAG to generate responses based on context.

4. tts.py: Manages the Text-to-Speech conversion, generating voice responses from text.

5. stt.py: Manages the Speech-to-Text conversion, capturing audio input from the user and converting it to text.

6. build_vector.py: A utility to build the vector store from a text file, such as fintech.txt, used for context-based retrieval.


# Database Integration (Future Enhancement)
The system currently logs session data in local files (logs/), but the next step would be to integrate MySQL for persistent session storage.
Sessions would be stored with details about the merchant, the conversation history, and any issues they raised.
Session Expiry: Sessions will be automatically deleted after 7 days if no further interaction occurs.
 

# Improving Real-Time Performance
Use Multi-Threading or Multi-Processing: By using asyncio with threading or multiprocessing, you can perform transcription, generation, and playback in parallel.
Optimize STT and TTS Speed: Depending on the platform and API, consider using faster models or reducing model sizes for faster inference.
Minimize Latency: Cache frequently requested responses and optimize the flow between different components (STT, TTS, RAG).


# Future Enhancements
Integration with MySQL for storing sessions and merchant details.
Improved multi-turn dialogues (e.g., follow-up questions and responses).
Hinglish language support for mixed language conversations.
Real-time sentiment analysis of the conversation to adjust the agent’s tone dynamically.
 
# License
This project is licensed under the MIT License. See the LICENSE file for more details.
