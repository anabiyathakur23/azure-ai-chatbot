<<<<<<< HEAD
# azure-ai-chatbot
=======
# Azure AI Chatbot (CLI)

A very simple command-line chatbot that uses **Azure OpenAI (GPT-4o)**.

## Folder Structure
```
azure-ai-chatbot/
├─ chatbot/
│  └─ chatbot.py
├─ docs/
│  └─ architecture/
│     ├─ architecture.png
│     └─ architecture.md
├─ requirements.txt
└─ README.md
```

## Prerequisites
- Python 3.9+
- Azure subscription with an **Azure OpenAI** resource (from Lab 1)
- A **model deployment**: e.g., `gpt-4o` (or `gpt-4` as fallback)

## Setup
1. Create and activate a virtual environment (optional but recommended)
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables (example):
   - **PowerShell (Windows)**
     ```powershell
     $env:AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"
     $env:AZURE_OPENAI_KEY="<your-api-key>"
     $env:AZURE_DEPLOYMENT_NAME="gpt-4o"
     ```
   - **macOS / Linux**
     ```bash
     export AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"
     export AZURE_OPENAI_KEY="<your-api-key>"
     export AZURE_DEPLOYMENT_NAME="gpt-4o"
     ```

## Run
```bash
python chatbot/chatbot.py
```

Type `exit` to quit.

## Testing
- Try greetings: "Hello", "Who are you?"
- Ask for facts or definitions.
- Try an empty message (should prompt you).
- Disconnect internet or change deployment name to see error handling.

## Deliverables (for Lab 2)
- `/docs/architecture/architecture.png` (diagram)
- `/docs/architecture/architecture.md` (explanation)
- Working chatbot script in `/chatbot/chatbot.py`
- Public GitHub repo named **azure-ai-chatbot**

## Notes
- Do **not** commit any API keys (.env or secrets).
- If `gpt-4o` is unavailable in your region, deploy `gpt-4` and update `AZURE_DEPLOYMENT_NAME`.
>>>>>>> 169d2e6 (Initial commit)
