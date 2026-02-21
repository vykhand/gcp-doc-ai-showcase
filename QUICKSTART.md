# GCP Document AI - Quick Start Guide

This guide walks you through setting up GCP Document AI from scratch.

> **Note:** Steps 1–2 and the CLI option in step 4 use the `gcloud` CLI. If you don't have it installed, follow the [official installation guide](https://cloud.google.com/sdk/docs/install). On macOS you can also install it via Homebrew:
>
> ```bash
> brew install --cask google-cloud-sdk
> ```
>
> After installing, authenticate with `gcloud auth login`. If you prefer not to install the CLI, you can do everything through the [GCP Console](https://console.cloud.google.com) instead.

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

## 4. Create a Service Account & Download Key

### Via GCP Console (recommended)

1. Go to **GCP Console > IAM & Admin > Service Accounts**
2. Click **Create Service Account**
3. Name it (e.g., `docai-sa`), click **Create and Continue**
4. Grant the role **Document AI > Cloud Document AI API User** (`roles/documentai.apiUser`), click **Continue**, then **Done**
5. Click on the newly created service account
6. Go to the **Keys** tab
7. Click **Add Key > Create new key**
8. Select **JSON** and click **Create**
9. The key file downloads automatically — save it somewhere safe

### Via CLI

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

Edit `.env` with your endpoint and path to the service account key:

```
GCP_DOCAI_ENDPOINT=https://us-documentai.googleapis.com/v1/projects/my-docai-project/locations/us
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

The endpoint encodes your project ID and location. Replace `my-docai-project` with your project ID and `us` with your region (`us` or `eu`).

### Streamlit Cloud

No secrets are required by default. Each user provides their own endpoint and service account key JSON in the sidebar. See [STREAMLIT_DEPLOYMENT.md](STREAMLIT_DEPLOYMENT.md) for details.

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

Ensure the service account has `roles/documentai.apiUser`:

```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:docai-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/documentai.apiUser"
```

### "Processor not found" errors

- Check the processor ID is correct
- Ensure the processor is in the same location (us/eu) as your endpoint
- Verify the processor state is ENABLED in the Console

### No processors discovered

The app auto-discovers processors via the REST API. If none appear:
- Make sure you've created at least one processor in the configured project/location
- Verify the service account has `documentai.processors.list` permission

### Debug logging

```bash
export GCP_DOCAI_LOG_LEVEL=DEBUG
uv run streamlit run app.py
```
