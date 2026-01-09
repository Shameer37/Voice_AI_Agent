# from __future__ import annotations

# import os
# import time
# import threading
# from datetime import datetime, timedelta
# from typing import Optional

# from langchain_community.vectorstores import FAISS
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_classic.chains import ConversationalRetrievalChain
# from langchain_classic.memory import ConversationBufferWindowMemory
# from langchain_community.chat_message_histories import ChatMessageHistory
# from langchain_classic.prompts import PromptTemplate
# from langchain_anthropic import ChatAnthropic
# from anthropic import RateLimitError
# from langchain_openai import ChatOpenAI
# import logging
# logger = logging.getLogger(__name__)

# # ──────────────────────────────────────────────────────────────────────────────
# # Inline configuration (edit here)
# # ──────────────────────────────────────────────────────────────────────────────
# EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# ANTHROPIC_MODEL = "claude-opus-4-20250514"
# ANTHROPIC_TEMPERATURE = 0.3
# ANTHROPIC_TIMEOUT = 20            # seconds
# ANTHROPIC_MAX_TOKENS = 300




# # Simple client-side rate limit guard
# ANTHROPIC_RATE_MAX_CALLS = 4
# ANTHROPIC_RATE_WINDOW_SECS = 60

# # If not set here, we’ll read from env once at import time.
# ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY","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") 

# # Fallback line you asked for when the agent doesn’t know
# FALLBACK_UNKNOWN = (
#     "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है "
#     "तथा शीघ्र ही आपको जवाब देंगे!"
# )

# # ──────────────────────────────────────────────────────────────────────────────
# # Public API to set/override Anthropic key at runtime (optional)
# # ──────────────────────────────────────────────────────────────────────────────
# def set_anthropic_key(key: str) -> None:
#     global ANTHROPIC_API_KEY, _llm
#     ANTHROPIC_API_KEY = key
#     _init_llm(force=True)  # re-instantiate with new key

# # ──────────────────────────────────────────────────────────────────────────────
# # Memory store (in-process)
# # ──────────────────────────────────────────────────────────────────────────────
# user_memory_store: dict[str, tuple[ConversationBufferWindowMemory, datetime]] = {}

# def create_memory() -> ConversationBufferWindowMemory:
#     return ConversationBufferWindowMemory(
#         memory_key="history",
#         input_key="question",
#         return_messages=True,
#         chat_memory=ChatMessageHistory()
#     )

# def get_user_memory(session_id: str) -> ConversationBufferWindowMemory:
#     now = datetime.now()
#     item = user_memory_store.get(session_id)
#     if item:
#         mem, last_updated = item
#         if now - last_updated > timedelta(days=2):
#             mem = create_memory()
#     else:
#         print(f"🆕 New memory created for {session_id}")
#         mem = create_memory()
#     user_memory_store[session_id] = (mem, now)
#     return mem

# # ──────────────────────────────────────────────────────────────────────────────
# # Retriever / Vector store
# # ──────────────────────────────────────────────────────────────────────────────
# def load_context_retriever(vectorstore_path: str):
#     """
#     Loads FAISS index from disk and returns a retriever (k=3).
#     """
#     embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL,model_kwargs = {"device": "cuda"})
#     vectorstore = FAISS.load_local(
#         vectorstore_path,
#         embeddings,
#         allow_dangerous_deserialization=True
#     )
#     return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})

# # ──────────────────────────────────────────────────────────────────────────────
# # Prompt (tight and with explicit unknown-answer rule you wanted)
# # ──────────────────────────────────────────────────────────────────────────────
# # system_prompt = """You are a female, polite, and helpful AI voice agent named Swara from **Swift Money** (by **Quicksun Technologies**).

# # You are speaking on a PHONE CALL with a retail merchant in India who was previously active on Swift Money but is now inactive.

# # Your goal:
# # - Understand in simple words why they stopped using Swift Money.
# # - Help them solve the issue if possible.
# # - Politely encourage them to start using Swift Money again.

