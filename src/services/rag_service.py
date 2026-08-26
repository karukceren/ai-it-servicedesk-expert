"""
End-to-End RAG Pipeline Orchestrator with Confidence Guardrails & Fallback
==========================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Orchestrates the entire RAG pipeline from Hybrid Search retrieval,
    strict confidence thresholding (anti-hallucination / token-saving gate),
    dynamic prompt compiling, to LLM generation (single-turn & streaming).
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure clean UTF-8 console output on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.core.prompts import build_prompt_messages, PromptMode
from src.services.retrieval_service import retrieval_service, RetrievalService
from src.services.llm_service import llm_service, LLMService

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("RAGService")

# ===========================================================================
# Standard Fallback Constants
# ===========================================================================
DEFAULT_CONFIDENCE_THRESHOLD = float(os.getenv("RAG_CONFIDENCE_THRESHOLD", "0.25"))

STANDARD_FALLBACK_MESSAGE = (
    "Sorduğunuz konu teknik bilgi tabanımızda yer almamaktadır. Yalnızca IT Destek, Windows Server ve Oracle DB konularında yardımcı olabilirim. "
    "Lütfen talebinizi BT Servis Masası'na (IT Helpdesk) bilet olarak iletiniz."
)


class RAGService:
    """
    High-level orchestrator for Retrieval-Augmented Generation (RAG)
    with strict confidence gating, hallucination prevention, and token-saving fallback.
    """

    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        retriever: Optional[RetrievalService] = None,
        llm: Optional[LLMService] = None
    ):
        self.confidence_threshold = confidence_threshold
        self.retriever = retriever or retrieval_service
        self.llm = llm or llm_service

    def _get_domain_category_for_mode(self, mode: str) -> Optional[str]:
        """Maps user mode to knowledge base database category filter."""
        mapping = {
            PromptMode.SERVICE_DESK.value: "service_desk",
            PromptMode.WINDOWS_SERVER.value: "windows_server",
            PromptMode.ORACLE_DB.value: "oracle_db"
        }
        return mapping.get(mode.lower().strip()) if mode else None

    async def execute_rag(
        self,
        query: str,
        mode: str = "general",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 4
    ) -> Dict[str, Any]:
        """
        Executes end-to-end RAG pipeline:
        1. Retrieves context chunks using Hybrid Search (RRF).
        2. Evaluates the highest normalized confidence score against threshold.
        3. If score < threshold (or out-of-domain query):
           - Returns instant safe fallback message (Status: FALLBACK_TRIGGERED).
           - Consumes 0 LLM tokens.
        4. If score >= threshold:
           - Calls LLM with RAG context and domain prompt (Status: SUCCESS).

        Args:
            query (str): User question or problem scenario.
            mode (str): Domain expertise mode.
            conversation_history (list, optional): Previous chat messages.
            top_k (int): Number of chunks to retrieve.

        Returns:
            Dict[str, Any]: Execution result containing response, status, confidence, sources, and usage.
        """
        t0 = time.perf_counter()
        logger.info(f"Executing RAG pipeline for query='{query[:45]}...', mode={mode}")

        # 1. Retrieve Knowledge Base Context with Gating
        category_filter = self._get_domain_category_for_mode(mode)
        context_data = self.retriever.retrieve_context(
            query=query,
            category=category_filter,
            top_k=top_k
        )

        sources = context_data.get("sources_metadata", [])
        retrieval_status = context_data.get("status", "SUCCESS")
        top_confidence = sources[0].get("normalized_score", 0.0) if sources else 0.0
        top_confidence_pct = sources[0].get("formatted_confidence", "%0.00") if sources else "%0.00"

        # 2. Confidence Gating & Fallback Mechanism (Zero LLM Tokens)
        if retrieval_status == "BELOW_THRESHOLD" or not sources or top_confidence < self.confidence_threshold:
            logger.warning(
                f"Retrieval status is '{retrieval_status}' (confidence: {top_confidence:.4f}). "
                f"Triggering instant safe fallback without calling LLM."
            )
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return {
                "query": query,
                "mode": mode,
                "status": "FALLBACK_TRIGGERED",
                "fallback": True,
                "response": STANDARD_FALLBACK_MESSAGE,
                "confidence_score": top_confidence,
                "formatted_confidence": top_confidence_pct,
                "sources_metadata": [],
                "formatted_context": "",
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                },
                "latency_ms": elapsed_ms
            }

        # 3. High Confidence -> Proceed to LLM Generation
        llm_result = await self.llm.generate_response(
            query=query,
            mode=mode,
            conversation_history=conversation_history,
            top_k=top_k
        )

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "query": query,
            "mode": mode,
            "status": "SUCCESS",
            "fallback": False,
            "response": llm_result["response"],
            "confidence_score": top_confidence,
            "formatted_confidence": top_confidence_pct,
            "sources_metadata": sources,
            "formatted_context": context_data["formatted_context"],
            "usage": llm_result["usage"],
            "model": llm_result.get("model", "gpt-4o-mini"),
            "latency_ms": elapsed_ms
        }

    async def execute_rag_stream(
        self,
        query: str,
        mode: str = "general",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 4
    ) -> AsyncGenerator[str, None]:
        """
        Streaming execution of RAG pipeline. If confidence is below threshold,
        yields the standard fallback message immediately.
        """
        irrelevant_keywords = ["hava durumu", "yemekhane", "öğle menü", "yemek menüsü", "sinema", "şarkı", "tatil", "futbol"]
        q_lower = query.lower()
        is_explicitly_irrelevant = any(kw in q_lower for kw in irrelevant_keywords)

        category_filter = self._get_domain_category_for_mode(mode)
        context_data = self.retriever.retrieve_context(
            query=query,
            category=category_filter,
            top_k=top_k
        )

        sources = context_data.get("sources_metadata", [])
        retrieval_status = context_data.get("status", "SUCCESS")
        top_confidence = sources[0].get("normalized_score", 0.0) if sources else 0.0

        if retrieval_status == "BELOW_THRESHOLD" or not sources or top_confidence < self.confidence_threshold:
            words = STANDARD_FALLBACK_MESSAGE.split(" ")
            for w in words:
                yield w + " "
            return

        async for chunk in self.llm.generate_response_stream(
            query=query,
            mode=mode,
            conversation_history=conversation_history,
            top_k=top_k
        ):
            yield chunk


# Global singleton instance
rag_service = RAGService()
