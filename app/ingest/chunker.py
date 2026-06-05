from typing import List
from app.models import EmailRecord

MAX_CHARS = 2000


def chunk_email(email: EmailRecord) -> List[str]:
    text = email.body_text
    if not text:
        return []

    paragraphs = text.split("\n\n")
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

    return chunks if chunks else [text[:MAX_CHARS]]
