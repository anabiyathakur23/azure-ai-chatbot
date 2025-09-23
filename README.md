
# Azure AI Chatbot

A very simple command-line chatbot that uses **Azure OpenAI (GPT-4o)**.

## Folder Structure
```
azure-ai-chatbot/
├─ chatbot/
│  ├─ chatbot.py              # CLI chatbot with RAG, multi-lang, and speech support
│  ├─ upload_embeddings.py    # Uploads documents and builds FAISS index
├─ docs/
│  └─ architecture/
│     ├─ architecture_lab5.png  # Lab 5 updated architecture with speech services
│     └─ architecture.md
├─ requirements.txt
└─ README.md


```

## Prerequisites
- Python 3.9+
- Azure subscription with an **Azure OpenAI** resource (from Lab 1)
- Azure subscription with:
- Azure OpenAI resource (gpt-4o deployment)
- Azure Blob Storage for documents
- Azure Cognitive Speech Services (for speech-to-text & text-to-speech)
- Deployed key vault
- Optional: Azure Function App for deployment

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
4. Upload documents to Azure Blob Storage (kb-docs container)
5. Azure Key Vault Integration
    ***Store your OpenAI API key securely in Azure Key Vault:***
 ```powershell
 az keyvault secret set --vault-name <your-keyvault-name> --name "openaikey" --value "<your-openai-key>"
```
   ***In backend.py or chatbot.py, fetch it using DefaultAzureCredential or AzureCliCredential:***
```
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
vault_url = "https://<your-keyvault-name>.vault.azure.net/"
credential = DefaultAzureCredential()
client = SecretClient(vault_url=vault_url, credential=credential)
openai.api_key = client.get_secret("openaikey").value
```
- This allows you to avoid storing API keys directly in environment variables or code.
6. Generate FAISS index:
```powershell
   python chatbot/upload_embeddings.py
```
- Speak or type queries.
- Chatbot responds via text and optionally via speech.
- Type exit to quit.
- Supports English and Arabic queries.
- Can handle multi-topic queries using RAG.

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

## Deliverables (for Lab 6)
- Updated architecture diagram: /docs/architecture/architecture_lab5.png
- RAG-enabled chatbot: chatbot/chatbot.py
- Speech services integration: Azure Speech-to-Text & Text-to-Speech
- FAISS index files: faiss_index.index, docs.npy, doc_names.npy
- Deployed code to Azure Function App
- deployed key vault
- Optional bonus: Chatbot frontend (web or mobile)
