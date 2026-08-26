"""
Unit Tests for Domain-Specific System Prompts & Anti-Hallucination Guardrails
=============================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import pytest
from src.core.prompts import (
    PromptMode,
    BASE_GUARDRAILS,
    SERVICE_DESK_PROMPT,
    WINDOWS_SERVER_PROMPT,
    ORACLE_DB_PROMPT,
    GENERAL_SYSTEM_PROMPT,
    get_system_prompt_for_mode,
    build_prompt_messages,
)


class TestBaseGuardrails:
    """Verifies that mandatory guardrails, safety rules, and anti-hallucination phrases are intact."""

    def test_anti_hallucination_mandatory_phrase(self):
        """The standard disclaimer must be explicitly present in BASE_GUARDRAILS."""
        expected_phrase = "Bu konu mevcut bilgi tabanımda yer almamaktadır, lütfen sistem yöneticinize veya ilgili teknik birime danışınız."
        assert expected_phrase in BASE_GUARDRAILS

    def test_markdown_code_formatting_rules(self):
        """Must require markdown code blocks with language tags."""
        assert "```sql" in BASE_GUARDRAILS
        assert "```powershell" in BASE_GUARDRAILS
        assert "Markdown kod blokları" in BASE_GUARDRAILS

    def test_strict_context_constraint(self):
        """Must forbid generating unsubstantiated assumptions."""
        assert "YALNIZCA" in BASE_GUARDRAILS
        assert "BAĞLAM DOKÜMANLARI" in BASE_GUARDRAILS
        assert "ASLA tahmin yürütme" in BASE_GUARDRAILS


class TestDomainPrompts:
    """Verifies domain-specific prompt definitions and expertise requirements."""

    def test_service_desk_prompt_content(self):
        """Service Desk prompt must specify L1/L2 troubleshooting, ticketing, and user friendliness."""
        assert "Servis Masası" in SERVICE_DESK_PROMPT
        assert "L1/L2" in SERVICE_DESK_PROMPT
        assert "arıza giderme" in SERVICE_DESK_PROMPT
        assert "Bilet (ticket)" in SERVICE_DESK_PROMPT

    def test_windows_server_prompt_content(self):
        """Windows Server prompt must specify AD, GPO, PowerShell, IIS, and Event Viewer."""
        assert "Windows Sistem ve Altyapı Mühendisisin" in WINDOWS_SERVER_PROMPT
        assert "Active Directory" in WINDOWS_SERVER_PROMPT
        assert "PowerShell" in WINDOWS_SERVER_PROMPT
        assert "Event Viewer" in WINDOWS_SERVER_PROMPT

    def test_oracle_db_prompt_content(self):
        """Oracle DB prompt must specify DBA role, Tablespace, ORA codes, RMAN, and SQL."""
        assert "Oracle Veritabanı Yöneticisisin" in ORACLE_DB_PROMPT
        assert "Tablespace" in ORACLE_DB_PROMPT
        assert "ORA-" in ORACLE_DB_PROMPT
        assert "RMAN" in ORACLE_DB_PROMPT

    def test_get_system_prompt_for_mode_routing(self):
        """get_system_prompt_for_mode must route correctly and append BASE_GUARDRAILS."""
        # Service desk mode
        sd_prompt = get_system_prompt_for_mode("service_desk")
        assert "Servis Masası" in sd_prompt
        assert BASE_GUARDRAILS in sd_prompt

        # Windows server mode
        win_prompt = get_system_prompt_for_mode("windows_server")
        assert "Windows Sistem" in win_prompt
        assert BASE_GUARDRAILS in win_prompt

        # Oracle DB mode
        ora_prompt = get_system_prompt_for_mode("oracle_db")
        assert "Oracle Veritabanı" in ora_prompt
        assert BASE_GUARDRAILS in ora_prompt

        # General mode
        gen_prompt = get_system_prompt_for_mode("general")
        assert "Akıllı Servis Masası ve Sistem Uzmanı" in gen_prompt
        assert BASE_GUARDRAILS in gen_prompt

        # Unknown mode fallback to general
        fallback_prompt = get_system_prompt_for_mode("invalid_mode_xyz")
        assert "Akıllı Servis Masası ve Sistem Uzmanı" in fallback_prompt
        assert BASE_GUARDRAILS in fallback_prompt


class TestBuildPromptMessages:
    """Tests the message sequence builder (OpenAI chat format compiler)."""

    def test_build_messages_single_turn(self):
        """Should create a list with exactly 2 items: system and user message."""
        query = "How to restart Print Spooler?"
        context = "[BELGE 1] net stop spooler; net start spooler"
        messages = build_prompt_messages(
            query=query,
            context=context,
            mode="service_desk"
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "Servis Masası" in messages[0]["content"]
        assert "Bu konu mevcut bilgi tabanımda yer almamaktadır" in messages[0]["content"]

        assert messages[1]["role"] == "user"
        assert query in messages[1]["content"]
        assert context in messages[1]["content"]

    def test_build_messages_with_conversation_history(self):
        """Should insert past conversation turns between system and current user message."""
        history = [
            {"role": "user", "content": "I have an issue with VPN."},
            {"role": "assistant", "content": "What error code are you seeing?"},
            {"role": "user", "content": "It says Certificate Validation Failed."}
        ]
        query = "How do I fix the certificate?"
        context = "[BELGE 1] Use certmgr.msc to remove expired root CA."

        messages = build_prompt_messages(
            query=query,
            context=context,
            mode="service_desk",
            conversation_history=history,
            max_history_turns=5
        )

        assert len(messages) == 1 + len(history) + 1  # 5 messages total
        assert messages[0]["role"] == "system"
        assert messages[1] == history[0]
        assert messages[2] == history[1]
        assert messages[3] == history[2]
        assert messages[4]["role"] == "user"
        assert query in messages[4]["content"]

    def test_build_messages_history_truncation(self):
        """Should truncate past history turns to max_history_turns."""
        long_history = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(10)
        ]
        messages = build_prompt_messages(
            query="Latest query",
            context="Some context",
            mode="windows_server",
            conversation_history=long_history,
            max_history_turns=3
        )

        # 1 system + 3 history turns + 1 current user = 5 messages
        assert len(messages) == 5
        assert messages[1]["content"] == "Message 7"
        assert messages[2]["content"] == "Message 8"
        assert messages[3]["content"] == "Message 9"

    def test_build_messages_empty_context_fallback(self):
        """Empty context should trigger fallback notice in the user prompt."""
        messages = build_prompt_messages(
            query="Unknown technical issue",
            context="",
            mode="general"
        )
        assert len(messages) == 2
        assert "bulunamadı" in messages[1]["content"].lower()

    def test_build_messages_empty_query_fallback(self):
        """Empty query should trigger fallback notice."""
        messages = build_prompt_messages(
            query="   ",
            context="Some context",
            mode="oracle_db"
        )
        assert len(messages) == 2
        assert "(Boş soru)" in messages[1]["content"]
