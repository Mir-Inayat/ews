import json
import logging
import re
from typing import Any, Optional

from .llm_utils import llm_call_with_retry

logger = logging.getLogger(__name__)

def _extract_json_from_llm(llm: Any, prompt: str, max_retries: int = 2) -> dict | list | None:
    """Helper to extract JSON from the LLM response."""
    if not llm:
        logger.warning("[ContentExtractor] No LLM provided for extraction.")
        return None
        
    try:
        response_text = llm_call_with_retry(llm, prompt, max_retries=max_retries)
        if not response_text:
            return None
            
        # Try to find a JSON block in the response
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
        json_str = match.group(1) if match else response_text
        
        # Clean up in case there are stray characters
        json_str = json_str.strip()
        if not json_str:
            return None
            
        return json.loads(json_str)
    except Exception as exc:
        logger.error(f"[ContentExtractor] LLM JSON extraction failed: {exc}")
        return None

def extract_subcategory_content(category: str, subcategory: str, text: str, llm: Any = None) -> Any:
    """
    Route to the appropriate subcategory extraction logic.
    Returns structured data (dict or list) extracted from the text.
    """
    # Truncate text to avoid massive token costs/limits just in case
    # Cap at ~20,000 characters for text extraction
    truncated_text = text[:20000] 
    
    sub_lower = subcategory.lower()
    
    import re
    
    # Import the exact alias mapping rules to reliably route Unclassified sections
    try:
        from .workbook_population import MAPPING_RULES
    except ImportError:
        MAPPING_RULES = {}
        
    def _clean_str(s: str) -> str:
        s = s.lower()
        s = re.sub(r'\b(the|and|of|in|to)\b', '', s)
        s = re.sub(r'[^a-z0-9]', '', s)
        return s

    def matches_target(target_name: str) -> bool:
        aliases = MAPPING_RULES.get(target_name, [target_name.lower()])
        clean_sub = _clean_str(subcategory)
        for alias in aliases:
            clean_alias = _clean_str(alias)
            if clean_alias and (clean_alias in clean_sub or clean_sub in clean_alias):
                return True
        return False

    text_head = truncated_text.lower()[:500]

    # --- Governance ---
    if matches_target("Board of Directors") or (category == "Management & Governance" and "board" in sub_lower) or "board of directors" in text_head:
        return _extract_board_of_directors(truncated_text, llm)
    elif matches_target("Key Management Personnel") or (category == "Management & Governance" and ("kmp" in sub_lower or "personnel" in sub_lower)) or "key management personnel" in text_head:
        return _extract_kmp(truncated_text, llm)
    elif matches_target("Board Committees") or (category == "Management & Governance" and "committee" in sub_lower) or "audit committee" in text_head or "remuneration committee" in text_head:
        return _extract_committees(truncated_text, llm)
    elif matches_target("Corporate Governance") or category == "Management & Governance" or "corporate governance" in text_head:
        return _extract_corporate_governance(truncated_text, llm)
        
    # --- Shareholding ---
    elif matches_target("Share Capital") or (category == "Shareholding Information" and "capital" in sub_lower) or "share capital" in text_head:
        return _extract_share_capital(truncated_text, llm)
    elif matches_target("Shareholding Pattern") or matches_target("Major Shareholders") or (category == "Shareholding Information" and "pattern" in sub_lower) or "shareholding pattern" in text_head:
        return _extract_shareholding_pattern(truncated_text, llm)
    elif matches_target("Dividend Information") or (category == "Shareholding Information" and "dividend" in sub_lower) or "dividend" in text_head:
        return _extract_dividend(truncated_text, llm)
        
    # --- Company Information ---
    elif matches_target("Company Profile") or (category == "Company Information" and "profile" in sub_lower) or "company profile" in text_head or "about the company" in text_head:
        return _extract_company_profile(truncated_text, llm)
    elif matches_target("Business Overview") or matches_target("Business Review") or (category == "Company Information" and "overview" in sub_lower) or "business review" in text_head:
        return _extract_business_overview(truncated_text, llm)
    elif matches_target("Products & Services") or (category == "Company Information" and ("product" in sub_lower or "service" in sub_lower)) or "product offering" in text_head:
        return _extract_products_services(truncated_text, llm)
    elif matches_target("Subsidiaries & Group Structure") or (category == "Company Information" and "subsidiari" in sub_lower) or "subsidiaries" in text_head:
        return _extract_subsidiaries(truncated_text, llm)
        
    # --- MD&A ---
    # MD&A targets are usually extracted from a single MD&A section
    elif "management discussion" in sub_lower or "md&a" in sub_lower or matches_target("Industry Overview") or matches_target("Opportunities & Challenges") or matches_target("Future Outlook") or category == "Management Discussion & Analysis" or "management discussion and analysis" in text_head or "md&a" in text_head:
        return _extract_mda(truncated_text, llm)
        
    return None

