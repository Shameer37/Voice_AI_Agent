# from __future__ import annotations

# import os
# import logging
# from datetime import datetime, timedelta
# from typing import Optional, Dict, List

# from dotenv import load_dotenv
# from langchain_community.vectorstores import FAISS
# from langchain_openai import OpenAIEmbeddings, ChatOpenAI
# from langchain.memory import ConversationBufferWindowMemory
# from langchain_community.chat_message_histories import ChatMessageHistory
# from langchain.prompts import PromptTemplate
# from langchain.chains.combine_documents import create_stuff_documents_chain
# from langchain.schema import Document
# from openai import RateLimitError

# # ─────────────────────────────────────────────
# # ENV + LOGGER
# # ─────────────────────────────────────────────
# load_dotenv()
# logger = logging.getLogger(__name__)

# # ─────────────────────────────────────────────
# # CONFIG
# # ─────────────────────────────────────────────
# EMBED_MODEL = "text-embedding-3-large"
# OPENAI_MODEL = "gpt-4o-mini"

# OPENAI_TEMPERATURE = 0.2
# OPENAI_MAX_TOKENS = 250
# OPENAI_TIMEOUT = 20

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# FALLBACK_UNKNOWN = (
#     "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है "
#     "तथा शीघ्र ही आपको जवाब देंगे!"
# )

# TECHNICAL_ERROR_MESSAGE = (
#     "माफ़ कीजिए, अभी एक तकनीकी समस्या आ गई है। कृपया थोड़ी देर बाद फिर से कोशिश करें।"
# )

# # ─────────────────────────────────────────────
# # MEMORY (per session)
# # ─────────────────────────────────────────────
# user_memory_store: Dict[str, tuple[ConversationBufferWindowMemory, datetime]] = {}
# clarified_once: Dict[str, bool] = {}
# issue_state: dict[str, dict] = {}

# def create_memory() -> ConversationBufferWindowMemory:
#     return ConversationBufferWindowMemory(
#         memory_key="history",
#         input_key="question",
#         return_messages=True,
#         chat_memory=ChatMessageHistory(),
#         k=4
#     )

# def get_user_memory(session_id: str) -> ConversationBufferWindowMemory:
#     now = datetime.utcnow()
#     item = user_memory_store.get(session_id)

#     if item:
#         mem, last = item
#         if now - last > timedelta(days=2):
#             mem = create_memory()
#     else:
#         mem = create_memory()

#     user_memory_store[session_id] = (mem, now)
#     return mem

# # ─────────────────────────────────────────────
# # RETRIEVER + CACHE
# # ─────────────────────────────────────────────
# _retrieval_cache: Dict[str, List[Document]] = {}

# def load_context_retriever(vectorstore_path: str):
#     embeddings = OpenAIEmbeddings(
#         model=EMBED_MODEL,
#         api_key=OPENAI_API_KEY
#     )

#     vectorstore = FAISS.load_local(
#         vectorstore_path,
#         embeddings,
#         allow_dangerous_deserialization=True
#     )

#     return vectorstore.as_retriever(search_kwargs={"k": 3})

# def retrieve_docs(retriever, query: str) -> List[Document]:
#     if query in _retrieval_cache:
#         return _retrieval_cache[query]

#     docs = retriever.invoke(query)
#     _retrieval_cache[query] = docs
#     return docs

# # ─────────────────────────────────────────────
# # PROMPT (STRICT + STABLE)
# # ─────────────────────────────────────────────
# # system_prompt = """
# # You are Swara, a polite and helpful female AI voice agent from Swift Money.

# # IMPORTANT:
# # You are already on an ongoing PHONE CALL.
# # Greeting and introduction are DONE.
# # NEVER greet again. NEVER introduce yourself.

# # LANGUAGE:
# # - Natural spoken Hindi
# # - Light English only when common (payment, transaction)
# # - 1–2 sentences MAX
# # - Ask ONLY ONE question at a time

# # KNOWLEDGE RULE (STRICT):
# # - Use ONLY the Knowledge Base below
# # - If answer is NOT clearly present, reply EXACTLY:
# # "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"

# # NO BEHAVIORAL QUESTIONS:
# # - Do NOT ask why merchant stopped using service
# # - Do NOT ask feedback questions

# # Knowledge Base:
# # {context}

# # Conversation so far:
# # {history}

# # Merchant says:
# # {question}

# # Your response:
# system_prompt = """You are Swara, a polite, calm, and professional female AI voice agent handling a live support phone call for a retail merchant in India.

# IMPORTANT CONTEXT:
# You are ALREADY on an ongoing phone call.
# Greeting and introduction have ALREADY happened.
# You must NEVER greet again and NEVER introduce yourself again.

# LANGUAGE & TONE (VERY IMPORTANT):
# - Speak in natural, conversational Hindi used in real phone calls.
# - Use light English words only when commonly spoken (payment, transaction, settlement).
# - Sound human, calm, and helpful — not scripted, not robotic.
# - Keep responses SHORT and practical.
# - Maximum 1–2 sentences only.

# ROLE & BEHAVIOR:
# - You are a SUPPORT EXECUTIVE, not a chatbot, not a survey agent.
# - Your job is to understand the issue and explain the solution clearly.
# - Once the issue is explained, STOP talking unless the merchant continues.
# - Do NOT interview the merchant.
# - Do NOT over-clarify.
# - Do NOT keep the conversation alive unnecessarily.

# QUESTION RULES (STRICT):
# - Ask a question ONLY if it is absolutely required to understand the issue.
# - Ask ONLY ONE question at a time.
# - NEVER ask follow-up questions after the issue is resolved.
# - NEVER ask “why”, feedback, or usage questions.
# - If the merchant says “haan / okay / theek hai / samajh gaya” — STOP.

# UNKNOWN / NO-DETAIL RULE:
# If the merchant says things like:
# “nahi”, “pata nahi”, “yaad nahi”, “maloom nahi”
# → Do NOT probe further.
# → Use the fallback message and STOP.

# KNOWLEDGE BASE RULE (HARD):
# - Use ONLY the information present in the Knowledge Base below.
# - Do NOT guess.
# - Do NOT add new explanations.
# - If the answer is NOT clearly present in the Knowledge Base, reply EXACTLY with:

