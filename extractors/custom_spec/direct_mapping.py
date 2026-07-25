"""Direct Mapping Resolver — resolves DIRECT_MAPPING fields using canonical sections, tables, blocks, and evidence."""

from __future__ import annotations

import logging
import re
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

    # 1. Look for pre-extracted structured intelligence in processing_metadata
    proc_meta = canonical_doc.processing_metadata or {}
    raw_intel = proc_meta.get("raw_extractions", {})
    evidence_map = proc_meta.get("raw_evidence_map", {})

    # Check matching category/subcategory in structured intelligence
    match_val, match_evidence = _find_in_structured_intelligence(
        raw_intel, evidence_map, category, subcategory, entity_name, spec.synonyms
    )

    if match_val is not None:
        norm_val, unit, currency = normalize_field_value(match_val, spec.expected_value_type.value)

        # Build provenance from evidence
        prov_list: list[SourceReference] = []
        page_num = match_evidence.get("source_page", 1) if match_evidence else 1
        section_name = match_evidence.get("source_section") if match_evidence else subcategory

        # Find matching section_id from canonical sections
        sec_id = _find_section_id(canonical_doc.sections, section_name, page_num)

        prov_list.append(
            SourceReference(
                document_id=canonical_doc.document_id,
                page_number=page_num,
                section_id=sec_id,
                raw_text=str(match_evidence.get("source_text_snippet", match_val))[:200] if match_evidence else str(match_val)[:200],
            )
        )

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
            provenance=prov_list,
            validation_status=ValidationStatus.VALIDATED,
        )

    # 2. Check canonical tables
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
            unit=unit or canonical_doc.document_metadata.unit_denomination,
            currency=currency or canonical_doc.document_metadata.currency,
            confidence=0.90,
            explanation=f"Found structured tabular match for '{entity_name}' in table '{tbl_prov.table_id}'.",
            provenance=[tbl_prov],
            validation_status=ValidationStatus.VALIDATED,
        )

    # 3. Search canonical text blocks / sections directly
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

    # 4. Field not found
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

    # Search by category
    for cat_key, sub_dict in raw_intel.items():
        if isinstance(sub_dict, dict):
            for sub_key, val in sub_dict.items():
                sub_lower = sub_key.lower()
                for cand in candidates:
                    if cand in sub_lower or sub_lower in cand:
                        ev = evidence_map.get(sub_key) or evidence_map.get(entity_name)
                        return val, ev

    return None, None


def _find_section_id(sections: list[CanonicalSection], section_name: str, page_num: int) -> str | None:
    s_lower = section_name.lower()
    for sec in sections:
        if sec.start_page <= page_num <= sec.end_page:
            return sec.section_id
        if s_lower in sec.title_normalized or s_lower in sec.title_raw.lower():
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
            if cell.role == "data" and cell.raw_text:
                c_text = cell.raw_text.lower()
                for q in query_terms:
                    if q in c_text:
                        # Find adjacent numeric cell in same row
                        for adj_cell in tbl.cells:
                            if adj_cell.row_index == cell.row_index and adj_cell.column_index > cell.column_index:
                                prov = SourceReference(
                                    document_id=doc.document_id,
                                    page_number=tbl.page_numbers[0] if tbl.page_numbers else 1,
                                    section_id=tbl.table_id,
                                    table_id=tbl.table_id,
                                    cell_id=adj_cell.cell_id,
                                    raw_text=f"{cell.raw_text} -> {adj_cell.raw_text}",
                                )
                                return {"raw_text": adj_cell.raw_text}, adj_cell, prov
    return None, None, None


def _find_in_canonical_sections(
    doc: CanonicalDocument,
    entity_name: str,
    synonyms: list[str],
) -> tuple[str | None, SourceReference | None]:
    """Search text blocks in canonical sections for matching key-value text lines."""
    query_terms = [entity_name.lower()] + [s.lower() for s in synonyms]

    for sec in doc.sections:
        # Check text in blocks for this section
        for blk_id in sec.block_ids:
            # Find block
            for blk in doc.blocks:
                if blk.block_id == blk_id:
                    # Construct text from tokens
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
