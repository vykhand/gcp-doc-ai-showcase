"""
Configuration for GCP Document AI processors, categories, colors, and constants.
"""

from typing import Dict, List, Any

# GCP Document AI constants
GCP_DOCAI_LOCATIONS = ["us", "eu"]
GCP_DOCAI_DEFAULT_LOCATION = "us"

# Processor type definitions
# These define the known processor types. Actual processor IDs are project-specific
# and discovered via list_processors() or configured manually.
GCP_DOCAI_PROCESSORS = {
    "OCR_PROCESSOR": {
        "name": "Enterprise Document OCR",
        "description": "Extract text, handwriting, and layout from documents with high accuracy",
        "category": "General",
        "gcp_type": "OCR_PROCESSOR",
        "capabilities": ["text", "handwriting", "layout", "languages"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": False,
        "icon": "📖"
    },
    "FORM_PARSER_PROCESSOR": {
        "name": "Form Parser",
        "description": "Extract form fields (key-value pairs), tables, and checkboxes from structured documents",
        "category": "General",
        "gcp_type": "FORM_PARSER_PROCESSOR",
        "capabilities": ["text", "tables", "form_fields", "checkboxes"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": False,
        "icon": "📋"
    },
    "LAYOUT_PARSER_PROCESSOR": {
        "name": "Layout Parser",
        "description": (
            "Detect document layout (headings, paragraphs, lists, tables) and create "
            "RAG-ready chunks. Gemini-powered versions add figure/chart/table "
            "descriptions and improved reading order. Also supports DOCX, PPTX, XLSX, XLSM."
        ),
        "category": "General",
        "gcp_type": "LAYOUT_PARSER_PROCESSOR",
        "capabilities": ["text", "layout", "paragraphs", "tables", "headings", "chunks", "figures"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp", "docx", "pptx", "xlsx", "xlsm"],
        "entity_extraction": False,
        "icon": "📐"
    },
    "CUSTOM_EXTRACTION_PROCESSOR": {
        "name": "Custom Extractor (Gemini)",
        "description": (
            "Generative-AI custom extractor built on Gemini foundation models. "
            "Extracts user-defined entities, including derived (inferred) fields and "
            "detected signatures. The document-level prompt and schema are configured "
            "on the processor itself in the GCP Console."
        ),
        "category": "Custom",
        "gcp_type": "CUSTOM_EXTRACTION_PROCESSOR",
        "capabilities": ["text", "entities", "derived_entities", "signatures"],
        "max_pages_online": 30,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": True,
        "icon": "✨"
    },
    "INVOICE_PROCESSOR": {
        "name": "Invoice Parser",
        "description": "Extract key fields from invoices: vendor, dates, amounts, line items",
        "category": "Specialized",
        "gcp_type": "INVOICE_PROCESSOR",
        "capabilities": ["text", "entities", "tables"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": True,
        "icon": "📄"
    },
    "EXPENSE_PROCESSOR": {
        "name": "Expense Parser",
        "description": "Extract expense report information and receipt data",
        "category": "Specialized",
        "gcp_type": "EXPENSE_PROCESSOR",
        "capabilities": ["text", "entities"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": True,
        "icon": "🧾"
    },
    "UTILITY_PROCESSOR": {
        "name": "Utility Bill Parser",
        "description": "Extract information from utility bills",
        "category": "Specialized",
        "gcp_type": "UTILITY_PROCESSOR",
        "capabilities": ["text", "entities"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": True,
        "icon": "💡"
    },
    "BANK_STATEMENT_PROCESSOR": {
        "name": "Bank Statement Parser",
        "description": "Extract transactions and account information from bank statements",
        "category": "Financial",
        "gcp_type": "BANK_STATEMENT_PROCESSOR",
        "capabilities": ["text", "entities", "tables"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": True,
        "icon": "🏦"
    },
    "PAYSTUB_PROCESSOR": {
        "name": "Pay Stub Parser",
        "description": "Extract earnings, deductions, and employer information from pay stubs",
        "category": "Financial",
        "gcp_type": "PAYSTUB_PROCESSOR",
        "capabilities": ["text", "entities"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": True,
        "icon": "💰"
    },
    "W2_PROCESSOR": {
        "name": "W-2 Parser",
        "description": "Extract information from W-2 tax forms",
        "category": "Tax",
        "gcp_type": "W2_PROCESSOR",
        "capabilities": ["text", "entities"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": True,
        "icon": "📋"
    },
    "ID_PROOFING_PROCESSOR": {
        "name": "ID Document Parser",
        "description": "Extract information from identity documents (passports, driver licenses, national IDs)",
        "category": "Identity",
        "gcp_type": "ID_PROOFING_PROCESSOR",
        "capabilities": ["text", "entities"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": True,
        "icon": "🆔"
    },
    "US_PASSPORT_PROCESSOR": {
        "name": "US Passport Parser",
        "description": "Extract information from US passports",
        "category": "Identity",
        "gcp_type": "US_PASSPORT_PROCESSOR",
        "capabilities": ["text", "entities"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": True,
        "icon": "🛂"
    },
    "US_DRIVER_LICENSE_PROCESSOR": {
        "name": "US Driver License Parser",
        "description": "Extract information from US driver licenses",
        "category": "Identity",
        "gcp_type": "US_DRIVER_LICENSE_PROCESSOR",
        "capabilities": ["text", "entities"],
        "max_pages_online": 15,
        "supported_formats": ["pdf", "jpg", "png", "bmp", "tiff", "gif", "webp"],
        "entity_extraction": True,
        "icon": "🪪"
    },
}

# Processor categories for UI organization
PROCESSOR_CATEGORIES = [
    "General",
    "Custom",
    "Specialized",
    "Financial",
    "Tax",
    "Identity",
]

# Color coding for visualization (consistent with Azure showcase)
ELEMENT_COLORS = {
    "text": "#007ACC",              # Blue
    "tables": "#00B04F",            # Green
    "table": "#00B04F",             # Green (alias)
    "paragraphs": "#9932CC",        # Dark Orchid
    "paragraph": "#9932CC",         # Dark Orchid (alias)
    "form_fields": "#FF8C00",       # Orange
    "formFields": "#FF8C00",        # Orange (alias)
    "entities": "#DC143C",          # Crimson
    "entity": "#DC143C",            # Crimson (alias)
    "checkboxes": "#8A2BE2",        # Purple
    "checkbox": "#8A2BE2",          # Purple (alias)
    "signatures": "#008080",        # Teal
    "signature": "#008080",         # Teal (alias)
}

# File format support
SUPPORTED_FORMATS = {
    "pdf": {
        "extensions": [".pdf"],
        "mime_types": ["application/pdf"],
        "max_size_mb": 40,
        "description": "Portable Document Format"
    },
    "jpg": {
        "extensions": [".jpg", ".jpeg"],
        "mime_types": ["image/jpeg"],
        "max_size_mb": 40,
        "description": "JPEG Image"
    },
    "png": {
        "extensions": [".png"],
        "mime_types": ["image/png"],
        "max_size_mb": 40,
        "description": "PNG Image"
    },
    "bmp": {
        "extensions": [".bmp"],
        "mime_types": ["image/bmp"],
        "max_size_mb": 40,
        "description": "Bitmap Image"
    },
    "tiff": {
        "extensions": [".tiff", ".tif"],
        "mime_types": ["image/tiff"],
        "max_size_mb": 40,
        "description": "TIFF Image"
    },
    "gif": {
        "extensions": [".gif"],
        "mime_types": ["image/gif"],
        "max_size_mb": 40,
        "description": "GIF Image"
    },
    "webp": {
        "extensions": [".webp"],
        "mime_types": ["image/webp"],
        "max_size_mb": 40,
        "description": "WebP Image"
    },
    # Office formats are supported by the Layout Parser (GA). They are not
    # paginated images, so the app shows layout/chunk/text views but no
    # bounding-box overlay for these.
    "docx": {
        "extensions": [".docx"],
        "mime_types": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
        "max_size_mb": 40,
        "description": "Word Document (Layout Parser only)"
    },
    "pptx": {
        "extensions": [".pptx"],
        "mime_types": ["application/vnd.openxmlformats-officedocument.presentationml.presentation"],
        "max_size_mb": 40,
        "description": "PowerPoint Presentation (Layout Parser only)"
    },
    "xlsx": {
        "extensions": [".xlsx"],
        "mime_types": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
        "max_size_mb": 40,
        "description": "Excel Spreadsheet (Layout Parser only)"
    },
    "xlsm": {
        "extensions": [".xlsm"],
        "mime_types": ["application/vnd.ms-excel.sheet.macroEnabled.12"],
        "max_size_mb": 40,
        "description": "Macro-Enabled Excel Spreadsheet (Layout Parser only)"
    },
}

# MIME type lookup
MIME_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
}


def get_processors_by_category() -> Dict[str, List[str]]:
    """Get processors organized by category."""
    categorized: Dict[str, List[str]] = {}
    for proc_type, proc_info in GCP_DOCAI_PROCESSORS.items():
        category = proc_info.get("category", "Other")
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(proc_type)
    return categorized


def get_processor_display_name(processor_type: str) -> str:
    """Get the display name for a processor type."""
    if processor_type in GCP_DOCAI_PROCESSORS:
        info = GCP_DOCAI_PROCESSORS[processor_type]
        icon = info.get("icon", "")
        name = info["name"]
        return f"{icon} {name}" if icon else name
    return processor_type


def get_processor_info(processor_type: str) -> Dict[str, Any]:
    """Get full info dict for a processor type."""
    return GCP_DOCAI_PROCESSORS.get(processor_type, {})