# =====================================================================
# Extractors
# =====================================================================

def _extract_board_of_directors(text: str, llm: Any) -> list:
    prompt = f"""You are a financial analyst extracting the Board of Directors from an annual report.
Extract the board members as a JSON list of objects. Do not include any other text.
Each object should have:
- "name": string
- "designation": string
- "type": string (e.g. "Executive", "Non-Executive", "Independent")

Text:
{text}

Output JSON list:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, list) else []

def _extract_committees(text: str, llm: Any) -> list:
    prompt = f"""Extract the names of the Board Committees mentioned in the text (e.g. Audit Committee, CSR Committee).
Output a simple JSON list of strings.

Text:
{text}

Output JSON list:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, list) else []

def _extract_corporate_governance(text: str, llm: Any) -> dict:
    prompt = f"""You are a corporate governance analyst. Extract a brief summary of the corporate governance practices, policies, and philosophy of the company.
Output a JSON object with:
- "governance_philosophy": string (brief summary)
- "policies": list of strings (e.g., Whistle Blower Policy, Code of Conduct)
If no details are found, return {{}}.

Text:
{text}

Output JSON object:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, dict) else {}

def _extract_kmp(text: str, llm: Any) -> list:
    prompt = f"""Extract the Key Management Personnel (KMP) from the text.
Output a JSON list of objects, each with "name" and "designation".

Text:
{text}

Output JSON list:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, list) else []

def _extract_committees(text: str, llm: Any) -> list:
    prompt = f"""Extract the names of the Board Committees mentioned in the text (e.g. Audit Committee, CSR Committee).
Output a simple JSON list of strings.

Text:
{text}

Output JSON list:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, list) else []

def _extract_share_capital(text: str, llm: Any) -> dict:
    prompt = f"""Extract the Share Capital details from the text.
Output a JSON object with:
- "authorized_capital": string/number
- "paidup_capital": string/number

Text:
{text}

Output JSON object:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, dict) else {}

def _extract_shareholding_pattern(text: str, llm: Any) -> dict:
    prompt = f"""Extract the Shareholding Pattern percentage breakdown from the text.
Output a JSON object with:
- "promoter": string (percentage)
- "public": string (percentage)
- "institutions": string (percentage)

If a value is not found, use null.

Text:
{text}

Output JSON object:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, dict) else {}

def _extract_dividend(text: str, llm: Any) -> dict:
    # Example heuristic: regex for dividend
    match = re.search(r'(?i)dividend\s*(?:of|@)\s*(?:rs\.?|inr|₹)?\s*([\d\.]+)\s*(?:per share|/-|/ share|%|\b)', text)
    if match:
        return {"dividend_declared": match.group(1)}
        
    prompt = f"""Extract the declared dividend (per share or percentage) from the text.
Output a JSON object with a single key "dividend_declared". If not found, output {{}}.

Text:
{text}

Output JSON object:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, dict) else {}

def _extract_company_profile(text: str, llm: Any) -> dict:
    prompt = f"""Extract the Company Profile details from the text.
Output a JSON object with:
- "incorporation": string (year or details)
- "business_description": string (short summary)
- "manufacturing_locations": list of strings
- "certifications": list of strings

Text:
{text}

Output JSON object:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, dict) else {}

def _extract_business_overview(text: str, llm: Any) -> dict:
    prompt = f"""Extract the Business Overview from the text.
Output a JSON object with:
- "business_model": string
- "operating_segments": list of strings
- "key_markets": list of strings

Text:
{text}

Output JSON object:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, dict) else {}

def _extract_products_services(text: str, llm: Any) -> dict:
    prompt = f"""Extract the Products & Services from the text.
Output a JSON object with:
- "product_list": list of strings
- "offerings": list of strings
- "services": list of strings

Text:
{text}

Output JSON object:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, dict) else {}

def _extract_subsidiaries(text: str, llm: Any) -> dict:
    prompt = f"""Extract the Subsidiaries and Group Structure from the text.
Output a JSON object with:
- "subsidiaries": list of strings
- "associates": list of strings
- "jvs": list of strings (Joint Ventures)

Text:
{text}

Output JSON object:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, dict) else {}

def _extract_mda(text: str, llm: Any) -> dict:
    prompt = f"""You are a financial analyst reading the Management Discussion & Analysis (MD&A) section.
Extract the key points into a structured JSON object. Focus on the most important highlights.
Output a JSON object with:
- "industry_overview": string (summary of industry trends)
- "business_review": string (summary of operational/financial performance, e.g., revenue growth, EBITDA)
- "opportunities_and_risks": list of strings (growth drivers, competition, raw material costs, etc.)
- "future_outlook": string (guidance, targets for next FY, expansion plans)

Text:
{text}

Output JSON object:
"""
    result = _extract_json_from_llm(llm, prompt)
    return result if isinstance(result, dict) else {}