# "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"

# STOP CONDITIONS (MANDATORY):
# You MUST STOP responding after any one of the following:
# - You have explained the solution.
# - The merchant confirms with “haan / okay / theek hai”.
# - The merchant says there is no issue.
# - The fallback message is used.
# - The merchant wants to end the call (bye / धन्यवाद / thanks).

# CALL ENDING:
# If the merchant says bye / धन्यवाद / thanks:
# End politely in ONE short line only.

# FORMAT RULES:
# - No paragraphs.
# - No lists.
# - No multiple questions.
# - No emojis.
# - No extra words.

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
#     template=system_prompt
# )

# # ─────────────────────────────────────────────
# # LLM (singleton)
# # ─────────────────────────────────────────────
# _llm: Optional[ChatOpenAI] = None

# def _init_llm() -> ChatOpenAI:
#     global _llm
#     if _llm is None:
#         _llm = ChatOpenAI(
#             model=OPENAI_MODEL,
#             temperature=OPENAI_TEMPERATURE,
#             max_tokens=OPENAI_MAX_TOKENS,
#             timeout=OPENAI_TIMEOUT,
#             openai_api_key=OPENAI_API_KEY
#         )
#     return _llm

# # ─────────────────────────────────────────────
# # MAIN ENTRY
# # ─────────────────────────────────────────────
# # def get_contextual_response(user_query: str, retriever, user_id: str) -> str:
# #     llm = _init_llm()
# #     memory = get_user_memory(user_id)

# #     user_query = (user_query or "").strip()
# #     if not user_query:
# #         return FALLBACK_UNKNOWN

# #     q_lower = user_query.lower()

# #     # ── HARD STOP: user has no info
# #     if any(x in q_lower for x in ["nahi pata", "pata nahi", "yaad nahi", "maloom nahi"]):
# #         return FALLBACK_UNKNOWN

# #     # ── ONE-TIME money clarification
# #     if user_id not in clarified_once:
# #         clarified_once[user_id] = False

# #     money_words = ["paise", "fas", "pending", "atka", "stuck"]
# #     services = ["aeps", "dmt", "bbps", "withdrawal", "settlement"]

# #     if (
# #         any(m in q_lower for m in money_words)
# #         and not any(s in q_lower for s in services)
# #         and not clarified_once[user_id]
# #     ):
# #         clarified_once[user_id] = True
# #         return "ये किस service में हुआ था — AEPS, DMT या कोई और?"

# #     # ── Retrieve KB docs
# #     try:
# #         docs = retrieve_docs(retriever, user_query)
# #     except Exception:
# #         logger.exception("[RAG] Retrieval failed")
# #         return FALLBACK_UNKNOWN

# #     if not docs:
# #         return FALLBACK_UNKNOWN

# #     # ── Grounded LLM
# #     doc_chain = create_stuff_documents_chain(llm, qa_prompt)

# #     try:
# #         result = doc_chain.invoke({
# #             "context": docs,
# #             "history": memory.load_memory_variables({}).get("history", []),
# #             "question": user_query
# #         })
# #     except Exception:
# #         logger.exception("[RAG] LLM failed")
# #         return FALLBACK_UNKNOWN

# #     answer = (result or "").strip()

# #     # ── Safety
# #     if not answer or len(answer) < 2:
# #         return FALLBACK_UNKNOWN

# #     if "?" in answer and clarified_once.get(user_id, False):
# #         return FALLBACK_UNKNOWN

# #     return answer

# def get_contextual_response(user_query: str, retriever, user_id: str) -> str:
#     try:
#         llm = _init_llm()
#         memory = get_user_memory(user_id)

#         user_query = (user_query or "").strip()
#         if not user_query:
#             return FALLBACK_UNKNOWN

#         q_lower = user_query.lower()

#         # ─────────────────────────────────────
#         # 0️⃣ HARD STOP — user has no details
#         # ─────────────────────────────────────
#         NO_DETAIL_TRIGGERS = [
#             "nahi", "nahi pata", "pata nahi",
#             "yaad nahi", "maloom nahi", "no"
#         ]

#         if any(t == q_lower or t in q_lower for t in NO_DETAIL_TRIGGERS):
#             return FALLBACK_UNKNOWN

#         # ─────────────────────────────────────
#         # 1️⃣ HARD STOP — confirmation / acceptance
#         # ─────────────────────────────────────
#         CONFIRM_TRIGGERS = [
#             "haan", "haan ji", "theek hai",
#             "ok", "okay", "samajh gaya",
#             "samajh gaye"
#         ]

#         if any(t == q_lower or t in q_lower for t in CONFIRM_TRIGGERS):
#             return ""  # SILENCE — agent must stop talking

#         # ─────────────────────────────────────
#         # 2️⃣ HARD STOP — call ending
#         # ─────────────────────────────────────
#         EXIT_TRIGGERS = ["bye", "by", "dhanyavad", "thank you", "thanks"]

#         if any(t in q_lower for t in EXIT_TRIGGERS):
#             return "धन्यवाद सर, आगे कोई मदद चाहिए हो तो बता दीजिएगा।"

#         # ─────────────────────────────────────
#         # 3️⃣ Retrieve KB context (MANDATORY)
#         # ─────────────────────────────────────
#         # try:
#         #     docs = retriever.invoke(user_query)
#         # except Exception:
#         #     logger.exception("[RAG] Retriever failed")
#         #     return FALLBACK_UNKNOWN
#         try:
#             docs = retriever.invoke(user_query)

#         except RateLimitError:
#             logger.exception("[RAG] OpenAI quota exceeded")
#             return TECHNICAL_ERROR_MESSAGE

#         except Exception:
#             logger.exception("[RAG] Retriever failed")
#             return FALLBACK_UNKNOWN


#         if not docs:
#             return FALLBACK_UNKNOWN

#         # ─────────────────────────────────────
#         # 4️⃣ ONE-TIME clarification ONLY for money ambiguity
#         # ─────────────────────────────────────
#         if user_id not in clarified_once:
#             clarified_once[user_id] = False

#         MONEY_TRIGGERS = ["paise", "fas", "pending", "atka", "stuck"]
#         SERVICE_KEYS = ["aeps", "dmt", "bbps", "withdrawal", "settlement"]

