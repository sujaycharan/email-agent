from supabase import create_client, Client
from app.config import settings
from app.models import UserAccount, EmailRecord, EmailChunk, ChatMessage
from typing import Optional, List
from datetime import datetime

supabase: Client = create_client(settings.supabase_url, settings.supabase_key)


def get_user_by_whatsapp(whatsapp_number: str) -> Optional[UserAccount]:
    result = supabase.table("user_accounts").select("*").eq("whatsapp_number", whatsapp_number).limit(1).execute()
    if result.data:
        return UserAccount(**result.data[0])
    return None


def get_user_by_email(email: str) -> Optional[UserAccount]:
    result = supabase.table("user_accounts").select("*").eq("email", email).limit(1).execute()
    if result.data:
        return UserAccount(**result.data[0])
    return None


def create_user(user: UserAccount) -> UserAccount:
    supabase.table("user_accounts").insert(user.model_dump(mode="json")).execute()
    return user


def update_user_tokens(email: str, refresh_token: str, access_token: str, expiry: datetime):
    supabase.table("user_accounts").update({
        "gmail_refresh_token": refresh_token,
        "gmail_access_token": access_token,
        "gmail_token_expiry": expiry.isoformat(),
    }).eq("email", email).execute()


def update_user_whatsapp(email: str, whatsapp_number: str):
    supabase.table("user_accounts").update({
        "whatsapp_number": whatsapp_number,
    }).eq("email", email).execute()


def get_users_with_gmail() -> List[UserAccount]:
    result = supabase.table("user_accounts").select("*").not_.is_("gmail_refresh_token", "null").execute()
    return [UserAccount(**row) for row in result.data]


def email_exists(user_id: str, gmail_message_id: str) -> bool:
    result = supabase.table("emails").select("id").eq("user_id", user_id).eq("gmail_message_id", gmail_message_id).limit(1).execute()
    return len(result.data) > 0


def insert_email(email: EmailRecord) -> EmailRecord:
    supabase.table("emails").insert(email.model_dump(mode="json")).execute()
    return email


def insert_chunk_with_embedding(chunk: EmailChunk, embedding: list):
    data = chunk.model_dump(mode="json")
    data["embedding"] = embedding


def insert_chat_message(msg: ChatMessage):
    supabase.table("chat_messages").insert(msg.model_dump(mode="json")).execute()


def get_recent_chat_history(user_id: str, limit: int = 10) -> List[ChatMessage]:
    result = supabase.table("chat_messages").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
    return [ChatMessage(**row) for row in reversed(result.data)]
