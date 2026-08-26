"""
Domain-Specific System Prompts & Anti-Hallucination Guardrails Module
====================================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Provides robust, domain-tailored system prompts for Service Desk,
    Windows Server Engineering, and Oracle DBA roles with strict
    anti-hallucination guardrails, markdown code formatting constraints,
    and dynamic message sequence compilation.
"""

import sys
from enum import Enum
from typing import List, Dict, Any, Optional

# Ensure clean UTF-8 console output on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class PromptMode(str, Enum):
    """Supported domain expertise modes for system prompts."""
    GENERAL = "general"
    SERVICE_DESK = "service_desk"
    WINDOWS_SERVER = "windows_server"
    ORACLE_DB = "oracle_db"


# ===========================================================================
# 1. Base Anti-Hallucination & Operational Guardrails (BASE_GUARDRAILS)
# ===========================================================================
BASE_GUARDRAILS = """
=== TEMEL GÜVENLİK, DOĞRULUK VE DAVRANIŞ KURALLARI (GUARDRAILS) ===
1. KESİN KURAL (YALNIZCA BAĞLAM KULLANIMI):
   - Cevaplarını YALNIZCA sana sağlanan "BAĞLAM DOKÜMANLARI" içeriğindeki doğrulanmış teknik verilere dayandır.
   - Bağlamda bulunmayan varsayımsal bilgileri veya doğrulanmamış şirket içi prosedürleri kesinlikle kendin üretme.

2. HALÜSİNASYON VE ALAKASIZ BAĞLAM ENGELİ (ANTI-HALLUCINATION PROTOCOL):
   - DİKKAT: Sağlanan bağlam dokümanları kullanıcının sorusuyla doğrudan ilgili değilse veya bağlam boşsa, kesinlikle bağlamdaki metinleri/biletleri kullanıcıya sıralama. Doğrudan 'Sorduğunuz konu teknik bilgi tabanımızda yer almamaktadır. Yalnızca IT Destek, Windows Server ve Oracle DB konularında yardımcı olabilirim.' şeklinde kısa ve net bir yanıt ver.
   - Eğer kullanıcının sorusunun cevabı sağlanan bağlam metninde net ve açık bir şekilde yer almıyorsa ASLA tahmin yürütme veya bilgi uydurma; "Bu konu mevcut bilgi tabanımda yer almamaktadır, lütfen sistem yöneticinize veya ilgili teknik birime danışınız." şeklinde açıkça belirt.

3. KOD VE SCRIPT FORMATI:
   - Tüm teknik komutları, SQL sorgularını ve betikleri (PowerShell, SQL, Bash, CMD) KESİNLİKLE uygun dil etiketiyle Markdown kod blokları (```sql, ```powershell, ```bash, ```cmd) içerisinde ver.
   - Kod bloklarının ardından uygulanan parametrelerin ve bayrakların (flags) ne işe yaradığını kısaca açıkla.

4. DİL, ÜSLUP VE PROFESYONELLİK:
   - Profesyonel, net, doğrudan çözüme odaklı Türkçe teknik dil kullan.
   - Adımları mantıksal ve numaralandırılmış sıralamayla (1., 2., 3.) sun.

5. KRİTİK İŞLEM VE GÜVENLİK UYARISI:
   - Sistem kesintisi, veri kaybı veya servis durmasına neden olabilecek kritik komutlarda (örn: veritabanı oturumu sonlandırma, servis kapatma, disk temizliği) öncesinde dikkat uyarısı ver.
""".strip()


# ===========================================================================
# 2. Domain-Specific System Prompts
# ===========================================================================
SERVICE_DESK_PROMPT = """
Sen kurumsal bir organizasyonun Kıdemli IT Servis Masası (Service Desk L1/L2) Destek Uzmanısın.
Görevin; son kullanıcılardan ve çalışanlardan gelen VPN erişimi, parola/hesap kilitlenmeleri, Outlook senkronizasyon sorunları, yazıcı kuyruğu kilitlenmeleri (Spooler), BitLocker kurtarma anahtarı talepleri, disk alanı yetersizlikleri ve donanım/yazılım arızalarını en hızlı ve etkili şekilde çözmektir.

Uzmanlık Yaklaşımın:
- Kullanıcı dostu, nazik ve anlaşılır bir iletişim kur.
- Kullanıcının teknik bilgisi olmasa dahi kolayca uygulayabileceği adım adım arıza giderme (troubleshooting) yönergeleri sağla.
- Bilet (ticket) kaydı gerektiren durumlarda problem kategorisi ve öncelik seviyesi hakkında rehberlik et.
""".strip()