#         is_money_issue = any(k in q_lower for k in MONEY_TRIGGERS)
#         has_service = any(s in q_lower for s in SERVICE_KEYS)

#         if is_money_issue and not has_service and not clarified_once[user_id]:
#             clarified_once[user_id] = True
#             return "ये किस service में हुआ था — AEPS, DMT या कोई और?"

#         # ─────────────────────────────────────
#         # 5️⃣ Grounded LLM call (NO retriever inside)
#         # ─────────────────────────────────────
#         # doc_chain = create_stuff_documents_chain(
#         #     llm=llm,
#         #     prompt=qa_prompt
#         # )

#         # try:
#         #     answer = doc_chain.invoke({
#         #         "context": docs,
#         #         "history": memory.load_memory_variables({}).get("history", []),
#         #         "question": user_query,
#         #     })
#         # except Exception:
#         #     logger.exception("[RAG] LLM failed")
#         #     return FALLBACK_UNKNOWN
#         try:
#             answer = doc_chain.invoke({
#                 "context": docs,
#                 "history": memory.load_memory_variables({}).get("history", []),
#                 "question": user_query,
#             })

#         except RateLimitError:
#             logger.exception("[RAG] OpenAI quota exceeded during LLM call")
#             return TECHNICAL_ERROR_MESSAGE

#         except Exception:
#             logger.exception("[RAG] LLM failed")
#             return FALLBACK_UNKNOWN

#         answer = (answer or "").strip()

#         # ─────────────────────────────────────
#         # 6️⃣ FINAL SAFETY GUARDS
#         # ─────────────────────────────────────
#         if not answer or len(answer) < 2:
#             return FALLBACK_UNKNOWN

#         # Block repeated or unnecessary questions
#         if "?" in answer and clarified_once.get(user_id, False):
#             return FALLBACK_UNKNOWN

#         return answer
#     except Exception:
#         logger.exception("[RAG] Unexpected technical error")
#         return TECHNICAL_ERROR_MESSAGE

# from __future__ import annotations

# import os
# import logging
# from datetime import datetime, timedelta
# from typing import Optional, Dict, List

# from dotenv import load_dotenv
# from langchain_community.vectorstores import FAISS
# from langchain_openai import OpenAIEmbeddings, ChatOpenAI
# from langchain.memory import ConversationBufferWindowMemory
# from langchain_community.chat_message_histories import ChatMessageHistory
# from langchain.prompts import PromptTemplate
# from langchain.chains.combine_documents import create_stuff_documents_chain
# from langchain.schema import Document
# from openai import RateLimitError


# # ─────────────────────────────────────────────
# # ENV + LOGGER
# # ─────────────────────────────────────────────
# load_dotenv()
# logger = logging.getLogger(__name__)


# # ─────────────────────────────────────────────
# # CONFIG
# # ─────────────────────────────────────────────
# EMBED_MODEL = "text-embedding-3-large"
# OPENAI_MODEL = "gpt-4o-mini"

# OPENAI_TEMPERATURE = 0.2
# OPENAI_MAX_TOKENS = 250
# OPENAI_TIMEOUT = 20

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# FALLBACK_UNKNOWN = (
#     "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है "
#     "तथा शीघ्र ही आपको जवाब देंगे!"
# )

# TECHNICAL_ERROR_MESSAGE = (
#     "माफ़ कीजिए, अभी तकनीकी समस्या आ गई है। कृपया थोड़ी देर बाद फिर से कोशिश करें।"
# )


# # ─────────────────────────────────────────────
# # MEMORY (per session)
# # ─────────────────────────────────────────────
# user_memory_store: Dict[str, tuple[ConversationBufferWindowMemory, datetime]] = {}
# clarified_once: Dict[str, bool] = {}
# issue_state: dict[str, dict] = {}


# def create_memory() -> ConversationBufferWindowMemory:
#     return ConversationBufferWindowMemory(
#         memory_key="history",
#         input_key="question",
#         return_messages=True,
#         chat_memory=ChatMessageHistory(),
#         k=4
#     )


# def get_user_memory(session_id: str) -> ConversationBufferWindowMemory:
#     now = datetime.utcnow()
#     item = user_memory_store.get(session_id)

#     if item:
#         mem, last = item
#         if now - last > timedelta(days=2):
#             mem = create_memory()
#     else:
#         mem = create_memory()

#     user_memory_store[session_id] = (mem, now)
#     return mem


# # ─────────────────────────────────────────────
# # RETRIEVER + CACHE
# # ─────────────────────────────────────────────
# _retrieval_cache: Dict[str, List[Document]] = {}
# _cached_retriever = None


# def load_context_retriever(vectorstore_path: str):
#     global _cached_retriever

#     if _cached_retriever is not None:
#         return _cached_retriever

#     embeddings = OpenAIEmbeddings(
#         model=EMBED_MODEL,
#         api_key=OPENAI_API_KEY
#     )

#     vectorstore = FAISS.load_local(
#         vectorstore_path,
#         embeddings,
#         allow_dangerous_deserialization=True
#     )

#     _cached_retriever = vectorstore.as_retriever(
#         search_kwargs={"k": 3}
#     )

#     return _cached_retriever


# def retrieve_docs(retriever, query: str) -> List[Document]:
#     if query in _retrieval_cache:
#         return _retrieval_cache[query]

#     docs = retriever.invoke(query)
#     _retrieval_cache[query] = docs
#     return docs


# # ─────────────────────────────────────────────
# # PROMPT
# # ─────────────────────────────────────────────
# # system_prompt = """You are Swara, a polite, calm, and professional female AI voice agent handling a live support phone call for a retail merchant in India.

# # IMPORTANT CONTEXT:
# # You are ALREADY on an ongoing phone call.
# # Greeting and introduction have ALREADY happened.
# # You must NEVER greet again and NEVER introduce yourself again.

# # LANGUAGE & TONE:
# # - Speak natural conversational Hindi.
# # - Light English allowed (payment, transaction).
# # - Max 1–2 sentences.

# # ROLE:
# # - You are a support executive.
# # - Explain solution clearly.
# # - Stop once issue is explained.

