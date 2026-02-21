"""
GCP Document AI REST API client.
Handles all API interactions including document processing and result parsing.
Uses the REST API with API key authentication instead of the Python SDK.
"""

import base64
import json
import os
import traceback
from typing import Dict, Any, Optional, Tuple, List

import requests
import streamlit as st

from logging_config import get_logger

logger = get_logger(__name__)


class GCPDocumentAIClient:
    """Client for GCP Document AI using the REST API with API key auth."""

    def __init__(self, endpoint: str, api_key: str):
        """
        Initialize the GCP Document AI REST client.

        Args:
            endpoint: Base endpoint URL, e.g.
                https://us-documentai.googleapis.com/v1/projects/{project}/locations/{location}
            api_key: GCP API key restricted to the Cloud Document AI API
        """
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()

        logger.info(f"GCP Document AI REST client initialized for endpoint={self.endpoint}")

    def list_processors(self) -> List[Dict[str, Any]]:
        """
        Discover available processors in the project.

        Returns:
            List of processor info dicts with keys: name, display_name, type, state, id
        """
        url = f"{self.endpoint}/processors"
        try:
            resp = self.session.get(url, params={"key": self.api_key})
            resp.raise_for_status()
            data = resp.json()

            processors = []
            for proc in data.get("processors", []):
                proc_name = proc.get("name", "")
                proc_id = proc_name.split("/")[-1] if proc_name else ""
                processors.append({
                    "name": proc_name,
                    "display_name": proc.get("displayName", ""),
                    "type": proc.get("type", ""),
                    "state": proc.get("state", "UNKNOWN"),
                    "id": proc_id,
                })

            logger.info(f"Found {len(processors)} processors in project")
            return processors

        except Exception as e:
            logger.error(f"Failed to list processors: {e}")
            raise

    def process_document(
        self,
        processor_id: str,
        document_data: bytes,
        mime_type: str,
        field_mask: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a document synchronously (online processing).

        Args:
            processor_id: The processor ID (not the full resource name)
            document_data: Raw document bytes
            mime_type: MIME type of the document
            field_mask: Optional field mask to limit response fields

        Returns:
            Document dict (the "document" key from the REST response)
        """
        url = f"{self.endpoint}/processors/{processor_id}:process"
        content_b64 = base64.b64encode(document_data).decode("utf-8")

        body: Dict[str, Any] = {
            "rawDocument": {
                "content": content_b64,
                "mimeType": mime_type,
            }
        }

        if field_mask:
            body["fieldMask"] = field_mask

        logger.info(
            f"Processing document with processor {processor_id}, mime={mime_type}, size={len(document_data)} bytes"
        )

        try:
            resp = self.session.post(
                url, params={"key": self.api_key}, json=body
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info("Document processing completed successfully")
            return result.get("document", {})
        except requests.HTTPError as e:
            error_detail = ""
            try:
                error_detail = e.response.text
            except Exception:
                pass
            logger.error(f"Document processing failed: {e} — {error_detail}")
            logger.debug(f"Traceback:\n{traceback.format_exc()}")
            raise
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            logger.debug(f"Traceback:\n{traceback.format_exc()}")
            raise

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connectivity by listing processors.

        Returns:
            Tuple of (success, message)
        """
        try:
            processors = self.list_processors()
            count = len(processors)
            return True, f"Connection successful! Found {count} processor(s)."
        except Exception as e:
            return False, f"Connection failed: {e}"


class DocumentAnalysisResult:
    """Wrapper around the Document REST JSON dict for easier data access."""

    def __init__(self, document: Dict[str, Any]):
        self.document = document

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    def get_text(self) -> str:
        """Get the full OCR text."""
        return self.document.get("text", "")

    def _layout_to_text(self, layout: Optional[Dict[str, Any]]) -> str:
        """Resolve a layout's textAnchor to actual text from document.text."""
        full_text = self.document.get("text", "")
        if not layout:
            return ""
        text_anchor = layout.get("textAnchor")
        if not text_anchor:
            return ""
        segments = text_anchor.get("textSegments", [])
        if not segments:
            return ""
        parts = []
        for segment in segments:
            start = int(segment.get("startIndex", 0))
            end = int(segment.get("endIndex", 0))
            parts.append(full_text[start:end])
        return "".join(parts).strip()

    # ------------------------------------------------------------------
    # Page-level accessors
    # ------------------------------------------------------------------

    def get_pages(self) -> list:
        """Return all pages."""
        return self.document.get("pages", [])

    def get_page_text_lines(self, page_index: int = 0) -> List[Dict[str, Any]]:
        """Get text lines for a specific page."""
        pages = self.document.get("pages", [])
        if page_index >= len(pages):
            return []
        page = pages[page_index]
        lines = []
        for line in page.get("lines", []):
            layout = line.get("layout")
            text = self._layout_to_text(layout)
            confidence = layout.get("confidence", 0.0) if layout else 0.0
            vertices = self._get_normalized_vertices(
                layout.get("boundingPoly")
            ) if layout else []
            lines.append({
                "text": text,
                "confidence": confidence,
                "vertices": vertices,
            })
        return lines

    # ------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------

    def get_entities(self) -> List[Dict[str, Any]]:
        """Get all extracted entities."""
        entities = []
        for entity in self.document.get("entities", []):
            mention_text = entity.get("mentionText", "")
            normalized_value = ""
            nv = entity.get("normalizedValue")
            if nv:
                normalized_value = nv.get("text", "")

            vertices = []
            page_index = 0
            page_anchor = entity.get("pageAnchor")
            if page_anchor:
                page_refs = page_anchor.get("pageRefs", [])
                if page_refs:
                    ref = page_refs[0]
                    page_index = int(ref.get("page", 0))
                    bp = ref.get("boundingPoly")
                    if bp:
                        vertices = self._get_normalized_vertices(bp)

            entities.append({
                "type": entity.get("type", ""),
                "mention_text": mention_text,
                "normalized_value": normalized_value,
                "confidence": entity.get("confidence", 0.0),
                "page": page_index,
                "vertices": vertices,
            })
        return entities

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    def get_tables(self) -> List[Dict[str, Any]]:
        """Get all tables across all pages."""
        tables = []
        for page_idx, page in enumerate(self.document.get("pages", [])):
            for table in page.get("tables", []):
                header_rows = []
                for row in table.get("headerRows", []):
                    cells = []
                    for cell in row.get("cells", []):
                        cells.append(self._layout_to_text(cell.get("layout")))
                    header_rows.append(cells)

                body_rows = []
                for row in table.get("bodyRows", []):
                    cells = []
                    for cell in row.get("cells", []):
                        cells.append(self._layout_to_text(cell.get("layout")))
                    body_rows.append(cells)

                layout = table.get("layout")
                vertices = self._get_normalized_vertices(
                    layout.get("boundingPoly")
                ) if layout else []

                tables.append({
                    "page": page_idx,
                    "header_rows": header_rows,
                    "body_rows": body_rows,
                    "row_count": len(header_rows) + len(body_rows),
                    "col_count": len(body_rows[0]) if body_rows else (len(header_rows[0]) if header_rows else 0),
                    "vertices": vertices,
                    "confidence": layout.get("confidence", 0.0) if layout else 0.0,
                })
        return tables

    # ------------------------------------------------------------------
    # Form fields (key-value pairs)
    # ------------------------------------------------------------------

    def get_form_fields(self) -> List[Dict[str, Any]]:
        """Get all form fields (key-value pairs) across pages."""
        fields = []
        for page_idx, page in enumerate(self.document.get("pages", [])):
            for field in page.get("formFields", []):
                field_name = field.get("fieldName")
                field_value = field.get("fieldValue")

                key_text = self._layout_to_text(field_name)
                value_text = self._layout_to_text(field_value)

                key_vertices = self._get_normalized_vertices(
                    field_name.get("boundingPoly")
                ) if field_name else []
                value_vertices = self._get_normalized_vertices(
                    field_value.get("boundingPoly")
                ) if field_value else []

                confidence = field_name.get("confidence", 0.0) if field_name else 0.0

                fields.append({
                    "page": page_idx,
                    "key": key_text,
                    "value": value_text,
                    "key_vertices": key_vertices,
                    "value_vertices": value_vertices,
                    "confidence": confidence,
                })
        return fields

    # ------------------------------------------------------------------
    # Checkboxes / selection marks
    # ------------------------------------------------------------------

    def get_checkboxes(self) -> List[Dict[str, Any]]:
        """Get all detected checkboxes across pages."""
        checkboxes = []
        for page_idx, page in enumerate(self.document.get("pages", [])):
            # Actual selection mark detection (visual checkmarks)
            for block in page.get("visualElements", []):
                block_type = block.get("type", "")
                if block_type in ("filled_checkbox", "unfilled_checkbox"):
                    layout = block.get("layout")
                    vertices = self._get_normalized_vertices(
                        layout.get("boundingPoly")
                    ) if layout else []
                    checkboxes.append({
                        "page": page_idx,
                        "state": block_type,
                        "vertices": vertices,
                        "confidence": layout.get("confidence", 0.0) if layout else 0.0,
                    })

            # Also detect from form_fields with checkbox value_type
            for field in page.get("formFields", []):
                field_value = field.get("fieldValue")
                value_type = ""
                if field_value:
                    value_type = field_value.get("valueType", "")
                if "checkbox" in value_type.lower():
                    vertices = self._get_normalized_vertices(
                        field_value.get("boundingPoly")
                    ) if field_value else []
                    field_name = field.get("fieldName")
                    checkboxes.append({
                        "page": page_idx,
                        "state": value_type,
                        "key": self._layout_to_text(field_name),
                        "vertices": vertices,
                        "confidence": field_value.get("confidence", 0.0) if field_value else 0.0,
                    })
        return checkboxes

    # ------------------------------------------------------------------
    # Paragraphs
    # ------------------------------------------------------------------

    def get_paragraphs(self) -> List[Dict[str, Any]]:
        """Get all paragraphs across all pages."""
        paragraphs = []
        for page_idx, page in enumerate(self.document.get("pages", [])):
            for para in page.get("paragraphs", []):
                layout = para.get("layout")
                text = self._layout_to_text(layout)
                vertices = self._get_normalized_vertices(
                    layout.get("boundingPoly")
                ) if layout else []
                paragraphs.append({
                    "page": page_idx,
                    "text": text,
                    "vertices": vertices,
                    "confidence": layout.get("confidence", 0.0) if layout else 0.0,
                })
        return paragraphs

    # ------------------------------------------------------------------
    # Bounding boxes (unified)
    # ------------------------------------------------------------------

    def get_bounding_boxes(self) -> Dict[str, list]:
        """
        Extract all bounding boxes organized by element type.

        GCP Document AI uses normalized vertices (0.0 to 1.0).
        At render time, multiply by image dimensions to get pixel coordinates.

        Returns:
            Dict with keys: text, tables, paragraphs, form_fields, entities, checkboxes
        """
        bounding_boxes: Dict[str, list] = {
            "text": [],
            "tables": [],
            "paragraphs": [],
            "form_fields": [],
            "entities": [],
            "checkboxes": [],
        }

        # 1. Text lines
        for page_idx, page in enumerate(self.document.get("pages", [])):
            for line in page.get("lines", []):
                layout = line.get("layout")
                if not layout:
                    continue
                vertices = self._get_normalized_vertices(layout.get("boundingPoly"))
                if not vertices:
                    continue
                text = self._layout_to_text(layout)
                bounding_boxes["text"].append({
                    "page": page_idx,
                    "vertices": vertices,
                    "content": text,
                    "type": "text",
                    "confidence": layout.get("confidence", 0.0),
                })

        # 2. Tables
        for page_idx, page in enumerate(self.document.get("pages", [])):
            for table in page.get("tables", []):
                layout = table.get("layout")
                if not layout:
                    continue
                vertices = self._get_normalized_vertices(layout.get("boundingPoly"))
                if not vertices:
                    continue
                header_rows = table.get("headerRows", [])
                body_rows = table.get("bodyRows", [])
                row_count = len(header_rows) + len(body_rows)
                col_count = 0
                if body_rows:
                    col_count = len(body_rows[0].get("cells", []))
                elif header_rows:
                    col_count = len(header_rows[0].get("cells", []))
                bounding_boxes["tables"].append({
                    "page": page_idx,
                    "vertices": vertices,
                    "content": f"Table ({row_count} rows x {col_count} cols)",
                    "type": "table",
                    "confidence": layout.get("confidence", 0.0),
                    "details": {
                        "rowCount": row_count,
                        "columnCount": col_count,
                    },
                })

        # 3. Paragraphs
        for page_idx, page in enumerate(self.document.get("pages", [])):
            for para in page.get("paragraphs", []):
                layout = para.get("layout")
                if not layout:
                    continue
                vertices = self._get_normalized_vertices(layout.get("boundingPoly"))
                if not vertices:
                    continue
                text = self._layout_to_text(layout)
                bounding_boxes["paragraphs"].append({
                    "page": page_idx,
                    "vertices": vertices,
                    "content": text[:100] + ("..." if len(text) > 100 else ""),
                    "type": "paragraph",
                    "confidence": layout.get("confidence", 0.0),
                    "details": {"fullContent": text, "length": len(text)},
                })

        # 4. Form fields (key-value pairs)
        for page_idx, page in enumerate(self.document.get("pages", [])):
            for field in page.get("formFields", []):
                field_name = field.get("fieldName")
                field_value = field.get("fieldValue")

                # Key bounding box
                if field_name and field_name.get("boundingPoly"):
                    key_vertices = self._get_normalized_vertices(field_name.get("boundingPoly"))
                    key_text = self._layout_to_text(field_name)
                    value_text = self._layout_to_text(field_value) if field_value else ""
                    if key_vertices:
                        bounding_boxes["form_fields"].append({
                            "page": page_idx,
                            "vertices": key_vertices,
                            "content": f"Key: {key_text}",
                            "type": "key",
                            "confidence": field_name.get("confidence", 0.0),
                            "details": {
                                "role": "key",
                                "keyContent": key_text,
                                "valueContent": value_text,
                            },
                        })
                # Value bounding box
                if field_value and field_value.get("boundingPoly"):
                    value_vertices = self._get_normalized_vertices(field_value.get("boundingPoly"))
                    key_text = self._layout_to_text(field_name) if field_name else ""
                    value_text = self._layout_to_text(field_value)
                    if value_vertices:
                        bounding_boxes["form_fields"].append({
                            "page": page_idx,
                            "vertices": value_vertices,
                            "content": f"Value: {value_text}",
                            "type": "value",
                            "confidence": field_value.get("confidence", 0.0),
                            "details": {
                                "role": "value",
                                "keyContent": key_text,
                                "valueContent": value_text,
                            },
                        })

        # 5. Entities
        for entity in self.document.get("entities", []):
            page_index = 0
            vertices = []
            page_anchor = entity.get("pageAnchor")
            if page_anchor:
                page_refs = page_anchor.get("pageRefs", [])
                if page_refs:
                    ref = page_refs[0]
                    page_index = int(ref.get("page", 0))
                    bp = ref.get("boundingPoly")
                    if bp:
                        vertices = self._get_normalized_vertices(bp)

            if not vertices:
                continue

            normalized_value = ""
            nv = entity.get("normalizedValue")
            if nv:
                normalized_value = nv.get("text", "")

            entity_type = entity.get("type", "")
            mention_text = entity.get("mentionText", "")

            bounding_boxes["entities"].append({
                "page": page_index,
                "vertices": vertices,
                "content": f"{entity_type}: {mention_text}",
                "type": "entity",
                "confidence": entity.get("confidence", 0.0),
                "details": {
                    "entityType": entity_type,
                    "mentionText": mention_text,
                    "normalizedValue": normalized_value,
                },
            })

        # 6. Checkboxes
        for cb in self.get_checkboxes():
            if cb.get("vertices"):
                bounding_boxes["checkboxes"].append({
                    "page": cb["page"],
                    "vertices": cb["vertices"],
                    "content": f"Checkbox: {cb.get('state', 'unknown')}",
                    "type": "checkbox",
                    "confidence": cb.get("confidence", 0.0),
                    "details": {
                        "state": cb.get("state", "unknown"),
                        "key": cb.get("key", ""),
                    },
                })

        return bounding_boxes

    # ------------------------------------------------------------------
    # Formatted fields for display
    # ------------------------------------------------------------------

    def get_formatted_fields(self) -> Dict[str, Any]:
        """Get entities formatted for the Fields tab."""
        formatted: Dict[str, Any] = {}

        entities = self.get_entities()
        if entities:
            formatted["Entities"] = {}
            for ent in entities:
                field_name = ent["type"]
                formatted["Entities"][field_name] = {
                    "content": ent["mention_text"],
                    "normalized_value": ent["normalized_value"],
                    "confidence": ent["confidence"],
                    "type": "entity",
                }

        form_fields = self.get_form_fields()
        if form_fields:
            formatted["Form Fields"] = {}
            for ff in form_fields:
                key = ff["key"] or "(unnamed)"
                formatted["Form Fields"][key] = {
                    "content": ff["value"],
                    "confidence": ff["confidence"],
                    "type": "form_field",
                }

        return formatted

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return the document dict (already JSON-serializable)."""
        return self.document

    # ------------------------------------------------------------------
    # Vertex helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_normalized_vertices(bounding_poly: Optional[Dict[str, Any]]) -> List[Dict[str, float]]:
        """
        Extract normalized vertices from a boundingPoly dict.

        GCP Document AI provides normalizedVertices with x, y in [0.0, 1.0].
        Missing values default to 0.0.

        Returns:
            List of {x, y} dicts (typically 4 vertices for a quadrilateral)
        """
        if not bounding_poly:
            return []
        vertices = []
        for v in bounding_poly.get("normalizedVertices", []):
            vertices.append({
                "x": v.get("x", 0.0),
                "y": v.get("y", 0.0),
            })
        return vertices


# ------------------------------------------------------------------
# Auth helpers
# ------------------------------------------------------------------


def create_client_from_env() -> Optional[GCPDocumentAIClient]:
    """
    Create a GCP Document AI client from available configuration.

    Priority:
    1. Streamlit secrets (GCP_DOCAI_ENDPOINT + GCP_DOCAI_API_KEY)
    2. Environment variables
    3. None (caller should prompt for manual input)
    """
    endpoint = None
    api_key = None

    # Try Streamlit secrets first
    try:
        endpoint = st.secrets.get("GCP_DOCAI_ENDPOINT")
        api_key = st.secrets.get("GCP_DOCAI_API_KEY")
    except Exception:
        pass

    # Fall back to environment variables
    if not endpoint:
        endpoint = os.getenv("GCP_DOCAI_ENDPOINT")
    if not api_key:
        api_key = os.getenv("GCP_DOCAI_API_KEY")

    if endpoint and api_key:
        try:
            return GCPDocumentAIClient(endpoint, api_key)
        except Exception as e:
            logger.error(f"Failed to create client from env: {e}")
            return None

    return None
