from twilio.rest import Client
from app.config import settings
from app.database import client as db
from app.models import UserAccount, ChatMessage
from app.rag.engine import answer_question
import logging

logger = logging.getLogger(__name__)

twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)


def send_whatsapp(to_number: str, message: str):
    twilio_client.messages.create(
        body=message,
        from_=f"whatsapp:{settings.twilio_whatsapp_number}",
        to=f"whatsapp:{to_number}",
    )


def send_summary(to_number: str, summary: str):
    send_whatsapp(to_number, summary)


async def handle_incoming_message(from_number: str, body: str) -> str:
    user = db.get_user_by_whatsapp(from_number)

    if not user:
        if "@" in body and "." in body:
            email = body.lower().strip()
            existing = db.get_user_by_email(email)
            if existing:
                if existing.whatsapp_number:
                    return "This email is already linked to another WhatsApp number."
                db.update_user_whatsapp(email, from_number)
                return f"Linked to {email}. Visit {settings.app_url}/auth/gmail?email={email} to connect Gmail."
            new_user = UserAccount(email=email, whatsapp_number=from_number)
            db.create_user(new_user)
            return f"Account created for {email}. Visit {settings.app_url}/auth/gmail?email={email} to connect Gmail."
        return "Welcome! Send your email address to connect your Gmail account."

    if not user.gmail_refresh_token:
        return f"Please connect your Gmail first: {settings.app_url}/auth/gmail?email={user.email}"

    if body.lower() == "check mail":
        from app.ingest.processor import process_user_emails_async
        process_user_emails_async(user)
        return "Checking your mail... I'll notify you on WhatsApp when something arrives."

    chat_history = db.get_recent_chat_history(user.id, limit=5)
    try:
        answer = answer_question(user.id, body, chat_history)
    except Exception as e:
        if "invalid_grant" in str(e) or "expired" in str(e).lower() or "revoked" in str(e).lower():
            return f"Gmail token expired or revoked. Reconnect: {settings.app_url}/auth/gmail?email={user.email}"
        raise

    db.insert_chat_message(ChatMessage(user_id=user.id, role="user", content=body))
    db.insert_chat_message(ChatMessage(user_id=user.id, role="assistant", content=answer))

    return answer