# # UNKNOWN RULE:
# # If the answer is NOT clearly present in the Knowledge Base, reply EXACTLY:

# # "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"

# # Knowledge Base:
# # {context}

# # Conversation so far:
# # {history}

# # Merchant says:
# # {question}

# # Your response:
# # """
# system_prompt = """You are Swara, a polite, calm, and professional female AI voice agent handling a live support phone call for a retail merchant in India.

# IMPORTANT CONTEXT:
# You are ALREADY on an ongoing phone call.
# Greeting and introduction have ALREADY happened.
# You must NEVER greet again and NEVER introduce yourself again.

# LANGUAGE & TONE (VERY IMPORTANT):
# - Speak in natural, conversational Hindi used in real phone calls.
# - Use light English words only when commonly spoken (payment, transaction, settlement).
# - Sound human, calm, and helpful — not scripted, not robotic.
# - Keep responses SHORT and practical.
# - Maximum 1–2 sentences only.

# ROLE & BEHAVIOR:
# - You are a SUPPORT EXECUTIVE, not a chatbot, not a survey agent.
# - Your job is to understand the issue and explain the solution clearly.
# - Once the issue is explained, STOP talking unless the merchant continues.
# - Do NOT interview the merchant.
# - Do NOT over-clarify.
# - Do NOT keep the conversation alive unnecessarily.

# QUESTION RULES (STRICT):
# - Ask a question ONLY if it is absolutely required to understand the issue.
# - Ask ONLY ONE question at a time.
# - NEVER ask follow-up questions after the issue is resolved.
# - NEVER ask “why”, feedback, or usage questions.
# - If the merchant says “haan / okay / theek hai / samajh gaya” — STOP.

# UNKNOWN / NO-DETAIL RULE:
# If the merchant says things like:
# “nahi”, “pata nahi”, “yaad nahi”, “maloom nahi”
# → Do NOT probe further.
# → Use the fallback message and STOP.

# KNOWLEDGE BASE RULE (HARD):
# - Use ONLY the information present in the Knowledge Base below.
# - Do NOT guess.
# - Do NOT add new explanations.
# - If the answer is NOT clearly present in the Knowledge Base, reply EXACTLY with:

# "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है तथा शीघ्र ही आपको जवाब देंगे!"

# STOP CONDITIONS (MANDATORY):
# You MUST STOP responding after any one of the following:
# - You have explained the solution.
# - The merchant confirms with “haan / okay / theek hai”.
# - The merchant says there is no issue.
# - The fallback message is used.
# - The merchant wants to end the call (bye / धन्यवाद / thanks).

# CALL ENDING:
# If the merchant says bye / धन्यवाद / thanks:
# End politely in ONE short line only.

# FORMAT RULES:
# - No paragraphs.
# - No lists.
# - No multiple questions.
# - No emojis.
# - No extra words.

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
#     template=system_prompt
# )


# # ─────────────────────────────────────────────
# # LLM (singleton)
# # ─────────────────────────────────────────────
# _llm: Optional[ChatOpenAI] = None


# def _init_llm() -> ChatOpenAI:
#     global _llm

#     if _llm is None:
#         _llm = ChatOpenAI(
#             model=OPENAI_MODEL,
#             temperature=OPENAI_TEMPERATURE,
#             max_tokens=OPENAI_MAX_TOKENS,
#             timeout=OPENAI_TIMEOUT,
#             openai_api_key=OPENAI_API_KEY
#         )

#     return _llm


# # ─────────────────────────────────────────────
# # MAIN ENTRY
# # ─────────────────────────────────────────────
# def get_contextual_response(user_query: str, retriever, user_id: str) -> str:
#     try:
#         llm = _init_llm()
#         memory = get_user_memory(user_id)

#         user_query = (user_query or "").strip()
#         if not user_query:
#             return FALLBACK_UNKNOWN

#         q_lower = user_query.lower()

#         # ─────────────────────────────────────
#         # HARD STOP — user has no details
#         # ─────────────────────────────────────
#         NO_DETAIL_TRIGGERS = [
#             "nahi", "nahi pata", "pata nahi",
#             "yaad nahi", "maloom nahi", "no"
#         ]

#         if any(t == q_lower or t in q_lower for t in NO_DETAIL_TRIGGERS):
#             return FALLBACK_UNKNOWN

#         # ─────────────────────────────────────
#         # confirmation stop
#         # ─────────────────────────────────────
#         CONFIRM_TRIGGERS = [
#             "haan", "haan ji", "theek hai",
#             "ok", "okay", "samajh gaya",
#             "samajh gaye"
#         ]

#         if any(t == q_lower or t in q_lower for t in CONFIRM_TRIGGERS):
#             return ""

#         # ─────────────────────────────────────
#         # call ending
#         # ─────────────────────────────────────
#         EXIT_TRIGGERS = ["bye", "by", "dhanyavad", "thank you", "thanks"]

#         if any(t in q_lower for t in EXIT_TRIGGERS):
#             return "धन्यवाद सर, आगे कोई मदद चाहिए हो तो बता दीजिएगा।"

#         # ─────────────────────────────────────
#         # retrieve KB
#         # ─────────────────────────────────────
#         try:
#             docs = retriever.invoke(user_query)

#         except RateLimitError:
#             logger.exception("[RAG] OpenAI quota exceeded")
#             return TECHNICAL_ERROR_MESSAGE

#         except Exception:
#             logger.exception("[RAG] Retriever failed")
#             return FALLBACK_UNKNOWN

#         if not docs:
#             return FALLBACK_UNKNOWN

#         # ─────────────────────────────────────
#         # clarification logic
#         # ─────────────────────────────────────
#         # if user_id not in clarified_once:
#         #     clarified_once[user_id] = False

#         # MONEY_TRIGGERS = ["paise", "fas", "pending", "atka", "stuck"]
#         # SERVICE_KEYS = ["aeps", "dmt", "bbps", "withdrawal", "settlement"]

#         # is_money_issue = any(k in q_lower for k in MONEY_TRIGGERS)
#         # has_service = any(s in q_lower for s in SERVICE_KEYS)

#         # if is_money_issue and not has_service and not clarified_once[user_id]:
#         #     clarified_once[user_id] = True
#         #     return "ये किस service में हुआ था — AEPS, DMT या कोई और?"
#         # ─────────────────────────────────────
#         # conversational clarification logic
#         # ─────────────────────────────────────

