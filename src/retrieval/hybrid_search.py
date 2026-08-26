"""
Hybrid Search Retrieval Engine (Dense Vector + Sparse BM25/Full-Text) with RRF
==============================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Implements a state-of-the-art Hybrid Search pipeline combining dense vector
    similarity (PostgreSQL pgvector / sentence-transformers) with sparse full-text
    keyword search (PostgreSQL TSVector GIN) merged via Reciprocal Rank Fusion (RRF).
"""

import os
import re
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add project root to sys.path for direct CLI execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
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
logger = logging.getLogger("HybridSearchEngine")


class HybridSearchEngine:
    """
    Hybrid Search Engine combining Dense Vector embeddings (pgvector)
    and Sparse Full-Text Keyword Search (tsvector) using Reciprocal Rank Fusion (RRF).
    """

    DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384
    DEFAULT_RRF_K = 60  # Standard smoothing constant for RRF

    def __init__(
        self,
        db_host: Optional[str] = None,
        db_port: Optional[int] = None,
        db_user: Optional[str] = None,
        db_password: Optional[str] = None,
        db_name: Optional[str] = None,
        model_name: str = DEFAULT_MODEL_NAME,
        rrf_k: int = DEFAULT_RRF_K
    ):
        """
        Initializes the HybridSearchEngine.

        Args:
            db_host (str, optional): Database host (default from env or 'localhost').
            db_port (int, optional): Database port (default: 5432).
            db_user (str, optional): Database user (default: 'postgres').
            db_password (str, optional): Database password (default: 'password123').
            db_name (str, optional): Database name (default: 'it_support_db').
            model_name (str): Dense embedding model identifier.
            rrf_k (int): Reciprocal Rank Fusion constant (default: 60).
        """
        self.db_host = db_host or os.getenv("POSTGRES_HOST", "localhost")
        self.db_port = int(db_port or os.getenv("POSTGRES_PORT", "5432"))
        self.db_user = db_user or os.getenv("POSTGRES_USER", "postgres")
        self.db_password = db_password or os.getenv("POSTGRES_PASSWORD", "password123")
        self.db_name = db_name or os.getenv("POSTGRES_DB", "it_support_db")

        self.model_name = model_name
        self.rrf_k = rrf_k
        self._model: Optional[SentenceTransformer] = None
        self._connection = None

        # Ensure database schema is upgraded for hybrid search
        self.ensure_hybrid_schema()

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-loads the SentenceTransformer embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model '{self.model_name}'...")
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully.")
        return self._model

    def _discover_wsl_ip(self) -> Optional[str]:
        """Discovers WSL host IP when running in Windows/WSL hybrid environment."""
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
        """
        if self._connection is not None and not self._connection.closed:
            return self._connection

        from src.models.base import discover_db_host
        active_host = discover_db_host()

        hosts_to_try = [active_host]
        if self.db_host not in hosts_to_try:
            hosts_to_try.insert(0, self.db_host)

        last_error = None
        for host in hosts_to_try:
            try:
                conn = psycopg2.connect(
                    host=host,
                    port=self.db_port,
                    user=self.db_user,
                    password=self.db_password,
                    dbname=self.db_name,
                    connect_timeout=3
                )
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                register_vector(conn)
                self._connection = conn
                return self._connection
            except Exception as e:
                last_error = e

        raise ConnectionError(
            f"Failed to connect to PostgreSQL ({self.db_name}) on hosts {hosts_to_try}: {last_error}"
        )

    def ensure_hybrid_schema(self):
        """
        Ensures the `knowledge_base` table exists with `tsv` tsvector column
        and corresponding GIN index for fast full-text keyword retrieval.
        """
        conn = self.get_connection()
        with conn.cursor() as cur:
            # 1. Create table if not exists
            cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id SERIAL PRIMARY KEY,
                chunk_id VARCHAR(100) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                category VARCHAR(50) NOT NULL,
                subcategory VARCHAR(100),
                content TEXT NOT NULL,
                source VARCHAR(255),
                metadata JSONB,
                embedding vector(384)
            );
            """)

            # 2. Add generated tsvector column if not exists
            cur.execute("""
            ALTER TABLE knowledge_base 
            ADD COLUMN IF NOT EXISTS tsv tsvector 
            GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
            """)

            # 3. Create GIN index on tsv column for fast text searches
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_base_tsv_gin 
            ON knowledge_base 
            USING gin (tsv);
            """)

            # 3. Create HNSW index on vector embedding if not exists
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding_hnsw 
            ON knowledge_base 
            USING hnsw (embedding vector_cosine_ops);
            """)

            # 4. Create GIN index on metadata JSONB if not exists
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_base_metadata_gin 
            ON knowledge_base 
            USING gin (metadata);
            """)

        logger.info("[OK] Hybrid Search schema & indices (TSVector GIN + Vector HNSW) verified.")

    def _build_sparse_query_terms(self, query: str) -> str:
        """
        Sanitizes and converts user query into a robust disjunctive (OR) TSQuery string
        for BM25-like full-text keyword coverage in PostgreSQL.
        """
        tokens = re.findall(r"[\w\u00C0-\u017F]+", query, flags=re.UNICODE)
        # Filter tokens with length >= 2
        valid_terms = [t for t in tokens if len(t) >= 2]
        if not valid_terms:
            return ""
        # Join with OR operator (|) for maximum keyword recall
        return " | ".join(valid_terms)

    # -----------------------------------------------------------------------
    # 1. Dense Vector Search (pgvector)
    # -----------------------------------------------------------------------
    def dense_search(
        self,
        query: str,
        top_k: int = 20,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic vector search using Cosine Distance (<=>).

        Args:
            query (str): User natural language query.
            top_k (int): Number of dense candidates to retrieve.
            category (str, optional): Domain category filter.

        Returns:
            List[Dict[str, Any]]: List of matching records with dense_similarity and dense_rank.
        """
        conn = self.get_connection()
        query_embedding = self.model.encode(query, normalize_embeddings=True).tolist()

        sql = """
        SELECT 
            id,
            content,
            metadata,
            1 - (embedding <=> %s::vector) AS dense_similarity
        FROM knowledge_base
        WHERE (%s IS NULL OR metadata->>'category' = %s)
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s;
        """

        results = []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                sql,
                (query_embedding, category, category, query_embedding, top_k)
            )
            rows = cur.fetchall()
            for rank, row in enumerate(rows, start=1):
                results.append({
                    "id": str(row["id"]),
                    "content": row["content"],
                    "metadata": row["metadata"],
                    "dense_similarity": float(row["dense_similarity"]),
                    "dense_rank": rank
                })

        return results

    # -----------------------------------------------------------------------
    # 2. Sparse Full-Text Search (PostgreSQL TSVector)
    # -----------------------------------------------------------------------
    def sparse_search(
        self,
        query: str,
        top_k: int = 20,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs BM25-like sparse full-text search using PostgreSQL TSVector and GIN index.

        Args:
            query (str): Search query containing keywords, technical error codes, or cmdlets.
            top_k (int): Number of sparse candidates to retrieve.
            category (str, optional): Domain category filter.

        Returns:
            List[Dict[str, Any]]: List of matching records with sparse_score and sparse_rank.
        """
        conn = self.get_connection()
        or_terms = self._build_sparse_query_terms(query)
        if not or_terms:
            return []

        sql = """
        SELECT 
            kb.id,
            kb.content,
            kb.metadata,
            ts_rank_cd(kb.tsv, to_tsquery('english', %s)) AS sparse_score
        FROM knowledge_base kb
        WHERE 
            kb.tsv @@ to_tsquery('english', %s)
            AND (%s IS NULL OR kb.metadata->>'category' = %s)
        ORDER BY sparse_score DESC
        LIMIT %s;
        """

        results = []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    sql,
                    (or_terms, or_terms, category, category, top_k)
                )
                rows = cur.fetchall()
                for rank, row in enumerate(rows, start=1):
                    results.append({
                        "id": str(row["id"]),
                        "content": row["content"],
                        "metadata": row["metadata"],
                        "sparse_score": float(row["sparse_score"]),
                        "sparse_rank": rank
                    })
            except Exception as e:
                logger.warning(f"Sparse search error with query '{query}': {e}")

        return results

    # -----------------------------------------------------------------------
    # 3. Reciprocal Rank Fusion (RRF) Hybrid Search
    # -----------------------------------------------------------------------
    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        dense_top_k: int = 20,
        sparse_top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Executes Dense and Sparse searches and fuses their rankings using
        Reciprocal Rank Fusion (RRF):
            RRF_Score(d) = 1 / (60 + rank_dense) + 1 / (60 + rank_sparse)

        Args:
            query (str): User natural language or technical query.
            top_k (int): Number of final top results to return (default: 5).
            category (str, optional): Domain category filter ('windows_server', 'oracle_db', 'service_desk').
            dense_top_k (int): Candidate pool size for dense retrieval.
            sparse_top_k (int): Candidate pool size for sparse retrieval.

        Returns:
            List[Dict[str, Any]]: RRF-ranked results with combined score, dense rank, and sparse rank.
        """
        dense_results = self.dense_search(query, top_k=dense_top_k, category=category)
        sparse_results = self.sparse_search(query, top_k=sparse_top_k, category=category)

        # Merge candidate documents by UUID
        candidates: Dict[str, Dict[str, Any]] = {}

        # 1. Incorporate Dense Results
        for item in dense_results:
            doc_id = item["id"]
            dense_rank = item["dense_rank"]
            dense_rrf = 1.0 / (self.rrf_k + dense_rank)

            candidates[doc_id] = {
                "id": doc_id,
                "content": item["content"],
                "metadata": item["metadata"],
                "dense_rank": dense_rank,
                "sparse_rank": None,
                "dense_similarity": item["dense_similarity"],
                "sparse_score": 0.0,
                "rrf_score": dense_rrf
            }

        # 2. Incorporate Sparse Results and Fuse
        for item in sparse_results:
            doc_id = item["id"]
            sparse_rank = item["sparse_rank"]
            sparse_rrf = 1.0 / (self.rrf_k + sparse_rank)

            if doc_id in candidates:
                candidates[doc_id]["sparse_rank"] = sparse_rank
                candidates[doc_id]["sparse_score"] = item["sparse_score"]
                candidates[doc_id]["rrf_score"] += sparse_rrf
            else:
                candidates[doc_id] = {
                    "id": doc_id,
                    "content": item["content"],
                    "metadata": item["metadata"],
                    "dense_rank": None,
                    "sparse_rank": sparse_rank,
                    "dense_similarity": 0.0,
                    "sparse_score": item["sparse_score"],
                    "rrf_score": sparse_rrf
                }

        # 3. Normalize scores against theoretical maximum RRF (k=60 -> 2/61)
        max_possible_rrf = 2.0 / (self.rrf_k + 1.0)
        for doc in candidates.values():
            raw_score = float(doc["rrf_score"])
            norm_score = min(1.0, round(raw_score / max_possible_rrf, 4))
            conf_pct = min(100.0, round(norm_score * 100.0, 2))
            doc["raw_rrf_score"] = raw_score
            doc["normalized_score"] = norm_score
            doc["confidence_percentage"] = conf_pct
            doc["formatted_confidence"] = f"%{conf_pct:.2f}"

        # 4. Sort by RRF Score descending
        ranked_results = sorted(
            candidates.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )

        return ranked_results[:top_k]

    # -----------------------------------------------------------------------
    # 4. Technical Accuracy Verification Suite
    # -----------------------------------------------------------------------
    def run_technical_accuracy_tests(self):
        """
        Runs comprehensive technical domain test scenarios (ORA errors, Event IDs,
        PowerShell/SQL cmdlets, VPN/Spooler issues) and displays detailed accuracy
        metrics comparing Dense, Sparse, and Hybrid (RRF) results with normalized scores.
        """
        test_cases = [
            {
                "query": "ORA-01653 unable to extend table in tablespace USERS",
                "domain": "Oracle DB",
                "expected_category": "oracle_db",
                "expected_keywords": ["ORA-01653", "tablespace", "users01.dbf"]
            },
            {
                "query": "Event ID 4625 Failed Logon Security Event Log PowerShell Get-WinEvent",
                "domain": "Windows Server",
                "expected_category": "windows_server",
                "expected_keywords": ["4625", "Get-WinEvent", "Failed Logon"]
            },
            {
                "query": "Unlock-ADAccount Search-ADAccount LockedOut Active Directory",
                "domain": "Windows Server / AD",
                "expected_category": "windows_server",
                "expected_keywords": ["Unlock-ADAccount", "Search-ADAccount", "Active Directory"]
            },
            {
                "query": "HTTP Error 500.19 0x8007000d URL Rewrite IIS iisreset",
                "domain": "IIS Web Server",
                "expected_category": "windows_server",
                "expected_keywords": ["500.19", "0x8007000d", "urlrewrite"]
            },
            {
                "query": "net stop spooler PRINTERS .SPL .SHD Spooler Error",
                "domain": "Service Desk / Print",
                "expected_category": "service_desk",
                "expected_keywords": ["spooler", "PRINTERS", "net stop"]
            },
            {
                "query": "VPN Certificate Validation Failed FortiClient certmgr.msc",
                "domain": "Service Desk / VPN",
                "expected_category": "service_desk",
                "expected_keywords": ["VPN", "Certificate Validation Failed", "certmgr.msc"]
            }
        ]

        print("\n" + "=" * 95)
        print("=== HIBRIT ARAMA (HYBRID SEARCH - DENSE + SPARSE RRF) NORMALIZED ISABET TESTLERI ===")
        print("=" * 95)

        top1_hits = 0
        top3_hits = 0
        total_tests = len(test_cases)

        for idx, tc in enumerate(test_cases, start=1):
            query = tc["query"]
            domain = tc["domain"]
            exp_cat = tc["expected_category"]
            keywords = tc["expected_keywords"]

            print(f"\n[{idx}/{total_tests}] Test Sorgusu: \"{query}\"")
            print(f"     Hedef Alan: {domain} | Beklenen Kategori: {exp_cat.upper()}")
            print("-" * 95)

            # Perform Hybrid Search
            hybrid_matches = self.hybrid_search(query=query, top_k=3)

            is_top1_hit = False
            is_top3_hit = False

            for rank, item in enumerate(hybrid_matches, start=1):
                meta = item["metadata"]
                cat = meta.get("category", "N/A")
                title = meta.get("title", meta.get("subcategory", "N/A"))
                orig_id = meta.get("original_id", "N/A")
                content = item["content"]

                dense_r = f"#{item['dense_rank']}" if item["dense_rank"] else "YOK"
                sparse_r = f"#{item['sparse_rank']}" if item["sparse_rank"] else "YOK"
                raw_rrf = item.get("raw_rrf_score", item["rrf_score"])
                conf_pct = item.get("confidence_percentage", 0.0)
                norm_score = item.get("normalized_score", 0.0)

                # Keyword match verification
                has_keywords = any(kw.lower() in content.lower() for kw in keywords)

                if rank == 1 and (cat == exp_cat or has_keywords):
                    is_top1_hit = True
                if rank <= 3 and (cat == exp_cat or has_keywords):
                    is_top3_hit = True

                snippet = content.replace("\n", " ")[:110]

                print(f"  #{rank} | Güven / İsabet Oranı: %{conf_pct:.2f} (Ham RRF: {raw_rrf:.6f} | Normalize: {norm_score:.4f})")
                print(f"     • Sıralama : [Dense: {dense_r} | Sparse: {sparse_r}]")
                print(f"     • Kategori : {cat.upper()} | Kayıt ID: {orig_id} | Başlık: {title}")
                print(f"     • Önizleme : {snippet}...")

            if is_top1_hit:
                top1_hits += 1
                print("  => SONUC: [BASARILI - Top-1 Eslesme]")
            elif is_top3_hit:
                top3_hits += 1
                print("  => SONUC: [BASARILI - Top-3 Eslesme]")
            else:
                print("  => SONUC: [UYARI - Hedef Eslesmedi]")

        print("\n" + "=" * 90)
        print("📊 HIBRIT ARAMA (RRF) PERFORMANS OZETI:")
        print(f"  • Toplam Test Sayısı : {total_tests}")
        print(f"  • Top-1 Isabet Oranı : %{(top1_hits / total_tests) * 100:.1f} ({top1_hits}/{total_tests})")
        print(f"  • Top-3 Isabet Oranı : %{((top1_hits + top3_hits) / total_tests) * 100:.1f} ({top1_hits + top3_hits}/{total_tests})")
        print("=" * 90 + "\n")


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------
def main():
    """CLI Execution entry point for Hybrid Search."""
    print("=" * 90)
    print("=== AKILLI SERVIS MASASI & SISTEM UZMANI - HIBRIT ARAMA (RRF) MOTORU ===")
    print("=" * 90)

    engine = HybridSearchEngine()
    engine.run_technical_accuracy_tests()


if __name__ == "__main__":
    main()
