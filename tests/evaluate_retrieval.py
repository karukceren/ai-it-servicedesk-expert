"""
Information Retrieval (IR) Evaluation & Benchmarking Suite
===========================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Computes rigorous IR evaluation metrics (Hit Rate@k, Recall@k, MRR@k)
    for the Hybrid Search (Dense + Sparse RRF) engine across Ground-Truth
    technical queries (Windows Server, Oracle DB, IT Service Desk).
"""

import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

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

from src.retrieval.hybrid_search import HybridSearchEngine


# ===========================================================================
# 1. Ground Truth Benchmark Dataset (12 Technical Query Test Cases)
# ===========================================================================
GROUND_TRUTH_DATASET: List[Dict[str, Any]] = [
    # --- Service Desk Domain ---
    {
        "id": "GT-01",
        "query": "VPN girişinde Certificate Validation Failed hatası ve certmgr.msc kök sertifika çözümü",
        "domain": "IT Service Desk",
        "expected_category": "service_desk",
        "expected_original_id": "TCK-2026-001",
        "expected_title": "VPN Girişinde 'Certificate Validation Failed' Hatası",
        "relevant_keywords": ["certmgr.msc", "Certificate Validation Failed", "FortiClient", "Trusted Root"]
    },
    {
        "id": "GT-02",
        "query": "Active Directory hesap kilidi açma ve parola sıfırlama talebi account is locked out",
        "domain": "IT Service Desk",
        "expected_category": "service_desk",
        "expected_original_id": "TCK-2026-002",
        "expected_title": "Active Directory Hesap Kilidi ve Şifre Sıfırlama",
        "relevant_keywords": ["Account is locked out", "Active Directory Users and Computers", "şifre sıfırlama"]
    },
    {
        "id": "GT-03",
        "query": "Yazıcı kuyruğunda belge kilitlenmesi net stop spooler PRINTERS SPL temizleme",
        "domain": "IT Service Desk",
        "expected_category": "service_desk",
        "expected_original_id": "TCK-2026-003",
        "expected_title": "Yazıcı Kuyruğunda Belge Kilitlenmesi (Spooler Error)",
        "relevant_keywords": ["net stop spooler", "PRINTERS", ".SPL", ".SHD", "net start spooler"]
    },
    {
        "id": "GT-04",
        "query": "BitLocker kurtarma anahtarı 48 haneli recovery password TPM çipi talebi",
        "domain": "IT Service Desk",
        "expected_category": "service_desk",
        "expected_original_id": "TCK-2026-008",
        "expected_title": "BitLocker Kurtarma Anahtarı (Recovery Key) Talebi",
        "relevant_keywords": ["BitLocker", "Recovery Key", "48 haneli", "TPM"]
    },
    {
        "id": "GT-05",
        "query": "C sürücüsü disk doldu cleanmgr.exe verylowdisk SoftwareDistribution Download temizliği",
        "domain": "IT Service Desk",
        "expected_category": "service_desk",
        "expected_original_id": "TCK-2026-009",
        "expected_title": "C: Sürücüsü Doldu - Sistem Güncellemesi Yapılamıyor",
        "relevant_keywords": ["cleanmgr.exe", "SoftwareDistribution", "Download", "disk alanı"]
    },

    # --- Windows Server Domain ---
    {
        "id": "GT-06",
        "query": "PowerShell Search-ADAccount -LockedOut ve Unlock-ADAccount ile hesap kilidi açma",
        "domain": "Windows Server / AD",
        "expected_category": "windows_server",
        "expected_original_id": "WIN-KB-001",
        "expected_title": "Active Directory / GPO",
        "relevant_keywords": ["Search-ADAccount", "Unlock-ADAccount", "LockedOut", "ActiveDirectory"]
    },
    {
        "id": "GT-07",
        "query": "HTTP Error 500.19 0x8007000d URL Rewrite modülü IIS yapılandırma iisreset",
        "domain": "Windows Server / IIS",
        "expected_category": "windows_server",
        "expected_original_id": "WIN-KB-002",
        "expected_title": "IIS / Web Server",
        "relevant_keywords": ["500.19", "0x8007000d", "URL Rewrite", "Get-WebConfigurationProperty", "iisreset"]
    },
    {
        "id": "GT-08",
        "query": "Event ID 4625 Failed Logon Security Event Log PowerShell Get-WinEvent",
        "domain": "Windows Server / Security",
        "expected_category": "windows_server",
        "expected_original_id": "WIN-KB-003",
        "expected_title": "Security / Event Viewer",
        "relevant_keywords": ["4625", "Failed Logon", "Get-WinEvent", "Security", "LogonType"]
    },

    # --- Oracle DB Domain ---
    {
        "id": "GT-09",
        "query": "ORA-01653 unable to extend table in tablespace USERS dba_tablespace_usage_metrics",
        "domain": "Oracle DB",
        "expected_category": "oracle_db",
        "expected_original_id": "ORA-KB-001",
        "expected_title": "Tablespace Management",
        "relevant_keywords": ["ORA-01653", "tablespace_name", "AUTOEXTEND ON", "dba_tablespace_usage_metrics"]
    },
    {
        "id": "GT-10",
        "query": "Oracle DB blocking session kilitlenen oturum tespiti v$session ALTER SYSTEM KILL SESSION",
        "domain": "Oracle DB",
        "expected_category": "oracle_db",
        "expected_original_id": "ORA-KB-004",
        "expected_title": "Concurrency & Locking",
        "relevant_keywords": ["blocker_sid", "blocked_sid", "v$session", "KILL SESSION", "Blocking Session"]
    },
    {
        "id": "GT-11",
        "query": "Oracle RMAN Incremental Level 0 backup crosscheck archivelog all",
        "domain": "Oracle DB",
        "expected_category": "oracle_db",
        "expected_original_id": "ORA-KB-003",
        "expected_title": "Backup & RMAN",
        "relevant_keywords": ["RMAN", "INCREMENTAL LEVEL 0", "DATABASE PLUS ARCHIVELOG", "CROSSCHECK"]
    },
    {
        "id": "GT-12",
        "query": "Oracle UNUSABLE index rebuild online DBMS_STATS.GATHER_INDEX_STATS",
        "domain": "Oracle DB",
        "expected_category": "oracle_db",
        "expected_original_id": "ORA-KB-005",
        "expected_title": "Index & Maintenance",
        "relevant_keywords": ["UNUSABLE", "REBUILD ONLINE", "DBMS_STATS.GATHER_INDEX_STATS", "user_indexes"]
    },
    {
        "id": "GT-13",
        "query": "Oracle DB yüksek CPU tüketen sorgu EXPLAIN PLAN FOR ve DBMS_XPLAN.DISPLAY analizi",
        "domain": "Oracle DB",
        "expected_category": "oracle_db",
        "expected_original_id": "ORA-KB-006",
        "expected_title": "Performance & Explain Plan",
        "relevant_keywords": ["EXPLAIN PLAN FOR", "DBMS_XPLAN.DISPLAY", "PLAN_TABLE", "Full Table Scan"]
    }
]


