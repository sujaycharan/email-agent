import httpx
import logging
from app.config import settings
from app.database import vector_store
from app.models import ChatMessage
from typing import List

logger = logging.getLogger(__name__)

EMBED_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"
CHAT_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"


def _embed_text(text: str) -> list[float]:
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            EMBED_URL,
            json={"inputs": text, "options": {"wait_for_model": True}},
        )
        data = resp.json()
        if isinstance(data, list) and data and isinstance(data[0], list):
            dim = len(data[0])
            pooled = [0.0] * dim
            for vec in data:
                for i in range(dim):
                    pooled[i] += vec[i]
            return [v / len(data) for v in pooled]
        if isinstance(data, list) and data and isinstance(data[0], (int, float)):
            return data
        logger.error(f"Embedding API error: {data}")
        raise Exception(f"Unexpected embedding format: {data}")


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
