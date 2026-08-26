"""
Streamlit Web UI - Akıllı Servis Masası ve Sistem Uzmanı Chatbot
===============================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Modern, multi-mode, real-time streaming conversational AI interface.
    Features:
    - JWT Authentication & Registration Flow
    - Multi-Tenant Chat Session Management (+ New Session, List, Delete)
    - Domain Mode Selector (IT Service Desk, Windows Server, Oracle DB)
    - Real-Time SSE Token Streaming (Server-Sent Events) via FastAPI Backend
    - Advanced RAG Citation & Chunk Inspector (Expander, Snippets, Confidence %)
    - User Feedback Mechanism (Thumbs Up/Down, Comments, Toast Notifications)
    - Automated Audit Trail Logging (Query, Session, Feedback)
"""

import os
import json
import uuid
import time
import httpx
import pandas as pd
import streamlit as st
from typing import List, Dict, Any, Optional, Generator

# Backend API Configuration (Docker / Local Host)
BACKEND_URL = os.getenv("API_URL", os.getenv("BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")

# Page Configuration
st.set_page_config(
    page_title="Akıllı Servis Masası & Sistem Uzmanı Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Glassmorphic & Modern UI
CUSTOM_CSS = """
<style>
    /* Global Typography & Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Main Header Styling */
    .main-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 1.2rem 1.8rem;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .main-header h2 {
        color: #f8fafc;
        margin: 0;
        font-weight: 700;
        font-size: 1.5rem;
    }
    .main-header p {
        color: #94a3b8;
        margin: 0.2rem 0 0 0;
        font-size: 0.88rem;
    }

    /* Domain Badges */
    .badge {
        display: inline-block;
        padding: 0.3rem 0.75rem;
        font-size: 0.78rem;
        font-weight: 600;
        border-radius: 9999px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-service-desk {
        background-color: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    .badge-windows-server {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-oracle-db {
        background-color: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .badge-general {
        background-color: rgba(168, 85, 247, 0.15);
        color: #c084fc;
        border: 1px solid rgba(168, 85, 247, 0.3);
    }

    /* User Profile Card */
    .user-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 1rem;
    }

    /* Citation Card Box */
    .citation-card {
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.6rem;
        margin-bottom: 0.6rem;
        font-size: 0.88rem;
    }
    .citation-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        padding-bottom: 0.4rem;
    }
    .citation-score {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        padding: 0.2rem 0.5rem;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .citation-chunk-text {
        background: rgba(0, 0, 0, 0.25);
        padding: 0.6rem;
        border-left: 3px solid #38bdf8;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.82rem;
        color: #cbd5e1;
        white-space: pre-wrap;
        margin-top: 0.4rem;
    }

    /* Welcome Card */
    .welcome-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        margin-top: 2rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ===========================================================================
# 1. State Management & Initialization
# ===========================================================================
def init_session_state():
    """Initializes Streamlit session state keys."""
    if "token" not in st.session_state:
        st.session_state.token = None
    if "user" not in st.session_state:
        st.session_state.user = None
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    if "current_session_title" not in st.session_state:
        st.session_state.current_session_title = "Yeni Sohbet"
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_mode" not in st.session_state:
        st.session_state.selected_mode = "service_desk"
    if "sessions_list" not in st.session_state:
        st.session_state.sessions_list = []
    if "feedback_submitted" not in st.session_state:
        st.session_state.feedback_submitted = set()

    if "active_view" not in st.session_state:
        st.session_state.active_view = "chat"


init_session_state()


# ===========================================================================
# 2. Backend API Client Helper
# ===========================================================================
class APIClient:
    """Helper for asynchronous & synchronous communication with FastAPI backend."""

    @staticmethod
    def get_headers() -> Dict[str, str]:
        token = st.session_state.token
        return {"Authorization": f"Bearer {token}"} if token else {}

    @staticmethod
    def check_health() -> bool:
        try:
            r = httpx.get(f"{BACKEND_URL}/api/health", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def login(email: str, password: str) -> Dict[str, Any]:
        with httpx.Client(base_url=BACKEND_URL, timeout=8.0) as client:
            resp = client.post("/api/auth/login", json={"email": email, "password": password})
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            detail = resp.json().get("detail", "Giriş başarısız.")
            return {"success": False, "error": detail}

    @staticmethod
    def register(email: str, password: str, role: str = "user") -> Dict[str, Any]:
        with httpx.Client(base_url=BACKEND_URL, timeout=8.0) as client:
            resp = client.post("/api/auth/register", json={"email": email, "password": password, "role": role})
            if resp.status_code == 201:
                return {"success": True, "data": resp.json()}
            detail = resp.json().get("detail", "Kayıt başarısız.")
            return {"success": False, "error": detail}

    @classmethod
    def fetch_sessions(cls) -> List[Dict[str, Any]]:
        try:
            with httpx.Client(base_url=BACKEND_URL, headers=cls.get_headers(), timeout=5.0) as client:
                resp = client.get("/api/chat/sessions")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            st.error(f"Oturumlar çekilemedi: {e}")
        return []

    @classmethod
    def create_session(cls, title: str = "Yeni Sohbet") -> Optional[Dict[str, Any]]:
        try:
            with httpx.Client(base_url=BACKEND_URL, headers=cls.get_headers(), timeout=5.0) as client:
                resp = client.post("/api/chat/sessions", json={"title": title})
                if resp.status_code == 201:
                    return resp.json()
        except Exception as e:
            st.error(f"Yeni oturum açılamadı: {e}")
        return None

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        try:
            with httpx.Client(base_url=BACKEND_URL, headers=cls.get_headers(), timeout=5.0) as client:
                resp = client.delete(f"/api/chat/sessions/{session_id}")
                return resp.status_code == 200
        except Exception as e:
            st.error(f"Oturum silinemedi: {e}")
        return False

    @classmethod
    def fetch_history(cls, session_id: str) -> List[Dict[str, Any]]:
        try:
            with httpx.Client(base_url=BACKEND_URL, headers=cls.get_headers(), timeout=6.0) as client:
                resp = client.get(f"/api/chat/sessions/{session_id}/history")
                if resp.status_code == 200:
                    return resp.json().get("messages", [])
        except Exception as e:
            st.error(f"Mesaj geçmişi yüklenemedi: {e}")
        return []

    @classmethod
    def submit_feedback(cls, message_id: str, rating: int, comment: Optional[str] = None) -> bool:
        try:
            with httpx.Client(base_url=BACKEND_URL, headers=cls.get_headers(), timeout=5.0) as client:
                resp = client.post(
                    "/api/chat/feedback",
                    json={"message_id": message_id, "rating": rating, "comment": comment}
                )
                return resp.status_code == 201
        except Exception as e:
            st.error(f"Geri bildirim gönderilemedi: {e}")
        return False

    @classmethod
    def fetch_analytics_summary(cls) -> Optional[Dict[str, Any]]:
        try:
            with httpx.Client(base_url=BACKEND_URL, headers=cls.get_headers(), timeout=8.0) as client:
                resp = client.get("/api/analytics/summary")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            st.error(f"Analitik verileri çekilemedi: {e}")
        return None

    @classmethod
    def stream_chat_sse(
        cls,
        session_id: str,
        query: str,
        mode: str
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Connects to backend /api/chat/stream and yields parsed Server-Sent Events.
        """
        payload = {
            "session_id": session_id,
            "query": query,
            "mode": mode
        }
        with httpx.Client(base_url=BACKEND_URL, headers=cls.get_headers(), timeout=60.0) as client:
            with client.stream("POST", "/api/chat/stream", json=payload) as response:
                if response.status_code != 200:
                    yield {
                        "type": "error",
                        "content": f"Sunucu hatası: HTTP {response.status_code} - {response.read().decode('utf-8')}"
                    }
                    return

                buffer = ""
                for chunk in response.iter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        event_text, buffer = buffer.split("\n\n", 1)
                        for line in event_text.splitlines():
                            if line.startswith("data:"):
                                raw_json = line[5:].strip()
                                if raw_json:
                                    try:
                                        data = json.loads(raw_json)
                                        yield data
                                    except Exception:
                                        pass


# ===========================================================================
# 3. Authentication Screen (Login / Register Tabs)
# ===========================================================================
def render_auth_screen():
    """Renders modern login and registration forms."""
    st.markdown("<div style='text-align: center; margin-top: 3rem;'>", unsafe_allow_html=True)
    st.markdown("<h1>🤖 Akıllı Servis Masası ve Sistem Uzmanı</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Kurumsal BT Destek, Windows Server & Oracle DBA Yapay Zeka Asistanı</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        tab_login, tab_register = st.tabs(["🔑 Giriş Yap", "📝 Kayıt Ol"])

        with tab_login:
            st.markdown("#### Hesabınıza Giriş Yapın")
            with st.form("login_form"):
                email = st.text_input("Kurumsal E-Posta", placeholder="kullanici@corp.local")
                password = st.text_input("Parola", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Giriş Yap", use_container_width=True, type="primary")

                if submitted:
                    if not email or not password:
                        st.warning("Lütfen e-posta ve parolanızı giriniz.")
                    else:
                        with st.spinner("Kimlik doğrulanıyor..."):
                            res = APIClient.login(email=email.strip(), password=password)
                            if res["success"]:
                                st.session_state.token = res["data"]["access_token"]
                                st.session_state.user = res["data"]["user"]
                                st.success("Giriş başarılı! Yönlendiriliyorsunuz...")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(f"Giriş Başarısız: {res['error']}")

        with tab_register:
            st.markdown("#### Yeni Kullanıcı Oluşturun")
            with st.form("register_form"):
                reg_email = st.text_input("Kurumsal E-Posta", placeholder="ad.soyad@corp.local")
                reg_password = st.text_input("Güçlü Parola", type="password", placeholder="En az 8 karakter, büyük harf ve sayı")
                reg_role = st.selectbox(
                    "Yetki Rolü",
                    ["user", "admin"],
                    format_func=lambda x: "Standart Kullanıcı (user)" if x == "user" else "Sistem Yöneticisi (admin)"
                )
                reg_submitted = st.form_submit_button("Kayıt Ol", use_container_width=True)

                if reg_submitted:
                    if not reg_email or not reg_password:
                        st.warning("Lütfen tüm alanları doldurunuz.")
                    else:
                        with st.spinner("Kullanıcı kaydı yapılıyor..."):
                            res = APIClient.register(email=reg_email.strip(), password=reg_password, role=reg_role)
                            if res["success"]:
                                st.success("Kayıt başarıyla tamamlandı! Giriş yapabilirsiniz.")
                            else:
                                st.error(f"Kayıt Hatası: {res['error']}")


# ===========================================================================
# 4. Sidebar Interface (Modes & Session Management)
# ===========================================================================
def render_sidebar():
    """Renders user profile, domain selector, and session history management."""
    with st.sidebar:
        # User Info Card
        user = st.session_state.user or {}
        role_label = "🛡️ Admin" if user.get("role") == "admin" else "👤 Standart Kullanıcı"
        st.markdown(
            f"""
            <div class="user-card">
                <div style="font-weight: 600; color: #f8fafc; font-size: 0.95rem;">{user.get('email', 'Kullanıcı')}</div>
                <div style="font-size: 0.8rem; color: #38bdf8; margin-top: 0.2rem;">{role_label}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Logout Button
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            st.session_state.token = None
            st.session_state.user = None
            st.session_state.current_session_id = None
            st.session_state.messages = []
            st.rerun()

        st.markdown("---")

        # Navigation Switcher
        st.markdown("### 📍 Ekran Seçimi")
        nav_options = {
            "chat": "💬 Akıllı Sohbet Masası",
            "analytics": "📊 Sistem & Analitik Paneli"
        }
        current_nav = st.radio(
            "Gezinme:",
            options=list(nav_options.keys()),
            format_func=lambda x: nav_options[x],
            index=0 if st.session_state.active_view == "chat" else 1,
            label_visibility="collapsed"
        )
        if current_nav != st.session_state.active_view:
            st.session_state.active_view = current_nav
            st.rerun()

        st.markdown("---")

        # 1. Domain Mode Selector (Active in Chat View)
        if st.session_state.active_view == "chat":
            st.markdown("### 🎯 Uzmanlık Alanı Modu")
            mode_options = {
                "service_desk": "🛠️ IT Servis Masası (Genel Destek)",
                "windows_server": "🪟 Windows Server & AD Uzmanı",
                "oracle_db": "🗄️ Oracle DBA & SQL Uzmanı",
                "general": "🌐 Genel Teknik Mod"
            }
            selected_mode_key = st.radio(
                label="Uzmanlık Alanı:",
                options=list(mode_options.keys()),
                format_func=lambda x: mode_options[x],
                index=list(mode_options.keys()).index(st.session_state.selected_mode),
                label_visibility="collapsed"
            )
            if selected_mode_key != st.session_state.selected_mode:
                st.session_state.selected_mode = selected_mode_key

            st.markdown("---")

        # 2. Session Management
        st.markdown("### 💬 Sohbet Oturumları")

        # New Session Button
        if st.button("➕ Yeni Sohbet Başlat", use_container_width=True, type="primary"):
            new_sess = APIClient.create_session(title=f"Sohbet - {time.strftime('%H:%M')}")
            if new_sess:
                st.session_state.current_session_id = new_sess["id"]
                st.session_state.current_session_title = new_sess["title"]
                st.session_state.messages = []
                st.rerun()

        # List User Sessions
        sessions = APIClient.fetch_sessions()
        st.session_state.sessions_list = sessions

        if not sessions:
            st.caption("Henüz kayıtlı bir sohbet oturumunuz bulunmuyor.")
        else:
            for s in sessions:
                s_id = s["id"]
                s_title = s.get("title", "Sohbet")
                s_count = s.get("message_count", 0)
                is_active = (s_id == st.session_state.current_session_id)

                col_btn, col_del = st.columns([5, 1])
                with col_btn:
                    prefix = "👉 " if is_active else "📄 "
                    btn_label = f"{prefix}{s_title} ({s_count})"
                    if st.button(btn_label, key=f"sess_btn_{s_id}", use_container_width=True):
                        st.session_state.current_session_id = s_id
                        st.session_state.current_session_title = s_title
                        # Load history
                        st.session_state.messages = APIClient.fetch_history(s_id)
                        st.rerun()

                with col_del:
                    if st.button("🗑️", key=f"del_btn_{s_id}", help="Oturumu Sil"):
                        if APIClient.delete_session(s_id):
                            if st.session_state.current_session_id == s_id:
                                st.session_state.current_session_id = None
                                st.session_state.messages = []
                            st.rerun()


# ===========================================================================
# 5. Main Chat Area & Streaming Engine
# ===========================================================================
def render_chat_area():
    """Renders the active conversation and handles real-time response generation."""
    mode = st.session_state.selected_mode
    mode_badge_class = f"badge-{mode.replace('_', '-')}"
    mode_titles = {
        "service_desk": "IT Servis Masası Uzmanı",
        "windows_server": "Windows Server & AD Uzmanı",
        "oracle_db": "Oracle DBA & SQL Uzmanı",
        "general": "Genel Sistem Modu"
    }

    # Main Header
    st.markdown(
        f"""
        <div class="main-header">
            <div>
                <h2>{st.session_state.current_session_title}</h2>
                <p>Sorununuzu yazınız; RAG motorumuz kurumsal bilgi tabanını tarayarak doğrulanmış çözümü sunacaktır.</p>
            </div>
            <div>
                <span class="badge {mode_badge_class}">{mode_titles.get(mode, 'Genel')}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # If no session is active, auto-create one
    if not st.session_state.current_session_id:
        if st.session_state.sessions_list:
            first_sess = st.session_state.sessions_list[0]
            st.session_state.current_session_id = first_sess["id"]
            st.session_state.current_session_title = first_sess["title"]
            st.session_state.messages = APIClient.fetch_history(first_sess["id"])
        else:
            new_sess = APIClient.create_session(title="İlk Sohbet")
            if new_sess:
                st.session_state.current_session_id = new_sess["id"]
                st.session_state.current_session_title = new_sess["title"]
                st.session_state.messages = []

    # Display Existing Messages
    for msg_idx, msg in enumerate(st.session_state.messages):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        sources_meta = msg.get("sources_metadata") or {}
        msg_id = msg.get("id")
        feedback = msg.get("feedback")

        with st.chat_message(role, avatar="🧑‍💻" if role == "user" else "🤖"):
            st.markdown(content)

            # If Assistant Message -> Render Citations & Feedback Widget
            if role == "assistant":
                sources = sources_meta.get("sources", [])
                confidence = sources_meta.get("confidence_score")
                status = sources_meta.get("status", "SUCCESS")

                # 1. Enhanced RAG Citations & Similarity Score Expander
                if sources and len(sources) > 0:
                    conf_pct = sources[0].get("formatted_confidence", f"%{confidence * 100:.1f}" if confidence else "%95.0+")
                    with st.expander(f"📚 Kullanılan Kaynaklar ve Güven Skorları (Eşleşme: {conf_pct})", expanded=False):
                        for s_idx, src in enumerate(sources, 1):
                            title = src.get("title", "Doküman")
                            cat = src.get("category", "genel")
                            norm_score = src.get("formatted_confidence", "")
                            raw_score = src.get("raw_rrf_score", "")
                            chunk_snippet = src.get("content") or src.get("snippet", "İçerik detayı.")
                            source_file = src.get("source", "Kurumsal Bilgi Tabanı")

                            badge_style = f"badge-{cat.replace('_', '-')}" if cat else "badge-general"
                            st.markdown(
                                f"""
                                <div class="citation-card">
                                    <div class="citation-card-header">
                                        <div>
                                            <strong>[{s_idx}] {title}</strong>
                                            <span class="badge {badge_style}" style="font-size: 0.7rem; margin-left: 0.5rem;">{cat}</span>
                                        </div>
                                        <div class="citation-score">Güven: {norm_score}</div>
                                    </div>
                                    <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.3rem;">
                                        📁 Kaynak: <code>{source_file}</code> | Ham RRF: <code>{raw_score}</code>
                                    </div>
                                    <div class="citation-chunk-text">{chunk_snippet}</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                # 2. Qualitative User Feedback (Thumbs Up / Down) Mechanism
                if msg_id:
                    col_fb1, col_fb2 = st.columns([2, 5])
                    current_rating = feedback.get("rating") if feedback else None

                    with col_fb1:
                        if current_rating == 5 or msg_id in st.session_state.feedback_submitted:
                            st.caption("✅ Geri bildiriminiz iletildi: 👍 (Faydalı)")
                        elif current_rating == 1:
                            st.caption("✅ Geri bildiriminiz iletildi: 👎 (Yetersiz)")
                        else:
                            btn_up, btn_down = st.columns(2)
                            with btn_up:
                                if st.button("👍 Beğendim", key=f"thumb_up_{msg_id}", help="Cevap doğru ve faydalı"):
                                    if APIClient.submit_feedback(msg_id, rating=5, comment="Faydalı ve doğru çözüm."):
                                        st.session_state.feedback_submitted.add(msg_id)
                                        st.toast("Geri bildiriminiz kaydedildi, teşekkürler! 🎉", icon="✅")
                                        time.sleep(0.4)
                                        st.rerun()
                            with btn_down:
                                if st.button("👎 Yetersiz", key=f"thumb_down_{msg_id}", help="Cevap yetersiz veya eksik"):
                                    if APIClient.submit_feedback(msg_id, rating=1, comment="Yetersiz veya eksik çözüm."):
                                        st.session_state.feedback_submitted.add(msg_id)
                                        st.toast("Geri bildiriminiz kaydedildi, inceleyeceğiz. 📝", icon="ℹ️")
                                        time.sleep(0.4)
                                        st.rerun()

    # Show Welcome Card if No Messages
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="welcome-card">
                <h3>👋 Merhaba! Size nasıl yardımcı olabilirim?</h3>
                <p style="color: #94a3b8; max-width: 600px; margin: 0.5rem auto 1.5rem auto;">
                    Kurumsal bilgi tabanımızda arama yaparak teknik adımları, PowerShell scriptlerini ve SQL komutlarını adım adım sunabilirim.
                </p>
                <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                    <span class="badge badge-windows-server">💡 Active Directory Kilit Açma</span>
                    <span class="badge badge-oracle-db">💡 ORA-01653 Tablespace Büyütme</span>
                    <span class="badge badge-service-desk">💡 BitLocker Kurtarma Anahtarı</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # User Chat Input
    if user_prompt := st.chat_input("Sorunuzu veya karşılaştığınız teknik problemi yazınız..."):
        session_id = st.session_state.current_session_id
        if not session_id:
            st.error("Lütfen önce bir sohbet oturumu açınız.")
            return

        # 1. Render User Message Immediately
        st.session_state.messages.append({
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": user_prompt,
            "sources_metadata": {}
        })
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(user_prompt)

        # 2. Render Assistant Streamed Response
        with st.chat_message("assistant", avatar="🤖"):
            response_placeholder = st.empty()
            full_response = ""
            final_sources_metadata = {}
            assistant_msg_id = str(uuid.uuid4())

            # Generator for streaming tokens
            def stream_generator():
                nonlocal full_response, final_sources_metadata, assistant_msg_id
                for event in APIClient.stream_chat_sse(
                    session_id=session_id,
                    query=user_prompt,
                    mode=mode
                ):
                    event_type = event.get("type")
                    if event_type == "token":
                        token = event.get("content", "")
                        full_response += token
                        yield token
                    elif event_type == "done":
                        assistant_msg_id = event.get("message_id", assistant_msg_id)
                        final_sources_metadata = {
                            "status": event.get("status", "SUCCESS"),
                            "sources": event.get("sources_metadata", [])
                        }
                    elif event_type == "error":
                        err = event.get("content", "Hata oluştu.")
                        yield f"\n\n❌ **Hata:** {err}"

            # Stream into UI
            st.write_stream(stream_generator())

            # Append to session messages state
            st.session_state.messages.append({
                "id": assistant_msg_id,
                "role": "assistant",
                "content": full_response,
                "sources_metadata": final_sources_metadata,
                "feedback": None
            })

            st.rerun()


# ===========================================================================
# 6. Observability & Admin Analytics Dashboard
# ===========================================================================
def render_analytics_dashboard():
    """Renders the enterprise observability, RAG metrics, and audit log dashboard."""
    st.markdown(
        """
        <div class="main-header">
            <div>
                <h2>📊 Sistem & Gözlemlenebilirlik (Observability) Paneli</h2>
                <div style="color: #94a3b8; font-size: 0.9rem; margin-top: 0.3rem;">
                    RAG Arama Performansı, Güvenilirlik Eşikleri, Kullanıcı Memnuniyeti ve Güvenlik Denetim Günlüğü
                </div>
            </div>
            <div>
                <span class="badge-tag" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4);">
                    🟢 Sistem Sağlıklı (Live)
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.spinner("Analitik verileri PostgreSQL ve Prometheus'tan yükleniyor..."):
        analytics_data = APIClient.fetch_analytics_summary()

    if not analytics_data or analytics_data.get("status") != "success":
        st.error("Analitik verileri alınamadı. Lütfen FastAPI backend servisinin aktif olduğunu doğrulayınız.")
        return

    kpis = analytics_data.get("kpis", {})
    categories = analytics_data.get("category_distribution", {})
    activity_trend = analytics_data.get("activity_trend", [])
    recent_audits = analytics_data.get("recent_audit_logs", [])
    recent_feedbacks = analytics_data.get("recent_feedbacks", [])

    # 1. Executive KPI Metrics Cards
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    with kpi_col1:
        st.metric(
            label="💬 Toplam Soru Hacmi",
            value=f"{kpis.get('total_queries', 0):,}",
            delta=f"{kpis.get('total_sessions', 0)} Oturum / {kpis.get('total_users', 0)} Kullanıcı"
        )
    with kpi_col2:
        conf_val = kpis.get("avg_confidence_score_percent", 0.0)
        st.metric(
            label="🎯 Ortalama Güven Skoru",
            value=f"%{conf_val}",
            delta="Hedef Eşik: >%85.0" if conf_val >= 85 else "Eşik Altı İnceleme"
        )
    with kpi_col3:
        sat_val = kpis.get("satisfaction_rate_percent", 100.0)
        st.metric(
            label="⭐ Kullanıcı Memnuniyeti",
            value=f"%{sat_val}",
            delta=f"{kpis.get('positive_feedbacks', 0)} Pozitif / {kpis.get('total_feedbacks', 0)} Toplam"
        )
    with kpi_col4:
        st.metric(
            label="🛡️ Güvenlik Kalkanı (Fallback)",
            value=f"{kpis.get('fallback_query_count', 0)} Adet",
            delta="0-Token Out-of-Domain"
        )

    st.markdown("---")

    # 2. Charts and Data Visualizations
    chart_col1, chart_col2 = st.columns([1, 1])

    with chart_col1:
        st.markdown("### 📊 Uzmanlık Alanına Göre Soru Dağılımı")
        cat_df = pd.DataFrame([
            {"Kategori": "IT Servis Masası", "Soru Sayısı": categories.get("service_desk", 0)},
            {"Kategori": "Windows Server & AD", "Soru Sayısı": categories.get("windows_server", 0)},
            {"Kategori": "Oracle DB & SQL", "Soru Sayısı": categories.get("oracle_db", 0)},
            {"Kategori": "Genel / Fallback", "Soru Sayısı": categories.get("general", 0)}
        ]).set_index("Kategori")
        st.bar_chart(cat_df, color="#38bdf8", use_container_width=True)

    with chart_col2:
        st.markdown("### 📈 Aktivite ve Soru Hacmi Trendi")
        if activity_trend:
            trend_df = pd.DataFrame(activity_trend)
            trend_df = trend_df.rename(columns={"timestamp": "Zaman", "query_count": "İstek Sayısı"}).set_index("Zaman")
            st.line_chart(trend_df, color="#818cf8", use_container_width=True)
        else:
            st.info("Henüz trend grafiği oluşturacak yeterli zaman serisi verisi bulunmuyor.")

    st.markdown("---")

    # 3. System Health & Infrastructure Info Box
    st.markdown("### 🗄️ Altyapı ve Vektör Veritabanı Durumu")
    info_col1, info_col2, info_col3 = st.columns(3)
    with info_col1:
        st.info(f"📚 **Vektör Bilgi Tabanı:** {kpis.get('total_knowledge_chunks', 128)} Chunk (384 Boyutlu pgvector)")
    with info_col2:
        st.info("⚡ **LLM Motoru:** OpenAI GPT-4o-mini (Streaming SSE)")
    with info_col3:
        st.info("📡 **Prometheus Metrikleri:** `http://localhost:8000/metrics`")

    st.markdown("---")

    # 4. Interactive Data Tables (Audit Logs & Feedbacks)
    tab_audit, tab_feedback = st.tabs(["🛡️ Son Güvenlik Denetim İzi (Audit Logs)", "⭐ Kullanıcı Geri Bildirimleri"])

    with tab_audit:
        st.markdown("#### Gerçek Zamanlı Güvenlik & Denetim Günlüğü (Son 15 Kayıt)")
        if recent_audits:
            audit_df = pd.DataFrame(recent_audits)
            audit_df = audit_df.rename(columns={
                "action": "Eylem / İşlem",
                "user_email": "Kullanıcı E-Posta",
                "ip_address": "İstemci IP",
                "timestamp": "Zaman Damgası"
            })[["Zaman Damgası", "Eylem / İşlem", "Kullanıcı E-Posta", "İstemci IP"]]
            st.dataframe(audit_df, use_container_width=True, hide_index=True)
        else:
            st.caption("Henüz denetim kaydı bulunmuyor.")

    with tab_feedback:
        st.markdown("#### Kullanıcı Değerlendirmeleri ve Niteliksel Geri Bildirimler")
        if recent_feedbacks:
            fb_df = pd.DataFrame(recent_feedbacks)
            fb_df["rating"] = fb_df["rating"].apply(lambda r: f"{'⭐' * r} ({r}/5)" if r > 1 else f"👎 ({r}/5)")
            fb_df = fb_df.rename(columns={
                "rating": "Puan",
                "comment": "Kullanıcı Yorumu",
                "message_snippet": "İlgili Yanıt Özeti",
                "created_at": "Tarih"
            })[["Tarih", "Puan", "Kullanıcı Yorumu", "İlgili Yanıt Özeti"]]
            st.dataframe(fb_df, use_container_width=True, hide_index=True)
        else:
            st.caption("Henüz kullanıcı geri bildirimi kaydedilmedi.")


# ===========================================================================
# 7. Main Application Router
# ===========================================================================
def main():
    """Main Streamlit execution controller."""
    # Check Backend Connectivity
    if not APIClient.check_health():
        st.warning(
            f"⚠️ **FastAPI Backend Sunucusuna Bağlanılamadı!** (`{BACKEND_URL}`)\n\n"
            "Lütfen terminalde backend sunucusunu çalıştırdığınızdan emin olunuz:\n"
            "```powershell\n"
            "python src/main.py\n"
            "# veya\n"
            "uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload\n"
            "```"
        )

    # Route: Auth Screen vs Main Navigation Screen
    if not st.session_state.token or not st.session_state.user:
        render_auth_screen()
    else:
        render_sidebar()
        if st.session_state.active_view == "analytics":
            render_analytics_dashboard()
        else:
            render_chat_area()


if __name__ == "__main__":
    main()
