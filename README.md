
# Azure AI Chatbot

A very simple command-line chatbot that uses **Azure OpenAI (GPT-4o)**.

## Folder Structure
```
azure-ai-chatbot/
├─ chatbot/
│  ├─ chatbot.py              # CLI chatbot (Lab 3)
├─ docs/
│  └─ architecture/
│     ├─ architecture_v1.0.png  # Lab 2 architecture
│     ├─ architecture_v1.1.png  # Lab 3 architecture (session + storage)
│     └─ architecture.md
├─ requirements.txt
└─ README.md

```

## Prerequisites
- Python 3.9+
- Azure subscription with an **Azure OpenAI** resource (from Lab 1)
- Azure subscription with:
   Azure OpenAI resource (gpt-4o deployment)
   Azure CosmosDB / Azure Storage for session persistence
   Azure Function App for hosting the chatbot
- Azure Cognitive Search for RAG (document retrieval)

## Setup
1. Create and activate a virtual environment (optional but recommended)
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables (example):
   - **PowerShell (Windows)**
     ```powershell
     $env:AZURE_OPENAI_ENDPOINT="(https://anabi-meobtnsg-swedencentral.cognitiveservices.azure.com)"
     $env:AZURE_OPENAI_KEY="<my-api-key>"
     $env:AZURE_DEPLOYMENT_NAME="gpt-4o"
     $env:COSMOSDB_URL="<your-cosmos-url>"
     $env:COSMOSDB_KEY="<your-cosmos-key>"

     ```

## Run
```bash
python chatbot/chatbot.py
```

Type `exit` to quit.
Type `clear` to reset session.
Type `history` to view stored conversation


## Testing
- Try greetings: "Hello", "Who are you?"
- Ask for facts or definitions.
- Try an empty message (should prompt you).
- Disconnect internet or change deployment name to see error handling.

## Deliverables (for Lab 3)
- `/docs/architecture/architecture.png` (diagram)
- Working chatbot script in `/chatbot/chatbot.py`
- Public GitHub repo named **azure-ai-chatbot**
- Updated architecture diagram (architecture_v1.1.png)
- Azure Function App code (chatbot/function_app.py)
- Persistent chatbot with session history
- Public GitHub repo azure-ai-chatbot