# # VERY IMPORTANT SPEAKING STYLE (this is a phone call, not chat):
# # - Answer in **natural spoken Hindi**, with very light simple English words only where needed (e.g., "payment", "settlement", "balance").
# # - Use **short sentences**, like a human speaking. Prefer 1–2 short lines, not long paragraphs.
# # - Be friendly but professional. Small fillers like “जी”, “अच्छा”, “ठीक है” are okay, but do NOT overuse them.
# # - NEVER sound like a script reader. Vary your phrasing a bit across turns.
# # - Do NOT repeat the same greeting in every answer.
# # - Do NOT restate the full company intro again and again.

# # Flow of the call:
# # 1) Greet once at the beginning and introduce yourself as Swara from Swift Money.
# # 2) Ask why they stopped using Swift Money and listen carefully.
# # 3) Use ONLY the Knowledge Base to give accurate information and solutions.
# # 4) If needed, ask for their phone number for follow-up.
# # 5) Ask if there are any other doubts or issues.
# # 6) If you are unaware or the answer is NOT in the Knowledge Base, reply EXACTLY:
# #    "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"
# # 7) If the user clearly wants to end (bye/thanks/धन्यवाद/नहीं etc.), close the call briefly and politely.

# # Hard rules:
# # - Use ONLY the Knowledge Base below. If something is not covered, use the fallback line in step 6.
# # - Keep every answer short (ideally 1–2 lines).
# # - Make sure your tone is empathetic and practical, like a real support agent.

# # Knowledge Base (use ONLY this):
# # {context}

# # Chat History:
# # {history}

# # Question:
# # {question}
# # """

# system_prompt = """
# You are Swara, a polite and helpful female AI voice agent from Swift Money.

# IMPORTANT CONTEXT:
# You are already connected on a PHONE CALL with a retail merchant in India.
# The greeting and introduction have ALREADY happened.

# GREETING RULE (HARD):
# - NEVER greet again.
# - NEVER introduce yourself again.
# - NEVER repeat company name unless strictly required.

# YOUR GOAL:
# - Understand why the merchant stopped using Swift Money.
# - Help resolve the issue if possible.
# - Encourage them to restart usage, politely.

# SPEAKING STYLE (VOICE CALL):
# - Speak in natural spoken Hindi.
# - Use light English words only if common (payment, transaction, settlement).
# - Keep responses SHORT.
# - Max 2 sentences.
# - Prefer asking ONE clear question.
# - Friendly, empathetic, practical.

# FLOW RULES:
# - Ask clarifying questions if the issue is unclear.
# - Use the Knowledge Base for factual answers.
# - For clarification questions, use common sense.
# - Do NOT over-explain.
# - Do NOT sound scripted.

# FALLBACK RULE (STRICT):
# If the answer is NOT present in the Knowledge Base, reply EXACTLY:
# "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"

# EXIT RULE:
# If the merchant wants to end the call (bye / धन्यवाद ):
# - End politely in one short line.

# RESPONSE FORMAT:
# - 1–2 short sentences only.
# - No paragraphs.


# Knowledge Base:
# {context}

# Conversation so far:
# {history}

# Merchant says:
# {question}

# Your response:
# """

# # qa_prompt = PromptTemplate(
# #     input_variables=["context", "history", "question"],
# #     template=system_prompt
# # )

# qa_prompt = PromptTemplate(
#     input_variables=["context", "history", "question"],
#     template=system_prompt
# )

# # ──────────────────────────────────────────────────────────────────────────────
# # Anthropic client (LangChain wrapper) + simple rate limiter
# # ──────────────────────────────────────────────────────────────────────────────
# class _RateLimiter:
#     def __init__(self, max_calls: int, per_seconds: int):
#         self.max_calls = max_calls
#         self.per_seconds = per_seconds
#         self.lock = threading.Lock()
#         self.calls: list[float] = []

