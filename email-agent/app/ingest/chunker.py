from typing import List
from app.models import EmailRecord

MAX_CHARS = 2000


def chunk_email(email: EmailRecord) -> List[str]:
    text = email.body_text
    if not text:
        return []

    header_parts = []
    if email.subject:
        header_parts.append(f"Subject: {email.subject}")
    if email.sender_name:
        header_parts.append(f"From: {email.sender_name}")
    elif email.sender_email:
        header_parts.append(f"From: {email.sender_email}")
    if email.received_at:
        header_parts.append(f"Date: {email.received_at.strftime('%Y-%m-%d %H:%M')}")

    header = " | ".join(header_parts)
    full_text = f"{header}\n\n{text}"

    paragraphs = full_text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 < MAX_CHARS:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            current = para + "\n\n"

    if current:
        chunks.append(current.strip())

    return chunks if chunks else [full_text[:MAX_CHARS]]
