"""
Unit & Integration Tests for Retrieval Service Context Generation
==================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import pytest
from src.services.retrieval_service import RetrievalService, retrieval_service


class TestContextFormatting:
    """Unit tests for format_context_for_llm function."""

    def test_format_context_with_documents(self):
        """Standard documents must format into the required LLM context template."""
        mock_docs = [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "content": "SELECT tablespace_name, bytes FROM dba_data_files;",
                "metadata": {
                    "category": "oracle_db",
                    "title": "Oracle Tablespace Query",
                    "chunk_id": "ORA-CHK-01",
                    "source": "oracle_qa.json"
                },
                "rrf_score": 0.0325,
                "dense_rank": 1,
                "sparse_rank": 2
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "content": "ALTER TABLESPACE USERS ADD DATAFILE 'u02.dbf' SIZE 100M;",
                "metadata": {
                    "category": "oracle_db",
                    "title": "Extend Tablespace",
                    "chunk_id": "ORA-EXT-02",
                    "source": "oracle_qa.json"
                },
                "rrf_score": 0.0310,
                "dense_rank": 2,
                "sparse_rank": 3
            }
        ]

        formatted_context, sources = RetrievalService.format_context_for_llm(mock_docs)

        # Assert format structure
        assert "[BELGE 1]" in formatted_context
        assert "Kategori: oracle_db | Başlık: Oracle Tablespace Query" in formatted_context
        assert "SELECT tablespace_name, bytes FROM dba_data_files;" in formatted_context
        assert "[BELGE 2]" in formatted_context
        assert "Kategori: oracle_db | Başlık: Extend Tablespace" in formatted_context
        assert "---" in formatted_context

        # Assert sources metadata
        assert len(sources) == 2
        assert sources[0]["chunk_id"] == "ORA-CHK-01"
        assert sources[0]["category"] == "oracle_db"
        assert sources[0]["raw_rrf_score"] == 0.0325
        assert 0.0 <= sources[0]["normalized_score"] <= 1.0
        assert 0.0 <= sources[0]["confidence_percentage"] <= 100.0
        assert "%" in sources[0]["formatted_confidence"]
        assert sources[0]["dense_rank"] == 1
        assert sources[0]["sparse_rank"] == 2

    def test_format_context_empty_list(self):
        """Empty document list should return fallback message and empty metadata."""
        formatted_context, sources = RetrievalService.format_context_for_llm([])
        assert "kaydı bulunamadı" in formatted_context
        assert sources == []


class TestLiveRetrievalService:
    """Integration tests executing live Hybrid Search and Context generation against PostgreSQL."""

    def test_retrieve_context_oracle_tablespace(self):
        """Querying tablespace in Oracle should return relevant Oracle DB chunks."""
        result = retrieval_service.retrieve_context(
            query="How to check tablespace in Oracle",
            category="oracle_db",
            top_k=3
        )

        assert result["query"] == "How to check tablespace in Oracle"
        assert result["category"] == "oracle_db"
        assert result["top_k"] == 3
        assert result["total_retrieved"] >= 1

        # Formatted Context asserts
        assert "[BELGE 1]" in result["formatted_context"]
        assert "oracle_db" in result["formatted_context"].lower()

        # Check content keywords
        context_lower = result["formatted_context"].lower()
        assert "tablespace" in context_lower or "dba_tablespace" in context_lower or "oracle" in context_lower

        # Check metadata list
        assert len(result["sources_metadata"]) >= 1
        first_source = result["sources_metadata"][0]
        assert "chunk_id" in first_source
        assert "category" in first_source
        assert first_source["category"] == "oracle_db"
        assert first_source["raw_rrf_score"] > 0
        assert 0.0 < first_source["normalized_score"] <= 1.0
        assert 0.0 < first_source["confidence_percentage"] <= 100.0
        assert "%" in first_source["formatted_confidence"]

    def test_retrieve_context_windows_server_filtering(self):
        """Filtering by windows_server must only return windows_server chunks."""
        result = retrieval_service.retrieve_context(
            query="Event ID 4625 Failed Logon Security Log",
            category="windows_server",
            top_k=3
        )

        assert result["total_retrieved"] >= 1
        for meta in result["sources_metadata"]:
            assert meta["category"] == "windows_server"

        assert "4625" in result["formatted_context"] or "logon" in result["formatted_context"].lower()

    def test_retrieve_context_empty_query(self):
        """Empty query must return safe empty payload with BELOW_THRESHOLD status without crashing."""
        result = retrieval_service.retrieve_context(query="", top_k=4)
        assert result["total_retrieved"] == 0
        assert result["sources_metadata"] == []
        assert result["status"] == "BELOW_THRESHOLD"
        assert result["formatted_context"] == ""

    def test_retrieve_context_below_threshold_irrelevant_query(self):
        """Out-of-domain query (e.g. food, cafeteria) must return BELOW_THRESHOLD with empty docs."""
        result = retrieval_service.retrieve_context(query="Öğle yemeğinde ne var?", top_k=4)
        assert result["total_retrieved"] == 0
        assert result["sources_metadata"] == []
        assert result["status"] == "BELOW_THRESHOLD"
        assert result["formatted_context"] == ""


if __name__ == "__main__":
    pytest.main(["-v", __file__])
