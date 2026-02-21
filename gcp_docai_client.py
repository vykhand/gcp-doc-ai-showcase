"""
GCP Document AI REST API client.
Handles all API interactions including document processing and result parsing.
Uses the REST API with service account JSON for authentication (no SDK).
"""

import base64
import json
import os
import time
import traceback
from typing import Dict, Any, Optional, Tuple, List

import requests
import streamlit as st
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from logging_config import get_logger

logger = get_logger(__name__)

_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_TOKEN_LIFETIME = 3600  # seconds


def _b64url(data: bytes) -> str:
    """Base64url-encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _mint_access_token_sa(cred_info: Dict[str, Any]) -> Tuple[str, float]:
    """
    Create a self-signed JWT and exchange it for a Google OAuth2 access token.
    Used for service_account credentials.

    Returns:
        (access_token, expiry_timestamp)
    """
    now = int(time.time())
    header = json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    payload = json.dumps({
        "iss": cred_info["client_email"],
        "scope": _SCOPE,
        "aud": cred_info["token_uri"],
        "iat": now,
        "exp": now + _TOKEN_LIFETIME,
    }).encode()

    signing_input = _b64url(header) + "." + _b64url(payload)
    private_key = serialization.load_pem_private_key(
        cred_info["private_key"].encode(), password=None
    )
    signature = private_key.sign(
        signing_input.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    jwt_token = signing_input + "." + _b64url(signature)

    resp = requests.post(
        cred_info["token_uri"],
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt_token,
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", _TOKEN_LIFETIME)
    return access_token, now + expires_in


def _refresh_access_token_user(cred_info: Dict[str, Any]) -> Tuple[str, float]:
    """
    Use a refresh token to obtain an access token.
    Used for authorized_user credentials (ADC from ``gcloud auth application-default login``).

    Returns:
        (access_token, expiry_timestamp)
    """
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "refresh_token",
            "client_id": cred_info["client_id"],
            "client_secret": cred_info["client_secret"],
            "refresh_token": cred_info["refresh_token"],
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", _TOKEN_LIFETIME)
    return access_token, int(time.time()) + expires_in


def _get_access_token(cred_info: Dict[str, Any]) -> Tuple[str, float]:
    """Dispatch to the right token minting strategy based on credential type."""
    cred_type = cred_info.get("type", "")
    if cred_type == "service_account":
        return _mint_access_token_sa(cred_info)
    elif cred_type == "authorized_user":
        return _refresh_access_token_user(cred_info)
    else:
        raise ValueError(f"Unsupported credential type: {cred_type!r}")


class GCPDocumentAIClient:
    """Client for GCP Document AI using the REST API with OAuth2 auth."""

    def __init__(self, endpoint: str, cred_info: Dict[str, Any]):
        """
        Initialize the GCP Document AI REST client.

        Args:
            endpoint: Base endpoint URL, e.g.
                https://us-documentai.googleapis.com/v1/projects/{project}/locations/{location}
            cred_info: Parsed credential JSON dict (service_account or authorized_user).
        """
        self.endpoint = endpoint.rstrip("/")
        self._cred_info = cred_info
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self.session = requests.Session()

        logger.info(f"GCP Document AI REST client initialized for endpoint={self.endpoint}")

    def _get_auth_headers(self) -> Dict[str, str]:
        """Return Authorization header, refreshing the token if needed."""
        if not self._access_token or time.time() >= self._token_expiry - 60:
            self._access_token, self._token_expiry = _get_access_token(self._cred_info)
        return {"Authorization": f"Bearer {self._access_token}"}

    def list_processors(self) -> List[Dict[str, Any]]:
        """
        Discover available processors in the project.

        Returns:
            List of processor info dicts with keys: name, display_name, type, state, id
        """
        url = f"{self.endpoint}/processors"
        try:
            resp = self.session.get(url, headers=self._get_auth_headers())
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
        process_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a document synchronously (online processing).

        Args:
            processor_id: The processor ID (not the full resource name)
            document_data: Raw document bytes
            mime_type: MIME type of the document
            field_mask: Optional field mask to limit response fields
            process_options: Optional processOptions dict (e.g. layoutConfig)

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

        if process_options:
            body["processOptions"] = process_options

        logger.info(
            f"Processing document with processor {processor_id}, mime={mime_type}, size={len(document_data)} bytes"
        )

        try:
            resp = self.session.post(
                url, headers=self._get_auth_headers(), json=body
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
        logger.debug(f"DocumentAnalysisResult top-level keys: {list(document.keys())}")

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

    # ------------------------------------------------------------------
    # Layout Parser accessors
    # ------------------------------------------------------------------

    def is_layout_parser_result(self) -> bool:
        """Return True if the result comes from a Layout Parser processor.

        Layout Parser populates ``documentLayout`` instead of the traditional
        ``pages`` array.
        """
        has_layout = bool(self.document.get("documentLayout"))
        has_pages_content = any(
            page.get("lines") or page.get("paragraphs") or page.get("tables") or page.get("formFields")
            for page in self.document.get("pages", [])
        )
        return has_layout and not has_pages_content

    def get_document_layout(self) -> List[Dict[str, Any]]:
        """Recursively parse ``documentLayout.blocks`` into a flat list.

        Each entry has:
          - type: str  (heading-1 … heading-5, paragraph, table, list, block)
          - text: str
          - page_start: int
          - page_end: int
          - level: int  (nesting depth, 0 = top-level)
        """
        doc_layout = self.document.get("documentLayout", {})
        blocks = doc_layout.get("blocks", [])
        result: List[Dict[str, Any]] = []
        self._walk_layout_blocks(blocks, result, level=0)
        return result

    def _walk_layout_blocks(
        self,
        blocks: List[Dict[str, Any]],
        out: List[Dict[str, Any]],
        level: int,
    ) -> None:
        """Recursively walk layout blocks and append flat entries to *out*."""
        for block in blocks:
            block_type = "block"
            text = ""

            # Determine type and extract text from the block's content
            text_block = block.get("textBlock")
            table_block = block.get("tableBlock")
            list_block = block.get("listBlock")

            if text_block:
                block_type = text_block.get("type", "paragraph").lower().replace("_", "-")
                text = text_block.get("text", "")
            elif table_block:
                block_type = "table"
                # Reconstruct text from table body/header rows
                parts = []
                for row in table_block.get("headerRows", []) + table_block.get("bodyRows", []):
                    cell_texts = []
                    for cell in row.get("cells", []):
                        # cells may contain nested blocks
                        cell_parts = []
                        for cb in cell.get("blocks", []):
                            tb = cb.get("textBlock")
                            if tb:
                                cell_parts.append(tb.get("text", ""))
                        cell_texts.append(" ".join(cell_parts).strip())
                    parts.append(" | ".join(cell_texts))
                text = "\n".join(parts)
            elif list_block:
                block_type = "list"
                # list blocks contain nested blocks for each list item
                parts = []
                for lb in list_block.get("listEntries", []):
                    for cb in lb.get("blocks", []):
                        tb = cb.get("textBlock")
                        if tb:
                            parts.append(tb.get("text", ""))
                text = "\n".join(parts)

            # Page span
            page_span = block.get("pageSpan", {})
            page_start = int(page_span.get("pageStart", 0))
            page_end = int(page_span.get("pageEnd", page_start))

            out.append({
                "type": block_type,
                "text": text.strip(),
                "page_start": page_start,
                "page_end": page_end,
                "level": level,
            })

            # Recurse into nested blocks (textBlock and others can have sub-blocks)
            nested = block.get("blocks", [])
            if nested:
                self._walk_layout_blocks(nested, out, level + 1)

    def get_layout_page_count(self) -> int:
        """Derive page count from layout block page spans.

        The REST API uses 1-based page numbering in ``pageSpan``, so the
        max ``pageEnd`` value already equals the page count.
        """
        # Prefer the pages array when present (may contain empty page stubs)
        pages = self.document.get("pages", [])
        if pages:
            return len(pages)
        blocks = self.get_document_layout()
        if not blocks:
            return 0
        return max(b["page_end"] for b in blocks)

    def get_chunked_document(self) -> List[Dict[str, Any]]:
        """Parse ``chunkedDocument.chunks`` into a list of dicts.

        Each entry has:
          - chunk_id: str
          - content: str
          - page_span: dict with ``page_start`` and ``page_end``
        """
        chunked = self.document.get("chunkedDocument", {})
        chunks = chunked.get("chunks", [])
        result = []
        for chunk in chunks:
            page_span = chunk.get("pageSpan", {})
            result.append({
                "chunk_id": chunk.get("chunkId", ""),
                "content": chunk.get("content", ""),
                "page_span": {
                    "page_start": int(page_span.get("pageStart", 0)),
                    "page_end": int(page_span.get("pageEnd", 0)),
                },
            })
        return result

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


_ADC_PATH = os.path.join(
    os.path.expanduser("~"), ".config", "gcloud", "application_default_credentials.json"
)


def _load_cred_info_from_file(path: str) -> Optional[Dict[str, Any]]:
    """Load and parse a credential JSON file (service account or ADC)."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def create_client_from_env() -> Optional[GCPDocumentAIClient]:
    """
    Create a GCP Document AI client from available configuration.

    Priority:
    1. Streamlit secrets (GCP_DOCAI_ENDPOINT + [gcp_service_account])
    2. Env vars (GCP_DOCAI_ENDPOINT + GOOGLE_APPLICATION_CREDENTIALS file)
    3. GCP_DOCAI_ENDPOINT + Application Default Credentials (gcloud auth application-default login)
    4. None (caller should prompt for manual input)
    """
    endpoint = None
    cred_info = None

    # Try Streamlit secrets first
    try:
        endpoint = st.secrets.get("GCP_DOCAI_ENDPOINT")
        if endpoint:
            cred_info = dict(st.secrets["gcp_service_account"])
    except Exception:
        pass

    # Fall back to environment variables
    if not endpoint:
        endpoint = os.getenv("GCP_DOCAI_ENDPOINT")

    if endpoint and not cred_info:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path:
            cred_info = _load_cred_info_from_file(cred_path)

    # Fall back to ADC file from gcloud auth application-default login
    if endpoint and not cred_info:
        cred_info = _load_cred_info_from_file(_ADC_PATH)

    if endpoint and cred_info:
        try:
            return GCPDocumentAIClient(endpoint, cred_info)
        except Exception as e:
            logger.error(f"Failed to create client from env: {e}")
            return None

    return None
