"""
Vector Embedding and PostgreSQL (pgvector) Storage Pipeline
============================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Loads preprocessed text chunks from `data/processed/clean_chunks.json`,
    generates 384-dimensional dense vector embeddings using
    `sentence-transformers/all-MiniLM-L6-v2`, inserts them in batches into
    the PostgreSQL `knowledge_base` table with pgvector, and conducts
    semantic search similarity verification (sanity check) queries.
"""

import os
import sys
import json
import uuid
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values, Json
from pgvector.psycopg2 import register_vector
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Output Encoding Configuration (UTF-8 on Windows cp1254)
# ---------------------------------------------------------------------------
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

LOG_FORMAT = "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("VectorStoreManager")


class VectorStoreManager:
    """
    Manages vector generation, PostgreSQL pgvector connection,
    bulk insertion, and semantic similarity search.
    """

    DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384

    def __init__(
        self,
        db_host: Optional[str] = None,
        db_port: Optional[int] = None,
        db_user: Optional[str] = None,
        db_password: Optional[str] = None,
        db_name: Optional[str] = None,
        model_name: str = DEFAULT_MODEL_NAME,
        chunks_file_path: Optional[Path] = None
    ):
        """
        Initializes the VectorStoreManager.

        Args:
            db_host (str, optional): PostgreSQL host (default from env or 'localhost').
            db_port (int, optional): PostgreSQL port (default: 5432).
            db_user (str, optional): Database username (default: 'postgres').
            db_password (str, optional): Database password (default: 'password123').
            db_name (str, optional): Database name (default: 'it_support_db').
            model_name (str): SentenceTransformer model identifier.
            chunks_file_path (Path, optional): Path to clean_chunks.json.
        """
        project_root = Path(__file__).resolve().parent.parent.parent
        self.chunks_file_path = chunks_file_path or (project_root / "data" / "processed" / "clean_chunks.json")

        self.db_host = db_host or os.getenv("POSTGRES_HOST", "localhost")
        self.db_port = int(db_port or os.getenv("POSTGRES_PORT", "5432"))
        self.db_user = db_user or os.getenv("POSTGRES_USER", "postgres")
        self.db_password = db_password or os.getenv("POSTGRES_PASSWORD", "password123")
        self.db_name = db_name or os.getenv("POSTGRES_DB", "it_support_db")

        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None
        self._connection = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-loads the SentenceTransformer embedding model."""
        if self._model is None:
            logger.info(f"Loading SentenceTransformer model: '{self.model_name}'...")
            self._model = SentenceTransformer(self.model_name)
            logger.info(f"Model loaded successfully. Vector Dimension: {self.EMBEDDING_DIM}")
        return self._model

    def _discover_wsl_ip(self) -> Optional[str]:
        """Attempts to discover WSL host IP when running from Windows."""
        commands = [
            ["wsl", "-d", "Ubuntu", "hostname", "-I"],
            ["wsl", "hostname", "-i"]
        ]
        for cmd in commands:
            try:
                out = subprocess.check_output(cmd, text=True, timeout=3).strip()
                ips = [x for x in out.split() if "." in x and not x.startswith("127.")]
                if ips:
                    return ips[0]
            except Exception:
                continue
        return None

    def get_connection(self):
        """
        Establishes and returns a connected psycopg2 instance with pgvector registered.
        Implements intelligent fallback to WSL host if localhost encounters a port collision.
        """
        if self._connection is not None and not self._connection.closed:
            return self._connection

        hosts_to_try = [self.db_host]
        if self.db_host in ("localhost", "127.0.0.1"):
            wsl_ip = self._discover_wsl_ip()
            if wsl_ip and wsl_ip not in hosts_to_try:
                hosts_to_try.append(wsl_ip)

        last_error = None
        for host in hosts_to_try:
            try:
                logger.info(f"Connecting to PostgreSQL at {host}:{self.db_port}/{self.db_name} as '{self.db_user}'...")
                conn = psycopg2.connect(
                    host=host,
                    port=self.db_port,
                    user=self.db_user,
                    password=self.db_password,
                    dbname=self.db_name,
                    connect_timeout=5
                )
                conn.autocommit = True
                register_vector(conn)
                self._connection = conn
                logger.info(f"[OK] Connected to PostgreSQL with pgvector on host '{host}'.")
                return self._connection
            except Exception as e:
                last_error = e
                logger.warning(f"Connection attempt to {host} failed: {e}")

        raise ConnectionError(
            f"Failed to connect to PostgreSQL ({self.db_name}) on hosts {hosts_to_try}: {last_error}"
        )

    def ensure_table_schema(self):
        """
        Verifies that PostgreSQL vector extension, table, and HNSW index exist.
        """
        conn = self.get_connection()
        with conn.cursor() as cur:
            # 1. Enable pgvector extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")

            # 2. Ensure knowledge_base table exists
            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                content TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                embedding vector({self.EMBEDDING_DIM}),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 3. Create HNSW index on vector column for cosine distance
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding_hnsw 
            ON knowledge_base 
            USING hnsw (embedding vector_cosine_ops);
            """)

            # 4. Create GIN index on metadata JSONB for rapid domain/category filtering
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_base_metadata_gin 
            ON knowledge_base 
            USING gin (metadata);
            """)

        logger.info(f"[OK] Database schema and HNSW index verified for table 'knowledge_base'.")

    def load_chunks(self) -> List[Dict[str, Any]]:
        """Loads cleaned chunk records from JSON file."""
        if not self.chunks_file_path.exists():
            raise FileNotFoundError(
                f"Clean chunks file not found at: {self.chunks_file_path.resolve()}.\n"
                f"Please run `python src/data/preprocess.py` first."
            )

        with open(self.chunks_file_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        logger.info(f"Loaded {len(chunks)} chunks from {self.chunks_file_path.resolve()}.")
        return chunks

    def generate_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generates dense vector embeddings in batches using SentenceTransformer.

        Args:
            texts (List[str]): List of clean text chunks.
            batch_size (int): Embedding inference batch size.

        Returns:
            List[List[float]]: List of 384-dimensional embedding vectors.
        """
        logger.info(f"Generating embeddings for {len(texts)} text chunks (batch_size={batch_size})...")
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_numpy=True
        )
        return embeddings.tolist()

    def store_chunks(
        self,
        chunks: List[Dict[str, Any]],
        batch_size: int = 100,
        clear_existing: bool = True
    ) -> int:
        """
        Embeds and bulk inserts chunks into the PostgreSQL `knowledge_base` table.

        Args:
            chunks (List[Dict[str, Any]]): List of chunk dictionaries.
            batch_size (int): Bulk insert batch size (default: 100).
            clear_existing (bool): If True, truncates existing knowledge_base records before insert.

        Returns:
            int: Number of records inserted.
        """
        if not chunks:
            logger.warning("No chunks provided for storage.")
            return 0

        self.ensure_table_schema()
        conn = self.get_connection()

        if clear_existing:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE knowledge_base RESTART IDENTITY;")
                logger.info("Cleared previous records from 'knowledge_base' table.")

        # Extract text content for embedding
        texts = [item.get("content", item.get("chunk_content", "")) for item in chunks]
        embeddings = self.generate_embeddings(texts, batch_size=32)

        # Prepare row tuples for bulk insert
        insert_records = []
        for item, emb in zip(chunks, embeddings):
            chunk_id = item.get("chunk_id") or str(uuid.uuid4())
            content = item.get("content") or item.get("chunk_content") or ""
            metadata = item.get("metadata") or {}

            # Ensure essential metadata keys exist
            metadata.setdefault("chunk_id", chunk_id)
            metadata.setdefault("source", item.get("source", "unknown"))
            metadata.setdefault("category", item.get("category", "general"))

            insert_records.append((
                chunk_id,
                content,
                Json(metadata),
                emb
            ))

        # Perform batched insertion using execute_values
        insert_query = """
        INSERT INTO knowledge_base (id, content, metadata, embedding)
        VALUES %s
        ON CONFLICT (id) DO UPDATE 
        SET content = EXCLUDED.content,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding,
            created_at = CURRENT_TIMESTAMP;
        """

        logger.info(f"Bulk inserting {len(insert_records)} records into PostgreSQL in batches of {batch_size}...")
        total_inserted = 0

        for i in tqdm(range(0, len(insert_records), batch_size), desc="Storing Batches in pgvector"):
            batch = insert_records[i:i + batch_size]
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    insert_query,
                    batch,
                    template="(%s, %s, %s, %s)",
                    page_size=batch_size
                )
            total_inserted += len(batch)

        logger.info(f"[OK] Successfully stored {total_inserted} vector records in 'knowledge_base'.")
        return total_inserted

    def search_similar(
        self,
        query: str,
        top_k: int = 3,
        category_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic similarity search against `knowledge_base` using Cosine Distance (<=>).

        Args:
            query (str): Natural language search query.
            top_k (int): Number of nearest records to return.
            category_filter (str, optional): Optional category filter ('windows_server', 'oracle_db', 'service_desk').

        Returns:
            List[Dict[str, Any]]: List of matching records with similarity score and metadata.
        """
        conn = self.get_connection()
        query_embedding = self.model.encode(query, normalize_embeddings=True).tolist()

        sql = """
        SELECT 
            id,
            content,
            metadata,
            1 - (embedding <=> %s::vector) AS similarity_score
        FROM knowledge_base
        WHERE (%s IS NULL OR metadata->>'category' = %s)
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s;
        """

        results = []
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (query_embedding, category_filter, category_filter, query_embedding, top_k)
            )
            rows = cur.fetchall()
            for row in rows:
                results.append({
                    "id": str(row[0]),
                    "content": row[1],
                    "metadata": row[2],
                    "similarity": float(row[3])
                })

        return results

    def run_sanity_checks(self):
        """
        Executes standard sanity check semantic queries and outputs a clear
        formatted report to the console.
        """
        test_queries = [
            "How to reset user password in Active Directory",
            "ORA-01653: unable to extend table in tablespace",
            "VPN connection failure after network update"
        ]

        print("\n" + "=" * 80)
        print("=== DOGRULAMA / BENZERLIK TESTI (SANITY CHECK) ===")
        print("=" * 80)

        for q_idx, query in enumerate(test_queries, 1):
            print(f"\n[{q_idx}/3] Test Sorgusu: \"{query}\"")
            print("-" * 80)

            matches = self.search_similar(query=query, top_k=3)

            if not matches:
                print("  [UYARI] Hiç eşleşen kayıt bulunamadı.")
                continue

            for rank, item in enumerate(matches, 1):
                score = item["similarity"]
                meta = item["metadata"]
                category = meta.get("category", "N/A")
                orig_id = meta.get("original_id", "N/A")
                title = meta.get("title", meta.get("subcategory", "N/A"))
                source = meta.get("source", "N/A")

                # Create brief snippet
                content_preview = item["content"].replace("\n", " ")[:140]

                print(f"  #{rank} | Benzerlik Skoru: %{score * 100:.2f} ({score:.4f})")
                print(f"     • Kategori : {category.upper()} | Kayıt ID: {orig_id}")
                print(f"     • Başlık   : {title}")
                print(f"     • Kaynak   : {source}")
                print(f"     • İçerik   : {content_preview}...")
                print()

        print("=" * 80)
        print("[OK] Vektör veritabanı doğrulama testleri başarıyla tamamlandı.")
        print("=" * 80 + "\n")


# ---------------------------------------------------------------------------
# CLI Execution Pipeline
# ---------------------------------------------------------------------------
def main():
    """Main execution entrypoint for embed and store pipeline."""
    print("=" * 80)
    print("=== AKILLI SERVIS MASASI & SISTEM UZMANI - VEKTORLESTIRME VE KAYIT HATTI ===")
    print("=" * 80)

    manager = VectorStoreManager()

    # 1. Load Preprocessed Clean Chunks
    chunks = manager.load_chunks()

    # 2. Embed & Store into PostgreSQL pgvector
    inserted_count = manager.store_chunks(chunks=chunks, batch_size=100, clear_existing=True)
    print(f"\n[OK] Toplam {inserted_count} chunk vektörleştirilerek 'knowledge_base' tablosuna aktarıldı.")

    # 3. Run Verification / Sanity Check Queries
    manager.run_sanity_checks()


if __name__ == "__main__":
    main()
