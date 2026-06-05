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

CHAT_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}"

_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
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
    query_embedding = _embed_text(question)

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
