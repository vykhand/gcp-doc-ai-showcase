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

No secrets configuration is needed by default. Each user provides their own **endpoint** and **API key** in the sidebar. This ensures users consume their own GCP resources.

If you want to pre-configure defaults (so users don't have to enter credentials), add secrets in the Streamlit Cloud dashboard:

1. Open your app's settings
2. Go to the **Secrets** tab
3. Add:

```toml
GCP_DOCAI_ENDPOINT = "https://us-documentai.googleapis.com/v1/projects/your-project/locations/us"
GCP_DOCAI_API_KEY = "your-api-key"
```

4. Click **Save**

## Step 4: System Dependencies

The `packages.txt` file tells Streamlit Cloud to install `poppler-utils` (needed for PDF rendering). This file is automatically detected.

## Verifying the Deployment

After deployment:

1. Open the app URL
2. Enter your endpoint and API key in the sidebar
3. Check the **Connection Status** expander — it should show "Connection successful!"
4. Your processors should appear in the processor dropdown
5. Upload a document and test analysis

## Troubleshooting

### App crashes on startup

- Check the Streamlit Cloud logs for import errors
- Ensure `requirements.txt` is up to date (`uv pip compile pyproject.toml -o requirements.txt`)
- Verify `packages.txt` includes `poppler-utils`

### Authentication failures

- Verify the API key is valid and restricted to the Cloud Document AI API
- Ensure the Document AI API is enabled in the GCP project
- Check that the endpoint URL is correctly formatted

### No processors found

- Ensure at least one processor is created in the project/location specified in the endpoint
- Verify the API key has access to the Document AI API