#     def acquire(self):
#         with self.lock:
#             now = time.time()
#             # purge old calls
#             self.calls = [t for t in self.calls if now - t < self.per_seconds]
#             if len(self.calls) >= self.max_calls:
#                 sleep_for = self.per_seconds - (now - self.calls[0])
#                 if sleep_for > 0:
#                     time.sleep(sleep_for)
#                 # purge again after sleep
#                 now = time.time()
#                 self.calls = [t for t in self.calls if now - t < self.per_seconds]
#             self.calls.append(time.time())

# _anthropic_limiter = _RateLimiter(ANTHROPIC_RATE_MAX_CALLS, ANTHROPIC_RATE_WINDOW_SECS)
# _llm: Optional[ChatAnthropic] = None

# def _init_llm(force: bool = False) -> ChatAnthropic:
#     global _llm
#     if _llm is not None and not force:
#         return _llm
#     if not ANTHROPIC_API_KEY:
#         raise RuntimeError(
#             "ANTHROPIC_API_KEY is not set. Either call set_anthropic_key('sk-ant-...') "
#             "or set the variable at the top of rag_engine.py."
#         )
#     _llm = ChatAnthropic(
#         model=ANTHROPIC_MODEL,
#         temperature=ANTHROPIC_TEMPERATURE,
#         api_key=ANTHROPIC_API_KEY,
#         max_retries=0,          # we apply our own limiter
#         max_tokens=ANTHROPIC_MAX_TOKENS,
#         timeout=ANTHROPIC_TIMEOUT
#     )
#     return _llm

# # ──────────────────────────────────────────────────────────────────────────────
# # Main entry: get_contextual_response
# # ──────────────────────────────────────────────────────────────────────────────
# def get_contextual_response(user_query: str, retriever, user_id: str) -> str:
#     """
#     Blocking function; safe to call via asyncio.to_thread in your WS loop.
#     Uses ConversationalRetrievalChain with the inline prompt above.
#     If the model returns empty/irrelevant text, we apply the fixed fallback line.
#     """
#     llm = _init_llm()

#     # Nudge to answer in Hindi
#     hint = "उत्तर हिंदी में दें: "
#     user_query = hint + (user_query or "").strip()

#     mem = get_user_memory(user_id)

#     qa_chain = ConversationalRetrievalChain.from_llm(
#         llm=llm,
#         retriever=retriever,
#         memory=mem,
#         combine_docs_chain_kwargs={"prompt": qa_prompt},
#         return_source_documents=False
#     )

#     try:
#         _anthropic_limiter.acquire()
#         result = qa_chain.invoke({"question": user_query, "chat_history": []})
#         answer = (result.get("answer") or "").strip()

#         # Guardrails: if LLM returns nothing or apologizes vaguely, force your fallback line
#         if not answer or len(answer) < 2:
#             return FALLBACK_UNKNOWN

#         lowered = answer.lower()
#         if any(
#             phrase in lowered
#             for phrase in [
#                 "i’m sorry", "i am sorry", "sorry", "माफ़ कीजिए", "क्षमा", "मुझे खेद है"
#             ]
#         ):
#             return FALLBACK_UNKNOWN

#         return answer

#     except RateLimitError:
#         # Graceful short fallback under rate limits
#         return "अभी सिस्टम व्यस्त है, लेकिन मैंने आपकी बात नोट कर ली है—कृपया एक वाक्य में फिर से बताइए।"
#     except Exception as e:
#         logger = logging.getLogger(__name__)
#         logger.exception("[RAG] LLM call failed")
#         return "माफ़ कीजिए, अभी तकनीकी समस्या आ गई। कृपया दोबारा एक बार कह दीजिए।"


from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_classic.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.3
OPENAI_MAX_TOKENS = 300
OPENAI_TIMEOUT = 20

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

FALLBACK_UNKNOWN = (
    "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है "
    "तथा शीघ्र ही आपको जवाब देंगे!"
)