# ===========================================================================
# 2. Evaluation Engine Class
# ===========================================================================
class RetrievalEvaluator:
    """
    Evaluates Information Retrieval metrics for Dense, Sparse, and Hybrid RRF searches.
    """

    def __init__(self, engine: Optional[HybridSearchEngine] = None):
        self.engine = engine or HybridSearchEngine()

    @staticmethod
    def is_match(item: Dict[str, Any], ground_truth: Dict[str, Any]) -> bool:
        """
        Determines whether a retrieved document matches the ground truth criteria.
        Checks original_id, chunk_id, title match, or keyword presence.
        """
        meta = item.get("metadata") or {}
        content = item.get("content", "")

        orig_id = meta.get("original_id", "")
        title = meta.get("title", "")
        cat = meta.get("category", "")

        # 1. Exact ID Match
        if ground_truth.get("expected_original_id") and orig_id == ground_truth["expected_original_id"]:
            return True

        # 2. Exact Title Match
        if ground_truth.get("expected_title") and title.lower() == ground_truth["expected_title"].lower():
            return True

        # 3. Category + Multiple Keyword Match
        keywords = ground_truth.get("relevant_keywords", [])
        matched_keywords = sum(1 for kw in keywords if kw.lower() in content.lower())
        if cat == ground_truth["expected_category"] and matched_keywords >= 2:
            return True

        return False

    def evaluate_benchmark(
        self,
        dataset: List[Dict[str, Any]] = GROUND_TRUTH_DATASET,
        top_k_eval: int = 5
    ) -> Dict[str, Any]:
        """
        Runs evaluation on all dataset test cases and calculates IR metrics.

        Returns:
            Dict containing detailed per-query results and aggregated metrics.
        """
        k_values = [1, 3, 5]
        query_eval_records = []

        total_queries = len(dataset)
        hits = {k: 0 for k in k_values}
        recalls = {k: 0.0 for k in k_values}
        reciprocal_ranks = {k: 0.0 for k in k_values}

        total_latency_ms = 0.0

        for idx, gt in enumerate(dataset, start=1):
            query = gt["query"]

            t0 = time.perf_counter()
            results = self.engine.hybrid_search(
                query=query,
                top_k=top_k_eval,
                category=None  # Test broad hybrid retrieval without prior domain filter
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            total_latency_ms += elapsed_ms

            # Determine rank of first relevant match
            first_match_rank: Optional[int] = None
            for rank, item in enumerate(results, start=1):
                if self.is_match(item, gt):
                    first_match_rank = rank
                    break

            # Calculate metrics for this query
            query_metrics = {
                "id": gt["id"],
                "domain": gt["domain"],
                "query": query,
                "first_match_rank": first_match_rank,
                "latency_ms": elapsed_ms,
                "top_result_title": results[0]["metadata"].get("title", "N/A") if results else "N/A",
                "top_result_confidence": results[0].get("formatted_confidence", "%0.00") if results else "%0.00"
            }

            for k in k_values:
                is_hit = 1 if (first_match_rank is not None and first_match_rank <= k) else 0
                hits[k] += is_hit
                recalls[k] += float(is_hit)
                reciprocal_ranks[k] += (1.0 / first_match_rank) if (first_match_rank and first_match_rank <= k) else 0.0

            query_eval_records.append(query_metrics)

        # Aggregate metrics
        aggregated_metrics = {}
        for k in k_values:
            hit_rate = hits[k] / total_queries
            recall = recalls[k] / total_queries
            mrr = reciprocal_ranks[k] / total_queries

            aggregated_metrics[f"hit_rate@{k}"] = hit_rate
            aggregated_metrics[f"recall@{k}"] = recall
            aggregated_metrics[f"mrr@{k}"] = mrr

        avg_latency = total_latency_ms / total_queries

        return {
            "total_queries": total_queries,
            "avg_latency_ms": round(avg_latency, 2),
            "metrics": aggregated_metrics,
            "query_records": query_eval_records
        }

    def print_markdown_report(self, eval_results: Dict[str, Any]):
        """Prints a comprehensive, publication-ready Markdown report to console."""
        records = eval_results["query_records"]
        metrics = eval_results["metrics"]

        print("\n" + "=" * 105)
        print("📊 HİBRİT ARAMA (RRF) BİLGİ ERİŞİMİ (INFORMATION RETRIEVAL) DEĞERLENDİRME RAPORU")
        print("=" * 105)

        print("\n### 🔍 1. Sorgu Bazlı Doğrulama Tablosu (Per-Query Results)\n")
        print("| # | Test ID | Alan (Domain) | İlk İsabet Sırası | Güven Oranı | En Üst Doküman Başlığı | Gecikme |")
        print("| :---: | :---: | :--- | :---: | :---: | :--- | :---: |")

        for i, rec in enumerate(records, start=1):
            rank_str = f"**#{rec['first_match_rank']}** ✅" if rec['first_match_rank'] == 1 else (
                f"#{rec['first_match_rank']} ✅" if rec['first_match_rank'] is not None else "❌ Bulunamadı"
            )
            title = rec['top_result_title'][:36] + ("..." if len(rec['top_result_title']) > 36 else "")
            print(
                f"| {i:02d} | `{rec['id']}` | {rec['domain']:<22} | {rank_str:<17} | "
                f"{rec['top_result_confidence']:<11} | {title:<39} | {rec['latency_ms']:.1f} ms |"
            )

        print("\n" + "-" * 105)
        print("\n### 📈 2. Nihai Bilgi Erişimi (IR) Metrik Tablosu (Aggregated Metrics)\n")
        print("| Metrik Parametresi | k = 1 | k = 3 | k = 5 | Açıklama |")
        print("| :--- | :---: | :---: | :---: | :--- |")
        print(
            f"| **Hit Rate@k** | **%{metrics['hit_rate@1']*100:.2f}** | **%{metrics['hit_rate@3']*100:.2f}** | **%{metrics['hit_rate@5']*100:.2f}** | "
            f"Doğru dokümanın ilk k sonuçta yer alma olasılığı |"
        )
        print(
            f"| **Recall@k** | **%{metrics['recall@1']*100:.2f}** | **%{metrics['recall@3']*100:.2f}** | **%{metrics['recall@5']*100:.2f}** | "
            f"Hedeflenen referans dokümanların yakalanma oranı |"
        )
        print(
            f"| **MRR@k (Mean Reciprocal Rank)** | **{metrics['mrr@1']:.4f}** | **{metrics['mrr@3']:.4f}** | **{metrics['mrr@5']:.4f}** | "
            f"İlk doğru dokümanın sıra terslerinin ortalaması (1/Rank) |"
        )

        print("\n" + "-" * 105)
        print(f"⏱️ **Ortalama Çıkarım & Arama Gecikmesi (Avg Latency):** {eval_results['avg_latency_ms']} ms")
        print(f"🎯 **Toplam Değerlendirilen Sorgu Sayısı:** {eval_results['total_queries']}")
        print("=" * 105 + "\n")


# ===========================================================================
# 3. Direct CLI & Pytest Execution
# ===========================================================================
def test_retrieval_evaluation_benchmark():
    """Pytest test case asserting high benchmark metrics."""
    evaluator = RetrievalEvaluator()
    results = evaluator.evaluate_benchmark()

    # Verify high retrieval performance thresholds
    assert results["metrics"]["hit_rate@1"] >= 0.90, "Hit Rate@1 must be at least %90"
    assert results["metrics"]["hit_rate@3"] >= 0.95, "Hit Rate@3 must be at least %95"
    assert results["metrics"]["recall@3"] >= 0.95, "Recall@3 must be at least %95"
    assert results["metrics"]["mrr@3"] >= 0.90, "MRR@3 must be at least 0.90"


def main():
    """Main execution function for CLI."""
    evaluator = RetrievalEvaluator()
    results = evaluator.evaluate_benchmark()
    evaluator.print_markdown_report(results)


if __name__ == "__main__":
    main()
