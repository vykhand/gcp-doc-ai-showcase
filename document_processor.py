"""
Document processing utilities for GCP Document AI Streamlit showcase.
Handles file uploads, validation, PDF-to-image conversion, and coordinate math.
"""

import io
import base64
import json
from typing import Dict, Any, Optional, Tuple, List

from PIL import Image, ImageDraw
import pdf2image
import streamlit as st

from config import SUPPORTED_FORMATS, ELEMENT_COLORS, MIME_TYPE_MAP
from logging_config import get_logger

logger = get_logger(__name__)


class DocumentProcessor:
    """Handles document processing, validation, and image conversion."""

    @staticmethod
    def validate_file(uploaded_file) -> Tuple[bool, str]:
        """
        Validate uploaded file format and size.

        Args:
            uploaded_file: Streamlit uploaded file object

        Returns:
            Tuple of (is_valid, message)
        """
        if not uploaded_file:
            return False, "No file uploaded"

        file_extension = ""
        if hasattr(uploaded_file, "name") and "." in uploaded_file.name:
            file_extension = uploaded_file.name.lower().split(".")[-1]

        supported_extensions = []
        for format_info in SUPPORTED_FORMATS.values():
            supported_extensions.extend(
                [ext.lower().lstrip(".") for ext in format_info["extensions"]]
            )

        if file_extension not in supported_extensions:
            return (
                False,
                f"Unsupported file format: .{file_extension}. Supported: {', '.join(supported_extensions)}",
            )

        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        max_size = 40  # GCP online processing limit

        if file_size_mb > max_size:
            return (
                False,
                f"File size ({file_size_mb:.1f} MB) exceeds the {max_size} MB limit for online processing",
            )

        return True, "File is valid"

    @staticmethod
    def get_file_info(uploaded_file) -> Dict[str, Any]:
        """Get metadata about the uploaded file."""
        if not uploaded_file:
            return {}

        file_size_bytes = len(uploaded_file.getvalue())
        file_size_mb = file_size_bytes / (1024 * 1024)
        file_extension = ""
        if hasattr(uploaded_file, "name") and "." in uploaded_file.name:
            file_extension = uploaded_file.name.lower().split(".")[-1]

        return {
            "name": uploaded_file.name,
            "size_bytes": file_size_bytes,
            "size_mb": round(file_size_mb, 2),
            "type": getattr(uploaded_file, "type", ""),
            "extension": file_extension,
        }

    @staticmethod
    def get_mime_type(filename: str) -> str:
        """Get the MIME type for a file based on its extension."""
        if "." in filename:
            ext = "." + filename.lower().split(".")[-1]
            return MIME_TYPE_MAP.get(ext, "application/octet-stream")
        return "application/octet-stream"

    @staticmethod
    def convert_to_images(file_data: bytes, file_type: str) -> List[Image.Image]:
        """
        Convert a document to PIL Images for display.

        Args:
            file_data: Raw file bytes
            file_type: File extension or MIME type

        Returns:
            List of PIL Images (one per page)
        """
        images: List[Image.Image] = []

        if not file_data or len(file_data) == 0:
            st.error("Document data is empty or corrupted")
            return images

        try:
            if file_type.lower() in ["pdf", "application/pdf"]:
                if not file_data.startswith(b"%PDF"):
                    st.error("File does not appear to be a valid PDF document")
                    return images
                try:
                    images = pdf2image.convert_from_bytes(
                        file_data,
                        dpi=150,
                        first_page=1,
                        last_page=10,
                        fmt="RGB",
                        thread_count=1,
                        use_pdftocairo=False,
                    )
                except Exception as pdf_error:
                    try:
                        images = pdf2image.convert_from_bytes(
                            file_data,
                            dpi=100,
                            first_page=1,
                            last_page=5,
                            fmt="RGB",
                            thread_count=1,
                        )
                    except Exception as fallback_error:
                        st.error(
                            f"PDF conversion failed: {pdf_error}. Fallback also failed: {fallback_error}"
                        )
                        return images

            elif file_type.lower() in [
                "jpg", "jpeg", "png", "bmp", "tiff", "tif", "gif", "webp",
            ] or file_type.startswith("image/"):
                try:
                    image_stream = io.BytesIO(file_data)
                    image = Image.open(image_stream)
                    image.verify()
                    image_stream.seek(0)
                    image = Image.open(image_stream)

                    if image.mode not in ["RGB", "RGBA"]:
                        image = image.convert("RGB")
                    elif image.mode == "RGBA":
                        background = Image.new("RGB", image.size, (255, 255, 255))
                        background.paste(image, mask=image.split()[-1])
                        image = background

                    images = [image]
                except Exception as img_error:
                    st.error(f"Image processing failed: {img_error}")
                    return images
            else:
                st.error(f"Unsupported file type for preview: {file_type}")

        except Exception as e:
            st.error(f"Error converting document to images: {e}")

        return images

    @staticmethod
    def normalized_vertices_to_pixel_coords(
        vertices: List[Dict[str, float]], img_width: int, img_height: int
    ) -> List[Tuple[int, int]]:
        """
        Convert GCP normalized vertices (0.0-1.0) to pixel coordinates.

        Args:
            vertices: List of {x, y} dicts with values in [0.0, 1.0]
            img_width: Image width in pixels
            img_height: Image height in pixels

        Returns:
            List of (x, y) pixel coordinate tuples
        """
        points = []
        for v in vertices:
            x = max(0, min(int(v["x"] * img_width), img_width))
            y = max(0, min(int(v["y"] * img_height), img_height))
            points.append((x, y))
        return points

    @staticmethod
    def encode_image_for_display(image: Image.Image, fmt: str = "PNG") -> str:
        """Encode a PIL Image as a base64 data URI."""
        buffer = io.BytesIO()
        image.save(buffer, format=fmt)
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/{fmt.lower()};base64,{img_str}"

    @staticmethod
    def create_sample_documents() -> Dict[str, Dict[str, Any]]:
        """Define sample documents for demo purposes."""
        _gcs = "https://storage.googleapis.com/cloud-samples-data/documentai/SampleDocuments"
        return {
            "Winnie the Pooh - 3 Pages (OCR)": {
                "description": "Multi-page PDF for testing OCR Processor",
                "processor_type": "OCR_PROCESSOR",
                "url": f"{_gcs}/OCR_PROCESSOR/Winnie_the_Pooh_3_Pages.pdf",
            },
            "Intake Form (Form Parser)": {
                "description": "Sample intake form for testing Form Parser",
                "processor_type": "FORM_PARSER_PROCESSOR",
                "url": f"{_gcs}/FORM_PARSER_PROCESSOR/intake-form.pdf",
            },
            "Winnie the Pooh (Layout Parser)": {
                "description": "Book excerpt for testing Layout Parser (3 pages)",
                "processor_type": "LAYOUT_PARSER_PROCESSOR",
                "url": f"{_gcs}/OCR_PROCESSOR/Winnie_the_Pooh_3_Pages.pdf",
            },
            "Google Invoice": {
                "description": "Sample invoice for testing Invoice Parser",
                "processor_type": "INVOICE_PROCESSOR",
                "url": f"{_gcs}/INVOICE_PROCESSOR/google_invoice.pdf",
            },
            "Office Depot Receipt (Expense)": {
                "description": "Redacted receipt for testing Expense Parser",
                "processor_type": "EXPENSE_PROCESSOR",
                "url": f"{_gcs}/EXPENSE_PROCESSOR/office-depot-redacted.pdf",
            },
            "SCE&G Utility Bill": {
                "description": "Utility bill for testing Utility Parser",
                "processor_type": "UTILITY_PROCESSOR",
                "url": f"{_gcs}/UTILITY_PROCESSOR/sce_g-bill.pdf",
            },
            "Bank Statement": {
                "description": "Lending bank statement for testing Bank Statement Parser",
                "processor_type": "BANK_STATEMENT_PROCESSOR",
                "url": f"{_gcs}/BANK_STATEMENT_PROCESSOR/lending_bankstatement.pdf",
            },
            "CA Hourly Pay Stub": {
                "description": "California hourly pay stub for testing Paystub Parser",
                "processor_type": "PAYSTUB_PROCESSOR",
                "url": "https://www.dir.ca.gov/dlse/paystub.pdf",
            },
            "2020 W-2 Form": {
                "description": "W-2 tax form for testing W2 Parser",
                "processor_type": "W2_PROCESSOR",
                "url": f"{_gcs}/FORM_W2_PROCESSOR/2020FormW-2.pdf",
            },
            "ID Document (Identity Proofing)": {
                "description": "Two-page ID document for testing ID Proofing Processor",
                "processor_type": "ID_PROOFING_PROCESSOR",
                "url": f"{_gcs}/ID_PROOFING_PROCESSOR/identity_fraud_two_pages_id.pdf",
            },
            "US Passport Specimen": {
                "description": "Next-gen US passport specimen for testing Passport Parser",
                "processor_type": "US_PASSPORT_PROCESSOR",
                "url": f"{_gcs}/US_PASSPORT_PROCESSOR/2020-Next-Gen-US-Passport.pdf",
            },
            "Driver License": {
                "description": "Sample driver license for testing DL Parser",
                "processor_type": "US_DRIVER_LICENSE_PROCESSOR",
                "url": f"{_gcs}/US_DRIVER_LICENSE_PROCESSOR/dl3.pdf",
            },
        }

    @staticmethod
    def download_sample_document(url: str) -> Optional[bytes]:
        """Download a sample document from a URL."""
        try:
            import requests

            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            st.error(f"Error downloading sample document: {e}")
        return None