WINDOWS_SERVER_PROMPT = """
Sen kurumsal seviyede görev yapan Kıdemli Windows Sistem ve Altyapı Mühendisisin (Senior Windows Systems Engineer).
Görevin; Windows Server (2016/2019/2022), Active Directory Domain Services (AD DS), Group Policy (GPO), DNS/DHCP altyapısı, IIS Web Server (HTTP 500.19, URL Rewrite), Event Viewer (Event ID 4625 vb.) güvenlik log analizi ve PowerShell otomasyonu konularında derin teknik çözümler üretmektir.

Uzmanlık Yaklaşımın:
- Sistem yöneticilerine doğrudan uygulanabilir, test edilmiş PowerShell cmdlet'leri ve yönetimsel komutlar sağla.
- Problemlerin kök neden analizini (Root Cause Analysis) açıklayarak kalıcı çözüm sun.
- Güvenlik ve en iyi uygulama (Best Practice) standartlarına uygun yapılandırmalar öner.
""".strip()

ORACLE_DB_PROMPT = """
Sen kurumsal seviyede görev yapan Kıdemli Oracle Veritabanı Yöneticisisin (Senior Oracle DBA).
Görevin; Oracle Database (12c/19c/21c), Tablespace ve Datafile yönetimi (ORA-01653), Kilitlenmeler ve Blocking Session analizi (v$session, ORA-00060), RMAN yedekleme ve kurtarma stratejileri, Index Rebuild (UNUSABLE indexler), SQL Performans analizi ve Explain Plan optimizasyonu konularında kesin ve güvenilir DBA çözümleri sunmaktır.

Uzmanlık Yaklaşımın:
- SQL*Plus ve Oracle Data Dictionary (DBA_*, V$* view'ları) standartlarına uygun optimize edilmiş SQL scriptleri sun.
- Hata kodlarının (ORA-XXXXX) kesin teknik nedenini ve üretim ortamında güvenle çalıştırılacak kurtarma adımlarını belirt.
- Canlı sistemlerde kilitlenme oluşturmamak için Online (ör: `REBUILD ONLINE`) bakım pratiklerini tavsiye et.
""".strip()

GENERAL_SYSTEM_PROMPT = """
Sen kurumsal bir BT Departmanı için geliştirilmiş Akıllı Servis Masası ve Sistem Uzmanı Yapay Zeka Asistanısın.
Görevin; IT Servis Masası, Windows Server Altyapısı ve Oracle Veritabanı yönetimi alanlarında gelen teknik sorulara sağlanan bağlam doğrultusunda en doğru çözümleri sunmaktır.
""".strip()


# Prompt Registry Map
DOMAIN_PROMPTS: Dict[str, str] = {
    PromptMode.GENERAL.value: GENERAL_SYSTEM_PROMPT,
    PromptMode.SERVICE_DESK.value: SERVICE_DESK_PROMPT,
    PromptMode.WINDOWS_SERVER.value: WINDOWS_SERVER_PROMPT,
    PromptMode.ORACLE_DB.value: ORACLE_DB_PROMPT,
}


# ===========================================================================
# 3. Dynamic Message Sequence Compiler (build_prompt_messages)
# ===========================================================================
def get_system_prompt_for_mode(mode: str = "general") -> str:
    """
    Retrieves the combined system prompt and base guardrails for a given expertise mode.

    Args:
        mode (str): Expertise mode ('service_desk', 'windows_server', 'oracle_db', 'general').

    Returns:
        str: Assembled full system prompt text including guardrails.
    """
    normalized_mode = mode.lower().strip() if mode else PromptMode.GENERAL.value
    domain_prompt = DOMAIN_PROMPTS.get(normalized_mode, GENERAL_SYSTEM_PROMPT)

    full_system_prompt = (
        f"{domain_prompt}\n\n"
        f"{BASE_GUARDRAILS}"
    )
    return full_system_prompt


def build_prompt_messages(
    query: str,
    context: str,
    mode: str = "general",
    conversation_history: Optional[List[Dict[str, str]]] = None,
    max_history_turns: int = 5
) -> List[Dict[str, str]]:
    """
    Compiles standard OpenAI chat completion message format
    ([{"role": "system", "content": ...}, {"role": "user", "content": ...}])
    by combining domain-specific system instructions, anti-hallucination guardrails,
    trimmed conversation history, and the user's RAG-augmented query.

    Args:
        query (str): The current user query or technical question.
        context (str): Formatted RAG context documents retrieved from knowledge base.
        mode (str): Target domain mode ('service_desk', 'windows_server', 'oracle_db', 'general').
        conversation_history (list, optional): Previous chat messages for multi-turn context.
        max_history_turns (int): Maximum past message turns to include (default: 5).

    Returns:
        List[Dict[str, str]]: Sequence of formatted messages ready for LLM API invocation.
    """
    messages: List[Dict[str, str]] = []

    # 1. System Role Message with Domain Instructions & Guardrails
    system_content = get_system_prompt_for_mode(mode)
    messages.append({
        "role": "system",
        "content": system_content
    })

    # 2. Append Trimmed Multi-Turn Conversation History (if provided)
    if conversation_history:
        # Filter out any misplaced system messages from history and take last N
        clean_history = [
            {"role": msg.get("role", "user"), "content": msg.get("content", "").strip()}
            for msg in conversation_history
            if msg.get("role") in ("user", "assistant") and msg.get("content")
        ]
        trimmed_history = clean_history[-max_history_turns:]
        messages.extend(trimmed_history)

    # 3. Format Context and Current User Query
    clean_context = context.strip() if (context and context.strip()) else "(İlgili teknik doküman veya bilgi tabanı kaydı bulunamadı.)"
    clean_query = query.strip() if (query and query.strip()) else "(Boş soru)"

    user_prompt = (
        f"=== BAĞLAM DOKÜMANLARI (KAYNAKLAR) ===\n"
        f"{clean_context}\n\n"
        f"=== KULLANICI SORUSU ===\n"
        f"{clean_query}\n\n"
        f"Lütfen yukarıdaki bağlam dokümanlarına ve uzmanlık talimatlarına dayanarak soruyu yanıtla."
    )

    messages.append({
        "role": "user",
        "content": user_prompt
    })

    return messages


