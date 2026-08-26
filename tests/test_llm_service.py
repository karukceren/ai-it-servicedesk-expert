"""
Unit & Integration Tests for LLM Service (GPT-4o-mini & Streaming)
===================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import sys
import pytest
import asyncio
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure clean UTF-8 console output on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.services.llm_service import LLMService, llm_service


@pytest.mark.asyncio
class TestLLMServiceResponses:
    """Asynchronous test suite verifying single-turn and streaming LLM responses."""

    async def test_windows_server_scenario(self):
        """Should generate accurate Windows Server PowerShell response with sources metadata."""
        query = "PowerShell Search-ADAccount ve Unlock-ADAccount ile hesap kilidi nasıl açılır?"
        result = await llm_service.generate_response(
            query=query,
            mode="windows_server"
        )

        assert result["query"] == query
        assert result["mode"] == "windows_server"
        assert len(result["response"]) > 20
        assert len(result["sources_metadata"]) >= 1
        assert "usage" in result
        assert result["usage"]["prompt_tokens"] > 0

        # Check content contains PowerShell keywords or code block
        response_lower = result["response"].lower()
        assert "unlock-adaccount" in response_lower or "search-adaccount" in response_lower or "powershell" in response_lower

    async def test_oracle_db_scenario(self):
        """Should generate accurate Oracle DB tablespace response with SQL script."""
        query = "ORA-01653 unable to extend table hatası ve tablespace datafile büyütme"
        result = await llm_service.generate_response(
            query=query,
            mode="oracle_db"
        )

        assert result["query"] == query
        assert result["mode"] == "oracle_db"
        assert len(result["response"]) > 20
        assert len(result["sources_metadata"]) >= 1

        response_lower = result["response"].lower()
        assert "ora-01653" in response_lower or "tablespace" in response_lower or "datafile" in response_lower

    async def test_hallucination_out_of_domain_scenario(self):
        """Out of domain question should trigger the strict anti-hallucination guardrail phrase."""
        query = "Bugün şirket yemekhanesinde hangi yemekler var ve öğle menüsü nedir?"
        result = await llm_service.generate_response(
            query=query,
            mode="service_desk"
        )

        assert result["query"] == query
        assert "bilgi tabanımızda yer almamaktadır" in result["response"] or "bilgi tabanımda yer almamaktadır" in result["response"]

    async def test_streaming_generation(self):
        """generate_response_stream must yield token chunks asynchronously."""
        query = "Kilitli Active Directory hesabı nasıl açılır?"
        tokens = []
        async for chunk in llm_service.generate_response_stream(query=query, mode="windows_server"):
            tokens.append(chunk)

        assert len(tokens) >= 1
        full_streamed_text = "".join(tokens)
        assert len(full_streamed_text) > 10


# ===========================================================================
# CLI Visual Demonstration Runner
# ===========================================================================
async def run_visual_demo():
    """Runs 3 live test scenarios and prints formatted LLM responses to console."""
    print("=" * 95)
    print("🤖 LLM SERVİS KATMANI (GPT-4o-mini & RAG) - CANLI CEVAP ÜRETİM TESTİ")
    print("=" * 95)

    test_scenarios = [
        {
            "id": 1,
            "title": "Windows Server Uzmanlık Modu (PowerShell & Active Directory)",
            "mode": "windows_server",
            "query": "PowerShell ile kilitli Active Directory kullanıcılarını bulup kilidini nasıl açabilirim?",
        },
        {
            "id": 2,
            "title": "Oracle DBA Uzmanlık Modu (Tablespace Doluluk ve ORA-01653)",
            "mode": "oracle_db",
            "query": "ORA-01653: unable to extend table hatası aldım. USERS tablespace'ine nasıl yeni datafile eklerim?",
        },
        {
            "id": 3,
            "title": "Anti-Hallucination Guardrails Testi (Bilgi Tabanı Dışı Soru)",
            "mode": "service_desk",
            "query": "Bugün şirket yemekhanesinde hangi yemekler var ve öğle menüsü nedir?",
        }
    ]

    for sc in test_scenarios:
        print(f"\n[{sc['id']}/3] {sc['title']}")
        print(f"     Mod: [{sc['mode'].upper()}] | Soru: \"{sc['query']}\"")
        print("-" * 95)

        result = await llm_service.generate_response(
            query=sc["query"],
            mode=sc["mode"]
        )

        print("\n📄 [LLM ÜRETTİĞİ CEVAP]:")
        print(result["response"])

        print("\n🏷️ [RAG REFERANS KAYNAKLARI (METADATA)]:")
        if result["sources_metadata"]:
            for meta in result["sources_metadata"][:2]:
                print(
                    f"  • [Belge #{meta['index']}] Güven: {meta['formatted_confidence']} "
                    f"| ID: {meta['chunk_id'][:18]}... | Kategori: {meta['category'].upper()} | Başlık: {meta['title']}"
                )
        else:
            print("  • (İlgili referans doküman bulunamadı.)")

        print(f"\n⏱️ Gecikme: {result['latency_ms']} ms | Model: {result['model']} | Token Kullanımı: {result['usage']}")
        print("-" * 95)

    print("\n" + "=" * 95)
    print("✅ LLM SERVİS KATMANI TESTLERİ BAŞARIYLA TAMAMLANDI!")
    print("=" * 95)


def main():
    """Main CLI execution."""
    asyncio.run(run_visual_demo())


if __name__ == "__main__":
    main()