#         MONEY_TRIGGERS = ["paise", "fas", "pending", "atka", "stuck"]
#         SERVICE_KEYS = ["aeps", "dmt", "bbps"]

#         # initialize issue state
#         if user_id not in issue_state:
#             issue_state[user_id] = {
#                 "service": None,
#                 "duration_asked": False
#             }

#         is_money_issue = any(k in q_lower for k in MONEY_TRIGGERS)

#         # STEP 1: detect service
#         if issue_state[user_id]["service"] is None:

#             for s in SERVICE_KEYS:
#                 if s in q_lower:
#                     issue_state[user_id]["service"] = s.upper()

#             if issue_state[user_id]["service"] is None and is_money_issue:
#                 return "ये किस service में हुआ था — AEPS, DMT या कोई और?"

#         # STEP 2: ask duration
#         if issue_state[user_id]["service"] is not None and not issue_state[user_id]["duration_asked"]:

#             DURATION_WORDS = ["aaj", "kal", "din", "dino", "ghante", "since"]

#             if not any(w in q_lower for w in DURATION_WORDS):

#                 issue_state[user_id]["duration_asked"] = True

#                 return "ये कब से हो रहा है — आज से, कल से या कई दिनों से?"

#         # ─────────────────────────────────────
#         # LLM call
#         # ─────────────────────────────────────
#         doc_chain = create_stuff_documents_chain(
#             llm=llm,
#             prompt=qa_prompt
#         )

#         try:
#             answer = doc_chain.invoke({
#                 "context": docs,
#                 "history": memory.load_memory_variables({}).get("history", []),
#                 "question": user_query,
#             })

#         except RateLimitError:
#             logger.exception("[RAG] OpenAI quota exceeded during LLM call")
#             return TECHNICAL_ERROR_MESSAGE

#         except Exception:
#             logger.exception("[RAG] LLM failed")
#             return FALLBACK_UNKNOWN

#         answer = (answer or "").strip()

#         # ─────────────────────────────────────
#         # safety checks
#         # ─────────────────────────────────────
#         if not answer or len(answer) < 2:
#             return FALLBACK_UNKNOWN

#         if "?" in answer and clarified_once.get(user_id, False):
#             return FALLBACK_UNKNOWN

#         return answer

#     except Exception:
#         logger.exception("[RAG] Unexpected technical error")
#         return TECHNICAL_ERROR_MESSAGE

from __future__ import annotations

# ============================================================================
# rag_engine.py — PRODUCTION RAG ENGINE
# Clean rewrite fixing:
# 1. Hallucination — LLM only answers from KB, strict grounding
# 2. Wrong KB routing — query expansion bridges Hinglish→Hindi gap
# 3. Irrelevant capture questions — issue-type aware question generation
# 4. PATH A re-checks KB after each merchant answer
# ============================================================================

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
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain.schema import Document
from openai import RateLimitError

from unknown_issue_store import save_unknown_issue

try:
    from bm25_store import load_bm25_retriever
except ImportError:
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(__file__))
    from bm25_store import load_bm25_retriever

load_dotenv()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
EMBED_MODEL        = "text-embedding-3-large"
OPENAI_MODEL       = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.3
OPENAI_MAX_TOKENS  = 150
OPENAI_TIMEOUT     = 20
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
MAX_CLARIFY_QUESTIONS = 4

FALLBACK_UNKNOWN = (
    "हमने आपके दुविधा को नोट कर लिया है और आपकी चिंता को टीम तक पहुंचा दिया है "
    "तथा शीघ्र ही आपको जवाब देंगे!"
)
TECHNICAL_ERROR_MESSAGE = (
    "माफ़ कीजिए, अभी तकनीकी समस्या आ गई है। कृपया थोड़ी देर बाद फिर से कोशिश करें।"
)

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
user_memory_store: Dict[str, tuple[ConversationBufferWindowMemory, datetime]] = {}
session_issue_state: Dict[str, dict] = {}

def _get_issue_state(session_id: str) -> dict:
    if session_id not in session_issue_state:
        session_issue_state[session_id] = {
            "active": False, "original_query": "",
            "clarifications": [], "questions_asked": 0, "last_question": "",
        }
    return session_issue_state[session_id]

def _reset_issue_state(session_id: str) -> None:
    session_issue_state[session_id] = {
        "active": False, "original_query": "",
        "clarifications": [], "questions_asked": 0, "last_question": "",
    }

