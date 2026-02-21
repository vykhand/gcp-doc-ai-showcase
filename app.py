"""
GCP Document AI Streamlit Showcase Application.

Interactive interface for processing documents with GCP Document AI processors
and visually overlaying extracted information with bounding boxes and tooltips.
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import html as html_lib
import base64
from io import BytesIO
from typing import Optional, Dict, Any

from dotenv import load_dotenv

from logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

from config import GCP_DOCAI_PROCESSORS, get_processor_display_name
from gcp_docai_client import (
    GCPDocumentAIClient,
    DocumentAnalysisResult,
    create_client_from_env,
)
from document_processor import DocumentProcessor, ResultsFormatter
from ui_components import (
    ProcessorSelector,
    FileUploadSection,
    ResultsDisplay,
    StatusDisplay,
    render_connection_status,
)
from simple_annotator import SimpleDocumentAnnotator

load_dotenv()

# ------------------------------------------------------------------
# Page config & CSS
# ------------------------------------------------------------------

st.set_page_config(
    page_title="GCP Document AI Showcase",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        color: #4285F4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    defaults = {
        "analysis_result": None,  # DocumentAnalysisResult
        "raw_result_dict": None,  # JSON dict
        "document_images": None,
        "selected_processor": None,
        "uploaded_file": None,
        "current_file_id": None,
        "current_page_idx": 0,
        "gcp_client": None,
        "discovered_processors": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ------------------------------------------------------------------
# Client creation
# ------------------------------------------------------------------


def create_gcp_client() -> Optional[GCPDocumentAIClient]:
    """Create GCP Document AI client from endpoint + service account JSON."""
    client = create_client_from_env()

    if client:
        return client

    # Fall back to manual input in sidebar
    st.sidebar.warning("GCP credentials not found in environment or secrets.")
    st.sidebar.markdown("### Connect to Document AI")

    endpoint = st.sidebar.text_input(
        "Endpoint",
        placeholder="https://us-documentai.googleapis.com/v1/projects/PROJECT_ID/locations/us",
        help="Your Document AI endpoint URL (encodes project ID and location)",
    )

    sa_json_str = st.sidebar.text_area(
        "Service Account Key (JSON)",
        placeholder='{"type": "service_account", ...}',
        help="Paste the full contents of your service account key JSON file",
        height=150,
    )

    if endpoint and sa_json_str:
        try:
            import json as _json
            sa_info = _json.loads(sa_json_str)
            client = GCPDocumentAIClient(endpoint, sa_info)
            st.sidebar.success("Client created!")
            return client
        except Exception as e:
            st.sidebar.error(f"Failed to create client: {e}")
            return None

    # Show setup help
    with st.sidebar.expander("Setup Help", expanded=False):
        st.markdown(
            "**1. Create a Service Account & Download Key**\n"
            "```bash\n"
            "gcloud iam service-accounts create docai-sa\n"
            "gcloud projects add-iam-policy-binding PROJECT \\\\\n"
            "  --member='serviceAccount:docai-sa@PROJECT.iam.gserviceaccount.com' \\\\\n"
            "  --role='roles/documentai.apiUser'\n"
            "gcloud iam service-accounts keys create key.json \\\\\n"
            "  --iam-account=docai-sa@PROJECT.iam.gserviceaccount.com\n"
            "```\n"
            "Paste the contents of `key.json` above.\n\n"
            "**2. Construct the Endpoint**\n"
            "```\n"
            "https://{LOCATION}-documentai.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}\n"
            "```\n"
            "Example:\n"
            "```\n"
            "https://us-documentai.googleapis.com/v1/projects/my-project/locations/us\n"
            "```\n\n"
            "**3. Environment Variables (optional)**\n"
            "```bash\n"
            "export GCP_DOCAI_ENDPOINT='https://...'\n"
            "export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json'\n"
            "```"
        )
    return None


# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------


def render_main_header():
    """Render the main application header."""
    st.markdown(
        '<h1 class="main-header">GCP Document AI Showcase</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sub-header">Process documents with GCP Document AI and visualize extracted information with interactive bounding boxes</p>',
        unsafe_allow_html=True,
    )
    st.info(
        "**Author:** Andrey Vykhodtsev | "
        "**License:** MIT License | "
        "Attribution required when using or modifying this code"
    )


# ------------------------------------------------------------------
# Document analysis handler
# ------------------------------------------------------------------


def handle_document_analysis(
    client: GCPDocumentAIClient,
    processor_info: Dict[str, Any],
    file_data: bytes,
    mime_type: str,
):
    """
    Run document processing and store results in session state.

    Args:
        client: GCP Document AI client
        processor_info: Dict with processor_id, processor_type, display_name
        file_data: Raw document bytes
        mime_type: MIME type of the document
    """
    processor_id = processor_info["processor_id"]
    logger.info(f"Starting analysis with processor {processor_id}, mime={mime_type}, size={len(file_data)} bytes")

    status_placeholder = st.empty()

    with st.spinner("Processing document..."):
        status_placeholder.info("Uploading document and processing...")

        try:
            # Enable chunking for Layout Parser so chunkedDocument is populated
            process_options = None
            proc_type = processor_info.get("processor_type", "")
            if proc_type == "LAYOUT_PARSER_PROCESSOR":
                process_options = {
                    "layoutConfig": {
                        "chunkingConfig": {
                            "chunkSize": 500,
                            "includeAncestorHeadings": True,
                        }
                    }
                }

            document_dict = client.process_document(
                processor_id=processor_id,
                document_data=file_data,
                mime_type=mime_type,
                process_options=process_options,
            )

            analysis = DocumentAnalysisResult(document_dict)
            st.session_state.analysis_result = analysis
            st.session_state.raw_result_dict = document_dict

            status_placeholder.success("Document analysis completed successfully!")

            # Summary metrics
            if analysis.is_layout_parser_result():
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Pages", analysis.get_layout_page_count())
                with col2:
                    st.metric("Blocks", len(analysis.get_document_layout()))
                with col3:
                    st.metric("Chunks", len(analysis.get_chunked_document()))
                with col4:
                    text = analysis.get_text()
                    char_count = len(text) if text else sum(
                        len(b["text"]) for b in analysis.get_document_layout()
                    )
                    st.metric("Characters", char_count)
            else:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Pages", len(analysis.get_pages()))
                with col2:
                    st.metric("Tables", len(analysis.get_tables()))
                with col3:
                    st.metric("Form Fields", len(analysis.get_form_fields()))
                with col4:
                    st.metric("Entities", len(analysis.get_entities()))

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Document analysis failed: {error_msg}")
            status_placeholder.error(f"Analysis failed: {error_msg}")
            st.session_state.analysis_result = None
            st.session_state.raw_result_dict = None

            with st.expander("Error Details", expanded=True):
                st.code(error_msg)

            if "permission" in error_msg.lower() or "403" in error_msg:
                st.info(
                    "**Tip**: Ensure your service account has the "
                    "`roles/documentai.apiUser` role."
                )
            elif "not found" in error_msg.lower() or "404" in error_msg:
                st.info(
                    "**Tip**: Check that the processor ID is correct and exists in your project."
                )
            elif "invalid" in error_msg.lower():
                st.info(
                    "**Tip**: The document may be in an unsupported format for this processor."
                )


# ------------------------------------------------------------------
# Interactive annotation overlay (HTML + JS)
# ------------------------------------------------------------------

# Color and label configuration for element types
ELEMENT_INFO = {
    "text": {"color": "#007ACC", "name": "Text Line"},
    "tables": {"color": "#00B04F", "name": "Table"},
    "paragraphs": {"color": "#9932CC", "name": "Paragraph"},
    "form_fields": {"color": "#FF8C00", "name": "Form Field"},
    "entities": {"color": "#DC143C", "name": "Entity"},
    "checkboxes": {"color": "#8A2BE2", "name": "Checkbox"},
}


def _create_interactive_annotations(
    image, bounding_boxes, page_idx, zoom_level=1.0
):
    """
    Create HTML with interactive annotation overlays and rich tooltips.

    GCP uses normalized vertices (0-1), so pixel = vertex * image_dimension * zoom.
    """
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    image_data = base64.b64encode(buffer.getvalue()).decode()

    # Filter for current page
    page_boxes = {}
    for box_type, boxes in bounding_boxes.items():
        page_boxes[box_type] = [b for b in boxes if b.get("page", 0) == page_idx]

    overlays_html = ""
    container_id = f"doc-viewer-{page_idx}"
    overlay_count = 0

    img_w = image.width
    img_h = image.height

    for box_type, boxes in page_boxes.items():
        info = ELEMENT_INFO.get(
            box_type, {"color": "#FF0000", "name": box_type.title()}
        )
        color = info["color"]
        type_name = info["name"]

        for box in boxes:
            vertices = box.get("vertices", [])
            if len(vertices) < 3:
                continue

            # Convert normalized vertices to zoomed pixel coords
            x_coords = [v["x"] * img_w * zoom_level for v in vertices]
            y_coords = [v["y"] * img_h * zoom_level for v in vertices]

            x_min = max(0, int(min(x_coords)))
            y_min = max(0, int(min(y_coords)))
            x_max = min(int(img_w * zoom_level), int(max(x_coords)))
            y_max = min(int(img_h * zoom_level), int(max(y_coords)))

            width = x_max - x_min
            height = y_max - y_min

            if width <= 2 or height <= 2:
                continue

            # Build tooltip content
            content = box.get("content", "").strip()
            confidence = box.get("confidence", 1.0)

            tooltip_lines = [
                f"<div style='font-weight:bold;color:{color};'>{type_name}</div>"
            ]

            if content:
                display_content = (
                    content[:100] + "..." if len(content) > 100 else content
                )
                tooltip_lines.append(
                    f"<div style='margin:5px 0;'><strong>Content:</strong><br>{html_lib.escape(display_content)}</div>"
                )

            if confidence < 1.0:
                tooltip_lines.append(
                    f"<div style='font-size:0.9em;color:#666;'><strong>Confidence:</strong> {confidence:.1%}</div>"
                )

            details = box.get("details")
            if details:
                if box_type == "tables":
                    rows = details.get("rowCount", 0)
                    cols = details.get("columnCount", 0)
                    tooltip_lines.append(
                        f"<div style='font-size:0.9em;color:#666;'><strong>Size:</strong> {rows} rows x {cols} columns</div>"
                    )
                elif box_type == "form_fields":
                    role = details.get("role", "").title()
                    key_c = details.get("keyContent", "")
                    val_c = details.get("valueContent", "")
                    if role:
                        tooltip_lines.append(
                            f"<div style='font-size:0.9em;color:#666;'><strong>Role:</strong> {role}</div>"
                        )
                    if key_c and val_c:
                        tooltip_lines.append(
                            f"<div style='font-size:0.9em;color:#666;'><strong>{html_lib.escape(key_c)}</strong> = {html_lib.escape(val_c)}</div>"
                        )
                elif box_type == "entities":
                    etype = details.get("entityType", "")
                    norm = details.get("normalizedValue", "")
                    if etype:
                        tooltip_lines.append(
                            f"<div style='font-size:0.9em;color:#666;'><strong>Type:</strong> {html_lib.escape(etype)}</div>"
                        )
                    if norm:
                        tooltip_lines.append(
                            f"<div style='font-size:0.9em;color:#666;'><strong>Normalized:</strong> {html_lib.escape(norm)}</div>"
                        )
                elif box_type == "checkboxes":
                    state = details.get("state", "unknown")
                    tooltip_lines.append(
                        f"<div style='font-size:0.9em;color:#666;'><strong>State:</strong> {state}</div>"
                    )

            tooltip_content = "".join(tooltip_lines)
            overlay_id = f"overlay-{overlay_count}"
            overlay_count += 1

            overlays_html += f'''
            <div class="annotation-overlay"
                 id="{overlay_id}"
                 data-tooltip="{html_lib.escape(tooltip_content)}"
                 style="position:absolute;left:{x_min}px;top:{y_min}px;width:{width}px;height:{height}px;
                        border:2px solid {color};background:rgba(0,0,0,0.05);cursor:help;
                        transition:all 0.2s ease;">
            </div>'''

    display_w = int(img_w * zoom_level)
    display_h = int(img_h * zoom_level)

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
        body {{ margin: 0; padding: 10px; font-family: 'Source Sans Pro', sans-serif; }}
        .annotation-overlay {{ transition: all 0.2s ease; }}
        .annotation-overlay:hover {{
            background: rgba(255,255,255,0.3) !important;
            border-width: 3px !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important;
        }}
        .custom-tooltip {{ word-wrap: break-word; white-space: normal; }}
        #{container_id} {{ margin: 0 auto; display: block; }}
        </style>
    </head>
    <body>
        <div id="{container_id}" style="position:relative;display:inline-block;">
            <img src="data:image/png;base64,{image_data}"
                 style="display:block;width:{display_w}px;height:{display_h}px;border:1px solid #ddd;border-radius:5px;"
                 alt="Document page {page_idx + 1}" />
            {overlays_html}

            <div id="tooltip-{container_id}" class="custom-tooltip"
                 style="position:absolute;background:rgba(0,0,0,0.9);color:white;padding:12px;
                        border-radius:8px;font-size:13px;line-height:1.4;max-width:300px;
                        pointer-events:none;z-index:1000;display:none;
                        box-shadow:0 4px 12px rgba(0,0,0,0.3);">
            </div>
        </div>

        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            const container = document.getElementById('{container_id}');
            const tooltip = document.getElementById('tooltip-{container_id}');
            if (!container || !tooltip) return;

            const overlays = container.querySelectorAll('.annotation-overlay');
            overlays.forEach(overlay => {{
                overlay.addEventListener('mouseenter', function(e) {{
                    const tc = this.getAttribute('data-tooltip');
                    if (tc) {{ tooltip.innerHTML = tc; tooltip.style.display = 'block'; }}
                }});
                overlay.addEventListener('mousemove', function(e) {{
                    const rect = container.getBoundingClientRect();
                    let x = e.clientX - rect.left + 10;
                    let y = e.clientY - rect.top - 10;
                    const tr = tooltip.getBoundingClientRect();
                    const cr = container.getBoundingClientRect();
                    if (x + tr.width > cr.width) x = x - tr.width - 20;
                    if (y < 0) y = y + 30;
                    tooltip.style.left = x + 'px';
                    tooltip.style.top = y + 'px';
                }});
                overlay.addEventListener('mouseleave', function() {{
                    tooltip.style.display = 'none';
                }});
            }});
        }});
        </script>
    </body>
    </html>
    '''

    return html_content


# ------------------------------------------------------------------
# Annotation legend
# ------------------------------------------------------------------


def _show_annotation_legend(display_width: int, zoom_level: float):
    """Display annotation legend."""
    width = int(display_width * zoom_level)
    with st.expander("Document Annotations Legend", expanded=False):
        items_html = ""
        for box_type, info in ELEMENT_INFO.items():
            items_html += f"""
            <div style="display: flex; align-items: center;">
                <div style="width: 20px; height: 12px; background-color: {info['color']};
                            margin-right: 8px; border: 1px solid #ccc; border-radius: 2px;"></div>
                <span style="font-size: 14px; color: #333;">{info['name']}</span>
            </div>
            """
        st.markdown(
            f"""
            <div style="background: linear-gradient(90deg, #f8f9fa 0%, #e9ecef 100%);
                        padding: 15px; border-radius: 8px; border: 1px solid #dee2e6;
                        width: {width}px; max-width: 100%;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px;">
                    {items_html}
                </div>
                <div style="font-size: 12px; color: #6c757d; margin-top: 10px; font-style: italic;">
                    Hover over highlighted areas to see detailed information
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ------------------------------------------------------------------
# Document preview
# ------------------------------------------------------------------


