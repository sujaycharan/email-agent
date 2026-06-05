import base64
import re
from email.utils import parsedate_to_datetime
from typing import Optional, Dict, Any, List, Tuple
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def get_gmail_service(refresh_token: str, client_id: str, client_secret: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.modify"],
    )
    return build("gmail", "v1", credentials=creds)


def _decode_data(data: str) -> str:
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def get_text_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    mime = payload["mimeType"]
    body = payload.get("body", {})

    if mime == "text/plain" and body.get("data"):
        return _decode_data(body["data"])

    if mime == "text/html" and body.get("data"):
        return _decode_data(body["data"])

    parts = payload.get("parts", [])
    for part in parts:
        result = get_text_from_payload(part)
        if result:
            return result

    return None


def get_header(headers: list, name: str) -> Optional[str]:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return None


def parse_sender(from_header: str) -> Tuple[Optional[str], Optional[str]]:
    match = re.match(r'"?([^"]*)"?\s*<([^>]+)>', from_header)
    if match:
        return (match.group(1).strip() or None, match.group(2))
    return (None, from_header.strip())


def fetch_unread_emails(service) -> List[Dict[str, Any]]:
    messages = []
    page_token = None
    while True:
        result = service.users().messages().list(
            userId="me",
            q="is:unread",
            pageToken=page_token,
            maxResults=50,
        ).execute()
        messages.extend(result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    emails = []
    for msg in messages:
        full = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="full",
        ).execute()
        emails.append(full)

    return emails


def parse_email_message(user_id: str, msg: Dict[str, Any]) -> dict:
    payload = msg["payload"]
    headers = payload.get("headers", [])

    body_text = get_text_from_payload(payload)
    sender = get_header(headers, "From")
    sender_name, sender_email = parse_sender(sender) if sender else (None, None)

    date_str = get_header(headers, "Date")
    received_at = None
    if date_str:
        try:
            received_at = parsedate_to_datetime(date_str)
        except Exception:
            pass

    return {
        "user_id": user_id,
        "gmail_message_id": msg["id"],
        "thread_id": msg.get("threadId"),
        "subject": get_header(headers, "Subject"),
        "sender_name": sender_name,
        "sender_email": sender_email,
        "snippet": msg.get("snippet"),
        "body_text": body_text,
        "received_at": received_at,
    }


def mark_as_read(service, message_id: str):
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def ensure_label(service, label_name: str = "Processed") -> str:
    labels = service.users().labels().list(userId="me").execute()
    for label in labels.get("labels", []):
        if label["name"] == label_name:
            return label["id"]
    new_label = service.users().labels().create(
        userId="me",
        body={
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()
    return new_label["id"]


def add_label(service, message_id: str, label_id: str):
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": [label_id]},
    ).execute()