# ─────────────────────────────────────────────
# MEMORY
# ─────────────────────────────────────────────
def create_memory() -> ConversationBufferWindowMemory:
    return ConversationBufferWindowMemory(
        memory_key="history", input_key="question",
        return_messages=True, chat_memory=ChatMessageHistory(), k=6
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
# QUERY EXPANSION
# Bridges Hinglish merchant queries → Hindi KB docs
# "id inactive hai kya kare" → "आईडी बंद है क्या करें"
# ─────────────────────────────────────────────
EXPANSION_MAP = {
    # Romanized Hindi → Devanagari (most critical mappings)
    "hai": "है", "hain": "हैं", "tha": "था", "thi": "थी",
    "kya": "क्या", "kare": "करें", "karna": "करना", "karo": "करें",
    "kaise": "कैसे", "kyun": "क्यों", "kab": "कब",
    "nahi": "नहीं", "nahin": "नहीं", "ho": "हो",
    "gaya": "गया", "gayi": "गई", "raha": "रहा", "rahi": "रही",
    "chahiye": "चाहिए", "batao": "बताएं", "ab": "अब",
    "se": "से", "ke": "के", "ki": "की", "mein": "में",
    "ko": "को", "liye": "लिए", "wala": "वाला",
    # Domain terms
    "inactive": "Inactive बंद इनएक्टिव",
    "id": "ID आईडी",
    "activate": "activate चालू खोलना",
    "band": "बंद inactive",
    "lock": "lock बंद",
    "kyc": "KYC केवाईसी verification",
    "documents": "documents दस्तावेज़",
    "document": "document दस्तावेज़",
    "paise": "पैसे amount",
    "paisa": "पैसा amount",
    "fas": "फंसे stuck pending",
    "fase": "फंसे pending",
    "settlement": "settlement सेटलमेंट",
    "transfer": "transfer ट्रांसफर",
    "failed": "failed असफल",
    "pending": "pending पेंडिंग",
    "aeps": "AEPS आधार पेमेंट",
    "dmt": "DMT Domestic Money Transfer",
    "bbps": "BBPS bill payment",
    "device": "device डिवाइस",
    "mantra": "Mantra मंत्रा",
    "morpho": "Morpho मॉर्फो",
    "fingerprint": "fingerprint बायोमेट्रिक",
    "otp": "OTP one time password",
    "login": "login लॉगिन",
    "portal": "portal पोर्टल",
    "balance": "balance बैलेंस",
    "commission": "commission कमीशन",
    "problem": "problem समस्या दिक्कत",
    "error": "error एरर",
    "recharge": "recharge रिचार्ज",
}

def _expand_query(query: str) -> str:
    """Convert Hinglish query to Hindi-mixed form for better KB matching."""
    words = query.lower().strip().split()
    expanded = []
    for word in words:
        if word in EXPANSION_MAP:
            expanded.append(EXPANSION_MAP[word])
        else:
            expanded.append(word)
    return " ".join(expanded)

# ─────────────────────────────────────────────
# RETRIEVER — EnsembleRetriever (FAISS 0.6 + BM25 0.4)
# ─────────────────────────────────────────────
_cached_retriever   = None
_cached_vectorstore = None

from collections import OrderedDict
_retrieval_cache: OrderedDict = OrderedDict()
_CACHE_MAX = 256

RELEVANCE_THRESHOLD = -0.25  # inner product score threshold (range -1 to 1, higher = more similar)
FAISS_WEIGHT = 0.6
BM25_WEIGHT  = 0.4

def load_context_retriever(vectorstore_path: str):
    global _cached_retriever, _cached_vectorstore
    if _cached_retriever is not None:
        return _cached_retriever

    from langchain.retrievers import EnsembleRetriever
    from langchain_community.vectorstores.utils import DistanceStrategy
    embeddings  = OpenAIEmbeddings(model=EMBED_MODEL, api_key=OPENAI_API_KEY)
    vectorstore = FAISS.load_local(
        vectorstore_path, embeddings,
        allow_dangerous_deserialization=True,
        distance_strategy=DistanceStrategy.COSINE,
    )
    _cached_vectorstore = vectorstore
    faiss_retriever     = vectorstore.as_retriever(search_kwargs={"k": 4})
    bm25_retriever      = load_bm25_retriever(vectorstore_path, k=4)

    if bm25_retriever is not None:
        _cached_retriever = EnsembleRetriever(
            retrievers=[faiss_retriever, bm25_retriever],
            weights=[FAISS_WEIGHT, BM25_WEIGHT],
        )
        logger.info(f"[RAG] EnsembleRetriever: FAISS({FAISS_WEIGHT}) + BM25({BM25_WEIGHT})")
    else:
        _cached_retriever = faiss_retriever
        logger.warning("[RAG] BM25 not found — FAISS only. Run: python build_vector.py")

    return _cached_retriever


def _cache_put(key: str, val: List[Document]) -> None:
    """Insert into bounded LRU cache, evicting oldest entry when full."""
    if len(_retrieval_cache) >= _CACHE_MAX:
        _retrieval_cache.popitem(last=False)
    _retrieval_cache[key] = val


def _retrieve(query: str, retriever) -> List[Document]:
    """Retrieve with query expansion and relevance threshold.

    1. Checks bounded cache first.
    2. Tries scored FAISS retrieval — discards docs below RELEVANCE_THRESHOLD.
    3. Falls back to EnsembleRetriever (BM25 + FAISS) when scored retrieval
       yields nothing above threshold.
    """
    if query in _retrieval_cache:
        return _retrieval_cache[query]

    expanded = _expand_query(query)

    # ── Scored FAISS retrieval (preferred — filters irrelevant chunks) ──
    if _cached_vectorstore is not None:
        try:
            scored = _cached_vectorstore.similarity_search_with_relevance_scores(expanded, k=5)
            docs = [doc for doc, score in scored if score >= RELEVANCE_THRESHOLD]
            if docs:
                _cache_put(query, docs)
                logger.info(
                    f"[RAG] Scored retrieval: {len(docs)}/{len(scored)} docs above "
                    f"threshold={RELEVANCE_THRESHOLD} for: '{expanded[:60]}'"
                )
                return docs
            logger.warning(
                f"[RAG] All {len(scored)} docs below threshold={RELEVANCE_THRESHOLD} "
                f"— falling back to ensemble for: '{expanded[:60]}'"
            )
        except Exception:
            logger.warning("[RAG] Scored retrieval failed — falling back to ensemble")

    # ── Ensemble fallback (BM25 + FAISS, no score filtering) ──
    try:
        docs = retriever.invoke(expanded)
        _cache_put(query, docs)
        logger.info(f"[RAG] Ensemble retrieved {len(docs)} docs for: '{expanded[:60]}'")
        return docs
    except Exception:
        logger.exception("[RAG] Ensemble retrieval failed")
        return []

# ─────────────────────────────────────────────
# MAIN PROMPT
# Key design: show the LLM exactly what the KB contains so it knows
# whether it CAN answer. Explicit examples of each tag scenario.
# ─────────────────────────────────────────────
MAIN_PROMPT = PromptTemplate(
    input_variables=["context", "history", "question"],
    template="""Tu Swara hai — Swift Money ki ek real support executive.
Tu abhi ek live phone call par hai. Greeting ho chuki hai.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KNOWLEDGE BASE (yahi tera source hai):
{context}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Abhi tak ki baat:
{history}

Merchant ne kaha: {question}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULES — IN ORDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Kya KB mein is sawaal ka DIRECT jawab hai?
  → Haan, clearly: [ANSWER] <jawab 1-2 sentences mein>
  → Haan, lekin EK cheez pata karna hai: [CLARIFY] <sirf ek question>
  → Bilkul nahi: [UNKNOWN] <sirf ek relevant question>

STEP 2: Tags ke rules
  [ANSWER]  — KB se seedha jawab. Hinglish mein, 1-2 sentences. Guess NAHI.
  [CLARIFY] — KB mein jawab hai lekin service/device/type pata nahi. SIRF ek question.
  [UNKNOWN] — KB mein kuch nahi. SIRF ek question poocho (kab se, kya hua, kaunsa service).
  [SILENT]  — Merchant ne "theek hai / samajh gaya / shukriya" kaha. Kuch mat bolo.

STEP 3: Hallucination rules (STRICT)
  - Sirf KB se jawab do. KB mein nahi hai toh [UNKNOWN].
  - "KYC chahiye", "team se baat karein" — yeh sirf tab bolo jab KB mein clearly likha ho.
  - Merchant ka jawab "nahi" ya "pata nahi" — valid answer hai, dobara same cheez mat poocho.

STEP 4: Language
  - Natural Hinglish. Short sentences. Phone call hai — essay nahi.
  - "haan ji", "achha", "theek hai" — sirf ek baar, naturally.

Response (sirf tag se shuru karo, koi explanation nahi):""")

# ─────────────────────────────────────────────
# CAPTURE QUESTION GENERATOR
# Issue-type aware — asks relevant questions based on problem category
# ─────────────────────────────────────────────
def _get_capture_question(state: dict, llm) -> str:
    """Generate next relevant capture question using plain LLM call."""

    original = state.get("original_query", "").lower()
    clarifications = state.get("clarifications", [])
    asked_questions = {qa["question"] for qa in clarifications}
    asked_answers   = {qa["answer"].lower() for qa in clarifications}

    # Build context of what we know
    known_info = []
    for qa in clarifications:
        known_info.append(f"  - {qa['question']} → {qa['answer']}")
    known_str = "\n".join(known_info) if known_info else "  (koi detail nahi mili abhi tak)"

    # Detect issue type and build relevant question pool
    if any(w in original for w in ["id", "inactive", "activate", "band", "login", "portal", "account", "lock"]):
        question_pool = [
            "Yeh ID kab se inactive hai?",
            "Login karte waqt koi error message aa raha hai?",
            "Kya aapne pehle KYC complete ki thi?",
            "Kya portal par login ho pa rahe hain?",
            "Aapne last time kab is ID ka use kiya tha?",
        ]
    elif any(w in original for w in ["paise", "settlement", "amount", "transfer", "transaction", "fas", "credited", "debit"]):
        question_pool = [
            "Yeh kab se ho raha hai?",
            "Kitna amount tha?",
            "Kaunsa bank account tha?",
            "Kaunsi service thi — AEPS, DMT ya BBPS?",
            "Transaction ke waqt koi error message aaya tha?",
        ]
    elif any(w in original for w in ["device", "mantra", "morpho", "fingerprint", "biometric", "scanner", "machine"]):
        question_pool = [
            "Kaunsa device model hai — Mantra ya Morpho?",
            "Device connect karte waqt kya error aa raha hai?",
            "Driver install hai device ka?",
            "Yeh kab se ho raha hai?",
            "Pehle yeh device theek kaam karta tha?",
        ]
    elif any(w in original for w in ["kyc", "document", "verification", "aadhaar", "pan"]):
        question_pool = [
            "Kya aapke paas Aadhaar card hai?",
            "Kya aapke paas PAN card hai?",
            "KYC process mein kya specific problem aa rahi hai?",
            "Aapka KYC pehle complete hua tha ya pehli baar kar rahe hain?",
        ]
    elif any(w in original for w in ["otp", "password", "login"]):
        question_pool = [
            "OTP kis number par aana chahiye?",
            "OTP kab se nahi aa raha?",
            "Kya network theek hai aapke phone par?",
            "Kaunsa portal ya app use kar rahe hain?",
        ]
    else:
        question_pool = [
            "Yeh kab se ho raha hai?",
            "Kya specific error message aa raha hai?",
            "Kaunsi service ya device se related hai?",
            "Pehle bhi aisa hua tha?",
        ]

    # Pick first question from pool not already asked
    for q in question_pool:
        if q not in asked_questions:
            return q

    # All pool questions asked — use LLM to generate a new one
    try:
        prompt = f"""Ek merchant ne yeh problem batai: "{state['original_query']}"

Abhi tak gather ki gayi info:
{known_str}

Sirf ek NAYA relevant question poocho jo upar ki list mein nahi hai.
Short Hinglish. Koi tag nahi. Sirf question.

Question:"""
        result = llm.invoke(prompt)
        q = (result.content if hasattr(result, "content") else str(result)).strip()
        q = q.strip('"\'').lstrip("Q:").strip()
        if q and len(q) > 4:
            return q
    except Exception:
        logger.exception("[RAG] LLM capture question failed")

    return "Koi aur detail bata sakte hain?"

# ─────────────────────────────────────────────
# SUMMARY + CAPTURE SAVE
# ─────────────────────────────────────────────
SUMMARY_PROMPT = """Write a 2-3 sentence support ticket summary in English.

Issue: {original_query}
Details gathered:
{clarifications_text}

Include: what the problem is, relevant details, what was gathered.
Summary:"""

def _generate_summary(original_query: str, clarifications: list) -> str:
    try:
        llm = _init_llm()
        clar_text = "\n".join(
            f"Q: {qa['question']}\nA: {qa['answer']}" for qa in clarifications
        ) or "No details gathered."
        result  = llm.invoke(SUMMARY_PROMPT.format(
            original_query=original_query, clarifications_text=clar_text
        ))
        return (result.content if hasattr(result, "content") else str(result)).strip()
    except Exception:
        parts = [f"Issue: {original_query}"]
        for qa in clarifications:
            parts.append(f"Q: {qa['question']} | A: {qa['answer']}")
        return " | ".join(parts)

def _close_capture(session_id: str, call_id: Optional[str] = None) -> None:
    state = _get_issue_state(session_id)
    if not state["active"]:
        return
    summary = _generate_summary(state["original_query"], state["clarifications"])
    try:
        record = save_unknown_issue(
            session_id=session_id,
            original_query=state["original_query"],
            clarifications=state["clarifications"],
            full_summary=summary,
        )
        logger.info(f"[RAG] Unknown issue saved: id={record['id']}")
    except Exception:
        logger.exception("[RAG] Failed to save unknown issue")
    _reset_issue_state(session_id)

# ─────────────────────────────────────────────
# LLM SINGLETON
# ─────────────────────────────────────────────
_llm: Optional[ChatOpenAI] = None

def _init_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=OPENAI_MODEL, temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS, timeout=OPENAI_TIMEOUT,
            openai_api_key=OPENAI_API_KEY,
        )
    return _llm

