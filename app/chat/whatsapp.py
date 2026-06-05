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
        return "Welcome! Send your email address to connect your Gmail account."

    if not user.gmail_refresh_token:
        existing = db.get_user_by_email(body.lower().strip())
        if existing:
            if existing.whatsapp_number:
                return "This email is already linked to another WhatsApp number."
            db.update_user_whatsapp(body.lower().strip(), from_number)
            return f"Linked to {body}. Now visit {settings.app_url}/auth/gmail?email={body} to connect Gmail."
        new_user = UserAccount(email=body.lower().strip(), whatsapp_number=from_number)
        db.create_user(new_user)
        return f"Account created for {body}. Visit {settings.app_url}/auth/gmail?email={body} to connect Gmail."

    if body.lower() == "check mail":
        from app.ingest.processor import process_user_emails
        process_user_emails(user)
        return "Checked your mail!"

    chat_history = db.get_recent_chat_history(user.id, limit=5)
    answer = answer_question(user.id, body, chat_history)

    db.insert_chat_message(ChatMessage(user_id=user.id, role="user", content=body))
    db.insert_chat_message(ChatMessage(user_id=user.id, role="assistant", content=answer))

    return answer
