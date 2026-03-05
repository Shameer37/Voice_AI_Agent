from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.prompts import PromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.schema import Document

# ─────────────────────────────────────────────
# ENV + LOGGER
# ─────────────────────────────────────────────
load_dotenv()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
EMBED_MODEL = "text-embedding-3-large"
OPENAI_MODEL = "gpt-4o-mini"

OPENAI_TEMPERATURE = 0.2
OPENAI_MAX_TOKENS = 250
OPENAI_TIMEOUT = 20

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

FALLBACK_UNKNOWN = (
    "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है "
    "तथा शीघ्र ही आपको जवाब देंगे!"
)

# ─────────────────────────────────────────────
# MEMORY (per session)
# ─────────────────────────────────────────────
user_memory_store: Dict[str, tuple[ConversationBufferWindowMemory, datetime]] = {}
clarified_once: Dict[str, bool] = {}
issue_state: dict[str, dict] = {}

def create_memory() -> ConversationBufferWindowMemory:
    return ConversationBufferWindowMemory(
        memory_key="history",
        input_key="question",
        return_messages=True,
        chat_memory=ChatMessageHistory(),
        k=4
    )

def get_user_memory(session_id: str) -> ConversationBufferWindowMemory:
    now = datetime.utcnow()
    item = user_memory_store.get(session_id)

    if item:
        mem, last = item
        if now - last > timedelta(days=2):
            mem = create_memory()
    else:
        mem = create_memory()

    user_memory_store[session_id] = (mem, now)
    return mem

# ─────────────────────────────────────────────
# RETRIEVER + CACHE
# ─────────────────────────────────────────────
_retrieval_cache: Dict[str, List[Document]] = {}

def load_context_retriever(vectorstore_path: str):
    embeddings = OpenAIEmbeddings(
        model=EMBED_MODEL,
        api_key=OPENAI_API_KEY
    )

    vectorstore = FAISS.load_local(
        vectorstore_path,
        embeddings,
        allow_dangerous_deserialization=True
    )

    return vectorstore.as_retriever(search_kwargs={"k": 3})

def retrieve_docs(retriever, query: str) -> List[Document]:
    if query in _retrieval_cache:
        return _retrieval_cache[query]

    docs = retriever.invoke(query)
    _retrieval_cache[query] = docs
    return docs

# ─────────────────────────────────────────────
# PROMPT (STRICT + STABLE)
# ─────────────────────────────────────────────
# system_prompt = """
# You are Swara, a polite and helpful female AI voice agent from Swift Money.

# IMPORTANT:
# You are already on an ongoing PHONE CALL.
# Greeting and introduction are DONE.
# NEVER greet again. NEVER introduce yourself.

# LANGUAGE:
# - Natural spoken Hindi
# - Light English only when common (payment, transaction)
# - 1–2 sentences MAX
# - Ask ONLY ONE question at a time

# KNOWLEDGE RULE (STRICT):
# - Use ONLY the Knowledge Base below
# - If answer is NOT clearly present, reply EXACTLY:
# "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"

# NO BEHAVIORAL QUESTIONS:
# - Do NOT ask why merchant stopped using service
# - Do NOT ask feedback questions

# Knowledge Base:
# {context}

# Conversation so far:
# {history}

# Merchant says:
# {question}

