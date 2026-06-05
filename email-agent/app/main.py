import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.twiml.messaging_response import MessagingResponse

from app.config import settings
from app.gmail.auth import get_auth_url, exchange_code
from app.database import client as db
from app.models import UserAccount
from app.chat.whatsapp import handle_incoming_message
from app.ingest.processor import process_user_emails

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def scheduled_email_check():
    logger.info("Checking emails for all users...")
    users = db.get_users_with_gmail()
    for user in users:
        process_user_emails(user)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(scheduled_email_check, "interval", minutes=2)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    from_number = form.get("From", "").replace("whatsapp:", "")
    body = form.get("Body", "").strip()

    response_text = await handle_incoming_message(from_number, body)

    resp = MessagingResponse()
    resp.message(response_text)
    return Response(content=str(resp), media_type="application/xml")


@app.get("/auth/gmail")
async def auth_gmail(email: str):
    auth_url = get_auth_url(email)
    return RedirectResponse(auth_url)


@app.get("/auth/gmail/callback")
async def auth_gmail_callback(code: str, state: str):
    import json
    state_data = json.loads(state)
    email = state_data["email"]
    refresh_token, access_token, expiry = exchange_code(code, state)

    user = db.get_user_by_email(email)
    if not user:
        user = UserAccount(email=email)
        db.create_user(user)

    db.update_user_tokens(email, refresh_token, access_token, expiry)
    return {"message": "Gmail connected successfully! You can close this tab."}
