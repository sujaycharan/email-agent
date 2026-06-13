import spacy
import httpx
import logging
import subprocess
import sys
from app.config import settings
from app.database import vector_store
from app.models import ChatMessage
from typing import List

logger = logging.getLogger(__name__)

CHAT_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}"

_query_cache: dict[str, str] = {}
_CACHE_MAX_SIZE = 100

_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_md")
        except OSError:
            logger.info("Downloading en_core_web_md model...")
            subprocess.run(
                [sys.executable, "-m", "spacy", "download", "en_core_web_md"],
                check=True, capture_output=True,
            )
            _nlp = spacy.load("en_core_web_md")
    return _nlp


def _embed_text(text: str) -> list[float]:
    doc = _get_nlp()(text[:5000])
    return doc.vector.tolist()


def answer_question(user_id: str, question: str, chat_history: List[ChatMessage]) -> str:
    cache_key = f"{user_id}:{question.lower().strip()}"
    if cache_key in _query_cache:
        logger.info(f"Cache hit for user {user_id}")
        return _query_cache[cache_key]

    query_embedding = _embed_text(question)

    chunks = vector_store.search_similar(user_id, query_embedding, top_k=10)

    if not chunks:
        logger.warning(f"No chunks found for user {user_id}, question: {question[:50]}")
        return "I couldn't find any relevant emails to answer your question. Make sure emails have been processed."

    logger.info(f"Found {len(chunks)} chunks for user {user_id}, question: {question[:50]}")
    for i, c in enumerate(chunks[:3]):
        sim = c.get('similarity', 0)
        logger.info(f"  Chunk {i}: similarity={sim:.3f}, content={c['content'][:80]}...")

    filtered_chunks = [c for c in chunks if c.get('similarity', 0) > 0.3]
    if not filtered_chunks:
        logger.warning(f"All chunks below similarity threshold for user {user_id}")
        return "I found some emails but they don't seem relevant to your question. Try rephrasing."

    context = "\n\n".join(
        f"[Email {i+1}] (similarity: {c.get('similarity', 0):.2f}): {c['content']}"
        for i, c in enumerate(filtered_chunks[:5])
    )

    history_lines = []
    for msg in chat_history[-5:]:
        role = "User" if msg.role == "user" else "Assistant"
        history_lines.append(f"{role}: {msg.content}")
    history_text = "\n".join(history_lines)

    prompt = f"""You are an email assistant. Answer the user's question based ONLY on the provided email context.

Context from user's emails (ranked by relevance):
{context}

Chat history:
{history_text}

Question: {question}

Instructions:
- Answer conversationally and concisely
- Use ONLY information from the context above
- If the answer isn't in the context, say "I don't have that information in your emails"
- Do not make up information
- Cite which email number(s) you're referencing"""

    with httpx.Client(timeout=60.0) as client:
        for attempt in range(3):
            resp = client.post(
                CHAT_URL,
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            if resp.status_code == 429:
                wait = 60 * (attempt + 1)
                logger.warning(f"Gemini rate limit (429), waiting {wait}s before retry {attempt + 1}/3")
                import time
                time.sleep(wait)
                continue
            data = resp.json()
            if "candidates" not in data:
                error = data.get("error", {}).get("message", "Unknown Gemini error")
                logger.error(f"Gemini API error: {error}")
                return f"Error: {error}"
            answer = data["candidates"][0]["content"]["parts"][0]["text"]
            if len(_query_cache) >= _CACHE_MAX_SIZE:
                _query_cache.pop(next(iter(_query_cache)))
            _query_cache[cache_key] = answer
            return answer
        return "Error: Gemini rate limit exceeded after retries"
