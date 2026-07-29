"""Direct Mapping Resolver — resolves DIRECT_MAPPING fields using canonical sections, tables, blocks, and evidence."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from contracts import (
    CanonicalDocument,
    CanonicalSection,
    CustomExtractionFieldSpec,
    CustomExtractionResult,
    ExtractionStatus,
    SourceReference,
    ValidationStatus,
)
from .normalization import normalize_field_value

logger = logging.getLogger(__name__)


def resolve_direct_mapping(
    canonical_doc: CanonicalDocument,
    spec: CustomExtractionFieldSpec,
) -> CustomExtractionResult:
    """Resolve a single DIRECT_MAPPING field against CanonicalDocument.

    Parameters
    ----------
    canonical_doc : CanonicalDocument
        Canonical document JSON structure.
    spec : CustomExtractionFieldSpec
        Field specification.

    Returns
    -------
    CustomExtractionResult
        Result containing value, provenance, status, and explanation.
    """
    field_id = spec.field_id
    category = spec.category
    subcategory = spec.subcategory
    entity_name = spec.entity_name
    entity_type = spec.entity_type

    # -------------------------------------------------------------------------
    # 1. Check Document Metadata (Company Name, Auditor, Currency, FY End, etc.)
    # -------------------------------------------------------------------------
    meta_res = _find_in_document_metadata(canonical_doc, spec)
    if meta_res:
        return meta_res

    # -------------------------------------------------------------------------
    # 2. Table-type entity lookup (Balance Sheet, P&L, Cash Flow)
    # -------------------------------------------------------------------------
    if spec.expected_value_type.value == "table" or entity_type == "table":
        table_res = _find_table_entity(canonical_doc, spec)
        if table_res:
            return table_res

    # -------------------------------------------------------------------------
    # 3. Check canonical table cell labels (Highest Priority for Financials)
    # -------------------------------------------------------------------------
    table_match, tbl_cell, tbl_prov = _find_in_canonical_tables(canonical_doc, entity_name, spec.synonyms)
    if table_match:
        norm_val, unit, currency = normalize_field_value(table_match.get("raw_text"), spec.expected_value_type.value)
        return CustomExtractionResult(
            field_id=field_id,
            category=category,
            subcategory=subcategory,
            entity_name=entity_name,
            entity_type=entity_type,
            extraction_mode=spec.extraction_mode,
            status=ExtractionStatus.FOUND,
            value_raw=table_match.get("raw_text"),
            value_normalized=norm_val,
            unit=unit,
            currency=currency,
            confidence=0.88,
            explanation=f"Matched canonical table row '{entity_name}' on page {tbl_prov.page_number}.",
            provenance=[tbl_prov],
            validation_status=ValidationStatus.VALIDATED,
        )

    # -------------------------------------------------------------------------
    # 4. Look for pre-extracted structured intelligence in processing_metadata
    # -------------------------------------------------------------------------
    proc_meta = canonical_doc.processing_metadata or {}
    raw_intel = proc_meta.get("raw_extractions", {})
    evidence_map = proc_meta.get("raw_evidence_map", {})

    match_val, match_evidence = _find_in_structured_intelligence(
        raw_intel, evidence_map, category, subcategory, entity_name, spec.synonyms
    )

    if match_val is not None:
        # Prevent severe VLM hallucinations (e.g., lists/dicts for numeric fields)
        expected = spec.expected_value_type.value
        if expected in ("currency_amount", "number", "count", "percentage"):
            if isinstance(match_val, (list, dict)):
                match_val = None
                
    if match_val is not None:
        norm_val, unit, currency = normalize_field_value(match_val, spec.expected_value_type.value)
        page_num = (match_evidence.get("source_page") or 1) if match_evidence else 1
        section_name = match_evidence.get("source_section") if match_evidence else subcategory
        sec_id = _find_section_id(canonical_doc.sections, section_name, page_num)

        return CustomExtractionResult(
            field_id=field_id,
            category=category,
            subcategory=subcategory,
            entity_name=entity_name,
            entity_type=entity_type,
            extraction_mode=spec.extraction_mode,
            status=ExtractionStatus.FOUND,
            value_raw=str(match_val),
            value_normalized=norm_val,
            unit=unit,
            currency=currency,
            confidence=match_evidence.get("confidence", 0.92) if match_evidence else 0.88,
            explanation=f"Matched direct label '{entity_name}' from section '{section_name}' on page {page_num}.",
            provenance=[
                SourceReference(
                    document_id=canonical_doc.document_id,
                    page_number=page_num,
                    section_id=sec_id,
                    raw_text=str(match_evidence.get("source_text_snippet", match_val))[:200] if match_evidence else str(match_val)[:200],
                )
            ],
            validation_status=ValidationStatus.VALIDATED,
        )

    # -------------------------------------------------------------------------
    # 5. Check canonical section matching expected_section_types or synonyms
    # -------------------------------------------------------------------------
    sec_res = _find_section_by_type_or_synonym(canonical_doc, spec)
    if sec_res:
        return sec_res

    # -------------------------------------------------------------------------
    # 6. Regex text pattern matching (Employee Count, Ratios, Numbers)
    # -------------------------------------------------------------------------
    regex_match, reg_prov = _find_by_regex_patterns(canonical_doc, spec)
    if regex_match:
        norm_val, unit, currency = normalize_field_value(regex_match, spec.expected_value_type.value)
        return CustomExtractionResult(
            field_id=field_id,
            category=category,
            subcategory=subcategory,
            entity_name=entity_name,
            entity_type=entity_type,
            extraction_mode=spec.extraction_mode,
            status=ExtractionStatus.FOUND,
            value_raw=regex_match,
            value_normalized=norm_val,
            unit=unit or "count",
            currency=currency,
            confidence=0.82,
            explanation=f"Matched pattern for '{entity_name}' in section '{reg_prov.section_id}' on page {reg_prov.page_number}.",
            provenance=[reg_prov],
            validation_status=ValidationStatus.VALIDATED,
        )

    # -------------------------------------------------------------------------
    # 7. Search text blocks directly
    # -------------------------------------------------------------------------
    text_match, sec_prov = _find_in_canonical_sections(canonical_doc, entity_name, spec.synonyms)
    if text_match:
        norm_val, unit, currency = normalize_field_value(text_match, spec.expected_value_type.value)
        return CustomExtractionResult(
            field_id=field_id,
            category=category,
            subcategory=subcategory,
            entity_name=entity_name,
            entity_type=entity_type,
            extraction_mode=spec.extraction_mode,
            status=ExtractionStatus.FOUND,
            value_raw=text_match,
            value_normalized=norm_val,
            unit=unit,
            currency=currency,
            confidence=0.85,
            explanation=f"Found direct label text match for '{entity_name}' in section '{sec_prov.section_id}'.",
            provenance=[sec_prov],
            validation_status=ValidationStatus.VALIDATED,
        )

    # 8. Field not found
    return CustomExtractionResult(
        field_id=field_id,
        category=category,
        subcategory=subcategory,
        entity_name=entity_name,
        entity_type=entity_type,
        extraction_mode=spec.extraction_mode,
        status=ExtractionStatus.NOT_FOUND,
        confidence=0.0,
        explanation=f"No matching label or section found for '{entity_name}' in CanonicalDocument.",
        validation_status=ValidationStatus.NOT_RUN,
    )


# =============================================================================
# Helper Resolvers
# =============================================================================

def _find_in_document_metadata(
    canonical_doc: CanonicalDocument,
    spec: CustomExtractionFieldSpec,
) -> CustomExtractionResult | None:
    """Check DocumentMetadata for standard metadata fields like Company Name, Auditor, etc."""
    meta = canonical_doc.document_metadata
    e_name = spec.entity_name.lower()
    f_id = spec.field_id.lower()
    syns = [s.lower() for s in spec.synonyms]

    val = None
    exp = ""

    if ("company" in e_name or "company_name" in f_id or "company legal name" in e_name):
        if meta.company_name and meta.company_name != "Unknown Company":
            val = meta.company_name
            exp = "Extracted company legal name from document metadata."
        else:
            # Fallback to source PDF filename clean title
            raw_fn = Path(canonical_doc.source_metadata.file_name).stem
            clean_name = re.sub(r"[\-_]", " ", raw_fn).strip()
            val = clean_name
            exp = "Extracted company name from source PDF document title."
    elif ("auditor" in e_name or "auditor_report" in f_id) and (meta.auditor_name or meta.auditor_opinion):
        val = f"Auditor: {meta.auditor_name or 'N/A'} | Opinion: {meta.auditor_opinion or 'Clean/Unqualified'}"
        exp = "Extracted independent auditor report metadata."
    elif "fy_end" in f_id or "financial_year" in f_id:
        val = meta.fy_end
        exp = "Extracted reporting financial year."

    if val:
        norm_val, unit, currency = normalize_field_value(val, spec.expected_value_type.value)
        return CustomExtractionResult(
            field_id=spec.field_id,
            category=spec.category,
            subcategory=spec.subcategory,
            entity_name=spec.entity_name,
            entity_type=spec.entity_type,
            extraction_mode=spec.extraction_mode,
            status=ExtractionStatus.FOUND,
            value_raw=str(val),
            value_normalized=norm_val,
            unit=unit,
            currency=currency or meta.currency,
            confidence=0.95,
            explanation=exp,
            provenance=[
                SourceReference(
                    document_id=canonical_doc.document_id,
                    page_number=1,
                    raw_text=str(val),
                )
            ],
            validation_status=ValidationStatus.VALIDATED,
        )
    return None


def _find_table_entity(
    canonical_doc: CanonicalDocument,
    spec: CustomExtractionFieldSpec,
) -> CustomExtractionResult | None:
    """Match table entities against canonical tables and sections using candidate scoring and LLM disambiguation."""
    target_terms = [spec.field_id.lower(), spec.subcategory.lower(), spec.entity_name.lower()] + [s.lower() for s in spec.synonyms]
    is_consolidated = "consolidated" in spec.entity_name.lower() or any("consolidated" in s for s in spec.synonyms)
    is_standalone = "standalone" in spec.entity_name.lower() or any("standalone" in s for s in spec.synonyms)

    core_terms = []
    if any(k in spec.entity_name.lower() or k in spec.subcategory.lower() for k in ["balance sheet", "financial position"]):
        core_terms = ["balance sheet", "financial position"]
    elif any(k in spec.entity_name.lower() or k in spec.subcategory.lower() for k in ["profit", "loss", "income"]):
        core_terms = ["profit and loss", "profit & loss", "income statement", "revenue"]
    elif any(k in spec.entity_name.lower() or k in spec.subcategory.lower() for k in ["cash flow"]):
        core_terms = ["cash flow"]
    else:
        core_terms = ["balance sheet", "profit and loss", "cash flow"]

    candidates = []

    # 1. Search Canonical Tables directly
    for tbl in canonical_doc.tables:
        if not tbl.cells:
            continue
            
        # Get table text snippet (first 10 cells / first 3 rows)
        first_cells = sorted(tbl.cells, key=lambda c: (c.row_index, c.column_index))[:15]
        header_text = " ".join((c.raw_text or "") for c in first_cells).lower()

        # Find linked section title if any
        linked_sec = next((s for s in canonical_doc.sections if s.table_ids and tbl.table_id in s.table_ids), None)
        sec_text = (linked_sec.title_raw or linked_sec.title_normalized or "").lower() if linked_sec else ""
        
        combined_text = (header_text + " " + sec_text).strip()

        score = 0
        # Check core term presence
        if any(ct in combined_text for ct in core_terms):
            score += 10
            
        if score > 0:
            if is_consolidated:
                if "consolidated" in combined_text:
                    score += 15
                else:
                    score -= 10
            if is_standalone:
                if "standalone" in combined_text or "standalone" in sec_text:
                    score += 15
                elif "consolidated" in combined_text and "standalone" not in combined_text:
                    score -= 10

            candidates.append({
                "table": tbl,
                "section": linked_sec,
                "score": score,
                "header_snippet": combined_text[:300]
            })

    # Also search Sections if table wasn't directly scored
    for sec in canonical_doc.sections:
        if not sec.table_ids:
            continue
        s_title = (sec.title_raw or sec.title_normalized or "").lower()
        if any(ct in s_title for ct in core_terms):
            tbl_obj = next((t for t in canonical_doc.tables if t.table_id in sec.table_ids and t.cells), None)
            if tbl_obj and not any(c["table"].table_id == tbl_obj.table_id for c in candidates):
                score = 10
                if is_consolidated and "consolidated" in s_title:
                    score += 15
                elif is_standalone and "consolidated" not in s_title:
                    score += 15
                candidates.append({
                    "table": tbl_obj,
                    "section": sec,
                    "score": score,
                    "header_snippet": s_title[:300]
                })

    if not candidates:
        return None

    # Sort candidates by score
    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    # Disambiguate using On-Prem LLM if top 2 candidates are very close
    if len(candidates) > 1 and candidates[1]["score"] > 5 and (best["score"] - candidates[1]["score"]) < 10:
        try:
            from sources.annual_report.llm_config import get_llm
            from sources.annual_report.llm_utils import llm_call_with_retry, extract_json_from_response
            
            llm = get_llm()
            cand_descriptions = []
            for i, c in enumerate(candidates[:3]):
                cand_descriptions.append(f"Option {i}: Table ID '{c['table'].table_id}' (Page {c['table'].page_numbers[0] if c['table'].page_numbers else 1})\nSnippet: {c['header_snippet']}")
                
            prompt = (
                f"You are an expert financial audit assistant.\n"
                f"We are looking for the exact table corresponding to: '{spec.entity_name}'.\n\n"
                f"Here are the candidate tables:\n" + "\n\n".join(cand_descriptions) + "\n\n"
                f"Return a JSON object with 'selected_option_index' (0, 1, or 2) representing the best match. Output JSON ONLY:"
            )
            llm_res = llm_call_with_retry(llm, prompt)
            parsed = extract_json_from_response(llm_res) if llm_res else None
            if parsed and isinstance(parsed, dict) and "selected_option_index" in parsed:
                idx = parsed["selected_option_index"]
                if 0 <= idx < len(candidates[:3]):
                    best = candidates[idx]
        except Exception as e:
            logger.warning(f"LLM table selection failed, falling back to top scored candidate: {e}")

    if best["score"] <= 0:
        return None

    tbl_obj = best["table"]
    linked_sec = best["section"]
    page_no = (tbl_obj.page_numbers[0] if tbl_obj.page_numbers else 1) if not linked_sec else (linked_sec.start_page or 1)

    # Reconstruct the 2D grid
    max_row = max(c.row_index for c in tbl_obj.cells)
    max_col = max(c.column_index for c in tbl_obj.cells)
    grid = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]

    for cell in tbl_obj.cells:
        text = (cell.raw_text or "").replace("\n", " ").strip()
        grid[cell.row_index][cell.column_index] = text

    title = linked_sec.title_raw if linked_sec else f"Table {tbl_obj.table_id}"
    val_summary = f"Table '{title}' [Pages: {page_no}]"
    prov = SourceReference(
        document_id=canonical_doc.document_id,
        page_number=page_no,
        section_id=linked_sec.section_id if linked_sec else tbl_obj.table_id,
        table_id=tbl_obj.table_id,
        raw_text=title,
    )

    return CustomExtractionResult(
        field_id=spec.field_id,
        category=spec.category,
        subcategory=spec.subcategory,
        entity_name=spec.entity_name,
        entity_type=spec.entity_type,
        extraction_mode=spec.extraction_mode,
        status=ExtractionStatus.FOUND,
        value_raw=val_summary,
        value_normalized=grid,
        unit=canonical_doc.document_metadata.unit_denomination,
        currency=canonical_doc.document_metadata.currency,
        confidence=0.95 if best["score"] >= 20 else 0.85,
        explanation=f"Extracted statement table '{title}' (Page {page_no}).",
        provenance=[prov],
        validation_status=ValidationStatus.VALIDATED,
    )


def _find_section_by_type_or_synonym(
    canonical_doc: CanonicalDocument,
    spec: CustomExtractionFieldSpec,
) -> CustomExtractionResult | None:
    """Find a section matching expected_section_types or synonyms and extract its narrative summary."""
    search_types = [t.lower() for t in spec.expected_section_types]
    search_syns = [s.lower() for s in spec.synonyms] + [spec.subcategory.lower()]

    for sec in canonical_doc.sections:
        s_type = (sec.section_type or "").lower()
        sub_cat = (sec.subcategory or "").lower()
        t_raw = (sec.title_raw or "").lower()

        if any(st in s_type or st in sub_cat or st in t_raw for st in search_types + search_syns):
            # Gather text from first block of section
            block_tokens = []
            for b_id in sec.block_ids[:3]:
                blk = next((b for b in canonical_doc.blocks if b.block_id == b_id), None)
                if blk:
                    t_texts = [canonical_doc.token_registry[t].text for t in blk.token_ids if t in canonical_doc.token_registry]
                    if t_texts:
                        block_tokens.append(" ".join(t_texts))

            sec_text = " ".join(block_tokens)[:300] if block_tokens else sec.title_raw
            norm_val, unit, currency = normalize_field_value(sec_text, spec.expected_value_type.value)

            prov = SourceReference(
                document_id=canonical_doc.document_id,
                page_number=sec.start_page or 1,
                section_id=sec.section_id,
                raw_text=sec_text[:200],
            )

            return CustomExtractionResult(
                field_id=spec.field_id,
                category=spec.category,
                subcategory=spec.subcategory,
                entity_name=spec.entity_name,
                entity_type=spec.entity_type,
                extraction_mode=spec.extraction_mode,
                status=ExtractionStatus.FOUND,
                value_raw=sec_text,
                value_normalized=norm_val,
                unit=unit,
                currency=currency,
                confidence=0.88,
                explanation=f"Matched canonical section '{sec.title_raw}' (Type: {sec.section_type}) on page {sec.start_page}.",
                provenance=[prov],
                validation_status=ValidationStatus.VALIDATED,
            )
    return None


def _find_by_regex_patterns(
    canonical_doc: CanonicalDocument,
    spec: CustomExtractionFieldSpec,
) -> tuple[str | None, SourceReference | None]:
    """Search text blocks for numeric/regex patterns like Employee Count."""
    f_id = spec.field_id.lower()
    e_name = spec.entity_name.lower()

    regex_patterns = []
    
    # 1. Employee Count specific patterns
    if "employee" in f_id or "employee" in e_name or "workforce" in f_id or "headcount" in f_id:
        regex_patterns.extend([
            r"(?:total|permanent|regular|active|number of)?\s*(?:employees|workforce|people|headcount|manpower|personnel|staff)\s*(?:count|strength|as on|as at|in employment)?\s*[:\-=]?\s*([\d,]{2,})",
            r"([\d,]{2,})\s*(?:permanent|regular|active|full-time)?\s*(?:employees|workforce|people|personnel|staff)",
            r"(?:employees|workforce|headcount)\s*[:\-=]?\s*([\d,]+)",
        ])

    # 2. Universal Numeric Fallback (Aggressive table scraping from raw text)
    if spec.expected_value_type.value in ("currency_amount", "number"):
        terms = [re.escape(t.strip()) for t in [spec.entity_name] + spec.synonyms if len(t.strip()) > 2]
        if terms:
            terms_joined = "|".join(terms)
            # Matches: Label -> Optional Note Number/Letter -> Numeric Value
            # e.g. "Profit for the period A 12,938.22" -> captures "12,938.22"
            pattern = rf"(?i)(?:{terms_joined})\s*(?:[A-Za-z0-9\-\.]+\s*)?([\d\,\.\(\)]{{2,}})"
            regex_patterns.append(pattern)

    if not regex_patterns:
        return None, None

    # Search universally across all blocks to catch orphans missed by canonicalizer sections
    for blk in canonical_doc.blocks:
        b_tokens = [canonical_doc.token_registry[t].text for t in blk.token_ids if t in canonical_doc.token_registry]
        if not b_tokens:
            continue
            
        b_text = " ".join(b_tokens)
        for pat in regex_patterns:
            match = re.search(pat, b_text, re.IGNORECASE)
            if match:
                matched_val = match.group(1) if match.groups() else match.group(0)
                prov = SourceReference(
                    document_id=canonical_doc.document_id,
                    page_number=blk.page_number,
                    block_id=blk.block_id,
                    token_ids=blk.token_ids,
                    raw_text=b_text[:200],
                )
                return matched_val, prov
                
    return None, None


def _find_in_structured_intelligence(
    raw_intel: dict[str, Any],
    evidence_map: dict[str, Any],
    category: str,
    subcategory: str,
    entity_name: str,
    synonyms: list[str],
) -> tuple[Any, dict[str, Any] | None]:
    """Search for matching value in pre-extracted structured intelligence dict."""
    candidates = [entity_name.lower(), subcategory.lower()] + [s.lower() for s in synonyms]

    for cat_key, sub_dict in raw_intel.items():
        if isinstance(sub_dict, dict):
            for sub_key, val in sub_dict.items():
                sub_lower = sub_key.lower()
                for cand in candidates:
                    if cand in sub_lower or sub_lower in cand:
                        ev = evidence_map.get(sub_key) or evidence_map.get(entity_name)
                        return val, ev

    return None, None


def _find_section_id(sections: list[CanonicalSection], section_name: str | None, page_num: int | None) -> str | None:
    s_lower = section_name.lower() if section_name else ""
    for sec in sections:
        start_p = sec.start_page or 1
        end_p = sec.end_page or start_p
        if page_num is not None and start_p <= page_num <= end_p:
            return sec.section_id
        if s_lower and (s_lower in sec.title_normalized or s_lower in sec.title_raw.lower()):
            return sec.section_id
    return sections[0].section_id if sections else None



def _find_in_canonical_tables(
    doc: CanonicalDocument,
    entity_name: str,
    synonyms: list[str],
) -> tuple[dict[str, Any] | None, Any, SourceReference | None]:
    """Search canonical tables for matching row labels."""
    query_terms = [entity_name.lower()] + [s.lower() for s in synonyms]

    for tbl in doc.tables:
        for cell in tbl.cells:
            if cell.raw_text:
                c_text = cell.raw_text.lower()
                for q in query_terms:
                    if len(q) > 2:
                        import re
                        if re.search(rf'\b{re.escape(q)}\b', c_text):
                            for adj_cell in tbl.cells:
                                if adj_cell.row_index == cell.row_index and adj_cell.column_index > cell.column_index:
                                    if adj_cell.parsed_numeric is not None or any(char.isdigit() for char in adj_cell.raw_text):
                                        prov = SourceReference(
                                            document_id=doc.document_id,
                                            page_number=tbl.page_numbers[0] if tbl.page_numbers else 1,
                                            section_id=tbl.table_id,
                                            table_id=tbl.table_id,
                                            table_index=tbl.table_id,
                                            raw_text=f"{cell.raw_text} -> {adj_cell.raw_text}",
                                        )
                                        val_to_use = str(adj_cell.parsed_numeric) if adj_cell.parsed_numeric is not None else adj_cell.raw_text
                                        return {"raw_text": val_to_use}, adj_cell, prov
    return None, None, None


def _find_in_canonical_sections(
    doc: CanonicalDocument,
    entity_name: str,
    synonyms: list[str],
) -> tuple[str | None, SourceReference | None]:
    """Search text blocks in canonical sections for matching key-value text lines."""
    query_terms = [entity_name.lower()] + [s.lower() for s in synonyms]

    for sec in doc.sections:
        for blk_id in sec.block_ids:
            blk = next((b for b in doc.blocks if b.block_id == blk_id), None)
            if blk:
                block_tokens = [doc.token_registry[t_id].text for t_id in blk.token_ids if t_id in doc.token_registry]
                block_text = " ".join(block_tokens)
                b_lower = block_text.lower()

                for q in query_terms:
                    if q in b_lower:
                        prov = SourceReference(
                            document_id=doc.document_id,
                            page_number=blk.page_number,
                            section_id=sec.section_id,
                            block_id=blk.block_id,
                            token_ids=blk.token_ids,
                            raw_text=block_text[:200],
                        )
                        return block_text, prov
    return None, None
