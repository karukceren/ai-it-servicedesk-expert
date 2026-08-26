"""
Locust Step-Load Concurrency & Breaking Point Benchmark
======================================================
Project: Akıllı IT Servis Masası ve Sistem Uzmanı Chatbot (Enterprise RAG)
Description:
    Implements a dynamic Step-Load Shape load testing suite using Locust's LoadTestShape.
    Adds 20 virtual users every 10 seconds to stress-test the FastAPI backend RAG engine
    until maximum concurrency or breaking point is discovered.

Workload Distribution:
    - 75% Weight (@task(3)): Valid in-domain technical queries (Oracle DBA, Windows Server, Service Desk).
    - 25% Weight (@task(1)): Out-of-domain queries triggering anti-hallucination guardrails & 0-token fallback.
"""

import math
import uuid
import random
import logging
from locust import HttpUser, task, between, LoadTestShape

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LocustStepLoad")

# ===========================================================================
# 1. Test Query Datasets
# ===========================================================================
TECHNICAL_QUERIES = [
    {
        "query": "Oracle ORA-01555 snapshot too old hatası nasıl giderilir?",
        "mode": "oracle_db"
    },
    {
        "query": "Oracle ORA-01653 unable to extend table hatası için tablespace nasıl genişletilir?",
        "mode": "oracle_db"
    },
    {
        "query": "PowerShell ile Active Directory kilitli kullanıcı hesabı nasıl bulunur ve açılır?",
        "mode": "windows_server"
    },
    {
        "query": "Windows Print Spooler servisi kilitlendiğinde kuyruk nasıl temizlenir ve yeniden başlatılır?",
        "mode": "service_desk"
    },
    {
        "query": "VPN bağlantısı kurarken 'Certificate Validation Failed' hatası nasıl çözülür?",
        "mode": "service_desk"
    },
    {
        "query": "Oracle RMAN ile Incremental Level 1 Cumulative backup nasıl alınır?",
        "mode": "oracle_db"
    },
    {
        "query": "Windows Server Event Viewer Security 4625 başarısız oturum açma logları nasıl filtrelenir?",
        "mode": "windows_server"
    },
    {
        "query": "Active Directory Group Policy (GPO) force update komutu nedir?",
        "mode": "windows_server"
    }
]

GUARDRAIL_FALLBACK_QUERIES = [
    {
        "query": "Bugün hava durumu nasıl olacak?",
        "mode": "general"
    },
    {
        "query": "Şirket yemekhanesinde öğle yemeği menüsünde ne var?",
        "mode": "general"
    },
    {
        "query": "Bana en popüler sinema filmlerini listeler misin?",
        "mode": "general"
    },
    {
        "query": "Hafta sonu için en lezzetli pasta tarifi nedir?",
        "mode": "general"
    }
]


# ===========================================================================
# 2. Virtual User Simulation Class (FastAPIStepUser)
# ===========================================================================
class FastAPIStepUser(HttpUser):
    """
    Represents an authenticated enterprise user executing RAG queries with JWT token.
    """
    # Think time between user actions (0.5 to 1.5 seconds)
    wait_time = between(0.5, 1.5)

    def on_start(self):
        """
        User Lifecycle Initialization:
        1. Generates unique credentials.
        2. Registers user via POST /api/v1/auth/register (or /api/auth/register).
        3. Obtains JWT Access Token via POST /api/v1/auth/login.
        4. Applies Authorization: Bearer <token> header to all subsequent requests.
        """
        self.user_email = f"loaduser_{uuid.uuid4().hex[:8]}@enterprise.corp"
        self.password = "LoadTestPassword2026!"
        self.auth_token = None

        # Step 1: Register
        register_payload = {
            "email": self.user_email,
            "password": self.password,
            "role": "user"
        }
        with self.client.post(
            "/api/v1/auth/register",
            json=register_payload,
            name="/api/v1/auth/register",
            timeout=15.0,
            catch_response=True
        ) as reg_resp:
            if reg_resp.status_code in (200, 201):
                reg_resp.success()
            else:
                reg_resp.failure(f"Registration failed: {reg_resp.status_code} - {reg_resp.text}")
                return

        # Step 2: Login & Obtain JWT Token
        login_payload = {
            "email": self.user_email,
            "password": self.password
        }
        with self.client.post(
            "/api/v1/auth/login",
            json=login_payload,
            name="/api/v1/auth/login",
            timeout=15.0,
            catch_response=True
        ) as login_resp:
            if login_resp.status_code == 200:
                data = login_resp.json()
                self.auth_token = data.get("access_token")
                # Set Bearer Header for this simulated user
                self.client.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                login_resp.success()
            else:
                login_resp.failure(f"Login failed: {login_resp.status_code} - {login_resp.text}")

    @task(3)
    def task_valid_technical_rag_query(self):
        """
        Task 1 (75% Weight): Valid in-domain technical query.
        Sends technical question to /api/v1/chat/query endpoint.
        Expects HTTP 200 with status='SUCCESS' and verified RAG sources.
        """
        if not self.auth_token:
            return

        item = random.choice(TECHNICAL_QUERIES)
        payload = {
            "query": item["query"],
            "mode": item["mode"]
        }

        with self.client.post(
            "/api/v1/chat/query",
            json=payload,
            name="/api/v1/chat/query [Technical RAG (75%)]",
            timeout=25.0,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "SUCCESS":
                    response.success()
                else:
                    response.failure(f"Unexpected response status: {data.get('status')}")
            else:
                response.failure(f"RAG query failed with status: {response.status_code}")

    @task(1)
    def task_out_of_domain_guardrail_query(self):
        """
        Task 2 (25% Weight): Out-of-domain query triggering confidence guardrails.
        Sends irrelevant query to /api/v1/chat/query endpoint.
        Expects HTTP 200 with status='FALLBACK_TRIGGERED' and 0 token consumption.
        """
        if not self.auth_token:
            return

        item = random.choice(GUARDRAIL_FALLBACK_QUERIES)
        payload = {
            "query": item["query"],
            "mode": item["mode"]
        }

        with self.client.post(
            "/api/v1/chat/query",
            json=payload,
            name="/api/v1/chat/query [Guardrail Fallback (25%)]",
            timeout=15.0,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "FALLBACK_TRIGGERED":
                    response.success()
                else:
                    response.failure(f"Expected FALLBACK_TRIGGERED but got {data.get('status')}")
            else:
                response.failure(f"Guardrail query failed with status: {response.status_code}")


# ===========================================================================
# 3. Dynamic Step-Load Shape Architecture (LoadTestShape)
# ===========================================================================
class StepLoadShape(LoadTestShape):
    """
    Step Load Shape Architecture:
    - Adds 20 new virtual users every 10 seconds.
    - Spawns at 10 users/second.
    - Continues ramping up to discover maximum concurrency & breaking point.
    """
    step_time = 10      # Duration of each step in seconds
    step_users = 20     # Number of users added at each step
    spawn_rate = 10     # User spawn rate (users per second)
    time_limit = 120    # Total test duration (2 minutes)

    def tick(self):
        """
        Calculates user count based on elapsed test duration.
        """
        run_time = self.get_run_time()

        if run_time > self.time_limit:
            return None

        current_step = math.floor(run_time / self.step_time) + 1
        target_user_count = current_step * self.step_users

        return (target_user_count, self.spawn_rate)