# ─────────────────────────────────────────────────────────────
# Memory store
# ─────────────────────────────────────────────────────────────
user_memory_store: dict[str, tuple[ConversationBufferWindowMemory, datetime]] = {}

def create_memory() -> ConversationBufferWindowMemory:
    return ConversationBufferWindowMemory(
        memory_key="history",
        input_key="question",
        return_messages=True,
        chat_memory=ChatMessageHistory()
    )

def get_user_memory(session_id: str) -> ConversationBufferWindowMemory:
    now = datetime.now()
    item = user_memory_store.get(session_id)

    if item:
        mem, last_updated = item
        if now - last_updated > timedelta(days=2):
            mem = create_memory()
    else:
        logger.info(f"🆕 New memory created for {session_id}")
        mem = create_memory()

    user_memory_store[session_id] = (mem, now)
    return mem

# ─────────────────────────────────────────────────────────────
# Retriever
# ─────────────────────────────────────────────────────────────
def load_context_retriever(vectorstore_path: str):
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cuda"}
    )
    vectorstore = FAISS.load_local(
        vectorstore_path,
        embeddings,
        allow_dangerous_deserialization=True
    )
    return vectorstore.as_retriever(search_kwargs={"k": 2})

# ─────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────
# system_prompt = """
# You are Swara, a polite and helpful female AI voice agent from Swift Money.

# IMPORTANT CONTEXT:
# You are already connected on a PHONE CALL with a retail merchant in India.
# The greeting and introduction have ALREADY happened.

# GREETING RULE (HARD):
# - NEVER greet again.
# - NEVER introduce yourself again.
# - NEVER repeat company name unless strictly required.

# YOUR GOAL:
# - Understand why the merchant stopped using Swift Money.
# - Help resolve the issue if possible.
# - Encourage them to restart usage, politely.

# SPEAKING STYLE (VOICE CALL):
# - Speak in natural spoken Hindi.
# - Use light English words only if common (payment, transaction, settlement).
# - Keep responses SHORT.
# - Max 2 sentences.
# - Prefer asking ONE clear question.
# - Friendly, empathetic, practical.

# FLOW RULES:
# - Ask clarifying questions if the issue is unclear.
# - Use the Knowledge Base for factual answers.
# - For clarification questions, use common sense.
# - Do NOT over-explain.
# - Do NOT sound scripted.

# FALLBACK RULE (STRICT):
# If the answer is NOT present in the Knowledge Base, reply EXACTLY:
# "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"

# EXIT RULE:
# If the merchant wants to end the call (bye / धन्यवाद ):
# - End politely in one short line.

# RESPONSE FORMAT:
# - 1–2 short sentences only.
# - No paragraphs.


# Knowledge Base:
# {context}

# Conversation so far:
# {history}

# Merchant says:
# {question}

# Your response:
# """

system_prompt = """
You are Swara, a polite and helpful female AI voice agent from Swift Money.

IMPORTANT:
You are ALREADY on an ongoing phone call with the merchant.
The greeting and introduction have ALREADY happened.
DO NOT greet again. DO NOT introduce yourself again.

YOUR TASK:
- Understand why the merchant stopped using Swift Money.
- Help resolve the issue if possible.
- Politely encourage them to restart usage.

SPEAKING STYLE (VOICE CALL):
- Natural spoken Hindi.
- Light English only when common (payment, transaction, settlement).
- Short responses.
- Maximum 1–2 sentences.
- Ask only ONE clear question at a time.
- Empathetic, calm, practical.
- Never sound scripted.

STRICT RULES:
- NEVER greet.
- NEVER introduce yourself.
- NEVER repeat company name unless absolutely required.
- NEVER explain what Swift Money is.

KNOWLEDGE USAGE:
- Use ONLY the Knowledge Base below.
- If the answer is NOT in the Knowledge Base, reply EXACTLY:
  "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"

CALL ENDING:
- If the merchant says bye / धन्यवाद:
  End politely in one short line.



Knowledge Base:
{context}

Conversation so far:
{history}

Merchant says:
{question}

Your response:
"""