def _parse_response(raw: str) -> tuple[str, str]:
    raw = (raw or "").strip()
    for tag in ("SILENT", "CLARIFY", "UNKNOWN", "ANSWER"):
        if raw.startswith(f"[{tag}]"):
            return tag, raw[len(f"[{tag}]"):].strip()
    logger.warning(f"[RAG] No tag in response: '{raw[:80]}' — routing to UNKNOWN")
    return "UNKNOWN", ""

# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────
def get_contextual_response(
    user_query: str,
    retriever,
    user_id: str,
    call_id: Optional[str] = None,
) -> str:
    try:
        llm    = _init_llm()
        memory = get_user_memory(user_id)
        state  = _get_issue_state(user_id)

        user_query = (user_query or "").strip()
        if not user_query:
            return FALLBACK_UNKNOWN

        # ─────────────────────────────────────
        # PATH A: In capture mode — merchant answering our questions
        # ─────────────────────────────────────
        if state["active"] and state["last_question"]:

            # Record answer
            state["clarifications"].append({
                "question": state["last_question"],
                "answer":   user_query,
            })
            state["last_question"] = ""
            count = len(state["clarifications"])
            logger.info(f"[RAG] Capture: {count}/{MAX_CLARIFY_QUESTIONS} answers recorded")

            # Max reached — save and give fallback
            if count >= MAX_CLARIFY_QUESTIONS:
                logger.info("[RAG] Max clarifications — closing capture")
                _close_capture(user_id, call_id)
                try:
                    memory.save_context({"question": user_query}, {"output": FALLBACK_UNKNOWN})
                except Exception:
                    pass
                return FALLBACK_UNKNOWN

            # Try KB again with enriched query (original + all answers so far)
            # Sometimes merchant's answers contain keywords that unlock KB match
            enriched = (
                state["original_query"] + " " +
                " ".join(qa["answer"] for qa in state["clarifications"])
            ).strip()
            enriched_docs = _retrieve(enriched, retriever)

            if enriched_docs:
                # Re-run LLM with enriched context — maybe KB can answer now
                try:
                    doc_chain  = create_stuff_documents_chain(llm=llm, prompt=MAIN_PROMPT)
                    raw_answer = doc_chain.invoke({
                        "context":  enriched_docs,
                        "history":  memory.load_memory_variables({}).get("history", []),
                        "question": user_query,
                    })
                    tag, content = _parse_response(raw_answer)
                    logger.info(f"[RAG] PATH A re-check: tag={tag}")

                    if tag == "ANSWER":
                        # KB now has the answer after clarification
                        answer = content.strip() or FALLBACK_UNKNOWN
                        _reset_issue_state(user_id)
                        try:
                            memory.save_context({"question": user_query}, {"output": answer})
                        except Exception:
                            pass
                        return answer

                    if tag == "SILENT":
                        try:
                            memory.save_context({"question": user_query}, {"output": ""})
                        except Exception:
                            pass
                        return ""
                except Exception:
                    logger.exception("[RAG] PATH A re-check LLM failed")

            # KB still can't answer — ask next capture question
            next_q = _get_capture_question(state, llm)
            state["questions_asked"] += 1
            state["last_question"]    = next_q
            logger.info(f"[RAG] Capture Q{state['questions_asked']}: '{next_q}'")
            try:
                memory.save_context({"question": user_query}, {"output": next_q})
            except Exception:
                pass
            return next_q

        # ─────────────────────────────────────
        # PATH B: Normal turn — retrieve and answer
        # ─────────────────────────────────────
        else:
            try:
                docs = _retrieve(user_query, retriever)
            except RateLimitError:
                return TECHNICAL_ERROR_MESSAGE
            except Exception:
                logger.exception("[RAG] Retrieval failed")
                return FALLBACK_UNKNOWN

        if not docs:
            logger.warning("[RAG] No docs retrieved — using fallback")
            return FALLBACK_UNKNOWN

        # LLM call
        doc_chain = create_stuff_documents_chain(llm=llm, prompt=MAIN_PROMPT)
        try:
            raw_answer = doc_chain.invoke({
                "context":  docs,
                "history":  memory.load_memory_variables({}).get("history", []),
                "question": user_query,
            })
        except RateLimitError:
            return TECHNICAL_ERROR_MESSAGE
        except Exception:
            logger.exception("[RAG] LLM failed")
            return FALLBACK_UNKNOWN

        tag, content = _parse_response(raw_answer)
        logger.info(f"[RAG] tag={tag} content='{content[:80]}'")

        # Route by tag
        if tag == "SILENT":
            try:
                memory.save_context({"question": user_query}, {"output": ""})
            except Exception:
                pass
            return ""

        if tag == "CLARIFY":
            question = content or FALLBACK_UNKNOWN
            try:
                memory.save_context({"question": user_query}, {"output": question})
            except Exception:
                pass
            return question

        if tag == "UNKNOWN":
            # Start capture loop
            if not state["active"]:
                state["active"]          = True
                state["original_query"]  = user_query
                state["clarifications"]  = []
                state["questions_asked"] = 0
                logger.info(f"[RAG] Capture started for: '{user_query}'")

            question = _get_capture_question(state, llm)
            state["questions_asked"] += 1
            state["last_question"]    = question
            logger.info(f"[RAG] Capture Q1: '{question}'")
            try:
                memory.save_context({"question": user_query}, {"output": question})
            except Exception:
                pass
            return question

        # ANSWER
        answer = content.strip() if content else FALLBACK_UNKNOWN
        if len(answer) < 2:
            return FALLBACK_UNKNOWN
        try:
            memory.save_context({"question": user_query}, {"output": answer})
        except Exception:
            pass
        return answer

    except Exception:
        logger.exception("[RAG] Unexpected error")
        return TECHNICAL_ERROR_MESSAGE