class ResultsFormatter:
    """Format Document AI results for display."""

    @staticmethod
    def format_confidence_score(confidence: float) -> str:
        """Format a confidence score with color coding (HTML)."""
        percentage = confidence * 100
        if percentage >= 90:
            color = "green"
        elif percentage >= 70:
            color = "orange"
        else:
            color = "red"
        return f'<span style="color: {color}; font-weight: bold">{percentage:.1f}%</span>'

    @staticmethod
    def create_fields_table(fields_data: Dict[str, Any]) -> str:
        """Create an HTML table for structured fields display."""
        if not fields_data:
            return "<p>No fields extracted</p>"

        html = "<table style='width: 100%; border-collapse: collapse;'>"
        html += (
            "<tr style='background-color: #f0f0f0;'>"
            "<th style='border: 1px solid #ddd; padding: 8px;'>Field</th>"
            "<th style='border: 1px solid #ddd; padding: 8px;'>Content</th>"
            "<th style='border: 1px solid #ddd; padding: 8px;'>Confidence</th>"
            "</tr>"
        )

        for section_name, fields in fields_data.items():
            html += (
                f"<tr style='background-color: #e8f4f8;'>"
                f"<td colspan='3' style='border: 1px solid #ddd; padding: 8px; font-weight: bold;'>{section_name}</td>"
                f"</tr>"
            )
            for field_name, field_info in fields.items():
                content = str(field_info.get("content", ""))
                if len(content) > 100:
                    content = content[:97] + "..."
                confidence = field_info.get("confidence", 0)
                confidence_html = ResultsFormatter.format_confidence_score(confidence)
                html += (
                    f"<tr>"
                    f"<td style='border: 1px solid #ddd; padding: 8px;'>{field_name}</td>"
                    f"<td style='border: 1px solid #ddd; padding: 8px;'>{content}</td>"
                    f"<td style='border: 1px solid #ddd; padding: 8px;'>{confidence_html}</td>"
                    f"</tr>"
                )
        html += "</table>"
        return html
