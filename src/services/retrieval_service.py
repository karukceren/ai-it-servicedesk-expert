"""
RAG Retrieval & Context Generation Service Layer
=================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Provides an enterprise service layer wrapping Hybrid Search (Dense + Sparse RRF),
    domain-specific category filtering, and standardized LLM prompt context formatting.
"""

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add project root to sys.path for direct CLI execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.hybrid_search import HybridSearchEngine

# Ensure clean UTF-8 console output on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("RetrievalService")


class RetrievalService:
    """
    Service layer responsible for executing hybrid retrieval queries,
    applying domain category filters, and formatting retrieved knowledge
    chunks into structured context blocks for generative LLMs.
    """

    ALLOWED_CATEGORIES = {"windows_server", "oracle_db", "service_desk"}

    def __init__(self, engine: Optional[HybridSearchEngine] = None):
        """
        Initializes the RetrievalService with an underlying HybridSearchEngine.
        """
        self._engine = engine

    @property
    def engine(self) -> HybridSearchEngine:
        """Lazy initializes and returns the HybridSearchEngine instance."""
        if self._engine is None:
            self._engine = HybridSearchEngine()
        return self._engine

    @staticmethod
    def format_context_for_llm(
        retrieved_docs: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Formats retrieved knowledge base documents into a standardized,
        clean context string optimized for LLM comprehension, while extracting
        structured source metadata for citation tracking.

        Standard Format:
            ---
            [BELGE {index}]
            Kategori: {category} | Başlık: {title}
            İçerik: {content}
            ---

        Args:
            retrieved_docs (List[Dict[str, Any]]): List of raw documents returned from search.

        Returns:
            Tuple[str, List[Dict[str, Any]]]:
                - formatted_context (str): Formatted multi-document context block.
                - sources_metadata (List[dict]): Clean list of citation references.
        """
        if not retrieved_docs:
            return "(İlgili teknik doküman veya bilgi tabanı kaydı bulunamadı.)", []

        context_blocks: List[str] = []
        sources_metadata: List[Dict[str, Any]] = []

        max_possible_rrf = 2.0 / (60.0 + 1.0)

        for index, doc in enumerate(retrieved_docs, start=1):
            metadata = doc.get("metadata") or {}
            content = doc.get("content", "").strip()

            category = metadata.get("category", "genel").strip()
            title = metadata.get("title") or metadata.get("subcategory") or f"Doküman #{index}"
            chunk_id = metadata.get("chunk_id") or str(doc.get("id"))
            source = metadata.get("source", "knowledge_base")

            # Extract raw, normalized and percentage scores
            raw_rrf = round(float(doc.get("raw_rrf_score", doc.get("rrf_score", 0.0))), 6)
            norm_score = float(doc.get("normalized_score", min(1.0, round(raw_rrf / max_possible_rrf, 4))))
            conf_pct = float(doc.get("confidence_percentage", min(100.0, round(norm_score * 100.0, 2))))
            fmt_conf = doc.get("formatted_confidence", f"%{conf_pct:.2f}")

            dense_rank = doc.get("dense_rank")
            sparse_rank = doc.get("sparse_rank")

            # 1. Build standardized document block
            block = (
                f"---\n"
                f"[BELGE {index}]\n"
                f"Kategori: {category} | Başlık: {title}\n"
                f"İçerik:\n{content}\n"
                f"---"
            )
            context_blocks.append(block)

            # 2. Extract structured citation metadata
            sources_metadata.append({
                "index": index,
                "chunk_id": chunk_id,
                "title": title,
                "category": category,
                "source": source,
                "snippet": content[:240] + ("..." if len(content) > 240 else ""),
                "content": content,
                "raw_rrf_score": raw_rrf,
                "normalized_score": norm_score,
                "confidence_percentage": conf_pct,
                "formatted_confidence": fmt_conf,
                "dense_rank": dense_rank,
                "sparse_rank": sparse_rank
            })

        formatted_context = "\n\n".join(context_blocks)
        return formatted_context, sources_metadata

    CONFIDENCE_THRESHOLD = float(os.getenv("RAG_CONFIDENCE_THRESHOLD_RAW", "0.020"))

    def retrieve_context(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 4
    ) -> Dict[str, Any]:
        """
        Executes Hybrid Search (pgvector dense + TSVector sparse RRF) for a query,
        optionally filters by technical domain, and returns formatted context and metadata.
        If the top document score is below CONFIDENCE_THRESHOLD (0.020) or the query is
        out-of-domain, returns empty context with status="BELOW_THRESHOLD".

        Args:
            query (str): User natural language or technical query (e.g. 'How to check tablespace in Oracle').
            category (str, optional): Domain filter ('windows_server', 'oracle_db', 'service_desk').
            top_k (int): Maximum number of top-ranked chunks to return (default: 4).

        Returns:
            Dict[str, Any]: Structured dictionary containing:
                - `query`: Original search query string.
                - `category`: Applied domain category filter.
                - `top_k`: Requested limit.
                - `total_retrieved`: Number of matched chunks (0 if below threshold).
                - `status`: "SUCCESS" or "BELOW_THRESHOLD".
                - `formatted_context`: Standardized context string (empty if below threshold).
                - `sources_metadata`: List of citation references (empty if below threshold).
                - `raw_docs`: Original document items from search engine (empty if below threshold).
        """
        if not query or not query.strip():
            return {
                "query": "",
                "category": category,
                "top_k": top_k,
                "total_retrieved": 0,
                "status": "BELOW_THRESHOLD",
                "formatted_context": "",
                "sources_metadata": [],
                "raw_docs": []
            }

        clean_query = query.strip()

        # Check explicit out-of-domain keywords (food, weather, entertainment, chit-chat)
        irrelevant_keywords = [
            "öğle yemeği", "öğle yemeğinde", "yemekhane", "yemek menüsü", "menü", "yemekte ne var",
            "hava durumu", "yağmur", "futbol", "sinema", "şarkı", "tatil", "borsa", "dolar", "altın"
        ]
        q_lower = clean_query.lower()
        is_out_of_domain = any(kw in q_lower for kw in irrelevant_keywords)

        # Validate category filter
        clean_category = category.strip().lower() if category and category.strip() else None
        if clean_category and clean_category not in self.ALLOWED_CATEGORIES:
            logger.warning(f"Unknown category '{clean_category}' provided. Proceeding without filter.")
            clean_category = None

        logger.info(
            f"Retrieving context for query='{clean_query[:60]}...', category={clean_category}, top_k={top_k}"
        )

        # Execute Hybrid Search (Dense + Sparse RRF)
        raw_docs = self.engine.hybrid_search(
            query=clean_query,
            top_k=top_k,
            category=clean_category
        )

        # Confidence Threshold Check (Raw RRF >= 0.020)
        top_raw_score = float(raw_docs[0].get("raw_rrf_score", raw_docs[0].get("rrf_score", 0.0))) if raw_docs else 0.0

        if is_out_of_domain or not raw_docs or top_raw_score < self.CONFIDENCE_THRESHOLD:
            logger.warning(
                f"Query '{clean_query[:40]}...' matches below threshold ({top_raw_score:.6f} < {self.CONFIDENCE_THRESHOLD}) "
                f"or is out-of-domain. Returning empty context with BELOW_THRESHOLD status."
            )
            return {
                "query": clean_query,
                "category": clean_category,
                "top_k": top_k,
                "total_retrieved": 0,
                "status": "BELOW_THRESHOLD",
                "formatted_context": "",
                "sources_metadata": [],
                "raw_docs": []
            }

        # Format context and extract citation metadata for high-confidence documents
        formatted_context, sources_metadata = self.format_context_for_llm(raw_docs)

        logger.info(f"Successfully retrieved and formatted {len(raw_docs)} chunks (Top Score: {top_raw_score:.6f}) for LLM context.")

        return {
            "query": clean_query,
            "category": clean_category,
            "top_k": top_k,
            "total_retrieved": len(raw_docs),
            "status": "SUCCESS",
            "formatted_context": formatted_context,
            "sources_metadata": sources_metadata,
            "raw_docs": raw_docs
        }


# Singleton service instance for application-wide dependency injection
retrieval_service = RetrievalService()


# ---------------------------------------------------------------------------
# Direct CLI Test / Demonstration Execution
# ---------------------------------------------------------------------------
def main():
    """CLI demonstration and verification test."""
    print("=" * 80)
    print("=== RAG RETRIEVAL SERVICE - LLM BAGLAM (CONTEXT) URETIM TESTI ===")
    print("=" * 80)

    sample_query = "How to check tablespace in Oracle"
    print(f"\n🔍 Test Sorgusu: \"{sample_query}\" (Kategori: oracle_db, Top-K: 3)")
    print("-" * 80)

    result = retrieval_service.retrieve_context(
        query=sample_query,
        category="oracle_db",
        top_k=3
    )

    print("\n📄 LLM ICIN URETILEN STANDART BAGLAM METNI (FORMATTED CONTEXT):")
    print("-" * 80)
    print(result["formatted_context"])
    print("-" * 80)

    print("\n🏷️ ALINAN KAYNAK METADATALARI (SOURCES METADATA):")
    for meta in result["sources_metadata"]:
        print(
            f"  • [Belge #{meta['index']}] Güven / İsabet Oranı: {meta['formatted_confidence']} "
            f"(Normalize: {meta['normalized_score']:.4f} | Ham RRF: {meta['raw_rrf_score']:.6f})"
        )
        print(f"    - ID: {meta['chunk_id'][:20]}... | Kategori: {meta['category'].upper()} | Başlık: {meta['title']}")

    print("\n" + "=" * 80)
    print("✅ RETRIEVAL SERVICE CONTEXT GENERATION BASARIYLA TAMAMLANDI!")
    print("=" * 80)


if __name__ == "__main__":
    main()