qa_prompt = PromptTemplate(
    input_variables=["context", "history", "question"],
    template=system_prompt
)

# ─────────────────────────────────────────────────────────────
# OpenAI LLM (singleton)
# ─────────────────────────────────────────────────────────────
_llm: Optional[ChatOpenAI] = None

def _init_llm(force: bool = False) -> ChatOpenAI:
    global _llm

    if _llm is not None and not force:
        return _llm

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    _llm = ChatOpenAI(
        model=OPENAI_MODEL,
        temperature=OPENAI_TEMPERATURE,
        max_tokens=OPENAI_MAX_TOKENS,
        timeout=OPENAI_TIMEOUT,
        openai_api_key=OPENAI_API_KEY,
    )
    return _llm

# ─────────────────────────────────────────────────────────────
# Main RAG entry
# ─────────────────────────────────────────────────────────────
def get_contextual_response(user_query: str, retriever, user_id: str) -> str:
    llm = _init_llm()

    user_query = "उत्तर हिंदी में दें: " + (user_query or "").strip()
    memory = get_user_memory(user_id)

    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        combine_docs_chain_kwargs={"prompt": qa_prompt},
        return_source_documents=False
    )

    try:
        result = qa_chain.invoke({
            "question": user_query,
            "chat_history": []
        })

        answer = (result.get("answer") or "").strip()
        if not answer or len(answer) < 2:
            return FALLBACK_UNKNOWN

        return answer

    except Exception:
        logger.exception("[RAG] OpenAI call failed")
        return "माफ़ कीजिए, अभी तकनीकी समस्या आ गई। कृपया दोबारा एक बार कह दीजिए।"


# from __future__ import annotations

# import os
# import logging
# from datetime import datetime, timedelta
# from typing import Optional

# from langchain_community.vectorstores import FAISS
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_classic.chains import ConversationalRetrievalChain
# from langchain_classic.memory import ConversationBufferWindowMemory
# from langchain_community.chat_message_histories import ChatMessageHistory
# from langchain_classic.prompts import PromptTemplate
# from langchain_openai import ChatOpenAI

# logger = logging.getLogger(__name__)

# # ──────────────────────────────────────────────────────────────────────────────
# # Configuration
# # ──────────────────────────────────────────────────────────────────────────────
# EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# OPENAI_MODEL = "gpt-4o-mini"
# OPENAI_TEMPERATURE = 0.3
# OPENAI_MAX_TOKENS = 250
# OPENAI_TIMEOUT = 12  # lower = faster failure instead of hanging

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# FALLBACK_UNKNOWN = (
#     "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है "
#     "तथा शीघ्र ही आपको जवाब देंगे!"
# )

# # ──────────────────────────────────────────────────────────────────────────────
# # Memory store (per session)
# # ──────────────────────────────────────────────────────────────────────────────
# _user_memory_store: dict[str, tuple[ConversationBufferWindowMemory, datetime]] = {}

# def _create_memory() -> ConversationBufferWindowMemory:
#     return ConversationBufferWindowMemory(
#         memory_key="history",
#         input_key="question",
#         return_messages=True,
#         chat_memory=ChatMessageHistory(),
#         k=6,  # keep it small for speed
#     )

# def get_user_memory(session_id: str) -> ConversationBufferWindowMemory:
#     now = datetime.now()
#     item = _user_memory_store.get(session_id)

#     if item:
#         mem, last_seen = item
#         if now - last_seen > timedelta(days=2):
#             mem = _create_memory()
#     else:
#         logger.info(f"🆕 New memory created for session")
#         mem = _create_memory()

#     _user_memory_store[session_id] = (mem, now)
#     return mem

