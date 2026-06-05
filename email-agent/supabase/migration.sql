CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE user_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT,
  email TEXT UNIQUE NOT NULL,
  whatsapp_number TEXT UNIQUE,
  gmail_refresh_token TEXT,
  gmail_access_token TEXT,
  gmail_token_expiry TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE emails (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  gmail_message_id TEXT NOT NULL,
  thread_id TEXT,
  subject TEXT,
  sender_name TEXT,
  sender_email TEXT,
  snippet TEXT,
  body_text TEXT,
  received_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, gmail_message_id)
);

CREATE TABLE email_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email_id UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  embedding VECTOR(768),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_email_chunks_user_id ON email_chunks(user_id);
CREATE INDEX idx_email_chunks_embedding ON email_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chat_messages_user_id ON chat_messages(user_id);

CREATE OR REPLACE FUNCTION search_email_chunks(
  query_embedding VECTOR(768),
  user_uuid UUID,
  match_count INT DEFAULT 5
) RETURNS TABLE(
  id UUID,
  email_id UUID,
  content TEXT,
  similarity FLOAT
) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    ec.id,
    ec.email_id,
    ec.content,
    1 - (ec.embedding <=> query_embedding) AS similarity
  FROM email_chunks ec
  WHERE ec.user_id = user_uuid
    AND ec.embedding IS NOT NULL
  ORDER BY ec.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
