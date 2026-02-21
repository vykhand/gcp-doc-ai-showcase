# GCP Document AI Showcase

Interactive Streamlit application for processing documents with **Google Cloud Document AI** and visually overlaying extracted information (text, tables, entities, form fields, checkboxes) with interactive bounding boxes.

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
- Authentication (ADC or service account key)

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd gcp-doc-ai-showcase

# Install dependencies
uv sync

# Set up authentication (choose one):

# Option A: Application Default Credentials
gcloud auth application-default login
export GCP_PROJECT_ID="your-project-id"
export GCP_LOCATION="us"

# Option B: Service account key
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
export GCP_PROJECT_ID="your-project-id"
export GCP_LOCATION="us"

# Run the app
uv run streamlit run app.py
```

See [QUICKSTART.md](QUICKSTART.md) for detailed GCP setup instructions.

## Architecture

```
app.py                  # Main Streamlit entry point
config.py               # Processor definitions, categories, colors
gcp_docai_client.py     # GCP Document AI SDK client + DocumentAnalysisResult
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

## Authentication Options

1. **Application Default Credentials (ADC)**: `gcloud auth application-default login`
2. **Service Account Key**: Set `GOOGLE_APPLICATION_CREDENTIALS` env var
3. **Streamlit Secrets**: Configure in `.streamlit/secrets.toml` (for cloud deployment)
4. **Manual Input**: Enter credentials directly in the sidebar

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
