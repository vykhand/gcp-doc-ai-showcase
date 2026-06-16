"""
Reusable Streamlit UI components for the GCP Document AI showcase.
"""

import json
from typing import Dict, List, Any, Optional

import streamlit as st

from config import (
    GCP_DOCAI_PROCESSORS,
    PROCESSOR_CATEGORIES,
    get_processors_by_category,
    get_processor_display_name,
    get_processor_info,
)


# ------------------------------------------------------------------
# Processor selector
# ------------------------------------------------------------------


class ProcessorSelector:
    """Component for selecting a Document AI processor."""

    @staticmethod
    def render_processor_selector(
        discovered_processors: Optional[List[Dict[str, Any]]] = None,
        client: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Render processor selection UI.

        If discovered_processors are available (from list_processors), show them
        in a dropdown. Otherwise, fall back to manual processor ID entry with
        a type hint dropdown.

        Args:
            discovered_processors: Processors discovered in the project, if any.
            client: GCP client, used to list processor versions for the version
                selector.

        Returns:
            Dict with processor_id, processor_type, and processor_version, or None
        """
        st.sidebar.header("Processor")

        if discovered_processors:
            # Build options from discovered processors
            proc_options = {
                f"{p['display_name']} ({p['type']})": p
                for p in discovered_processors
                if p.get("state") == "ENABLED"
            }

            if not proc_options:
                st.sidebar.warning("No enabled processors found in this project.")
                return ProcessorSelector._render_manual_input()

            selected_label = st.sidebar.selectbox(
                "Choose a processor:",
                list(proc_options.keys()),
                help="Select from processors discovered in your GCP project",
            )

            if selected_label:
                proc = proc_options[selected_label]
                ProcessorSelector._render_processor_info_from_discovered(proc)
                version = ProcessorSelector._render_version_selector(client, proc["id"])
                return {
                    "processor_id": proc["id"],
                    "processor_type": proc["type"],
                    "display_name": proc["display_name"],
                    "processor_version": version,
                }
            return None
        else:
            return ProcessorSelector._render_manual_input()

    @staticmethod
    def _render_version_selector(client: Optional[Any], processor_id: str) -> Optional[str]:
        """Render a processor-version dropdown (deployed versions + default).

        Returns the selected version ID, or None for the processor's default
        version. Used to target Gemini-powered Layout Parser / Custom Extractor
        preview versions. Results are cached per processor to avoid an API call
        on every rerun.
        """
        if client is None:
            return None

        cache = st.session_state.setdefault("processor_versions_cache", {})
        if processor_id not in cache:
            try:
                cache[processor_id] = client.list_processor_versions(processor_id)
            except Exception:
                cache[processor_id] = []

        deployed = [v for v in cache[processor_id] if v.get("state") == "DEPLOYED"]

        # Map a human label -> version id; "Default version" -> None
        options: Dict[str, Optional[str]] = {"Default version": None}
        for v in deployed:
            label = v.get("display_name") or v.get("id")
            options[f"{label} ({v.get('id')})"] = v.get("id")

        if len(options) == 1:
            # No deployed versions discoverable; silently use the default.
            return None

        selected = st.sidebar.selectbox(
            "Processor version:",
            list(options.keys()),
            help=(
                "Choose a specific deployed version (e.g. a Gemini-powered "
                "Layout Parser or Custom Extractor), or use the processor default."
            ),
        )
        return options.get(selected)

    @staticmethod
    def _render_manual_input() -> Optional[Dict[str, Any]]:
        """Render manual processor ID input with processor type hint."""
        # Processor type hint dropdown
        categorized = get_processors_by_category()
        options = []
        option_to_type = {}

        for category in PROCESSOR_CATEGORIES:
            if category in categorized:
                for proc_type in categorized[category]:
                    display_name = get_processor_display_name(proc_type)
                    options.append(display_name)
                    option_to_type[display_name] = proc_type

        selected_type_label = st.sidebar.selectbox(
            "Processor type (reference):",
            options,
            help="Select the type of processor you want to use. You still need to provide the processor ID below.",
        )

        selected_type = option_to_type.get(selected_type_label)
        if selected_type:
            ProcessorSelector._render_processor_info(selected_type)

        processor_id = st.sidebar.text_input(
            "Processor ID",
            placeholder="abc123def456",
            help=(
                "Enter the processor ID from your GCP project. "
                "Find it in the GCP Console under Document AI > Processors."
            ),
        )

        processor_version = st.sidebar.text_input(
            "Processor version ID (optional)",
            placeholder="pretrained-layout-parser-v1.5-pro-2025-08-25",
            help=(
                "Optional. Target a specific deployed version (e.g. a Gemini-powered "
                "Layout Parser or Custom Extractor). Leave blank to use the default version."
            ),
        )

        if processor_id:
            return {
                "processor_id": processor_id.strip(),
                "processor_type": selected_type or "UNKNOWN",
                "display_name": selected_type_label or processor_id,
                "processor_version": processor_version.strip() or None,
            }
        return None

    @staticmethod
    def _render_processor_info(processor_type: str):
        """Display info about a processor type from our config."""
        info = get_processor_info(processor_type)
        if not info:
            return

        with st.sidebar.expander("Processor Information", expanded=False):
            st.write(f"**Name:** {info['name']}")
            st.write(f"**Description:** {info['description']}")
            st.write(f"**Category:** {info['category']}")
            st.write(f"**Max Pages (online):** {info['max_pages_online']}")
            st.write(f"**Entity Extraction:** {'Yes' if info['entity_extraction'] else 'No'}")
            st.write(f"**Capabilities:** {', '.join(info['capabilities'])}")

    @staticmethod
    def _render_processor_info_from_discovered(proc: Dict[str, Any]):
        """Display info about a discovered processor."""
        with st.sidebar.expander("Processor Information", expanded=False):
            st.write(f"**Display Name:** {proc['display_name']}")
            st.write(f"**Type:** {proc['type']}")
            st.write(f"**State:** {proc['state']}")
            st.write(f"**ID:** {proc['id']}")
            # Show additional info from our config if available
            info = get_processor_info(proc["type"])
            if info:
                st.write(f"**Description:** {info['description']}")
                st.write(f"**Max Pages (online):** {info['max_pages_online']}")
                st.write(f"**Entity Extraction:** {'Yes' if info['entity_extraction'] else 'No'}")


# ------------------------------------------------------------------
# Processing options
# ------------------------------------------------------------------


def render_processing_options(processor_type: str) -> Dict[str, Any]:
    """Render processing options in the sidebar and return them as a dict.

    Includes imageless mode (all processors) and OCR premium add-ons (shown only
    for the OCR processor). The returned dict is consumed by the analysis handler
    to build the request's ``processOptions`` / ``imagelessMode``.
    """
    opts: Dict[str, Any] = {"imageless_mode": False, "ocr": {}}
    with st.sidebar.expander("Processing Options", expanded=False):
        opts["imageless_mode"] = st.checkbox(
            "Imageless mode",
            value=False,
            help=(
                "Omit page images from the API response — smaller payload and up to "
                "30 pages online (instead of 15)."
            ),
        )
        if processor_type == "OCR_PROCESSOR":
            st.caption("OCR add-ons — require an OCR 2.0+ processor version")
            opts["ocr"] = {
                "enable_selection_mark_detection": st.checkbox(
                    "Selection mark detection",
                    value=False,
                    help="Detect filled / unfilled checkboxes and radio buttons.",
                ),
                "compute_style_info": st.checkbox(
                    "Font style info",
                    value=False,
                    help="Return font family, size, weight, and style.",
                ),
                "enable_math_ocr": st.checkbox(
                    "Math OCR (LaTeX)",
                    value=False,
                    help="Extract mathematical formulas as LaTeX.",
                ),
                "enable_image_quality_scores": st.checkbox(
                    "Image quality scores",
                    value=False,
                    help="Return page quality scores and defect detection.",
                ),
            }
    return opts


# ------------------------------------------------------------------
# File upload
# ------------------------------------------------------------------


class FileUploadSection:
    """Component for file upload and sample documents."""

    @staticmethod
    def render_upload_section():
        """
        Render the file upload section.

        Returns:
            Tuple of (uploaded_file, file_source_type)
        """
        st.header("Document Upload")

        upload_method = st.radio(
            "Choose upload method:",
            ["File Upload", "URL", "Sample Documents"],
            horizontal=True,
        )

        uploaded_file = None
        source_type = None

        if upload_method == "File Upload":
            uploaded_file = st.file_uploader(
                "Choose a document file",
                type=[
                    "pdf", "jpg", "jpeg", "png", "bmp", "tiff", "tif", "gif", "webp",
                    "docx", "pptx", "xlsx", "xlsm",
                ],
                help=(
                    "Upload a document (PDF, images, or Office files). Max 40 MB for "
                    "online processing. Office formats (DOCX/PPTX/XLSX/XLSM) require the "
                    "Layout Parser and have no image preview."
                ),
            )
            source_type = "upload"

        elif upload_method == "URL":
            url = st.text_input(
                "Enter document URL:",
                placeholder="https://example.com/document.pdf",
                help="Enter a direct URL to a document file",
            )
            if url and st.button("Load from URL"):
                with st.spinner("Downloading document..."):
                    from document_processor import DocumentProcessor

                    file_data = DocumentProcessor.download_sample_document(url)
                    if file_data:
                        import io

                        uploaded_file = io.BytesIO(file_data)
                        uploaded_file.name = url.split("/")[-1]
                        source_type = "url"
                        # Persist in session state so it survives reruns
                        st.session_state["_loaded_file"] = uploaded_file
                        st.session_state["_loaded_source"] = source_type
                    else:
                        st.error("Failed to download document from URL")

        elif upload_method == "Sample Documents":
            from document_processor import DocumentProcessor

            samples = DocumentProcessor.create_sample_documents()
            sample_names = list(samples.keys())
            selected_sample = st.selectbox(
                "Choose a sample document:",
                options=sample_names,
                help="Select a sample document for testing",
            )

            if selected_sample and st.button("Load Sample"):
                with st.spinner("Loading sample document..."):
                    sample_info = samples[selected_sample]
                    file_data = DocumentProcessor.download_sample_document(
                        sample_info["url"]
                    )
                    if file_data:
                        import io

                        uploaded_file = io.BytesIO(file_data)
                        uploaded_file.name = f"{selected_sample}.{sample_info['url'].split('.')[-1]}"
                        source_type = "sample"
                        st.session_state.recommended_processor = sample_info[
                            "processor_type"
                        ]
                        # Persist in session state so it survives reruns
                        st.session_state["_loaded_file"] = uploaded_file
                        st.session_state["_loaded_source"] = source_type
                    else:
                        st.error("Failed to load sample document")

        # On reruns (e.g. after clicking Analyze), restore from session state
        if uploaded_file is None and "_loaded_file" in st.session_state:
            uploaded_file = st.session_state["_loaded_file"]
            source_type = st.session_state.get("_loaded_source", "sample")

        # Clear persisted file when switching to File Upload (which has its own state)
        if upload_method == "File Upload" and "_loaded_file" in st.session_state:
            del st.session_state["_loaded_file"]
            del st.session_state["_loaded_source"]

        return uploaded_file, source_type


# ------------------------------------------------------------------
# Results display
# ------------------------------------------------------------------


class ResultsDisplay:
    """Display analysis results in multiple tabs."""

    @staticmethod
    def render_results_tabs(analysis_result, raw_dict: Dict[str, Any]):
        """
        Render results in a tabbed interface.

        Args:
            analysis_result: DocumentAnalysisResult instance
            raw_dict: JSON-serializable dict for the Raw JSON tab
        """
        is_layout = analysis_result.is_layout_parser_result()

        if is_layout:
            tab_names = ["Document Layout", "Chunks", "Entities / Fields", "Tables", "Form Fields", "Text", "Raw JSON"]
            tab_layout, tab_chunks, tab_entities, tab_tables, tab_form, tab_text, tab_json = st.tabs(tab_names)
        else:
            tab_names = ["Entities / Fields", "Tables", "Form Fields", "Text", "Raw JSON"]
            tab_entities, tab_tables, tab_form, tab_text, tab_json = st.tabs(tab_names)

        if is_layout:
            with tab_layout:
                ResultsDisplay._render_document_layout_view(analysis_result)
            with tab_chunks:
                ResultsDisplay._render_chunks_view(analysis_result)

        with tab_entities:
            ResultsDisplay._render_entities_view(analysis_result)

        with tab_tables:
            ResultsDisplay._render_tables_view(analysis_result)

        with tab_form:
            ResultsDisplay._render_form_fields_view(analysis_result)

        with tab_text:
            ResultsDisplay._render_text_view(analysis_result)

        with tab_json:
            ResultsDisplay._render_json_view(raw_dict)

    @staticmethod
    def _render_document_layout_view(analysis_result):
        """Render the hierarchical document layout from Layout Parser.

        Uses native Streamlit components for reliable rendering across themes.
        Page numbers from the API are already 1-based.
        """
        blocks = analysis_result.get_document_layout()
        if not blocks:
            st.info("No document layout blocks found.")
            return

        # Summary counts by type
        type_counts: Dict[str, int] = {}
        for b in blocks:
            t = b["type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        summary = ", ".join(f"{c} {t}" for t, c in type_counts.items())
        st.markdown(f"**{len(blocks)}** blocks detected  ({summary})")
        st.divider()

        for block in blocks:
            btype = block["type"]
            text = block["text"]
            page_start = block["page_start"]
            page_end = block["page_end"]

            # Page numbers are already 1-based from the API
            page_label = (
                f"p.{page_start}"
                if page_start == page_end
                else f"p.{page_start}\u2013{page_end}"
            )
            type_tag = btype.replace("-", " ").upper()

            if btype.startswith("heading"):
                st.caption(f"{type_tag}  \u00b7  {page_label}")
                if text:
                    st.markdown(f"**{text[:300]}**")
            elif btype in ("table", "list"):
                snippet = text[:80].replace("\n", " ") if text else "(empty)"
                with st.expander(f"{type_tag}  \u00b7  {page_label}  \u2014  {snippet}"):
                    if text:
                        st.text(text)
                    else:
                        st.caption("(no content)")
            else:
                snippet = text[:80].replace("\n", " ") if text else "(empty)"
                with st.expander(f"{type_tag}  \u00b7  {page_label}  \u2014  {snippet}"):
                    if text:
                        st.text(text)
                    else:
                        st.caption("(no content)")

    @staticmethod
    def _render_chunks_view(analysis_result):
        """Render chunked document data from Layout Parser."""
        chunks = analysis_result.get_chunked_document()
        if not chunks:
            st.info("No chunks found in the response.")
            return

        st.markdown(f"**{len(chunks)}** chunks extracted")

        for i, chunk in enumerate(chunks):
            page_span = chunk["page_span"]
            page_label = (
                f"Page {page_span['page_start']}"
                if page_span["page_start"] == page_span["page_end"]
                else f"Pages {page_span['page_start']}-{page_span['page_end']}"
            )
            header = f"Chunk {i + 1}"
            if chunk["chunk_id"]:
                header += f"  ({chunk['chunk_id']})"
            header += f"  — {page_label}"

            with st.expander(header, expanded=(i == 0)):
                st.text_area(
                    "Content",
                    value=chunk["content"],
                    height=min(300, max(100, len(chunk["content"]) // 3)),
                    disabled=True,
                    key=f"chunk_{i}",
                )

    @staticmethod
    def _render_entities_view(analysis_result):
        """Render extracted entities."""
        entities = analysis_result.get_entities()
        if not entities:
            st.info("No entities extracted. Try using a specialized processor (Invoice, Receipt, etc.).")
            return

        if any(ent.get("is_derived") for ent in entities):
            st.caption("✨ = derived entity (inferred by the model, not present verbatim in the text)")

        for ent in entities:
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                label = f"**{ent['type']}**"
                if ent.get("is_derived"):
                    label += " ✨"
                st.write(label)
            with col2:
                text = ent["mention_text"]
                if ent["normalized_value"]:
                    text += f" ({ent['normalized_value']})"
                st.write(text)
            with col3:
                conf = ent["confidence"] * 100
                if conf >= 90:
                    st.success(f"{conf:.1f}%")
                elif conf >= 70:
                    st.warning(f"{conf:.1f}%")
                else:
                    st.error(f"{conf:.1f}%")

    @staticmethod
    def _render_tables_view(analysis_result):
        """Render extracted tables."""
        tables = analysis_result.get_tables()
        if not tables:
            st.info("No tables detected.")
            return

        for i, table in enumerate(tables):
            with st.expander(
                f"Table {i + 1} (Page {table['page'] + 1}, {table['row_count']} rows x {table['col_count']} cols)",
                expanded=(i == 0),
            ):
                import pandas as pd

                all_rows = table["header_rows"] + table["body_rows"]
                if all_rows:
                    # Use first row as header if header_rows exist
                    if table["header_rows"]:
                        headers = table["header_rows"][0]
                        data = table["body_rows"]
                    else:
                        headers = [f"Col {j+1}" for j in range(table["col_count"])]
                        data = all_rows

                    try:
                        df = pd.DataFrame(data, columns=headers[:len(data[0])] if data else headers)
                        st.dataframe(df, use_container_width=True)
                    except Exception:
                        # Fall back to plain display
                        for row in all_rows:
                            st.write(" | ".join(row))

    @staticmethod
    def _render_form_fields_view(analysis_result):
        """Render form fields (key-value pairs)."""
        fields = analysis_result.get_form_fields()
        if not fields:
            st.info("No form fields detected. Try using the Form Parser processor.")
            return

        for ff in fields:
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                st.write(f"**{ff['key']}**")
            with col2:
                st.write(ff["value"])
            with col3:
                conf = ff["confidence"] * 100
                if conf >= 90:
                    st.success(f"{conf:.1f}%")
                elif conf >= 70:
                    st.warning(f"{conf:.1f}%")
                else:
                    st.error(f"{conf:.1f}%")

    @staticmethod
    def _render_text_view(analysis_result):
        """Render the full OCR text."""
        text = analysis_result.get_text()
        if text.strip():
            col1, col2 = st.columns([3, 1])
            with col2:
                st.download_button(
                    "Download Text",
                    data=text,
                    file_name="extracted_text.txt",
                    mime="text/plain",
                )
            st.markdown("### Extracted Text")
            st.text_area("", value=text, height=400, disabled=True)
        else:
            st.info("No text content available.")

    @staticmethod
    def _render_json_view(raw_dict: Dict[str, Any]):
        """Render the raw JSON response."""
        json_str = json.dumps(raw_dict, indent=2, ensure_ascii=False)

        col1, col2 = st.columns([3, 1])
        with col2:
            st.download_button(
                "Download JSON",
                data=json_str,
                file_name="analysis_result.json",
                mime="application/json",
            )

        st.markdown("### Raw Analysis Result")
        st.json(raw_dict)


# ------------------------------------------------------------------
# Status display
# ------------------------------------------------------------------


class StatusDisplay:
    """Status message helpers."""

    @staticmethod
    def show_progress(message: str):
        st.info(f"Processing: {message}")

    @staticmethod
    def show_success(message: str):
        st.success(message)

    @staticmethod
    def show_error(message: str):
        st.error(message)

    @staticmethod
    def show_warning(message: str):
        st.warning(message)


# ------------------------------------------------------------------
# Connection status
# ------------------------------------------------------------------


def render_connection_status(client):
    """Render connection status in the sidebar."""
    with st.sidebar.expander("Connection Status", expanded=False):
        if client:
            success, message = client.test_connection()
            if success:
                st.success(message)
            else:
                st.error(message)
        else:
            st.error(
                "No GCP Document AI client configured. "
                "Please enter your endpoint and API key."
            )
