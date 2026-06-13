from supabase import create_client, Client
from app.config import settings
from typing import List, Dict, Any

supabase: Client = create_client(settings.supabase_url, settings.supabase_key)


def search_similar(user_id: str, query_embedding: List[float], top_k: int = 5, threshold: float = 0.3) -> List[Dict[str, Any]]:
    result = supabase.rpc(
        "search_email_chunks",
        {
            "query_embedding": query_embedding,
            "user_uuid": user_id,
            "match_count": top_k * 2,
            "similarity_threshold": threshold,
        }
    ).execute()
    data = result.data or []
    return data[:top_k]