def render_document_preview(uploaded_file, file_source: str):
    """Render document preview with optional annotations."""
    if not uploaded_file:
        return

    st.header("Document Viewer")

    # Read file data
    try:
        if hasattr(uploaded_file, "read"):
            uploaded_file.seek(0)
            file_data = uploaded_file.read()
        elif hasattr(uploaded_file, "getvalue"):
            file_data = uploaded_file.getvalue()
        else:
            st.error("Unable to read file data")
            return

        if not file_data:
            st.error("File appears to be empty or corrupted")
            return
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return

    # File info
    file_info = (
        DocumentProcessor.get_file_info(uploaded_file)
        if hasattr(uploaded_file, "name")
        else {}
    )
    if file_info:
        c1, c2, c3, c4 = st.columns(4)
        name = file_info.get("name", "Unknown")
        with c1:
            st.metric("File Name", (name[:20] + "...") if len(name) > 20 else name)
        with c2:
            st.metric("File Size", f"{file_info.get('size_mb', 0)} MB")
        with c3:
            st.metric("File Type", file_info.get("extension", "?").upper())
        with c4:
            st.metric("Source", file_source.title())

    # Convert to images
    try:
        ext = (
            uploaded_file.name.split(".")[-1].lower()
            if hasattr(uploaded_file, "name")
            else "pdf"
        )
        images = DocumentProcessor.convert_to_images(file_data, ext)

        if not images:
            st.warning("Could not generate preview for this document type.")
            return

        st.session_state.document_images = images

        # Controls row
        col1, col2, col3 = st.columns([2, 2, 2])

        with col1:
            if len(images) > 1:
                st.session_state.current_page_idx = max(
                    0, min(st.session_state.current_page_idx, len(images) - 1)
                )
                nav1, nav2, nav3 = st.columns([1, 2, 1])
                with nav1:
                    if st.button("Prev", disabled=st.session_state.current_page_idx == 0):
                        st.session_state.current_page_idx -= 1
                        st.rerun()
                with nav2:
                    page_idx = st.selectbox(
                        "Page:",
                        range(len(images)),
                        index=st.session_state.current_page_idx,
                        format_func=lambda x: f"Page {x + 1} of {len(images)}",
                        key="page_selector",
                    )
                    if page_idx != st.session_state.current_page_idx:
                        st.session_state.current_page_idx = page_idx
                with nav3:
                    if st.button(
                        "Next",
                        disabled=st.session_state.current_page_idx == len(images) - 1,
                    ):
                        st.session_state.current_page_idx += 1
                        st.rerun()
                page_idx = st.session_state.current_page_idx
            else:
                page_idx = 0
                st.write("Page 1 of 1")

        with col2:
            has_result = st.session_state.analysis_result is not None
            show_annotations = st.checkbox(
                "Show Annotations", value=True, disabled=not has_result
            )
            if not has_result:
                st.caption("Annotations available after analysis")

        with col3:
            show_labels = st.checkbox(
                "Show labels",
                value=True,
                help="Show text labels on bounding boxes",
            )
            zoom_level = st.slider(
                "Zoom",
                min_value=0.25,
                max_value=2.0,
                value=1.0,
                step=0.25,
                format="%.2fx",
            )

        # Display image
        if page_idx < len(images):
            display_image = images[page_idx]

            if show_annotations and st.session_state.analysis_result:
                try:
                    analysis = st.session_state.analysis_result
                    bounding_boxes = analysis.get_bounding_boxes()

                    # Fix rotated page coordinates: if the API reports
                    # portrait dimensions but the rendered image is landscape
                    # (or vice-versa), the PDF has a /Rotate flag.  Transform
                    # normalised vertices so boxes align with the visual image.
                    api_dims = analysis.get_page_dimensions(page_idx)
                    if api_dims:
                        api_portrait = api_dims["width"] < api_dims["height"]
                        img_portrait = display_image.width < display_image.height
                        if api_portrait != img_portrait:
                            for boxes in bounding_boxes.values():
                                for box in boxes:
                                    if box.get("page", 0) == page_idx:
                                        box["vertices"] = [
                                            {"x": 1 - v["y"], "y": v["x"]}
                                            for v in box["vertices"]
                                        ]

                    # Check if there are any bounding boxes at all
                    has_boxes = any(boxes for boxes in bounding_boxes.values())

                    if not has_boxes and analysis.is_layout_parser_result():
                        st.info(
                            "Layout Parser detects document structure (headings, "
                            "paragraphs, tables, lists) but the GCP API does not "
                            "return bounding box coordinates for these blocks, so "
                            "visual overlays are not available. See the **Document "
                            "Layout** tab below for the detected structure. For "
                            "bounding box overlays, use **Form Parser** or **OCR "
                            "Processor** instead."
                        )
                        st.image(
                            display_image,
                            caption=f"Page {page_idx + 1}",
                            use_container_width=True,
                        )
                    elif show_labels:
                        _show_annotation_legend(display_image.width, zoom_level)
                        html_content = _create_interactive_annotations(
                            display_image, bounding_boxes, page_idx, zoom_level
                        )
                        component_height = int(display_image.height * zoom_level) + 40
                        components.html(html_content, height=component_height, scrolling=False)
                    else:
                        annotator = SimpleDocumentAnnotator()
                        annotated = annotator.annotate_image(
                            display_image, bounding_boxes, page_idx, show_labels=False
                        )
                        st.image(
                            annotated,
                            caption=f"Page {page_idx + 1} (annotated)",
                            use_container_width=True,
                        )
                except Exception as e:
                    st.error(f"Could not create annotations: {e}")
                    st.image(display_image, caption=f"Page {page_idx + 1}", use_container_width=True)
            else:
                st.image(display_image, caption=f"Page {page_idx + 1}", use_container_width=True)

    except Exception as e:
        st.error(f"Error generating document preview: {e}")


