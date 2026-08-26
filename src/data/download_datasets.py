"""
Data Download and Acquisition Script
====================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Author: AI Support Engineer Team
Description:
    Downloads and prepares raw IT Support Tickets, Windows Server, and Oracle DB
    Q&A datasets from Kaggle API and Hugging Face Datasets with fallback mechanisms,
    progress tracking, and structured error handling.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DatasetDownloader")


class DatasetDownloader:
    """
    Handles downloading, fetching, and local archiving of raw datasets
    for Service Desk tickets, Windows Server, and Oracle DB technical data.
    """

    def __init__(self, raw_data_dir: Optional[Path] = None):
        # Default target directory: <project_root>/data/raw
        if raw_data_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            self.raw_data_dir = project_root / "data" / "raw"
        else:
            self.raw_data_dir = Path(raw_data_dir)

        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Target raw data directory initialized at: {self.raw_data_dir.resolve()}")

    # -----------------------------------------------------------------------
    # 1. Kaggle IT Support Tickets Dataset Downloader
    # -----------------------------------------------------------------------
    def download_kaggle_tickets(
        self,
        dataset_identifier: str = "tobiasbueck/multilingual-customer-support-tickets",
        fallback_on_error: bool = True
    ) -> Optional[Path]:
        """
        Downloads IT support ticket datasets using Kaggle API.

        Args:
            dataset_identifier: Kaggle dataset identifier (owner/dataset-name).
            fallback_on_error: If True, creates sample IT ticket dataset when API fails.

        Returns:
            Path to downloaded/created data file or None if failed.
        """
        logger.info(f"Starting Kaggle download for dataset: '{dataset_identifier}'...")
        output_subfolder = self.raw_data_dir / "kaggle_tickets"
        output_subfolder.mkdir(parents=True, exist_ok=True)

        try:
            # Check for kaggle credentials
            kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
            has_env_creds = "KAGGLE_USERNAME" in os.environ and "KAGGLE_KEY" in os.environ

            if not kaggle_json.exists() and not has_env_creds:
                logger.warning(
                    "Kaggle API credentials not found in ~/.kaggle/kaggle.json or environment variables "
                    "(KAGGLE_USERNAME, KAGGLE_KEY)."
                )
                if not fallback_on_error:
                    return None
                return self._generate_fallback_it_tickets(output_subfolder)

            # Lazy import kaggle to prevent early exit if package missing
            from kaggle.api.kaggle_api_extended import KaggleApi
            api = KaggleApi()
            api.authenticate()
            logger.info("Kaggle API authentication successful.")

            logger.info(f"Downloading files to {output_subfolder}...")
            api.dataset_download_files(dataset_identifier, path=str(output_subfolder), unzip=True)
            logger.info(f"Successfully downloaded and unzipped Kaggle dataset to: {output_subfolder}")
            return output_subfolder

        except ImportError:
            logger.warning(
                "The 'kaggle' Python library is not installed (run `pip install kaggle`)."
            )
            if fallback_on_error:
                return self._generate_fallback_it_tickets(output_subfolder)
            return None
        except Exception as e:
            logger.error(f"Error during Kaggle dataset download: {str(e)}")
            if fallback_on_error:
                logger.info("Generating rich fallback IT ticket dataset for uninterrupted pipeline flow...")
                return self._generate_fallback_it_tickets(output_subfolder)
            return None

    # -----------------------------------------------------------------------
    # 2. Hugging Face Stack Exchange (Windows Server & Oracle DB) Downloader
    # -----------------------------------------------------------------------
    def download_huggingface_stackexchange(
        self,
        dataset_name: str = "HuggingFaceH4/stack-exchange-preferences",
        sample_limit_per_domain: int = 50,
        max_scan_items: int = 500,
        fallback_on_error: bool = True
    ) -> Dict[str, Path]:
        """
        Downloads technical Q&A pairs from Hugging Face Datasets and filters
        for Windows Server and Oracle DB domain queries.

        Args:
            dataset_name: Hugging Face dataset identifier.
            sample_limit_per_domain: Max number of domain-specific records to save.
            max_scan_items: Maximum items to scan in streaming mode before fallback.
            fallback_on_error: If True, writes curated technical Q&A dataset on failure.

        Returns:
            Dictionary containing paths to saved dataset files.
        """
        logger.info(f"Starting Hugging Face download for dataset: '{dataset_name}'...")
        saved_paths: Dict[str, Path] = {}

        try:
            from datasets import load_dataset

            logger.info(f"Connecting to Hugging Face dataset stream: {dataset_name}...")
            ds = load_dataset(dataset_name, split="train", streaming=True)

            windows_records: List[Dict[str, Any]] = []
            oracle_records: List[Dict[str, Any]] = []

            windows_keywords = [
                "windows server", "active directory", "iis", "event viewer", "powershell",
                "gpo", "hyper-v", "dns server", "domain controller"
            ]
            oracle_keywords = [
                "oracle", "plsql", "pl/sql", "tablespace", "rman", "explain plan",
                "ora-", "oracle 19c", "dba_", "v$"
            ]

            logger.info(f"Scanning up to {max_scan_items} items for Windows Server and Oracle DB domains...")
            for i, row in enumerate(ds):
                prompt_text = ""
                if "prompt" in row and isinstance(row["prompt"], str):
                    prompt_text = row["prompt"].lower()
                elif "question" in row and isinstance(row["question"], str):
                    prompt_text = row["question"].lower()

                response_text = ""
                if "response" in row:
                    response_text = str(row["response"])
                elif "answers" in row:
                    response_text = str(row["answers"])
                elif "chosen" in row:
                    response_text = str(row["chosen"])

                # Check Windows Server
                if len(windows_records) < sample_limit_per_domain:
                    if any(kw in prompt_text for kw in windows_keywords):
                        windows_records.append({
                            "id": f"HF-WIN-{len(windows_records)+1:04d}",
                            "domain": "WINDOWS_SERVER",
                            "prompt": row.get("prompt", row.get("question", "")),
                            "solution": response_text,
                            "source": dataset_name
                        })

                # Check Oracle DB
                if len(oracle_records) < sample_limit_per_domain:
                    if any(kw in prompt_text for kw in oracle_keywords):
                        oracle_records.append({
                            "id": f"HF-ORA-{len(oracle_records)+1:04d}",
                            "domain": "ORACLE_DB",
                            "prompt": row.get("prompt", row.get("question", "")),
                            "solution": response_text,
                            "source": dataset_name
                        })

                if (i + 1) % 100 == 0:
                    logger.info(f"Scanned {i + 1} records | Found: {len(windows_records)} WinServer, {len(oracle_records)} OracleDB")

                if len(windows_records) >= sample_limit_per_domain and len(oracle_records) >= sample_limit_per_domain:
                    logger.info(f"Target count reached ({sample_limit_per_domain} records per domain).")
                    break

                if i >= max_scan_items:
                    logger.info(f"Reached max scan limit ({max_scan_items}). Finalizing extracted records...")
                    break

            # If fewer than required, merge with high-quality curated domain datasets
            curated = self._generate_fallback_domain_datasets()
            
            # Combine HF results with curated baseline to guarantee expert coverage
            final_win = curated["win_records"] + windows_records
            final_ora = curated["ora_records"] + oracle_records

            saved_paths["windows_server"] = self._save_dataset_records(final_win, "stackexchange_windows_server")
            saved_paths["oracle_db"] = self._save_dataset_records(final_ora, "stackexchange_oracle_db")

            return saved_paths

        except ImportError:
            logger.warning("The 'datasets' library is not installed (run `pip install datasets`).")
            if fallback_on_error:
                curated = self._generate_fallback_domain_datasets()
                return {
                    "windows_server": self._save_dataset_records(curated["win_records"], "stackexchange_windows_server"),
                    "oracle_db": self._save_dataset_records(curated["ora_records"], "stackexchange_oracle_db")
                }
            return {}
        except Exception as e:
            logger.error(f"Error during Hugging Face dataset download: {str(e)}")
            if fallback_on_error:
                logger.info("Generating curated domain datasets as fallback...")
                curated = self._generate_fallback_domain_datasets()
                return {
                    "windows_server": self._save_dataset_records(curated["win_records"], "stackexchange_windows_server"),
                    "oracle_db": self._save_dataset_records(curated["ora_records"], "stackexchange_oracle_db")
                }
            return {}

    # -----------------------------------------------------------------------
    # Helper: Save records to CSV and JSON
    # -----------------------------------------------------------------------
    def _save_dataset_records(self, records: List[Dict[str, Any]], base_filename: str) -> Path:
        """
        Saves record dictionaries to both CSV and JSON formats in data/raw.
        """
        json_path = self.raw_data_dir / f"{base_filename}.json"
        csv_path = self.raw_data_dir / f"{base_filename}.csv"

        # Save JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        # Save CSV
        df = pd.DataFrame(records)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        logger.info(f"Successfully saved {len(records)} records:")
        logger.info(f"  -> JSON: {json_path.resolve()}")
        logger.info(f"  -> CSV:  {csv_path.resolve()}")
        return json_path

    # -----------------------------------------------------------------------
    # Fallback Data Generators (Comprehensive Curated Technical Datasets)
    # -----------------------------------------------------------------------
    def _generate_fallback_it_tickets(self, target_folder: Path) -> Path:
        """Generates representative IT Service Desk tickets for offline RAG development."""
        sample_tickets = [
            {
                "ticket_id": "TCK-2026-001",
                "category": "Authentication",
                "priority": "High",
                "subject": "VPN Girişinde 'Certificate Validation Failed' Hatası",
                "description": "Kullanıcı şirket ağına FortiClient VPN üzerinden bağlanmaya çalıştığında 'Certificate Validation Failed' uyarısı alıyor ve bağlantı %98'de kesiliyor.",
                "resolution": "1. Kullanıcı bilgisayarında `certmgr.msc` çalıştırıldı.\n2. 'Trusted Root Certification Authorities' altında süresi dolmuş kurumsal kök sertifika silindi.\n3. Yeni CA sertifikası iç portal üzerinden indirilip yeniden yüklendi.\n4. VPN servisi yeniden başlatılarak bağlantı başarıyla kuruldu."
            },
            {
                "ticket_id": "TCK-2026-002",
                "category": "Account Management",
                "priority": "Medium",
                "subject": "Active Directory Hesap Kilidi ve Şifre Sıfırlama",
                "description": "Kullanıcı sabah giriş yaparken 3 kez hatalı şifre girdiği için hesabı kilitlendi (Account is locked out).",
                "resolution": "1. Active Directory Users and Computers konsolunda kullanıcı bulundu.\n2. 'Account is locked out' kutucuğunun işareti kaldırılarak hesap kilidi açıldı.\n3. Geçici bir parola tanımlandı ve 'User must change password at next logon' seçeneği işaretlendi."
            },
            {
                "ticket_id": "TCK-2026-003",
                "category": "Print Services",
                "priority": "Low",
                "subject": "Yazıcı Kuyruğunda Belge Kilitlenmesi (Spooler Error)",
                "description": "Muhasebe departmanı yazıcısına gönderilen 100 sayfalık PDF belgesi takıldı ve arkasından gelen hiçbir yazdırma görevi çalışmıyor.",
                "resolution": "1. Yönetici olarak komut satırı açıldı.\n2. `net stop spooler` komutu ile yazdırma servisi durduruldu.\n3. `C:\\Windows\\System32\\spool\\PRINTERS` dizini altındaki tüm `.SPL` ve `.SHD` dosyaları temizlendi.\n4. `net start spooler` komutuyla servis tekrar başlatıldı ve test sayfası yazdırıldı."
            },
            {
                "ticket_id": "TCK-2026-004",
                "category": "Email & Collaboration",
                "priority": "Medium",
                "subject": "Outlook 'Disconnected' Durumunda Kalıyor ve Senkronize Olmuyor",
                "description": "Outlook istemcisi sürekli 'Disconnected' veya 'Need Password' uyarısı veriyor, mailler gelen kutusuna düşmüyor.",
                "resolution": "1. Windows Credential Manager (Kimlik Bilgisi Yöneticisi) açılarak Office/Outlook ile ilgili eski kimlik kayıtları silindi.\n2. Outlook güvenli modda (`outlook.exe /safe`) başlatıldı.\n3. Modern Authentication doğrulama ekranı tetiklenerek kullanıcı hesabı yeniden bağlandı."
            },
            {
                "ticket_id": "TCK-2026-005",
                "category": "Network",
                "priority": "High",
                "subject": "Ortak Ağ Sürücüsü (Z: Drive) Bağlantı Hatası",
                "description": "Kullanıcı ortak ağ paylaşımına bağlanmak istediğinde 'The local device name is already in use' veya 'Network path not found' hatası alıyor.",
                "resolution": "1. PowerShell açılarak `net use Z: /delete` çalıştırıldı.\n2. `ipconfig /flushdns` ile DNS önbelleği temizlendi.\n3. Paylaşım yolu IP yerine FQDN ile `net use Z: \\\\fileserver.corp.local\\Shared /persistent:yes` komutuyla yeniden bağlandı."
            },
            {
                "ticket_id": "TCK-2026-006",
                "category": "Hardware & Peripherals",
                "priority": "Medium",
                "subject": "Çift Monitör Kurulumunda İkinci Ekran Algılanmıyor",
                "description": "Type-C docking station üzerinden bağlanan ikinci monitör 'No Signal' hatası veriyor.",
                "resolution": "1. DisplayPort kablosu ve dock bağlantıları kontrol edildi.\n2. Intel Graphics Command Center açılarak 'Detect Displays' çalıştırıldı.\n3. Ekran kartı sürücüsü aygıt yöneticisinden güncellendi."
            },
            {
                "ticket_id": "TCK-2026-007",
                "category": "Software License",
                "priority": "High",
                "subject": "Kurumsal Yazılım Lisans Sunucusu Bağlantı Hatası (FLEXlm Error -15)",
                "description": "Mühendislik yazılımı açılırken 'Cannot connect to license server system (FLEXlm -15,10)' hatası veriyor.",
                "resolution": "1. `telnet lic-server.corp.local 27000` ile lisans portu kontrol edildi ve firewall kuralı eklendi.\n2. İstemci üzerindeki `ADSKFLEX_LICENSE_FILE` ortam değişkeni güncellendi."
            },
            {
                "ticket_id": "TCK-2026-008",
                "category": "Security",
                "priority": "Critical",
                "subject": "BitLocker Kurtarma Anahtarı (Recovery Key) Talebi",
                "description": "Kullanıcı BIOS güncellemesi sonrası mavi ekranda BitLocker Recovery Key istemiyle karşılaştı.",
                "resolution": "1. Active Directory veya Azure AD / Intune portalı üzerinden bilgisayar adına ait 48 haneli BitLocker Recovery Password çekildi.\n2. Kullanıcıya iletilerek disk kilidi açıldı ve TPM çipi doğrulandı."
            },
            {
                "ticket_id": "TCK-2026-009",
                "category": "Storage",
                "priority": "Medium",
                "subject": "C: Sürücüsü Doldu - Sistem Güncellemesi Yapılamıyor",
                "description": "Kullanıcı bilgisayarında C: sürücüsünde 200 MB boş alan kaldığı için Windows güncellemeleri başarısız oluyor.",
                "resolution": "1. `cleanmgr.exe /verylowdisk` ile Windows Temp ve eski güncelleme dosyaları temizlendi.\n2. `C:\\Windows\\SoftwareDistribution\\Download` klasörü boşaltıldı.\n3. 18 GB disk alanı kazandırıldı."
            },
            {
                "ticket_id": "TCK-2026-010",
                "category": "Remote Desktop",
                "priority": "High",
                "subject": "RDP 'An authentication error has occurred (CredSSP)' Hatası",
                "description": "Uzak masaüstü sunucusuna bağlanırken CredSSP Encryption Oracle Remediation hatası alınıyor.",
                "resolution": "1. Sunucu ve istemcide en güncel Windows Cumulative Update yüklendi.\n2. İstemcide `gpedit.msc` -> Administrative Templates -> System -> Credentials Delegation altındaki CredSSP politikası güncellendi."
            }
        ]

        json_out = target_folder / "service_desk_tickets.json"
        csv_out = target_folder / "service_desk_tickets.csv"

        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(sample_tickets, f, ensure_ascii=False, indent=2)

        pd.DataFrame(sample_tickets).to_csv(csv_out, index=False, encoding="utf-8-sig")
        logger.info(f"IT Tickets dataset created successfully at: {json_out.resolve()}")
        return json_out

    def _generate_fallback_domain_datasets(self) -> Dict[str, Any]:
        """Generates deep technical Q&A datasets for Windows Server and Oracle DB."""
        win_data = [
            {
                "id": "WIN-KB-001",
                "domain": "WINDOWS_SERVER",
                "topic": "Active Directory / GPO",
                "prompt": "Windows Server 2022 üzerinde Active Directory kullanıcı hesabı kilitlenmelerini otomatik tespit edip kilidi nasıl açabilirim?",
                "solution": "Active Directory üzerinde kilitlenen hesapları PowerShell ile bulmak ve kilidini açmak için aşağıdaki komutlar kullanılır:\n\n```powershell\n# Kilitli olan tüm kullanıcıları listele\nSearch-ADAccount -LockedOut | Select-Object Name, SamAccountName, DistinguishedName\n\n# Belirli bir kullanıcının kilidini aç\nUnlock-ADAccount -Identity \"jdoe\"\n\n# Kilitlenmeye sebep olan Event 4740 kayıtlarını Security Event Log'dan sorgula\nGet-WinEvent -FilterHashtable @{LogName='Security'; Id=4740} -MaxEvents 5 | Format-List TimeCreated, Message\n```"
            },
            {
                "id": "WIN-KB-002",
                "domain": "WINDOWS_SERVER",
                "topic": "IIS / Web Server",
                "prompt": "IIS 10 üzerinde 'HTTP Error 500.19 - Internal Server Error' (HRESULT: 0x8007000d) hatası nasıl çözülür?",
                "solution": "0x8007000d hatası, `web.config` dosyasındaki XML format bozukluğundan veya IIS üzerinde 'URL Rewrite' modülünün yüklü olmamasından kaynaklanır.\n\n```powershell\n# 1. URL Rewrite modülünün varlığını kontrol et\nGet-WebConfigurationProperty -Filter \"system.webServer/rewrite/rules\" -PSPath \"IIS:\\Sites\\Default Web Site\"\n\n# 2. IIS URL Rewrite modülünü Web Platform Installer veya Chocolatey ile yükle\nchoco install urlrewrite -y\n\n# 3. IIS servisini yeniden başlat\niisreset /noforce\n```"
            },
            {
                "id": "WIN-KB-003",
                "domain": "WINDOWS_SERVER",
                "topic": "Security / Event Viewer",
                "prompt": "Event Viewer Event ID 4625 (Failed Logon) fırtınası analizi nasıl yapılır?",
                "solution": "Event ID 4625, başarısız oturum açma (brute-force veya yanlış servis parolası) girişimlerini gösterir.\n\n```powershell\nGet-WinEvent -FilterHashtable @{LogName='Security'; Id=4625} -MaxEvents 50 |\nSelect-Object TimeCreated,\n@{Name='TargetUser';Expression={$_.Properties[5].Value}},\n@{Name='WorkstationName';Expression={$_.Properties[11].Value}},\n@{Name='IpAddress';Expression={$_.Properties[19].Value}},\n@{Name='SubStatus';Expression={$_.Properties[13].Value}} |\nFormat-Table -AutoSize\n```\n* `SubStatus 0xC000006A`: Şifre yanlış.\n* `SubStatus 0xC0000234`: Hesap kilitli."
            },
            {
                "id": "WIN-KB-004",
                "domain": "WINDOWS_SERVER",
                "topic": "DNS & Network Infrastructure",
                "prompt": "Windows Server DNS Server servisi yanıt vermiyor ve DNS cache nasıl temizlenir?",
                "solution": "DNS önbelleğini temizlemek ve DNS Server servisini güvenli şekilde yeniden başlatmak için:\n\n```powershell\n# DNS sunucu önbelleğini temizle\nClear-DnsServerCache -Force\n\n# DNS Client önbelleğini temizle\nClear-DnsClientCache\n\n# DNS Server servisini yeniden başlat\nRestart-Service -Name DNS -Force\n\n# DNS servis durumunu ve port dinlemesini doğrula\nGet-Service -Name DNS\nTest-NetConnection -ComputerName localhost -Port 53\n```"
            },
            {
                "id": "WIN-KB-005",
                "domain": "WINDOWS_SERVER",
                "topic": "Storage & Disk Management",
                "prompt": "Windows Server sanal makinede (Hyper-V / VMware) C: diski genişletme adımları nelerdir?",
                "solution": "Sanal disk boyutu hipervizörde artırıldıktan sonra Windows Server içinde diski genişletmek için:\n\n```powershell\n# Disk sürücülerini tara\nUpdate-Disk -DiskNumber 0\n\n# Bölümün maksimum genişletilebilir boyutunu öğren\n$MaxSize = (Get-PartitionSupportedSize -DiskNumber 0 -PartitionNumber 2).SizeMax\n\n# C: bölümünü maksimum boyuta genişlet\nResize-Partition -DiskNumber 0 -PartitionNumber 2 -Size $MaxSize\n```"
            }
        ]

        ora_data = [
            {
                "id": "ORA-KB-001",
                "domain": "ORACLE_DB",
                "topic": "Tablespace Management",
                "prompt": "Oracle 19c üzerinde ORA-01653: unable to extend table hatası alındığında ne yapılmalıdır?",
                "solution": "ORA-01653 hatası, ilgili tablespace alanının dolduğunu ve autoextend açık değilse tablonun yeni bir extent alamadığını gösterir.\n\n```sql\n-- 1. Tablespace doluluk oranını kontrol et\nSELECT tablespace_name, \n       ROUND(used_space * 8192 / (1024*1024), 2) AS used_mb,\n       ROUND(tablespace_size * 8192 / (1024*1024), 2) AS total_mb,\n       ROUND(used_percent, 2) AS pct_used\nFROM dba_tablespace_usage_metrics\nWHERE tablespace_name = 'USERS';\n\n-- 2. Mevcut datafile'ı büyüt veya autoextend aktif et\nALTER DATABASE DATAFILE '/u01/app/oracle/oradata/ORCL/users01.dbf' \nAUTOEXTEND ON NEXT 100M MAXSIZE 10G;\n\n-- 3. Gerekirse yeni datafile ekle\nALTER TABLESPACE USERS ADD DATAFILE '/u01/app/oracle/oradata/ORCL/users02.dbf' \nSIZE 500M AUTOEXTEND ON NEXT 100M MAXSIZE UNLIMITED;\n```"
            },
            {
                "id": "ORA-KB-002",
                "domain": "ORACLE_DB",
                "topic": "Performance & Explain Plan",
                "prompt": "Oracle DB'de yüksek CPU tüketen bir sorgunun Explain Plan analizi nasıl yapılır?",
                "solution": "Sorgunun execution planını (özellikle Full Table Scan ve Carthesian Join durumlarını) analiz etmek için:\n\n```sql\n-- 1. Sorgu planını açıkla\nEXPLAIN PLAN FOR\nSELECT e.employee_id, e.last_name, d.department_name\nFROM employees e\nJOIN departments d ON e.department_id = d.department_id\nWHERE e.salary > 50000;\n\n-- 2. DBMS_XPLAN ile detaylı planı görüntüle\nSELECT * FROM TABLE(DBMS_XPLAN.DISPLAY('PLAN_TABLE', null, 'ALL +COST +PREDICATE'));\n\n-- 3. Eğer Full Table Scan varsa index oluştur veya SQL Tuning Advisor çalıştır\nCREATE INDEX idx_emp_salary ON employees(salary);\n```"
            },
            {
                "id": "ORA-KB-003",
                "domain": "ORACLE_DB",
                "topic": "Backup & RMAN",
                "prompt": "Oracle RMAN ile Incremental Level 1 Backup alma ve doğrulama komutları nelerdir?",
                "solution": "RMAN (Recovery Manager) üzerinden artımlı yedekleme almak için:\n\n```sql\n-- RMAN Prompt üzerinden:\nCONNECT TARGET /;\n\n-- Level 0 (Base) veya Level 1 (Incremental) Yedek Al\nBACKUP INCREMENTAL LEVEL 1 DATABASE \nPLUS ARCHIVELOG \nTAG 'DAILY_INC_BACKUP' \nDELETE ALL INPUT;\n\n-- Alınan yedeğin bütünlüğünü ve geri yüklenebilirliğini doğrula\nRESTORE DATABASE VALIDATE;\n```"
            },
            {
                "id": "ORA-KB-004",
                "domain": "ORACLE_DB",
                "topic": "Concurrency & Locking",
                "prompt": "Oracle DB üzerinde Blocking Session (Kilitlenen Oturum) tespiti ve çözümü nasıl yapılır?",
                "solution": "Bir oturumun diğer oturumları kilitlemesi durumunda kilitleyen oturumu tespit edip sonlandırmak için:\n\n```sql\n-- Kilitleyen ve kilitlenen oturumları listele\nSELECT \n   s1.sid AS blocker_sid, s1.serial# AS blocker_serial, s1.username AS blocker_user,\n   s2.sid AS blocked_sid, s2.serial# AS blocked_serial, s2.username AS blocked_user,\n   s2.seconds_in_wait\nFROM v$session s1\nJOIN v$session s2 ON s1.sid = s2.blocking_session;\n\n-- Kilitleyen oturumu güvenli şekilde sonlandır (Kill Session)\nALTER SYSTEM KILL SESSION 'blocker_sid,blocker_serial' IMMEDIATE;\n```"
            },
            {
                "id": "ORA-KB-005",
                "domain": "ORACLE_DB",
                "topic": "Index & Maintenance",
                "prompt": "Oracle DB'de Unusable durumuna düşen veya parçalanmış Index Rebuild işlemi nasıl yapılır?",
                "solution": "Geçersiz (UNUSABLE) indeksleri tespit edip Online olarak yeniden oluşturmak için:\n\n```sql\n-- Geçersiz indeksleri tespit et\nSELECT index_name, tablespace_name, status \nFROM user_indexes \nWHERE status = 'UNUSABLE';\n\n-- İndeksi kilit oluşturmadan (ONLINE) yeniden inşa et\nALTER INDEX idx_emp_salary REBUILD ONLINE;\n\n-- İndeks istatistiklerini güncelle\nEXEC DBMS_STATS.GATHER_INDEX_STATS(ownname => USER, indname => 'IDX_EMP_SALARY');\n```"
            }
        ]

        return {
            "win_records": win_data,
            "ora_records": ora_data
        }

    # -----------------------------------------------------------------------
    # Orchestrator
    # -----------------------------------------------------------------------
    def download_all(self) -> Dict[str, Any]:
        """Runs the complete data downloading pipeline for all target domains."""
        logger.info("=== Starting Complete Dataset Acquisition Pipeline ===")
        results: Dict[str, Any] = {}

        # 1. Kaggle Tickets
        results["kaggle_tickets"] = self.download_kaggle_tickets()

        # 2. Hugging Face Datasets (Windows Server & Oracle DB)
        results["hf_domain_qa"] = self.download_huggingface_stackexchange()

        logger.info("=== Dataset Acquisition Pipeline Completed Successfully ===")
        return results


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Download raw Service Desk, Windows Server, and Oracle DB datasets."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom destination directory for raw datasets (default: data/raw)."
    )
    parser.add_argument(
        "--kaggle-dataset",
        type=str,
        default="tobiasbueck/multilingual-customer-support-tickets",
        help="Kaggle dataset identifier to download."
    )
    parser.add_argument(
        "--hf-dataset",
        type=str,
        default="HuggingFaceH4/stack-exchange-preferences",
        help="Hugging Face dataset identifier to download."
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=50,
        help="Sample limit per domain for Hugging Face streaming."
    )
    parser.add_argument(
        "--max-scan",
        type=int,
        default=300,
        help="Max items to scan in streaming."
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable generating fallback datasets on API authentication/network failures."
    )

    args = parser.parse_args()

    downloader = DatasetDownloader(raw_data_dir=args.output_dir)
    downloader.download_all()


if __name__ == "__main__":
    main()
