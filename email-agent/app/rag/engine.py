import httpx
import logging
from app.config import settings
from app.database import vector_store
from app.models import ChatMessage
from typing import List

logger = logging.getLogger(__name__)

EMBED_URL = f"https://generativelanguage.googleapis.com/v1/models/text-embedding-004:embedContent?key={settings.gemini_api_key}"
CHAT_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"


def _embed_text(text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
    with httpx.Client() as client:
        resp = client.post(
            EMBED_URL,
            json={
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
            },
        )
        data = resp.json()
        if "embedding" not in data:
            logger.error(f"Embedding API error: {data}")
            raise Exception(f"Embedding API returned: {data}")
        return data["embedding"]["values"]


def answer_question(user_id: str, question: str, chat_history: List[ChatMessage]) -> str:
    query_embedding = _embed_text(question, task_type="RETRIEVAL_QUERY")

    chunks = vector_store.search_similar(user_id, query_embedding, top_k=5)

    if not chunks:
        return "I couldn't find any relevant emails to answer your question."

    context = "\n\n".join(
        f"[Email {i+1}]: {c['content']}" for i, c in enumerate(chunks)
    )

    history_lines = []
    for msg in chat_history[-5:]:
        role = "User" if msg.role == "user" else "Assistant"
        history_lines.append(f"{role}: {msg.content}")
    history_text = "\n".join(history_lines)

    prompt = f"""You are an email assistant. Answer the user's question based on their emails.

Context from user's emails:
{context}

Chat history:
{history_text}

Question: {question}

Answer conversationally and concisely. If the answer isn't in the context, say so. Do not make up information."""

    with httpx.Client() as client:
        resp = client.post(
            CHAT_URL,
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
