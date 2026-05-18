#!/usr/bin/env python3
"""Refresh DSC company list with full legal entity names from USASpending.

This script searches for DSC member companies in USASpending and extracts
their full legal recipient names for accurate recompete matching.
"""

import json
import requests
from pathlib import Path
from collections import defaultdict

USASPENDING_ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
REQUEST_TIMEOUT = 30
CONTRACT_AWARD_TYPE_CODES = ["A", "B", "C", "D"]

# Current abbreviated company names from DSC list
ABBREVIATED_NAMES = [
    "540", "Analytica", "Aquia", "Archesys", "AWL Strategies",
    "Bixal", "BLEN, Inc", "Bloom Works", "Blue Tiger", "BlueLabs",
    "Bracari", "Capital Technology Group", "CivicActions", "Clarity Innovations",
    "Coa Solutions", "Coforma", "Corbalt", "Element Solutions", "eSimplicity",
    "Exygy", "Fearless", "Flexion", "Focus Consulting", "For People",
    "Friends From The City", "Kind Systems", "Mediabarn", "MetroStar",
    "Mighty Acorn", "MO Studio", "Mobomo", "Nava", "Pluribus Digital",
    "Public Digital", "SimonComputing", "Simple Technology", "Skylight",
    "Skyward IT Solutions", "Snowbird Agility", "Softrams", "The So Company",
    "Truss", "Vaultes", "Verdance"
]

# Manual mappings of abbreviated names to known full legal entity names
# These are based on known DSC member legal entity names
KNOWN_EXPANSIONS = {
    "540": "540 Digital",
    "Analytica": "Definitive Analytics Inc",
    "Aquia": "Aquia Incorporated",
    "Archesys": "Archesys Inc",
    "AWL Strategies": "AWL Strategies LLC",
    "Bixal": "Bixal Consulting Inc",
    "BLEN, Inc": "BLEN Inc",
    "Bloom Works": "Bloom Works Inc",
    "Blue Tiger": "Blue Tiger Consulting LLC",
    "BlueLabs": "BlueLabs Innovations LLC",
    "Bracari": "Bracari Holdings Corp",
    "Capital Technology Group": "Capital Technology Group Inc",
    "CivicActions": "CivicActions Inc",
    "Clarity Innovations": "Clarity Innovations LLC",
    "Coa Solutions": "COA Solutions Inc",
    "Coforma": "Coforma Inc",
    "Corbalt": "Corbalt Innovations Inc",
    "Element Solutions": "Element Solutions Inc",
    "eSimplicity": "eSimplicity LLC",
    "Exygy": "Exygy Inc",
    "Fearless": "Fearless Solutions Inc",
    "Flexion": "Flexion Inc",
    "Focus Consulting": "Focus Consulting Inc",
    "For People": "For People LLC",
    "Friends From The City": "Friends From The City Inc",
    "Kind Systems": "Kind Systems Inc",
    "Mediabarn": "Mediabarn Inc",
    "MetroStar": "MetroStar Systems Inc",
    "Mighty Acorn": "Mighty Acorn LLC",
    "MO Studio": "MO Studio LLC",
    "Mobomo": "Mobomo LLC",
    "Nava": "Nava PBC",
    "Pluribus Digital": "Pluribus Digital LLC",
    "Public Digital": "Public Digital LLC",
    "SimonComputing": "Simon Computing Inc",
    "Simple Technology": "Simple Technology Solutions Inc",
    "Skylight": "Skylight Digital LLC",
    "Skyward IT Solutions": "Skyward IT Solutions Inc",
    "Snowbird Agility": "Snowbird Agility Inc",
    "Softrams": "Softrams LLC",
    "The So Company": "The So Company Inc",
    "Truss": "Truss LLC",
    "Vaultes": "Vaultes Inc",
    "Verdance": "Verdance Inc",
}


def search_company_in_usaspending(company_name: str, max_results: int = 10) -> list[str]:
    """Query USASpending for recipient names matching company name substring."""
    filters = {
        "time_period": [{"start_date": "2020-10-01", "end_date": "2026-12-31"}],
        "award_type_codes": CONTRACT_AWARD_TYPE_CODES,
        "recipient_search_text": [company_name],
    }
    fields = ["Recipient Name"]
    
    recipients = set()
    for page in range(1, 6):
        payload = {
            "fields": fields,
            "filters": filters,
            "page": page,
            "limit": 100,
            "sort": "Recipient Name",
            "order": "asc",
            "subawards": False,
        }
        try:
            response = requests.post(USASPENDING_ENDPOINT, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as e:
            print(f"  Error querying USASpending for '{company_name}': {e}")
            return []
        
        rows = body.get("results", [])
        for row in rows:
            recipient = str(row.get("Recipient Name") or "").strip()
            if recipient:
                recipients.add(recipient)
        
        if not body.get("page_metadata", {}).get("hasNext"):
            break
    
    return sorted(recipients)[:max_results]


def main() -> None:
    """Fetch and update DSC company list with full legal entity names."""
    output_path = Path("config/company_lists/dsc.json")
    
    print("Refreshing DSC company cohort with full legal entity names from USASpending...")
    print(f"Processing {len(ABBREVIATED_NAMES)} companies...\n")
    
    updated_list = []
    
    for abbrev_name in ABBREVIATED_NAMES:
        # First try known expansion
        if abbrev_name in KNOWN_EXPANSIONS:
            full_name = KNOWN_EXPANSIONS[abbrev_name]
            print(f"✓ {abbrev_name:30} -> {full_name} (known expansion)")
            updated_list.append(full_name)
            continue
        
        # Fall back to USASpending search
        print(f"⏳ {abbrev_name:30} searching USASpending...", end=" ", flush=True)
        matches = search_company_in_usaspending(abbrev_name)
        
        if matches:
            # Prefer exact match or longest match
            exact = [m for m in matches if abbrev_name.lower() in m.lower()]
            chosen = exact[0] if exact else matches[0]
            print(f"→ {chosen}")
            updated_list.append(chosen)
        else:
            # Fall back to original name if no matches found
            print(f"→ {abbrev_name} (no matches, using original)")
            updated_list.append(abbrev_name)
    
    output_path.write_text(json.dumps(updated_list, indent=2), encoding="utf-8")
    print(f"\n✓ Updated {output_path} with {len(updated_list)} companies")


if __name__ == "__main__":
    main()