# ------------------------------------------------------------------
# Analysis results
# ------------------------------------------------------------------


def render_analysis_results():
    """Render analysis results section."""
    if not st.session_state.analysis_result:
        return

    st.header("Analysis Results")
    ResultsDisplay.render_results_tabs(
        st.session_state.analysis_result,
        st.session_state.raw_result_dict or {},
    )


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main():
    """Main application function."""
    logger.info("Starting GCP Document AI Showcase")

    initialize_session_state()
    render_main_header()

    # Create client
    client = create_gcp_client()

    if not client:
        logger.error("No GCP Document AI client available")
        st.stop()

    st.session_state.gcp_client = client

    # Discover processors
    if st.session_state.discovered_processors is None:
        try:
            st.session_state.discovered_processors = client.list_processors()
        except Exception as e:
            logger.warning(f"Could not discover processors: {e}")
            st.session_state.discovered_processors = []

    # Connection status
    render_connection_status(client)

    # Processor selection
    processor_info = ProcessorSelector.render_processor_selector(
        st.session_state.discovered_processors
        if st.session_state.discovered_processors
        else None
    )

    if not processor_info:
        st.info("Please select or configure a Document AI processor from the sidebar to begin.")
        st.stop()

    st.session_state.selected_processor = processor_info

    # Main content: two columns
    col1, col2 = st.columns([2, 3])

    with col1:
        uploaded_file, file_source = FileUploadSection.render_upload_section()

        # Clear state when file removed
        if not uploaded_file:
            if st.session_state.get("current_file_id") is not None:
                st.session_state.analysis_result = None
                st.session_state.raw_result_dict = None
                st.session_state.document_images = None
                st.session_state.current_page_idx = 0
                st.session_state.current_file_id = None
                st.session_state.uploaded_file = None

        if uploaded_file:
            # Detect document change
            current_file_id = None
            if hasattr(uploaded_file, "name") and hasattr(uploaded_file, "getvalue"):
                try:
                    size = len(uploaded_file.getvalue())
                    current_file_id = f"{uploaded_file.name}_{size}_{file_source}"
                except Exception:
                    current_file_id = f"{uploaded_file.name}_{file_source}"
            elif hasattr(uploaded_file, "name"):
                current_file_id = f"{uploaded_file.name}_{file_source}"
            else:
                current_file_id = f"unknown_{file_source}"

            if current_file_id != st.session_state.current_file_id:
                st.session_state.analysis_result = None
                st.session_state.raw_result_dict = None
                st.session_state.document_images = None
                st.session_state.current_page_idx = 0
                st.session_state.current_file_id = current_file_id

            # Validate
            is_valid, msg = DocumentProcessor.validate_file(uploaded_file)
            if is_valid:
                st.success(msg)
                st.session_state.uploaded_file = uploaded_file

                # Analyze button
                if st.button("Analyze Document", type="primary", use_container_width=True):
                    try:
                        if hasattr(uploaded_file, "read"):
                            uploaded_file.seek(0)
                            file_data = uploaded_file.read()
                        elif hasattr(uploaded_file, "getvalue"):
                            file_data = uploaded_file.getvalue()
                        else:
                            st.error("Unable to read file data for analysis")
                            st.stop()

                        if not file_data:
                            st.error("File data is empty. Please re-upload.")
                            st.stop()

                        mime_type = DocumentProcessor.get_mime_type(
                            uploaded_file.name if hasattr(uploaded_file, "name") else "document.pdf"
                        )
                        handle_document_analysis(
                            client, processor_info, file_data, mime_type
                        )
                    except Exception as e:
                        st.error(f"Error preparing file for analysis: {e}")
            else:
                st.error(msg)

    with col2:
        if st.session_state.uploaded_file:
            render_document_preview(
                st.session_state.uploaded_file, file_source or "upload"
            )

    # Full-width results
    render_analysis_results()

    # Footer
    st.markdown("---")
    st.markdown(
        "Built with [Streamlit](https://streamlit.io/) and "
        "[GCP Document AI](https://cloud.google.com/document-ai)"
    )


if __name__ == "__main__":
    main()
