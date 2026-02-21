# Deploying to Streamlit Community Cloud

## Prerequisites

- A GitHub repository with this project
- A Streamlit Community Cloud account ([share.streamlit.io](https://share.streamlit.io))
- A GCP service account with `roles/documentai.apiUser`

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

## Step 3: Configure Secrets

In the Streamlit Cloud dashboard:

1. Open your app's settings
2. Go to the **Secrets** tab
3. Paste the following (with your actual values):

```toml
GCP_PROJECT_ID = "your-gcp-project-id"
GCP_LOCATION = "us"

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
2. Check the sidebar - it should show "Connection successful!" in the Connection Status expander
3. Your processors should appear in the processor dropdown
4. Upload a document and test analysis

## Troubleshooting

### App crashes on startup

- Check the Streamlit Cloud logs for import errors
- Ensure `requirements.txt` is up to date (`uv pip compile pyproject.toml -o requirements.txt`)
- Verify `packages.txt` includes `poppler-utils`

### Authentication failures

- Double-check that the service account JSON fields in secrets are correct
- Ensure the `private_key` value includes the newlines (`\n`)
- Verify the service account has `roles/documentai.apiUser` on the project

### No processors found

- The service account needs `documentai.processors.list` permission
- Processors must be in the same location configured in `GCP_LOCATION`