def main():
    """CLI demonstration of prompt compiling for different modes and scenarios."""
    import json

    print("=" * 95)
    print("🤖 AKILLI SERVİS MASASI & SİSTEM UZMANI - SYSTEM PROMPT & GUARDRAILS GÖSTERİMİ")
    print("=" * 95)

    scenarios = [
        {
            "title": "1. Windows Server Uzmanlık Modu (Active Directory Hesap Kilidi)",
            "mode": "windows_server",
            "query": "Kullanıcı 3 kez yanlış şifre girdi, hesabı kilitlendi. PowerShell ile nasıl açılır?",
            "context": (
                "---\n"
                "[BELGE 1]\n"
                "Kategori: windows_server | Başlık: Active Directory / GPO\n"
                "İçerik:\n"
                "```powershell\n"
                "# Kilitli kullanıcıyı bul ve kilidini aç\n"
                "Search-ADAccount -LockedOut | Select-Object Name, SamAccountName\n"
                "Unlock-ADAccount -Identity 'johndoe'\n"
                "```\n"
                "---"
            ),
            "history": [
                {"role": "user", "content": "Bir personel sisteme giriş yapamıyor."},
                {"role": "assistant", "content": "Kullanıcı adını ve aldığı hata mesajını öğrenebilir miyim?"}
            ]
        },
        {
            "title": "2. Oracle DBA Uzmanlık Modu (Tablespace Doluluk ve ORA-01653)",
            "mode": "oracle_db",
            "query": "ORA-01653 hatası alıyoruz, USERS tablespace dolmuş. Datafile nasıl büyütülür?",
            "context": (
                "---\n"
                "[BELGE 1]\n"
                "Kategori: oracle_db | Başlık: Tablespace Management\n"
                "İçerik:\n"
                "```sql\n"
                "ALTER DATABASE DATAFILE '/u01/app/oracle/oradata/ORCL/users01.dbf'\n"
                "AUTOEXTEND ON NEXT 100M MAXSIZE 10G;\n"
                "```\n"
                "---"
            ),
            "history": None
        },
        {
            "title": "3. Halüsinasyon Engeli Testi (Bilgi Tabanında Olmayan Soru)",
            "mode": "service_desk",
            "query": "Şirketin yemekhane menüsünü ve bugün hangi yemeğin olduğunu söyler misin?",
            "context": "(İlgili teknik doküman veya bilgi tabanı kaydı bulunamadı.)",
            "history": None
        }
    ]

    for sc in scenarios:
        print(f"\n{sc['title']}")
        print("-" * 95)
        msgs = build_prompt_messages(
            query=sc["query"],
            context=sc["context"],
            mode=sc["mode"],
            conversation_history=sc["history"]
        )

        print(f"🔹 Seçilen Mod: [{sc['mode'].upper()}] | Toplam Mesaj Sayısı: {len(msgs)}")
        print("\n📜 [SYSTEM PROMPT & GUARDRAILS]:")
        print(msgs[0]["content"][:320] + "...\n[... BASE_GUARDRAILS KURALLARI EKLENDİ ...]")

        if len(msgs) > 2:
            print("\n💬 [GEÇMİŞ KONUŞMA MESAJLARI]:")
            for h in msgs[1:-1]:
                print(f"  • {h['role'].upper()}: {h['content']}")

        print("\n📥 [DERLENEN USER MESAJI & RAG BAĞLAMI]:")
        print(msgs[-1]["content"])
        print("-" * 95)

    print("\n" + "=" * 95)
    print("✅ SYSTEM PROMPT VE GUARDRAILS MESAJ DERLEME TESTİ BAŞARIYLA TAMAMLANDI!")
    print("=" * 95)


if __name__ == "__main__":
    main()

