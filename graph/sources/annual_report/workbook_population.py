import json
from typing import Any

# The definitive 16 target fields required by the workbook
WORKBOOK_TARGETS = [
    ("Company Information", "Company Profile"),
    ("Company Information", "Business Overview"),
    ("Company Information", "Products & Services"),
    ("Company Information", "Subsidiaries & Group Structure"),
    
    ("Management & Governance", "Board of Directors"),
    ("Management & Governance", "Key Management Personnel"),
    ("Management & Governance", "Corporate Governance"),
    ("Management & Governance", "Board Committees"),
    
    ("Shareholding Information", "Share Capital"),
    ("Shareholding Information", "Shareholding Pattern"),
    ("Shareholding Information", "Major Shareholders"),
    ("Shareholding Information", "Dividend Information"),
    
    ("Management Discussion & Analysis", "Industry Overview"),
    ("Management Discussion & Analysis", "Business Review"),
    ("Management Discussion & Analysis", "Opportunities & Challenges"),
    ("Management Discussion & Analysis", "Future Outlook"),
]

# The definitive alias mapping rules
MAPPING_RULES = {
    "Company Profile": ["company profile", "company overview", "about company", "corporate overview", "incorporation", "business description"],
    "Business Overview": ["business overview", "business model", "industry position", "principal activities", "operating segments"],
    "Products & Services": ["products & services", "product offerings", "business verticals", "products", "services", "offerings", "product list"],
    "Subsidiaries & Group Structure": ["subsidiaries & group structure", "subsidiaries", "associates", "jvs"],
    "Board of Directors": ["board of directors", "board structure", "director tables", "director profiles"],
    "Key Management Personnel": ["key management personnel", "kmp", "cfo", "company secretary", "managing director"],
    "Corporate Governance": ["corporate governance", "corporate governance report", "governance section", "compliance section"],
    "Board Committees": ["board committees", "audit committee", "csr committee", "nrc", "stakeholder committee", "committees"],
    "Share Capital": ["share capital", "balance sheet", "share capital note", "authorized_capital", "paidup_capital"],
    "Shareholding Pattern": ["shareholding pattern", "promoter", "public", "institutions"],
    "Major Shareholders": ["major shareholders", "promoter holdings", "top shareholders"],
    "Dividend Information": ["dividend information", "dividend declared", "dividend"],
    "Industry Overview": ["industry overview", "industry outlook", "railway sector", "market analysis"],
    "Business Review": ["business review", "performance review", "chairman's message", "letter to shareholders"],
    "Opportunities & Challenges": ["opportunities & challenges", "risk factors", "growth drivers", "challenges", "opportunities and risks"],
    "Future Outlook": ["future outlook", "future plans", "targets", "guidance", "outlook"]
}

def _format_value(value: Any) -> str:
    """Flatten structured JSON into a clean string for an Excel cell."""
    if value is None:
        return ""
    
    if isinstance(value, str):
        return value.strip()
        
    if isinstance(value, list):
        formatted_items = []
        for item in value:
            if isinstance(item, str):
                formatted_items.append(f"• {item.strip()}")
            elif isinstance(item, dict):
                # E.g. Board of Directors: {"name": "Kapil Bhatia", "designation": "MD", "type": "Executive"}
                name = item.get("name", "")
                designation = item.get("designation", "")
                typ = item.get("type", "")
                
                parts = []
                if name: parts.append(name)
                if designation: parts.append(designation)
                if typ: parts.append(f"({typ})")
                
                if parts:
                    formatted_items.append(f"• {' - '.join(parts)}")
                else:
                    # Fallback for generic dicts in lists
                    formatted_items.append(f"• {json.dumps(item)}")
        return "\n".join(formatted_items)
        
    if isinstance(value, dict):
        if "dividend_declared" in value:
            return str(value["dividend_declared"])
            
        lines = []
        for k, v in value.items():
            if v:
                clean_k = str(k).replace("_", " ").title()
                if isinstance(v, list):
                    lines.append(f"{clean_k}:")
                    lines.append(_format_value(v))
                else:
                    lines.append(f"{clean_k}: {v}")
        return "\n".join(lines)
        
    return str(value)

def _find_source_info(aliases: list[str], master_sections: list[dict]) -> tuple[str, str]:
    """Find the source page and confidence by checking all aliases against master sections."""
    best_match = None
    
    for sec in master_sections:
        sec_sub = sec.get("normalized_section_name", sec.get("raw_section_name", "")).lower()
        for alias in aliases:
            if alias in sec_sub or sec_sub in alias:
                best_match = sec
                break
        if best_match:
            break
            
    if best_match:
        start_page = best_match.get("start_page")
        end_page = best_match.get("end_page")
        if start_page == end_page:
            pages = f"Page {start_page}"
        else:
            pages = f"Pages {start_page}-{end_page}"
            
        conf = best_match.get("confidence", 0.0)
        return pages, f"{conf:.0%}" if conf > 0 else "N/A"
        
    return "Not Found", "N/A"

def populate_intelligence_report(structured_intelligence: dict, master_sections: list[dict]) -> list[dict]:
    """
    Map the raw structured_intelligence JSON into the strict 16-field 
    format using robust alias mapping and status validation.
    """
    # Flatten the hierarchical structured_intelligence for easier searching
    flat_intel = {}
    for cat, sub_dict in structured_intelligence.items():
        if isinstance(sub_dict, dict):
            for sub, val in sub_dict.items():
                if isinstance(val, dict):
                    for k, v in val.items():
                        flat_intel[k.replace("_", " ").lower()] = v
                flat_intel[sub.lower()] = val

    report_rows = []
    
    for cat, subcat in WORKBOOK_TARGETS:
        aliases = MAPPING_RULES.get(subcat, [subcat.lower()])
        
        extracted_value = ""
        # 1. Exact match on alias
        for alias in aliases:
            if alias in flat_intel and flat_intel[alias]:
                extracted_value = _format_value(flat_intel[alias])
                break
        
        # 2. Try partial match if no exact match
        if not extracted_value:
            for k, v in flat_intel.items():
                for alias in aliases:
                    if (alias in k or k in alias) and v:
                        extracted_value = _format_value(v)
                        break
                if extracted_value:
                    break
        
        # 3. Status logic and fallbacks
        if not extracted_value:
            if subcat == "Subsidiaries & Group Structure":
                status = "NOT APPLICABLE"
                extracted_value = "Not Disclosed / Not Applicable"
            else:
                status = "NOT DISCLOSED"
                extracted_value = "No information found"
                
            pages = "N/A"
            conf = "N/A"
        else:
            status = "FOUND"
            pages, conf = _find_source_info(aliases, master_sections)
            
        report_rows.append({
            "category": cat,
            "subcategory": subcat,
            "extracted_value": extracted_value,
            "source_page": pages,
            "confidence": conf,
            "status": status
        })
        
    return report_rows
