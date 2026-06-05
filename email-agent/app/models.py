from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class UserAccount(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    email: str
    whatsapp_number: Optional[str] = None
    gmail_refresh_token: Optional[str] = None
    gmail_access_token: Optional[str] = None
    gmail_token_expiry: Optional[datetime] = None
    gmail_connected_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)


class EmailRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    gmail_message_id: str
    thread_id: Optional[str] = None
    subject: Optional[str] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    snippet: Optional[str] = None
    body_text: Optional[str] = None
    received_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)


class EmailChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email_id: str
    user_id: str
    chunk_index: int
    content: str
    created_at: datetime = Field(default_factory=datetime.now)


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    role: str
    content: str
    created_at: datetime = Field(default_factory=datetime.now)
