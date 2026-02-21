"""
Reusable Streamlit UI components for the GCP Document AI showcase.
"""

import json
from typing import Dict, List, Any, Optional

import streamlit as st

from config import (
    GCP_DOCAI_PROCESSORS,
    PROCESSOR_CATEGORIES,
    GCP_DOCAI_LOCATIONS,
    GCP_DOCAI_DEFAULT_LOCATION,
    get_processors_by_category,
    get_processor_display_name,
    get_processor_info,
)


# ------------------------------------------------------------------
# Project configuration (GCP-specific)
# ------------------------------------------------------------------


class ProjectConfiguration:
    """GCP project configuration in the sidebar."""

    @staticmethod
    def render_project_config() -> Dict[str, Any]:
        """
        Render project ID, location, and auth method inputs.

        Returns:
            Dict with project_id, location, and optional credentials info.
        """
        st.sidebar.header("GCP Project")

        project_id = st.sidebar.text_input(
            "Project ID",
            value=st.session_state.get("gcp_project_id", ""),
            placeholder="my-gcp-project",
            help="Your Google Cloud project ID",
            key="gcp_project_id_input",
        )

        location = st.sidebar.selectbox(
            "Location",
            options=GCP_DOCAI_LOCATIONS,
            index=GCP_DOCAI_LOCATIONS.index(GCP_DOCAI_DEFAULT_LOCATION),
            help="Document AI processing location (us or eu)",
        )

        return {"project_id": project_id, "location": location}


# ------------------------------------------------------------------
# Processor selector
# ------------------------------------------------------------------


class ProcessorSelector:
    """Component for selecting a Document AI processor."""

    @staticmethod
    def render_processor_selector(
        discovered_processors: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Render processor selection UI.

        If discovered_processors are available (from list_processors), show them
        in a dropdown. Otherwise, fall back to manual processor ID entry with
        a type hint dropdown.

        Returns:
            Dict with processor_id and processor_type, or None
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
                return {
                    "processor_id": proc["id"],
                    "processor_type": proc["type"],
                    "display_name": proc["display_name"],
                }
            return None
        else:
            return ProcessorSelector._render_manual_input()

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

        if processor_id:
            return {
                "processor_id": processor_id.strip(),
                "processor_type": selected_type or "UNKNOWN",
                "display_name": selected_type_label or processor_id,
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
                type=["pdf", "jpg", "jpeg", "png", "bmp", "tiff", "tif", "gif", "webp"],
                help="Upload a document (PDF, images). Max 40 MB for online processing.",
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
                    else:
                        st.error("Failed to load sample document")

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
        tab_entities, tab_tables, tab_form, tab_text, tab_json = st.tabs(
            ["Entities / Fields", "Tables", "Form Fields", "Text", "Raw JSON"]
        )

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
    def _render_entities_view(analysis_result):
        """Render extracted entities."""
        entities = analysis_result.get_entities()
        if not entities:
            st.info("No entities extracted. Try using a specialized processor (Invoice, Receipt, etc.).")
            return

        for ent in entities:
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                st.write(f"**{ent['type']}**")
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
                "Please enter your project ID and credentials."
            )
