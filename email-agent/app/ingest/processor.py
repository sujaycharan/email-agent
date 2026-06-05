import google.generativeai as genai
import logging
import threading
import time

from app.config import settings
from app.gmail.fetcher import (
    get_gmail_service,
    fetch_unread_emails,
    parse_email_message,
    mark_as_read,
    ensure_label,
    add_label,
)
from app.ingest.chunker import chunk_email
from app.models import EmailRecord, EmailChunk, UserAccount
from app.database import client as db

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.gemini_api_key)

MAX_EMAILS_PER_RUN = 5


def _generate_embedding(text: str) -> list[float]:
    result = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="retrieval_document",
    )
    return result["embedding"]


def _generate_summary(email: EmailRecord) -> str:
    prompt = f"""Explain this email to a normal person. Be concise.

From: {email.sender_name or email.sender_email}
Subject: {email.subject}
Body: {email.body_text[:2000]}

Mention:
- Who sent it
- What it's about
- Any action required
- Any deadlines

Keep it under 100 words."""

    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return f"📬 {email.sender_name or email.sender_email} - {email.subject}\n\n{response.text}"


def process_user_emails(user: UserAccount):
    logger.info(f"Processing emails for {user.email}")
    try:
        service = get_gmail_service(
            user.gmail_refresh_token,
            settings.google_client_id,
            settings.google_client_secret,
        )

        label_id = ensure_label(service)
        messages = fetch_unread_emails(service)
        logger.info(f"{user.email}: {len(messages)} unread emails found")

        processed = 0
        for msg in messages:
            if processed >= MAX_EMAILS_PER_RUN:
                logger.info(f"{user.email}: hit limit of {MAX_EMAILS_PER_RUN}, stopping")
                break

            msg_id = msg["id"]

            if db.email_exists(user.id, msg_id):
                continue

            email_data = parse_email_message(user.id, msg)
            email = EmailRecord(**email_data)
            chunks_text = chunk_email(email)

            db.insert_email(email)

            for idx, chunk_text in enumerate(chunks_text):
                chunk = EmailChunk(
                    email_id=email.id,
                    user_id=user.id,
                    chunk_index=idx,
                    content=chunk_text,
                )
                embedding = _generate_embedding(chunk_text)
                db.insert_chunk_with_embedding(chunk, embedding)

            mark_as_read(service, msg_id)
            add_label(service, msg_id, label_id)

            processed += 1
            if user.whatsapp_number:
                from app.chat.whatsapp import send_summary
                summary = _generate_summary(email)
                send_summary(user.whatsapp_number, summary)

        logger.info(f"{user.email}: processed {processed} emails")

    except Exception as e:
        logger.error(f"Error processing emails for {user.email}: {e}")


def process_user_emails_async(user: UserAccount):
    thread = threading.Thread(target=process_user_emails, args=(user,), daemon=True)
    thread.start()
