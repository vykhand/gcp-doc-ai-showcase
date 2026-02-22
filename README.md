# GCP Document AI Showcase

Interactive Streamlit application for processing documents with **Google Cloud Document AI** and visually overlaying extracted information (text, tables, entities, form fields, checkboxes) with interactive bounding boxes.

**[Live Demo](https://gcp-doc-ai-showcase.streamlit.app/)**

## Features

- **Multiple processor types**: OCR, Form Parser, Layout Parser, Invoice, Receipt, Expense, Bank Statement, Pay Stub, W-2, ID Document, Passport, Driver License
- **Auto-discovery**: Automatically discovers processors configured in your GCP project
- **Interactive bounding boxes**: Hover tooltips showing content, confidence, and type-specific details
- **Visual annotation**: Color-coded overlays for text lines, tables, paragraphs, form fields, entities, and checkboxes
- **Multi-page support**: Page navigation with zoom controls
- **Multiple result views**: Entities, Tables, Form Fields, Text, Raw JSON tabs
- **Flexible upload**: File upload, URL input, or sample documents
- **Deployable**: Ready for Streamlit Community Cloud

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- A GCP project with Document AI API enabled
- At least one Document AI processor created in the project
- A service account with `roles/documentai.apiUser` and a downloaded JSON key

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd gcp-doc-ai-showcase

# Install dependencies
uv sync

# Set up authentication:
export GCP_DOCAI_ENDPOINT="https://us-documentai.googleapis.com/v1/projects/your-project-id/locations/us"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"

# Run the app
uv run streamlit run app.py
```

See [QUICKSTART.md](QUICKSTART.md) for detailed GCP setup instructions.

## Architecture

```
app.py                  # Main Streamlit entry point
config.py               # Processor definitions, categories, colors
gcp_docai_client.py     # GCP Document AI REST client + DocumentAnalysisResult
document_processor.py   # File validation, PDF-to-image, coordinate math
ui_components.py        # Reusable Streamlit UI components
simple_annotator.py     # PIL-based image annotation
logging_config.py       # Centralized logging
```

## Supported Formats

| Format | Extensions | Max Size |
|--------|-----------|----------|
| PDF | .pdf | 40 MB |
| JPEG | .jpg, .jpeg | 40 MB |
| PNG | .png | 40 MB |
| BMP | .bmp | 40 MB |
| TIFF | .tiff, .tif | 40 MB |
| GIF | .gif | 40 MB |
| WebP | .webp | 40 MB |

Online processing supports up to 15 pages per request.

## Authentication

Provide an **endpoint URL** and a **service account key**:

1. **Service account key**: Create a service account, grant `roles/documentai.apiUser`, download the JSON key.
2. **Endpoint**: `https://{location}-documentai.googleapis.com/v1/projects/{project_id}/locations/{location}`

You can supply these via:
- **Environment variables**: `GCP_DOCAI_ENDPOINT` and `GOOGLE_APPLICATION_CREDENTIALS`
- **Streamlit secrets**: Add to `.streamlit/secrets.toml`
- **Sidebar input**: Paste endpoint and key JSON directly in the app

## Visualization

Color scheme for bounding box annotations:

| Element Type | Color |
|-------------|-------|
| Text Lines | Blue `#007ACC` |
| Paragraphs | Dark Orchid `#9932CC` |
| Tables | Green `#00B04F` |
| Form Fields (KVPs) | Orange `#FF8C00` |
| Entities | Crimson `#DC143C` |
| Checkboxes | Purple `#8A2BE2` |

## Deployment

See [STREAMLIT_DEPLOYMENT.md](STREAMLIT_DEPLOYMENT.md) for Streamlit Community Cloud deployment instructions.

## License

MIT License. Attribution required when using or modifying this code.
