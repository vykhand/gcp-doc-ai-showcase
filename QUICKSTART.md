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

## 4. Set Up Authentication

### Option A: Application Default Credentials (local development)

```bash
gcloud auth application-default login
```

### Option B: Service Account (production / Streamlit Cloud)

```bash
# Create service account
gcloud iam service-accounts create docai-sa \
    --display-name="Document AI Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding my-docai-project \
    --member="serviceAccount:docai-sa@my-docai-project.iam.gserviceaccount.com" \
    --role="roles/documentai.apiUser"

# Download key
gcloud iam service-accounts keys create key.json \
    --iam-account=docai-sa@my-docai-project.iam.gserviceaccount.com
```

## 5. Configure the Application

### Local development

Create a `.env` file from the template:

```bash
cp .env.template .env
```

Edit `.env`:

```
GCP_PROJECT_ID=my-docai-project
GCP_LOCATION=us
```

If using a service account key file:

```
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

### Streamlit Cloud

Copy `.streamlit/secrets.toml.template` to `.streamlit/secrets.toml` and fill in your values. See [STREAMLIT_DEPLOYMENT.md](STREAMLIT_DEPLOYMENT.md) for details.

## 6. Run the Application

```bash
# Install dependencies
uv sync

# Run
uv run streamlit run app.py
```

The app will open in your browser. Select a processor from the sidebar, upload a document, and click **Analyze Document**.

## Troubleshooting

### "Permission denied" errors

Ensure your account/service account has `roles/documentai.apiUser`:

```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="user:you@example.com" \
    --role="roles/documentai.apiUser"
```

### "Processor not found" errors

- Check the processor ID is correct
- Ensure the processor is in the same location (us/eu) as configured
- Verify the processor state is ENABLED in the Console

### No processors discovered

The app auto-discovers processors via `list_processors()`. If none appear:
- Make sure you've created at least one processor in the configured project/location
- Check that your credentials have `documentai.processors.list` permission

### Debug logging

```bash
export GCP_DOCAI_LOG_LEVEL=DEBUG
uv run streamlit run app.py
```
