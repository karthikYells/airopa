"""The job-title dictionary (Section 3.3).

This is the component that decides disqualification, so it must be auditable
and reproducible. It is a dictionary match FIRST; a model is called only for
titles the dictionary does not resolve, and any model-resolved title is written
back here after human review so model cost per title trends to zero.

Matching is done on the normalised title (see title_classifier.normalise):
a phrase is TECH/NON-TECH/IT_SUPPORT if any of its family's representative
substrings appears in the normalised string. The qualifying noun is preserved
in normalisation so that 'manufacturing engineer' and 'software engineer' do
not both collapse to 'engineer'.
"""
from __future__ import annotations

# --- TECH: counts toward disqualification -----------------------------------
TECH_TITLES: dict[str, list[str]] = {
    "software_engineering": [
        "software engineer", "developer", "programmer", "full stack",
        "fullstack", "backend", "back end", "frontend", "front end",
        "mobile developer", "application developer", "web developer",
    ],
    "architecture": [
        "solution architect", "enterprise architect", "technical architect",
        "data architect", "cloud architect", "integration architect",
    ],
    "platform_operations": [
        "devops engineer", "devops", "site reliability engineer", "sre",
        "platform engineer", "cloud engineer", "infrastructure engineer",
        "systems engineer", "network engineer", "database administrator",
        "dba", "middleware engineer", "mainframe developer",
    ],
    "quality_engineering": [
        "qa engineer", "test engineer", "test automation engineer", "sdet",
        "performance engineer",
    ],
    "data_ai": [
        "data engineer", "data scientist", "machine learning engineer",
        "ml engineer", "ai engineer", "analytics engineer", "bi developer",
        "etl developer",
    ],
    "enterprise_applications": [
        "sap consultant", "abap developer", "abap", "sap basis",
        "s4 consultant", "s/4 consultant", "erp consultant",
        "salesforce developer", "dynamics developer", "servicenow developer",
        "workday integration",
    ],
    "security": [
        "security engineer", "cybersecurity analyst", "soc analyst",
        "iam engineer", "application security engineer", "appsec",
    ],
    "product_engineering": [
        "embedded engineer", "firmware engineer", "r&d engineer",
        "plm engineer", "simulation engineer",
    ],
    "technology_management": [
        "cto", "vp engineering", "engineering manager", "technical lead",
        "tech lead", "scrum master", "technical product owner",
        "release manager",
    ],
    "technical_delivery_support": [
        "build engineer", "configuration manager",
    ],
}

# Titles that are TECH only in a technical context (require a code-ish cue).
# Kept explicit so the default bias toward NON-TECH is auditable.
TECH_CONTEXTUAL: dict[str, list[str]] = {
    "contextual": [
        "technical writer", "data analyst",
        "cio located in india", "delivery manager",
        "design engineer",  # CAD/BIM context
    ],
}

# --- IT SUPPORT: tracked separately, does NOT count as tech ------------------
# Local site IT keeps laptops running; that is not a capability centre.
IT_SUPPORT_TITLES: list[str] = [
    "it support", "helpdesk", "help desk", "service desk", "desktop support",
    "it administrator", "end user computing",
]

# --- NON-TECH: does not count ------------------------------------------------
NON_TECH_TITLES: dict[str, list[str]] = {
    "commercial": [
        "sales manager", "account manager", "business development",
        "key account", "inside sales", "sales engineer", "channel manager",
        "distributor manager",
    ],
    "marketing": [
        "marketing manager", "brand", "communications", "digital marketing",
        "content", "events",
    ],
    "people_finance": [
        "hr", "recruiter", "talent acquisition", "payroll", "finance manager",
        "accountant", "controller", "accounts payable", "accounts receivable",
        "treasury", "tax",
    ],
    "supply_chain_plant": [
        "procurement", "purchasing", "sourcing", "buyer", "logistics",
        "warehouse", "planner", "production supervisor", "plant manager",
        "maintenance technician", "quality inspector",
    ],
    "plant_process_engineering": [
        "manufacturing engineer", "process engineer", "industrial engineer",
        "quality engineer", "tool designer", "production engineer",
    ],
    "field_service": [
        "service technician", "field service engineer", "installation engineer",
        "commissioning engineer",
    ],
    "corporate_legal": [
        "legal counsel", "compliance", "company secretary", "admin",
        "office manager", "facilities", "ehs",
    ],
    "country_leadership": [
        "managing director", "country manager", "branch manager",
        "regional head", "general manager",
    ],
}

# --- AMBIGUOUS: never auto-counted; default NON-TECH when context missing -----
# (Section 3.3 ambiguous table — default column is NON-TECH for all.)
AMBIGUOUS_TITLES: dict[str, str] = {
    "engineer": "NON_TECH",          # unqualified
    "project manager": "NON_TECH",
    "analyst": "NON_TECH",
    "consultant": "NON_TECH",
    "product manager": "NON_TECH",
    "designer": "NON_TECH",
    "operations manager": "NON_TECH",
    "automation engineer": "NON_TECH",
    "technical manager": "NON_TECH",
}

# --- Non-English title translations (Section 3.3) ----------------------------
# Maintained here rather than calling a model per title. Maps a foreign phrase
# to an English phrase the dictionaries already understand.
TRANSLATIONS: dict[str, str] = {
    # German
    "softwareentwickler": "software developer",
    "entwickler": "developer",
    "anwendungsentwickler": "application developer",
    "systemadministrator": "it administrator",
    "vertrieb": "sales",
    "vertriebsleiter": "sales manager",
    "einkauf": "purchasing",
    "einkaufer": "buyer",
    "buchhalter": "accountant",
    "personal": "hr",
    "geschaftsfuhrer": "managing director",
    "produktionsleiter": "plant manager",
    "konstrukteur": "design engineer",
    "fertigungsingenieur": "manufacturing engineer",
    # Dutch
    "ontwikkelaar": "developer",
    "softwareontwikkelaar": "software developer",
    "inkoper": "buyer",
    "verkoop": "sales",
    "boekhouder": "accountant",
    "directeur": "managing director",
    # French
    "developpeur": "developer",
    "ingenieur logiciel": "software engineer",
    "ingenieur": "engineer",
    "commercial": "sales",
    "acheteur": "buyer",
    "comptable": "accountant",
    "directeur general": "general manager",
}

# Seniority / grade tokens stripped before matching (Section 3.3).
SENIORITY_TOKENS: list[str] = [
    "senior", "sr", "jr", "junior", "lead", "principal", "staff",
    "associate", "head of", "deputy", "assistant", "trainee", "intern",
    "i", "ii", "iii", "iv", "1", "2", "3", "4",
]
