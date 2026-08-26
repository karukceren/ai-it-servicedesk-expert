"""
Data Preprocessing and Chunking Pipeline
=========================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Cleans raw IT tickets, Windows Server, and Oracle DB technical Q&A datasets,
    preserves SQL, PowerShell, and Bash code blocks intact, splits documents into
    semantically coherent chunks (chunk_size=700, chunk_overlap=100) using LangChain's
    RecursiveCharacterTextSplitter, enriches chunks with standardized metadata,
    and exports them to `data/processed/clean_chunks.json`.
"""

import os
import re
import sys
import ast
import html
import json
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DataPreprocessor")


class DataPreprocessor:
    """
    Cleans, structures, and chunks domain-specific technical IT support datasets
    for RAG (Retrieval-Augmented Generation) architectures.
    """

    def __init__(
        self,
        raw_data_dir: Optional[Path] = None,
        processed_data_dir: Optional[Path] = None,
        chunk_size: int = 700,
        chunk_overlap: int = 100
    ):
        """
        Initializes the DataPreprocessor.

        Args:
            raw_data_dir (Path, optional): Directory containing raw JSON/CSV data files.
            processed_data_dir (Path, optional): Directory to save processed clean chunks.
            chunk_size (int): Maximum size of each text chunk (default: 700 chars).
            chunk_overlap (int): Overlap between adjacent chunks (default: 100 chars).
        """
        project_root = Path(__file__).resolve().parent.parent.parent
        self.raw_data_dir = raw_data_dir or (project_root / "data" / "raw")
        self.processed_data_dir = processed_data_dir or (project_root / "data" / "processed")
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Initialize text splitter
        self.text_splitter = self._init_text_splitter()
        logger.info(
            f"DataPreprocessor initialized | Chunk Size: {self.chunk_size}, "
            f"Overlap: {self.chunk_overlap} | Target Dir: {self.processed_data_dir.resolve()}"
        )

    def _init_text_splitter(self):
        """
        Initializes LangChain's RecursiveCharacterTextSplitter with fallback logic.
        """
        try:
            try:
                from langchain_text_splitters import RecursiveCharacterTextSplitter
            except ImportError:
                from langchain.text_splitter import RecursiveCharacterTextSplitter

            logger.info("Using LangChain RecursiveCharacterTextSplitter.")
            return RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n```", "\n\n", "\n", ". ", " ", ""],
                length_function=len
            )
        except ImportError:
            logger.warning(
                "LangChain not found in environment. Using robust built-in RecursiveTextSplitter fallback."
            )
            return self._BuiltinRecursiveSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )

    # -----------------------------------------------------------------------
    # Built-in Fallback Splitter (Exact LangChain Recursive Logic)
    # -----------------------------------------------------------------------
    class _BuiltinRecursiveSplitter:
        def __init__(self, chunk_size: int = 700, chunk_overlap: int = 100):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            self.separators = ["\n\n```", "\n\n", "\n", ". ", " ", ""]

        def split_text(self, text: str) -> List[str]:
            if not text:
                return []
            if len(text) <= self.chunk_size:
                return [text.strip()]

            chunks = []
            start = 0
            while start < len(text):
                end = start + self.chunk_size
                if end >= len(text):
                    final_chunk = text[start:].strip()
                    if final_chunk:
                        chunks.append(final_chunk)
                    break

                split_point = -1
                for sep in self.separators:
                    pos = text.rfind(sep, start + self.chunk_overlap, end)
                    if pos != -1:
                        split_point = pos + len(sep)
                        break

                if split_point == -1 or split_point <= start:
                    split_point = end

                chunk = text[start:split_point].strip()
                if chunk:
                    chunks.append(chunk)
                start = max(split_point - self.chunk_overlap, start + 1)

            return chunks

    # -----------------------------------------------------------------------
    # 1. Regex Cleaning & Code Preservation Engine
    # -----------------------------------------------------------------------
    def clean_text(self, text: str) -> str:
        """
        Cleans raw noisy text while strictly preserving SQL, PowerShell, Bash,
        and general programming code blocks intact.

        Cleaning operations:
            1. Unescapes HTML entities (&amp;, &lt;, &gt;, &quot;, &#39;, &nbsp;).
            2. Converts HTML code blocks (<pre><code>, <code>) to Markdown blocks.
            3. Isolates and protects all code blocks (```...``` and `...`) with placeholders.
            4. Removes remaining HTML tags (<p>, <a>, <ul>, <li>, <div>, etc.).
            5. Sanitizes email addresses to prevent PII exposure.
            6. Strips email signatures, boilerplate footers, and mobile signatures.
            7. Normalizes excessive whitespace and meaningless control characters.
            8. Restores all original code blocks in their exact form.

        Args:
            text (str): Raw input text.

        Returns:
            str: Cleaned and normalized text with code blocks preserved.
        """
        if not text or not isinstance(text, str):
            return ""

        # Step 1: Decode HTML entities
        cleaned = html.unescape(text)

        # Step 2: Convert HTML code tags to Markdown format
        cleaned = re.sub(
            r"<pre>\s*<code(?:\s+class=[\"']?([a-zA-Z0-9_-]*)[\"']?)?>([\s\S]*?)</code>\s*</pre>",
            lambda m: f"\n\n```{m.group(1) or ''}\n{m.group(2).strip()}\n```\n\n",
            cleaned,
            flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"<code>([\s\S]*?)</code>",
            lambda m: f"`{m.group(1).strip()}`",
            cleaned,
            flags=re.IGNORECASE
        )

        # Step 3: Isolate and protect Markdown code blocks with temporary placeholders
        code_blocks = []

        def replace_code_block(match):
            code_blocks.append(match.group(0))
            return f"__PRESERVED_CODE_BLOCK_{len(code_blocks)-1}__"

        # Regex for fenced code blocks (```language ... ```) and inline code (`...`)
        protected_text = re.sub(r"```[\s\S]*?```", replace_code_block, cleaned)
        protected_text = re.sub(r"`[^`\n]+`", replace_code_block, protected_text)

        # Step 4: Remove remaining HTML tags
        cleaned = re.sub(r"<[^>]+>", " ", protected_text)

        # Step 5: Sanitize email addresses to protect PII
        cleaned = re.sub(
            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            "[EMAIL_REDACTED]",
            cleaned
        )

        # Step 6: Remove signature / boilerplate footers
        signature_patterns = [
            r"(?i)\b(best regards|kind regards|warm regards|regards|saygılarımla|iyi çalışmalar|teşekkürler|thanks & regards|thanks in advance|many thanks)[\s\S]*$",
            r"(?i)\b(sent from my (iphone|android|galaxy|ipad|device|mobile|outlook))[\s\S]*$",
            r"(?i)\b(confidentiality notice|this email and any files transmitted with it)[\s\S]*$"
        ]
        for pattern in signature_patterns:
            cleaned = re.sub(pattern, "", cleaned)

        # Step 7: Normalize whitespace and remove non-printable control characters
        cleaned = re.sub(r"[\r\t]+", " ", cleaned)
        cleaned = re.sub(r"[^\S\n]+", " ", cleaned)
        cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)

        # Step 8: Restore preserved code blocks
        for idx, original_code in enumerate(code_blocks):
            placeholder = f"__PRESERVED_CODE_BLOCK_{idx}__"
            cleaned = cleaned.replace(placeholder, original_code.strip())

        return cleaned.strip()

    def _extract_solution_content(self, solution_val: Any) -> str:
        """
        Extracts clean textual content from solution fields, handling both raw text
        and serialized/native list-of-answers structures from HuggingFace/StackExchange.
        """
        if not solution_val:
            return ""

        if isinstance(solution_val, str):
            val_str = solution_val.strip()
            if val_str.startswith("[") and ("text" in val_str or "answer_id" in val_str):
                try:
                    parsed = ast.literal_eval(val_str)
                    if isinstance(parsed, list):
                        selected = [a["text"] for a in parsed if isinstance(a, dict) and a.get("selected")]
                        if not selected:
                            selected = [a["text"] for a in parsed if isinstance(a, dict) and "text" in a]
                        return "\n\n".join(selected)
                except Exception:
                    pass
            return solution_val

        elif isinstance(solution_val, list):
            selected = [a["text"] for a in solution_val if isinstance(a, dict) and a.get("selected")]
            if not selected:
                selected = [a["text"] for a in solution_val if isinstance(a, dict) and "text" in a]
            return "\n\n".join(selected)

        return str(solution_val)

    # -----------------------------------------------------------------------
    # 2. Dataset Loaders & Normalizers
    # -----------------------------------------------------------------------
    def process_service_desk_tickets(self) -> List[Dict[str, Any]]:
        """
        Loads, cleans, and chunks Service Desk tickets into RAG-ready chunks.
        """
        ticket_file = self.raw_data_dir / "kaggle_tickets" / "service_desk_tickets.json"
        if not ticket_file.exists():
            ticket_file = self.raw_data_dir / "service_desk_tickets.json"

        if not ticket_file.exists():
            logger.warning(f"Service desk tickets file not found at: {ticket_file}")
            return []

        logger.info(f"Processing Service Desk Tickets from {ticket_file}...")
        with open(ticket_file, "r", encoding="utf-8") as f:
            raw_tickets = json.load(f)

        source_name = "service_desk_tickets.json"
        category = "service_desk"
        processed_chunks = []

        for item in raw_tickets:
            tck_id = item.get("ticket_id", f"TCK-{uuid.uuid4().hex[:6].upper()}")
            subcategory = item.get("category", "General Support")
            priority = item.get("priority", "Normal")
            subject = item.get("subject", "IT Support Request")
            description = self.clean_text(item.get("description", ""))
            resolution = self.clean_text(
                self._extract_solution_content(item.get("resolution", item.get("solution", "")))
            )

            # Assemble coherent domain document representation
            doc_content = (
                f"TICKET ID: {tck_id}\n"
                f"Kategori: {subcategory} | Öncelik: {priority}\n"
                f"Konu: {subject}\n"
                f"Problem Açıklaması:\n{description}\n\n"
                f"Çözüm ve Uygulanan Adımlar:\n{resolution}"
            ).strip()

            splits = self.text_splitter.split_text(doc_content)
            for idx, chunk_text in enumerate(splits):
                chunk_uuid = str(uuid.uuid4())
                chunk_entry = {
                    "chunk_id": chunk_uuid,
                    "content": chunk_text,
                    "chunk_content": chunk_text,
                    "source": source_name,
                    "category": category,
                    "metadata": {
                        "chunk_id": chunk_uuid,
                        "source": source_name,
                        "category": category,
                        "original_id": tck_id,
                        "title": subject,
                        "subcategory": subcategory,
                        "priority": priority,
                        "domain_tag": "SERVICE_DESK",
                        "chunk_index": idx,
                        "total_chunks": len(splits)
                    }
                }
                processed_chunks.append(chunk_entry)

        logger.info(f"Extracted {len(processed_chunks)} chunks from {len(raw_tickets)} Service Desk tickets.")
        return processed_chunks

    def process_technical_qa_file(
        self,
        file_path: Path,
        category: str,
        domain_tag: str
    ) -> List[Dict[str, Any]]:
        """
        Loads, cleans, and chunks domain technical Q&A datasets (Windows Server / Oracle DB).

        Args:
            file_path (Path): Path to JSON dataset file.
            category (str): Target category ('windows_server' or 'oracle_db').
            domain_tag (str): Specific domain tag ('WINDOWS_SERVER' or 'ORACLE_DB').

        Returns:
            List[Dict[str, Any]]: List of chunked and metadata-enriched documents.
        """
        if not file_path.exists():
            logger.warning(f"Technical dataset file not found at: {file_path}")
            return []

        logger.info(f"Processing {category} technical Q&A from {file_path}...")
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        source_name = file_path.name
        processed_chunks = []

        for item in raw_data:
            item_id = item.get("id", f"KB-{uuid.uuid4().hex[:6].upper()}")
            topic = item.get("topic", item.get("category", category.replace("_", " ").title()))
            prompt = self.clean_text(item.get("prompt", item.get("question", "")))
            solution_raw = self._extract_solution_content(item.get("solution", item.get("response", "")))
            solution = self.clean_text(solution_raw)

            if not prompt or not solution:
                continue

            doc_content = (
                f"UZMANLIK ALANI: {category.upper()}\n"
                f"Konu / Başlık: {topic}\n"
                f"Soru / Problem Senaryosu:\n{prompt}\n\n"
                f"Uzman Çözüm ve Teknik Adımlar:\n{solution}"
            ).strip()

            splits = self.text_splitter.split_text(doc_content)
            for idx, chunk_text in enumerate(splits):
                chunk_uuid = str(uuid.uuid4())
                chunk_entry = {
                    "chunk_id": chunk_uuid,
                    "content": chunk_text,
                    "chunk_content": chunk_text,
                    "source": source_name,
                    "category": category,
                    "metadata": {
                        "chunk_id": chunk_uuid,
                        "source": source_name,
                        "category": category,
                        "original_id": item_id,
                        "title": topic,
                        "subcategory": topic,
                        "domain_tag": domain_tag,
                        "chunk_index": idx,
                        "total_chunks": len(splits)
                    }
                }
                processed_chunks.append(chunk_entry)

        logger.info(f"Extracted {len(processed_chunks)} chunks from {len(raw_data)} {category} records.")
        return processed_chunks

    # -----------------------------------------------------------------------
    # 3. Main Pipeline Orchestrator
    # -----------------------------------------------------------------------
    def run_pipeline(self) -> Path:
        """
        Executes the complete cleaning, chunking, and metadata enrichment pipeline.
        Saves the output to `data/processed/clean_chunks.json`.

        Returns:
            Path: Absolute path to the generated `clean_chunks.json` file.
        """
        logger.info("=== Starting Data Preprocessing & Chunking Pipeline ===")
        all_chunks: List[Dict[str, Any]] = []

        # 1. Service Desk Tickets
        ticket_chunks = self.process_service_desk_tickets()
        all_chunks.extend(ticket_chunks)

        # 2. Windows Server Technical Q&A
        win_file = self.raw_data_dir / "stackexchange_windows_server.json"
        win_chunks = self.process_technical_qa_file(
            file_path=win_file,
            category="windows_server",
            domain_tag="WINDOWS_SERVER"
        )
        all_chunks.extend(win_chunks)

        # 3. Oracle DB Technical Q&A
        ora_file = self.raw_data_dir / "stackexchange_oracle_db.json"
        ora_chunks = self.process_technical_qa_file(
            file_path=ora_file,
            category="oracle_db",
            domain_tag="ORACLE_DB"
        )
        all_chunks.extend(ora_chunks)

        # Export Output to JSON
        output_file = self.processed_data_dir / "clean_chunks.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)

        # Log & Print Final Statistics
        total_chunks = len(all_chunks)
        logger.info("=== Pipeline Finished Successfully ===")
        logger.info(f"Total Chunks Generated: {total_chunks}")
        logger.info(f"  - Service Desk:   {len(ticket_chunks)} chunks")
        logger.info(f"  - Windows Server: {len(win_chunks)} chunks")
        logger.info(f"  - Oracle DB:      {len(ora_chunks)} chunks")
        logger.info(f"Processed chunks exported to: {output_file.resolve()}")

        print("\n=======================================================")
        print(f"  TOPLAM ÜRETİLEN CHUNK SAYISI : {total_chunks}")
        print(f"  - Servis Masası (Service Desk): {len(ticket_chunks)} chunk")
        print(f"  - Windows Server Uzmanlığı     : {len(win_chunks)} chunk")
        print(f"  - Oracle DB Uzmanlığı          : {len(ora_chunks)} chunk")
        print(f"  Çıktı Dosyası: {output_file.resolve()}")
        print("=======================================================\n")

        return output_file


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------
def main():
    """CLI Execution entry point."""
    preprocessor = DataPreprocessor(chunk_size=700, chunk_overlap=100)
    output_path = preprocessor.run_pipeline()
    print(f"[OK] Preprocessing completed. Chunks saved to: {output_path}")


if __name__ == "__main__":
    main()
