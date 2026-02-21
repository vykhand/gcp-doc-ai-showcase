# GCP Document AI - Quick Start Guide

This guide walks you through setting up GCP Document AI from scratch.

## 1. Create or Select a GCP Project

```bash
# Create a new project (optional)
gcloud projects create my-docai-project --name="Document AI Showcase"

# Set the project
gcloud config set project my-docai-project
```

## 2. Enable the Document AI API

```bash
gcloud services enable documentai.googleapis.com
```

## 3. Create Processors

You need to create at least one processor. Go to the [GCP Console > Document AI](https://console.cloud.google.com/ai/document-ai) or use the CLI.

### Via Console (recommended)

1. Navigate to **Document AI** in the GCP Console
2. Click **Create Processor**
3. Choose a processor type (e.g., "Enterprise Document OCR", "Invoice Parser", "Form Parser")
4. Select a region (us or eu)
5. Give it a name and click **Create**
6. Note the **Processor ID** from the processor details page

### Recommended processors to create for the showcase

| Processor Type | Use Case |
|---------------|----------|
| Enterprise Document OCR | General text extraction |
| Form Parser | Forms with key-value pairs and tables |
| Invoice Parser | Invoice processing |
| Expense Parser | Receipt/expense reports |

## 4. Create an API Key

1. Go to **GCP Console > APIs & Services > Credentials**
2. Click **Create Credentials > API Key**
3. Click **Restrict Key** and under **API restrictions**, select **Cloud Document AI API**
4. Save and copy your API key

## 5. Configure the Application

### Local development

Create a `.env` file from the template:

```bash
cp .env.template .env
```

Edit `.env` with your endpoint and API key:

```
GCP_DOCAI_ENDPOINT=https://us-documentai.googleapis.com/v1/projects/my-docai-project/locations/us
GCP_DOCAI_API_KEY=AIza...
```

The endpoint encodes your project ID and location. Replace `my-docai-project` with your project ID and `us` with your region (`us` or `eu`).

### Streamlit Cloud

No secrets are required by default. Each user provides their own endpoint and API key in the sidebar. See [STREAMLIT_DEPLOYMENT.md](STREAMLIT_DEPLOYMENT.md) for details.

## 6. Run the Application

```bash
# Install dependencies
uv sync

# Run
uv run streamlit run app.py
```

The app will open in your browser. Select a processor from the sidebar, upload a document, and click **Analyze Document**.

## Troubleshooting

### "Permission denied" or 403 errors

Ensure the API key is restricted to the **Cloud Document AI API** and that the Document AI API is enabled in your project.

### "Processor not found" errors

- Check the processor ID is correct
- Ensure the processor is in the same location (us/eu) as your endpoint
- Verify the processor state is ENABLED in the Console

### No processors discovered

The app auto-discovers processors via the REST API. If none appear:
- Make sure you've created at least one processor in the configured project/location
- Verify the API key has access to the Document AI API

### Debug logging

```bash
export GCP_DOCAI_LOG_LEVEL=DEBUG
uv run streamlit run app.py
```
