"""
GCP Document AI SDK client.
Handles all API interactions including document processing and result parsing.
"""

import json
import traceback
from typing import Dict, Any, Optional, Tuple, List

import streamlit as st
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.oauth2 import service_account
from google.protobuf.json_format import MessageToDict

from logging_config import get_logger

logger = get_logger(__name__)


class GCPDocumentAIClient:
    """Client for GCP Document AI using the Python SDK."""

    def __init__(
        self,
        project_id: str,
        location: str,
        credentials=None,
    ):
        """
        Initialize the GCP Document AI client.

        Args:
            project_id: GCP project ID
            location: Processing location (us or eu)
            credentials: Optional google.auth credentials object
        """
        self.project_id = project_id
        self.location = location
        self.parent = f"projects/{project_id}/locations/{location}"

        opts = ClientOptions(
            api_endpoint=f"{location}-documentai.googleapis.com"
        )

        if credentials:
            self.client = documentai.DocumentProcessorServiceClient(
                client_options=opts, credentials=credentials
            )
        else:
            # Uses Application Default Credentials
            self.client = documentai.DocumentProcessorServiceClient(
                client_options=opts
            )

        logger.info(
            f"GCP Document AI client initialized for project={project_id}, location={location}"
        )

    def list_processors(self) -> List[Dict[str, Any]]:
        """
        Discover available processors in the project.

        Returns:
            List of processor info dicts with keys: name, display_name, type, state, id
        """
        try:
            request = documentai.ListProcessorsRequest(parent=self.parent)
            response = self.client.list_processors(request=request)

            processors = []
            for processor in response:
                proc_name = processor.name  # full resource name
                proc_id = proc_name.split("/")[-1]
                processors.append({
                    "name": proc_name,
                    "display_name": processor.display_name,
                    "type": processor.type_,
                    "state": processor.state.name if processor.state else "UNKNOWN",
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
    ) -> documentai.Document:
        """
        Process a document synchronously (online processing).

        Args:
            processor_id: The processor ID (not the full resource name)
            document_data: Raw document bytes
            mime_type: MIME type of the document
            field_mask: Optional field mask to limit response fields

        Returns:
            Document protobuf object
        """
        resource_name = f"{self.parent}/processors/{processor_id}"

        raw_document = documentai.RawDocument(
            content=document_data, mime_type=mime_type
        )

        request = documentai.ProcessRequest(
            name=resource_name,
            raw_document=raw_document,
        )

        if field_mask:
            request.field_mask = field_mask

        logger.info(f"Processing document with processor {processor_id}, mime={mime_type}, size={len(document_data)} bytes")

        try:
            result = self.client.process_document(request=request)
            logger.info("Document processing completed successfully")
            return result.document
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
    """Wrapper around the Document protobuf for easier data access."""

    def __init__(self, document: documentai.Document):
        self.document = document

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    def get_text(self) -> str:
        """Get the full OCR text."""
        return self.document.text or ""

    def _layout_to_text(self, layout) -> str:
        """Resolve a layout's text_anchor to actual text from document.text."""
        full_text = self.document.text
        if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
            return ""
        parts = []
        for segment in layout.text_anchor.text_segments:
            start = int(segment.start_index)
            end = int(segment.end_index)
            parts.append(full_text[start:end])
        return "".join(parts).strip()

    # ------------------------------------------------------------------
    # Page-level accessors
    # ------------------------------------------------------------------

    def get_pages(self) -> list:
        """Return all pages."""
        return list(self.document.pages)

    def get_page_text_lines(self, page_index: int = 0) -> List[Dict[str, Any]]:
        """Get text lines for a specific page."""
        pages = self.document.pages
        if page_index >= len(pages):
            return []
        page = pages[page_index]
        lines = []
        for line in page.lines:
            text = self._layout_to_text(line.layout)
            confidence = line.layout.confidence if line.layout else 0.0
            vertices = self._get_normalized_vertices(line.layout.bounding_poly) if line.layout else []
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
        for entity in self.document.entities:
            mention_text = entity.mention_text or ""
            normalized_value = ""
            if entity.normalized_value:
                normalized_value = entity.normalized_value.text or ""

            vertices = []
            page_index = 0
            if entity.page_anchor and entity.page_anchor.page_refs:
                ref = entity.page_anchor.page_refs[0]
                page_index = int(ref.page) if ref.page else 0
                if ref.bounding_poly:
                    vertices = self._get_normalized_vertices(ref.bounding_poly)

            entities.append({
                "type": entity.type_,
                "mention_text": mention_text,
                "normalized_value": normalized_value,
                "confidence": entity.confidence,
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
        for page_idx, page in enumerate(self.document.pages):
            for table in page.tables:
                header_rows = []
                for row in table.header_rows:
                    cells = []
                    for cell in row.cells:
                        cells.append(self._layout_to_text(cell.layout))
                    header_rows.append(cells)

                body_rows = []
                for row in table.body_rows:
                    cells = []
                    for cell in row.cells:
                        cells.append(self._layout_to_text(cell.layout))
                    body_rows.append(cells)

                vertices = self._get_normalized_vertices(
                    table.layout.bounding_poly
                ) if table.layout else []

                tables.append({
                    "page": page_idx,
                    "header_rows": header_rows,
                    "body_rows": body_rows,
                    "row_count": len(header_rows) + len(body_rows),
                    "col_count": len(body_rows[0]) if body_rows else (len(header_rows[0]) if header_rows else 0),
                    "vertices": vertices,
                    "confidence": table.layout.confidence if table.layout else 0.0,
                })
        return tables

    # ------------------------------------------------------------------
    # Form fields (key-value pairs)
    # ------------------------------------------------------------------

    def get_form_fields(self) -> List[Dict[str, Any]]:
        """Get all form fields (key-value pairs) across pages."""
        fields = []
        for page_idx, page in enumerate(self.document.pages):
            for field in page.form_fields:
                key_text = self._layout_to_text(field.field_name)
                value_text = self._layout_to_text(field.field_value)

                key_vertices = self._get_normalized_vertices(
                    field.field_name.bounding_poly
                ) if field.field_name else []
                value_vertices = self._get_normalized_vertices(
                    field.field_value.bounding_poly
                ) if field.field_value else []

                confidence = field.field_name.confidence if field.field_name else 0.0

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
        for page_idx, page in enumerate(self.document.pages):
            for det in page.detected_languages:
                pass  # just iterating pages
            # Check for selection marks in form fields
            for field in page.form_fields:
                if field.field_value and field.field_value.value_type:
                    # value_type might be something like "filled_checkbox" or "unfilled_checkbox"
                    pass

            # Actual selection mark detection (visual checkmarks)
            for block in page.visual_elements:
                if block.type_ in ("filled_checkbox", "unfilled_checkbox"):
                    vertices = self._get_normalized_vertices(
                        block.layout.bounding_poly
                    ) if block.layout else []
                    checkboxes.append({
                        "page": page_idx,
                        "state": block.type_,
                        "vertices": vertices,
                        "confidence": block.layout.confidence if block.layout else 0.0,
                    })

            # Also detect from detected_checkboxes if the page has them
            # (Form Parser puts checkboxes in form_fields with value_type)
            for field in page.form_fields:
                value_type = ""
                if field.field_value:
                    value_type = field.field_value.value_type or ""
                if "checkbox" in value_type.lower():
                    vertices = self._get_normalized_vertices(
                        field.field_value.bounding_poly
                    ) if field.field_value else []
                    checkboxes.append({
                        "page": page_idx,
                        "state": value_type,
                        "key": self._layout_to_text(field.field_name),
                        "vertices": vertices,
                        "confidence": field.field_value.confidence if field.field_value else 0.0,
                    })
        return checkboxes

    # ------------------------------------------------------------------
    # Paragraphs
    # ------------------------------------------------------------------

    def get_paragraphs(self) -> List[Dict[str, Any]]:
        """Get all paragraphs across all pages."""
        paragraphs = []
        for page_idx, page in enumerate(self.document.pages):
            for para in page.paragraphs:
                text = self._layout_to_text(para.layout)
                vertices = self._get_normalized_vertices(
                    para.layout.bounding_poly
                ) if para.layout else []
                paragraphs.append({
                    "page": page_idx,
                    "text": text,
                    "vertices": vertices,
                    "confidence": para.layout.confidence if para.layout else 0.0,
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
        for page_idx, page in enumerate(self.document.pages):
            for line in page.lines:
                if not line.layout:
                    continue
                vertices = self._get_normalized_vertices(line.layout.bounding_poly)
                if not vertices:
                    continue
                text = self._layout_to_text(line.layout)
                bounding_boxes["text"].append({
                    "page": page_idx,
                    "vertices": vertices,
                    "content": text,
                    "type": "text",
                    "confidence": line.layout.confidence,
                })

        # 2. Tables
        for page_idx, page in enumerate(self.document.pages):
            for table in page.tables:
                if not table.layout:
                    continue
                vertices = self._get_normalized_vertices(table.layout.bounding_poly)
                if not vertices:
                    continue
                row_count = len(table.header_rows) + len(table.body_rows)
                col_count = 0
                if table.body_rows:
                    col_count = len(table.body_rows[0].cells)
                elif table.header_rows:
                    col_count = len(table.header_rows[0].cells)
                bounding_boxes["tables"].append({
                    "page": page_idx,
                    "vertices": vertices,
                    "content": f"Table ({row_count} rows x {col_count} cols)",
                    "type": "table",
                    "confidence": table.layout.confidence,
                    "details": {
                        "rowCount": row_count,
                        "columnCount": col_count,
                    },
                })

        # 3. Paragraphs
        for page_idx, page in enumerate(self.document.pages):
            for para in page.paragraphs:
                if not para.layout:
                    continue
                vertices = self._get_normalized_vertices(para.layout.bounding_poly)
                if not vertices:
                    continue
                text = self._layout_to_text(para.layout)
                bounding_boxes["paragraphs"].append({
                    "page": page_idx,
                    "vertices": vertices,
                    "content": text[:100] + ("..." if len(text) > 100 else ""),
                    "type": "paragraph",
                    "confidence": para.layout.confidence,
                    "details": {"fullContent": text, "length": len(text)},
                })

        # 4. Form fields (key-value pairs)
        for page_idx, page in enumerate(self.document.pages):
            for field in page.form_fields:
                # Key bounding box
                if field.field_name and field.field_name.bounding_poly:
                    key_vertices = self._get_normalized_vertices(field.field_name.bounding_poly)
                    key_text = self._layout_to_text(field.field_name)
                    value_text = self._layout_to_text(field.field_value) if field.field_value else ""
                    if key_vertices:
                        bounding_boxes["form_fields"].append({
                            "page": page_idx,
                            "vertices": key_vertices,
                            "content": f"Key: {key_text}",
                            "type": "key",
                            "confidence": field.field_name.confidence,
                            "details": {
                                "role": "key",
                                "keyContent": key_text,
                                "valueContent": value_text,
                            },
                        })
                # Value bounding box
                if field.field_value and field.field_value.bounding_poly:
                    value_vertices = self._get_normalized_vertices(field.field_value.bounding_poly)
                    key_text = self._layout_to_text(field.field_name) if field.field_name else ""
                    value_text = self._layout_to_text(field.field_value)
                    if value_vertices:
                        bounding_boxes["form_fields"].append({
                            "page": page_idx,
                            "vertices": value_vertices,
                            "content": f"Value: {value_text}",
                            "type": "value",
                            "confidence": field.field_value.confidence,
                            "details": {
                                "role": "value",
                                "keyContent": key_text,
                                "valueContent": value_text,
                            },
                        })

        # 5. Entities
        for entity in self.document.entities:
            page_index = 0
            vertices = []
            if entity.page_anchor and entity.page_anchor.page_refs:
                ref = entity.page_anchor.page_refs[0]
                page_index = int(ref.page) if ref.page else 0
                if ref.bounding_poly:
                    vertices = self._get_normalized_vertices(ref.bounding_poly)

            if not vertices:
                continue

            normalized_value = ""
            if entity.normalized_value:
                normalized_value = entity.normalized_value.text or ""

            bounding_boxes["entities"].append({
                "page": page_index,
                "vertices": vertices,
                "content": f"{entity.type_}: {entity.mention_text}",
                "type": "entity",
                "confidence": entity.confidence,
                "details": {
                    "entityType": entity.type_,
                    "mentionText": entity.mention_text,
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
        """Convert the Document protobuf to a JSON-serializable dict."""
        return MessageToDict(
            self.document._pb, preserving_proto_field_name=True
        )

    # ------------------------------------------------------------------
    # Vertex helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_normalized_vertices(bounding_poly) -> List[Dict[str, float]]:
        """
        Extract normalized vertices from a BoundingPoly.

        GCP Document AI provides normalized_vertices with x, y in [0.0, 1.0].
        Missing values default to 0.0.

        Returns:
            List of {x, y} dicts (typically 4 vertices for a quadrilateral)
        """
        if not bounding_poly:
            return []
        vertices = []
        for v in bounding_poly.normalized_vertices:
            vertices.append({
                "x": v.x if v.x else 0.0,
                "y": v.y if v.y else 0.0,
            })
        return vertices


# ------------------------------------------------------------------
# Auth helpers
# ------------------------------------------------------------------


def create_credentials_from_secrets() -> Optional[service_account.Credentials]:
    """Create credentials from Streamlit secrets (service account JSON)."""
    try:
        sa_info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return credentials
    except Exception:
        return None


def create_client_from_env() -> Optional[GCPDocumentAIClient]:
    """
    Create a GCP Document AI client using available credentials.

    Priority:
    1. Streamlit secrets (service account JSON + project config)
    2. Environment variables + Application Default Credentials
    3. None (caller should prompt for manual input)
    """
    import os

    project_id = None
    location = None
    credentials = None

    # Try Streamlit secrets first
    try:
        project_id = st.secrets.get("GCP_PROJECT_ID")
        location = st.secrets.get("GCP_LOCATION", "us")
        credentials = create_credentials_from_secrets()
    except Exception:
        pass

    # Fall back to environment variables
    if not project_id:
        project_id = os.getenv("GCP_PROJECT_ID")
    if not location:
        location = os.getenv("GCP_LOCATION", "us")

    if project_id:
        try:
            return GCPDocumentAIClient(project_id, location, credentials)
        except Exception as e:
            logger.error(f"Failed to create client from env: {e}")
            return None

    return None
