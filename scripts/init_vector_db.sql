-- ============================================================================
-- Script: init_vector_db.sql
-- Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
-- Description: Initializes PostgreSQL vector extension, knowledge_base table,
--              HNSW index for cosine distance, metadata GIN index, and 
--              tsvector column with GIN index for Hybrid Search (Dense + Sparse).
-- ============================================================================

-- 1. Enable pgvector and UUID extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Create Knowledge Base table for Hybrid RAG Search (Dense Vector + Sparse TSVector)
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(384), -- 384 dimensions for all-MiniLM-L6-v2 (or VECTOR(1536) for text-embedding-3-small)
    tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Create HNSW (Hierarchical Navigable Small World) Index for Cosine Distance
-- vector_cosine_ops is optimized for Cosine Distance (<=> operator)
CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding_hnsw 
ON knowledge_base 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 4. Create GIN index on metadata JSONB for high-speed category & domain filtering
CREATE INDEX IF NOT EXISTS idx_knowledge_base_metadata_gin 
ON knowledge_base 
USING gin (metadata);

-- 5. Create GIN index on tsv for high-speed Sparse Full-Text BM25/FTS Search
CREATE INDEX IF NOT EXISTS idx_knowledge_base_tsv_gin 
ON knowledge_base 
USING gin (tsv);

-- 6. Helper Function: Semantic Search with optional domain filtering & threshold
CREATE OR REPLACE FUNCTION search_knowledge_base_dense(
    query_embedding VECTOR(384),
    match_threshold FLOAT DEFAULT 0.30,
    match_count INT DEFAULT 5,
    filter_category TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        kb.id,
        kb.content,
        kb.metadata,
        1 - (kb.embedding <=> query_embedding) AS similarity
    FROM knowledge_base kb
    WHERE 
        (filter_category IS NULL OR kb.metadata->>'category' = filter_category)
        AND 1 - (kb.embedding <=> query_embedding) >= match_threshold
    ORDER BY kb.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Verification Comment
COMMENT ON TABLE knowledge_base IS 'Holds RAG vector embeddings, tsvector data, and chunk metadata for IT Service Desk, Windows Server, and Oracle DB hybrid search.';