# Your response:
system_prompt = """You are Swara, a polite, calm, and professional female AI voice agent handling a live support phone call for a retail merchant in India.

IMPORTANT CONTEXT:
You are ALREADY on an ongoing phone call.
Greeting and introduction have ALREADY happened.
You must NEVER greet again and NEVER introduce yourself again.

LANGUAGE & TONE (VERY IMPORTANT):
- Speak in natural, conversational Hindi used in real phone calls.
- Use light English words only when commonly spoken (payment, transaction, settlement).
- Sound human, calm, and helpful — not scripted, not robotic.
- Keep responses SHORT and practical.
- Maximum 1–2 sentences only.

ROLE & BEHAVIOR:
- You are a SUPPORT EXECUTIVE, not a chatbot, not a survey agent.
- Your job is to understand the issue and explain the solution clearly.
- Once the issue is explained, STOP talking unless the merchant continues.
- Do NOT interview the merchant.
- Do NOT over-clarify.
- Do NOT keep the conversation alive unnecessarily.

QUESTION RULES (STRICT):
- Ask a question ONLY if it is absolutely required to understand the issue.
- Ask ONLY ONE question at a time.
- NEVER ask follow-up questions after the issue is resolved.
- NEVER ask “why”, feedback, or usage questions.
- If the merchant says “haan / okay / theek hai / samajh gaya” — STOP.

UNKNOWN / NO-DETAIL RULE:
If the merchant says things like:
“nahi”, “pata nahi”, “yaad nahi”, “maloom nahi”
→ Do NOT probe further.
→ Use the fallback message and STOP.

KNOWLEDGE BASE RULE (HARD):
- Use ONLY the information present in the Knowledge Base below.
- Do NOT guess.
- Do NOT add new explanations.
- If the answer is NOT clearly present in the Knowledge Base, reply EXACTLY with:

"हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"

STOP CONDITIONS (MANDATORY):
You MUST STOP responding after any one of the following:
- You have explained the solution.
- The merchant confirms with “haan / okay / theek hai”.
- The merchant says there is no issue.
- The fallback message is used.
- The merchant wants to end the call (bye / धन्यवाद / thanks).

CALL ENDING:
If the merchant says bye / धन्यवाद / thanks:
End politely in ONE short line only.

FORMAT RULES:
- No paragraphs.
- No lists.
- No multiple questions.
- No emojis.
- No extra words.

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

# ─────────────────────────────────────────────
# LLM (singleton)
# ─────────────────────────────────────────────
_llm: Optional[ChatOpenAI] = None

def _init_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=OPENAI_MODEL,
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
            timeout=OPENAI_TIMEOUT,
            openai_api_key=OPENAI_API_KEY
        )
    return _llm

# ─────────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────────
# def get_contextual_response(user_query: str, retriever, user_id: str) -> str:
#     llm = _init_llm()
#     memory = get_user_memory(user_id)

#     user_query = (user_query or "").strip()
#     if not user_query:
#         return FALLBACK_UNKNOWN

#     q_lower = user_query.lower()

#     # ── HARD STOP: user has no info
#     if any(x in q_lower for x in ["nahi pata", "pata nahi", "yaad nahi", "maloom nahi"]):
#         return FALLBACK_UNKNOWN

#     # ── ONE-TIME money clarification
#     if user_id not in clarified_once:
#         clarified_once[user_id] = False

#     money_words = ["paise", "fas", "pending", "atka", "stuck"]
#     services = ["aeps", "dmt", "bbps", "withdrawal", "settlement"]

#     if (
#         any(m in q_lower for m in money_words)
#         and not any(s in q_lower for s in services)
#         and not clarified_once[user_id]
#     ):
#         clarified_once[user_id] = True
#         return "ये किस service में हुआ था — AEPS, DMT या कोई और?"

#     # ── Retrieve KB docs
#     try:
#         docs = retrieve_docs(retriever, user_query)
#     except Exception:
#         logger.exception("[RAG] Retrieval failed")
#         return FALLBACK_UNKNOWN

#     if not docs:
#         return FALLBACK_UNKNOWN

#     # ── Grounded LLM
#     doc_chain = create_stuff_documents_chain(llm, qa_prompt)

#     try:
#         result = doc_chain.invoke({
#             "context": docs,
#             "history": memory.load_memory_variables({}).get("history", []),
#             "question": user_query
#         })
#     except Exception:
#         logger.exception("[RAG] LLM failed")
#         return FALLBACK_UNKNOWN

#     answer = (result or "").strip()

#     # ── Safety
#     if not answer or len(answer) < 2:
#         return FALLBACK_UNKNOWN

#     if "?" in answer and clarified_once.get(user_id, False):
#         return FALLBACK_UNKNOWN

#     return answer

def get_contextual_response(user_query: str, retriever, user_id: str) -> str:
    llm = _init_llm()
    memory = get_user_memory(user_id)

    user_query = (user_query or "").strip()
    if not user_query:
        return FALLBACK_UNKNOWN

    q_lower = user_query.lower()

    # ─────────────────────────────────────
    # 0️⃣ HARD STOP — user has no details
    # ─────────────────────────────────────
    NO_DETAIL_TRIGGERS = [
        "nahi", "nahi pata", "pata nahi",
        "yaad nahi", "maloom nahi", "no"
    ]

    if any(t == q_lower or t in q_lower for t in NO_DETAIL_TRIGGERS):
        return FALLBACK_UNKNOWN

    # ─────────────────────────────────────
    # 1️⃣ HARD STOP — confirmation / acceptance
    # ─────────────────────────────────────
    CONFIRM_TRIGGERS = [
        "haan", "haan ji", "theek hai",
        "ok", "okay", "samajh gaya",
        "samajh gaye"
    ]

    if any(t == q_lower or t in q_lower for t in CONFIRM_TRIGGERS):
        return ""  # SILENCE — agent must stop talking

    # ─────────────────────────────────────
    # 2️⃣ HARD STOP — call ending
    # ─────────────────────────────────────
    EXIT_TRIGGERS = ["bye", "by", "dhanyavad", "thank you", "thanks"]

    if any(t in q_lower for t in EXIT_TRIGGERS):
        return "धन्यवाद सर, आगे कोई मदद चाहिए हो तो बता दीजिएगा।"

    # ─────────────────────────────────────
    # 3️⃣ Retrieve KB context (MANDATORY)
    # ─────────────────────────────────────
    try:
        docs = retriever.invoke(user_query)
    except Exception:
        logger.exception("[RAG] Retriever failed")
        return FALLBACK_UNKNOWN

    if not docs:
        return FALLBACK_UNKNOWN

    # ─────────────────────────────────────
    # 4️⃣ ONE-TIME clarification ONLY for money ambiguity
    # ─────────────────────────────────────
    if user_id not in clarified_once:
        clarified_once[user_id] = False

    MONEY_TRIGGERS = ["paise", "fas", "pending", "atka", "stuck"]
    SERVICE_KEYS = ["aeps", "dmt", "bbps", "withdrawal", "settlement"]

    is_money_issue = any(k in q_lower for k in MONEY_TRIGGERS)
    has_service = any(s in q_lower for s in SERVICE_KEYS)

    if is_money_issue and not has_service and not clarified_once[user_id]:
        clarified_once[user_id] = True
        return "ये किस service में हुआ था — AEPS, DMT या कोई और?"

    # ─────────────────────────────────────
    # 5️⃣ Grounded LLM call (NO retriever inside)
    # ─────────────────────────────────────
    doc_chain = create_stuff_documents_chain(
        llm=llm,
        prompt=qa_prompt
    )

    try:
        answer = doc_chain.invoke({
            "context": docs,
            "history": memory.load_memory_variables({}).get("history", []),
            "question": user_query,
        })
    except Exception:
        logger.exception("[RAG] LLM failed")
        return FALLBACK_UNKNOWN

    answer = (answer or "").strip()

    # ─────────────────────────────────────
    # 6️⃣ FINAL SAFETY GUARDS
    # ─────────────────────────────────────
    if not answer or len(answer) < 2:
        return FALLBACK_UNKNOWN

    # Block repeated or unnecessary questions
    if "?" in answer and clarified_once.get(user_id, False):
        return FALLBACK_UNKNOWN

    return answer