# Deploying to Streamlit Community Cloud

## Prerequisites

- A GitHub repository with this project
- A Streamlit Community Cloud account ([share.streamlit.io](https://share.streamlit.io))

## Step 1: Generate requirements.txt

Streamlit Cloud doesn't support `uv` natively, so generate a `requirements.txt`:

```bash
uv pip compile pyproject.toml -o requirements.txt
```

Commit `requirements.txt` to your repository.

## Step 2: Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app**
3. Select your GitHub repository
4. Set the main file path to `app.py`
5. Click **Deploy**

## Step 3: Authentication

No secrets configuration is needed by default. Each user provides their own **endpoint** and **service account key JSON** in the sidebar. This ensures users consume their own GCP resources.

If you want to pre-configure defaults (so users don't have to enter credentials), add secrets in the Streamlit Cloud dashboard:

1. Open your app's settings
2. Go to the **Secrets** tab
3. Add:

```toml
GCP_DOCAI_ENDPOINT = "https://us-documentai.googleapis.com/v1/projects/your-project/locations/us"

[gcp_service_account]
type = "service_account"
project_id = "your-gcp-project-id"
private_key_id = "your-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "docai-sa@your-project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
universe_domain = "googleapis.com"
```

4. Click **Save**

## Step 4: System Dependencies

The `packages.txt` file tells Streamlit Cloud to install `poppler-utils` (needed for PDF rendering). This file is automatically detected.

## Verifying the Deployment

After deployment:

1. Open the app URL
2. Enter your endpoint and paste your service account key JSON in the sidebar
3. Check the **Connection Status** expander — it should show "Connection successful!"
4. Your processors should appear in the processor dropdown
5. Upload a document and test analysis

## Troubleshooting

### App crashes on startup

- Check the Streamlit Cloud logs for import errors
- Ensure `requirements.txt` is up to date (`uv pip compile pyproject.toml -o requirements.txt`)
- Verify `packages.txt` includes `poppler-utils`

### Authentication failures

- Verify the service account JSON is valid (must contain `private_key`, `client_email`, `token_uri`)
- Ensure the service account has `roles/documentai.apiUser` on the project

### No processors found

- Ensure at least one processor is created in the project/location specified in the endpoint
- Verify the service account has `documentai.processors.list` permission
