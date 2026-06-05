import google.generativeai as genai
from app.config import settings
from app.database import vector_store
from app.models import ChatMessage
from typing import List

genai.configure(api_key=settings.gemini_api_key)


def _embed_text(text: str, task_type: str = "retrieval_query") -> list[float]:
    result = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type=task_type,
    )
    return result["embedding"]


def answer_question(user_id: str, question: str, chat_history: List[ChatMessage]) -> str:
    query_embedding = _embed_text(question, task_type="retrieval_query")

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

    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text
