import spacy
import logging
import threading
import subprocess
import sys
from datetime import datetime

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

MAX_EMAILS_PER_RUN = 5


def _generate_embedding(text: str) -> list[float]:
    doc = _get_nlp()(text[:5000])
    return doc.vector.tolist()


def _generate_summary(email: EmailRecord) -> str:
    body = (email.body_text or "")[:300]
    lines = [l for l in body.split("\n") if l.strip()]
    snippet = " | ".join(lines[:3])
    header = email.sender_name or email.sender_email
    return f"📬 {header} - {email.subject}\n\n{snippet}"


def process_user_emails(user: UserAccount):
    logger.info(f"Processing emails for {user.email}")
    try:
        service = get_gmail_service(
            user.gmail_refresh_token,
            settings.google_client_id,
            settings.google_client_secret,
        )

        label_id = ensure_label(service)

        since = user.gmail_connected_at
        if not since:
            logger.info(f"{user.email}: first connection, setting gmail_connected_at to now and skipping old emails")
            db.update_gmail_connected_at(user.email)
            since = datetime.now()

        messages = fetch_unread_emails(service, since=since)
        logger.info(f"{user.email}: {len(messages)} unread emails since {since}")

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
                try:
                    from app.chat.whatsapp import send_summary
                    summary = _generate_summary(email)
                    send_summary(user.whatsapp_number, summary)
                except Exception as e:
                    logger.error(f"Failed to send WhatsApp notification: {e}")

        logger.info(f"{user.email}: processed {processed} emails")

    except Exception as e:
        logger.error(f"Error processing emails for {user.email}: {e}", exc_info=True)


def process_user_emails_async(user: UserAccount):
    thread = threading.Thread(target=process_user_emails, args=(user,), daemon=True)
    thread.start()