# # ──────────────────────────────────────────────────────────────────────────────
# # Vector retriever
# # ──────────────────────────────────────────────────────────────────────────────
# def load_context_retriever(vectorstore_path: str):
#     embeddings = HuggingFaceEmbeddings(
#         model_name=EMBED_MODEL,
#         model_kwargs={"device": "cuda"},
#     )

#     vectorstore = FAISS.load_local(
#         vectorstore_path,
#         embeddings,
#         allow_dangerous_deserialization=True,
#     )

#     return vectorstore.as_retriever(
#         search_type="similarity",
#         search_kwargs={"k": 3},
#     )

# # ──────────────────────────────────────────────────────────────────────────────
# # Prompt
# # ──────────────────────────────────────────────────────────────────────────────
# system_prompt = """
# You are Swara, a polite and helpful female AI voice agent from Swift Money.

# IMPORTANT CONTEXT:
# You are already connected on a PHONE CALL with a retail merchant in India.
# The greeting and introduction have ALREADY happened.

# GREETING RULE (HARD):
# - NEVER greet again.
# - NEVER introduce yourself again.
# - NEVER repeat company name unless strictly required.

# YOUR GOAL:
# - Understand why the merchant stopped using Swift Money.
# - Help resolve the issue if possible.
# - Encourage them to restart usage, politely.

# SPEAKING STYLE (VOICE CALL):
# - Speak in natural spoken Hindi.
# - Use light English words only if common (payment, transaction, settlement).
# - Keep responses SHORT.
# - Max 2 sentences.
# - Prefer asking ONE clear question.

# FALLBACK RULE (STRICT):
# If the answer is NOT present in the Knowledge Base, reply EXACTLY:
# "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"

# Knowledge Base:
# {context}

# Conversation so far:
# {history}

# Merchant says:
# {question}

# Your response:
# """

# qa_prompt = PromptTemplate(
#     input_variables=["context", "history", "question"],
#     template=system_prompt,
# )

# # ──────────────────────────────────────────────────────────────────────────────
# # LLM (OpenAI)
# # ──────────────────────────────────────────────────────────────────────────────
# _llm: Optional[ChatOpenAI] = None

# def _init_llm(force: bool = False) -> ChatOpenAI:
#     global _llm

#     if _llm is not None and not force:
#         return _llm

#     if not OPENAI_API_KEY:
#         raise RuntimeError("OPENAI_API_KEY not set")

#     _llm = ChatOpenAI(
#         model=OPENAI_MODEL,
#         temperature=OPENAI_TEMPERATURE,
#         max_tokens=OPENAI_MAX_TOKENS,
#         timeout=OPENAI_TIMEOUT,
#         api_key=OPENAI_API_KEY,
#     )
#     return _llm

# # ──────────────────────────────────────────────────────────────────────────────
# # Main API
# # ──────────────────────────────────────────────────────────────────────────────
# def get_contextual_response(user_query: str, retriever, user_id: str) -> str:
#     """
#     Blocking call. Safe to run inside asyncio.to_thread().
#     """
#     llm = _init_llm()

#     user_query = "उत्तर हिंदी में दें: " + (user_query or "").strip()
#     memory = get_user_memory(user_id)

#     qa_chain = ConversationalRetrievalChain.from_llm(
#         llm=llm,
#         retriever=retriever,
#         memory=memory,
#         combine_docs_chain_kwargs={"prompt": qa_prompt},
#         return_source_documents=False,
#     )

#     try:
#         result = qa_chain.invoke({"question": user_query,  "chat_history": []})
#         answer = (result.get("answer") or "").strip()

#         if not answer or len(answer) < 2:
#             return FALLBACK_UNKNOWN

#         lowered = answer.lower()
#         if any(x in lowered for x in ["sorry", "माफ़", "क्षमा"]):
#             return FALLBACK_UNKNOWN

#         return answer

#     except Exception:
#         logger.exception("[RAG] OpenAI call failed")
#         return "माफ़ कीजिए, अभी तकनीकी समस्या आ गई। कृपया दोबारा एक बार कह दीजिए।"




 


   