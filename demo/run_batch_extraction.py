"""Batch Extraction Runner — runs Two-Layer Extraction Engine on a folder of PDFs.

Usage:
    python -m demo.run_batch_extraction --pdf-dir "C:\\Users\\miahmed.ext\\Downloads\\all pdfs" --spec sample_custom_spec.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from canonicalizer import canonicalize_pdf
from extractors.custom_spec import (
    export_custom_extraction_to_excel,
    extract_from_custom_spec,
    load_custom_spec,
)

logger = logging.getLogger("batch_extraction")


def run_batch(pdf_dir: Path, spec_path: Path, output_base: Path):
    if not pdf_dir.exists():
        print(f"Error: PDF directory not found at {pdf_dir}")
        sys.exit(1)

    if not spec_path.exists():
        print(f"Error: Spec file not found at {spec_path}")
        sys.exit(1)

    pdf_files = list(pdf_dir.glob("*.pdf")) + list(pdf_dir.glob("*.PDF"))
    if not pdf_files:
        print(f"No PDF files found in {pdf_dir}")
        return

    print("=" * 85)
    print("      ENTERPRISE BATCH DOCUMENT UNDERSTANDING ENGINE")
    print("=" * 85)
    print(f"  PDF Directory : {pdf_dir}")
    print(f"  Extraction Spec: {spec_path.name}")
    print(f"  Total PDFs Found: {len(pdf_files)}")
    print("-" * 85)

    spec_doc = load_custom_spec(spec_path)
    output_base.mkdir(parents=True, exist_ok=True)

    batch_summary = []

    for idx, pdf_file in enumerate(pdf_files, start=1):
        print(f"\n[{idx}/{len(pdf_files)}] Processing PDF: {pdf_file.name}...")
        t0 = time.time()
        try:
            # 1. Product 1 (Canonicalizer v0)
            canonical_doc = canonicalize_pdf(pdf_path=pdf_file, use_llm_taxonomy=False)

            doc_dir = output_base / pdf_file.stem.replace(" ", "_")
            doc_dir.mkdir(parents=True, exist_ok=True)

            canonical_json_path = doc_dir / "canonical_document.v0.json"
            with open(canonical_json_path, "w", encoding="utf-8") as f:
                f.write(canonical_doc.model_dump_json(indent=2))

            print(f"   ✓ Product 1 CanonicalDocument: {len(canonical_doc.pages)} pages, "
                  f"{len(canonical_doc.sections)} sections, {len(canonical_doc.tables)} tables")

            # 2. Product 2 (Custom Spec Engine)
            result_doc = extract_from_custom_spec(canonical_doc=canonical_doc, spec=spec_doc)

            result_json_path = doc_dir / "custom_extraction_result.json"
            result_excel_path = doc_dir / "custom_extraction_result.xlsx"

            with open(result_json_path, "w", encoding="utf-8") as f:
                f.write(result_doc.model_dump_json(indent=2))

            export_custom_extraction_to_excel(result_doc, output_path=result_excel_path)

            elapsed = time.time() - t0
            stats = result_doc.summary

            print(f"   ✓ Product 2 Custom Extractor: {stats.get('fields_found')}/{stats.get('total_fields_requested')} "
                  f"fields FOUND ({stats.get('completion_rate_pct')}%) [{elapsed:.1f}s]")

            batch_summary.append({
                "pdf_name": pdf_file.name,
                "document_id": canonical_doc.document_id,
                "pages": len(canonical_doc.pages),
                "sections": len(canonical_doc.sections),
                "tables": len(canonical_doc.tables),
                "total_fields": stats.get("total_fields_requested"),
                "found_fields": stats.get("fields_found"),
                "not_found_fields": stats.get("fields_not_found"),
                "completion_pct": stats.get("completion_rate_pct"),
                "elapsed_sec": round(elapsed, 1),
                "excel_path": str(result_excel_path),
                "status": "SUCCESS",
            })

        except Exception as exc:
            elapsed = time.time() - t0
            logger.error(f"Failed processing {pdf_file.name}: {exc}", exc_info=True)
            print(f"   ✗ ERROR: {exc}")
            batch_summary.append({
                "pdf_name": pdf_file.name,
                "document_id": "FAILED",
                "pages": 0,
                "sections": 0,
                "tables": 0,
                "total_fields": len(spec_doc.fields),
                "found_fields": 0,
                "not_found_fields": len(spec_doc.fields),
                "completion_pct": 0.0,
                "elapsed_sec": round(elapsed, 1),
                "excel_path": "",
                "status": f"FAILED: {exc}",
            })

    # Save summary report JSON & Print Table
    summary_json_path = output_base / "batch_summary.json"
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(batch_summary, f, indent=2)

    print("\n" + "=" * 85)
    print("                        BATCH EXTRACTION SUMMARY REPORT")
    print("=" * 85)
    print(f"{'PDF FILE NAME':<32} | {'PAGES':<5} | {'FOUND':<7} | {'PCT %':<6} | {'TIME(s)':<7} | {'STATUS'}")
    print("-" * 85)

    for item in batch_summary:
        fname = item["pdf_name"][:30]
        pages = str(item["pages"])
        found = f"{item['found_fields']}/{item['total_fields']}"
        pct = f"{item['completion_pct']}%"
        sec = f"{item['elapsed_sec']}s"
        st = item["status"][:15]
        print(f"{fname:<32} | {pages:<5} | {found:<7} | {pct:<6} | {sec:<7} | {st}")

    print("-" * 85)
    print(f"Batch report saved to: {summary_json_path}")
    print("=" * 85 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Run Batch Custom Extraction on a directory of PDFs")
    parser.add_argument(
        "--pdf-dir",
        type=str,
        default=r"C:\Users\miahmed.ext\Downloads\all pdfs",
        help="Directory containing company PDF annual reports",
    )
    parser.add_argument(
        "--spec",
        type=str,
        default="sample_custom_spec.json",
        help="Path to custom extraction spec JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory for batch artifacts",
    )

    args = parser.parse_args()
    run_batch(Path(args.pdf-dir if hasattr(args, 'pdf-dir') else args.pdf_dir), Path(args.spec), Path(args.output_dir))


if __name__ == "__main__":
    main()
