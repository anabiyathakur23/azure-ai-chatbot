
# Azure AI Chatbot

A very simple command-line chatbot that uses **Azure OpenAI (GPT-4o)**.

## Folder Structure
```
azure-ai-chatbot/
├─ chatbot/
│  ├─ chatbot.py              # CLI chatbot with RAG, multi-lang, speech, and function calling
│  ├─ upload_embeddings.py    # Uploads documents and builds FAISS index
├─ docs/
│  └─ architecture/
│     ├─ architecture_lab5.png  # Updated architecture with speech services
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
   ***Fetch secrets in chatbot.py using DefaultAzureCredential:**
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

Features

1. Text & Voice Queries
- Type in the CLI or speak using microphone (*voice* command).
- Chatbot responds via text and optional speech (*speak on/off*).

2. RAG Retrieval
- Chatbot searches uploaded documents for relevant answers.
- Responses include document references.
- If no context is found: *"I cannot answer this question as it is out of scope."*

3. Function Calling
   Supports the following callable functions:
        - **get_weather(city)** – Current weather for a city
        - **get_time()** – Current date and time
        - **calculate(expression)** – Evaluate math expressions
        - **fun_fact()** – Returns a fun fact

4. OCR & Document Support
- Handles .txt, .docx, .odt, .pdf, and image files (.png, .jpg, .jpeg, .bmp, .tiff).
- Uses Azure Computer Vision for text extraction.

5. Image Queries
- Ask about uploaded images (show, display, photo, etc.).
- Returns a URL to the image file.

6. Multi-Language Support
- Supports English and Arabic queries.

7. Conversation Management
- **history** – Shows conversation history
- **clear** – Clears conversation
- **exit or quit** – Exit chatbot

## Run
```bash
python chatbot/chatbot.py
```

**CLI commands:**
- exit / quit
- voice – Speak input
- speak on / speak off
- history – View conversation
- clear – Reset session

## Testing
- Try greetings: "Hello", "Who are you?"
- Ask functions: *"What's the weather in Doha?", "calculate 23*5", "tell me a fun fact"*
- Query documents or images in uploads/.
- Try an unsupported query to see "out of scope" response.

## Deliverables (for Lab 6)
- Updated architecture diagram: /docs/architecture/architecture_lab5.png
- RAG-enabled chatbot: chatbot/chatbot.py
- Function calling and Speech services integration: Azure Speech-to-Text & Text-to-Speech
- FAISS index files: faiss_index.index, docs.npy, doc_names.npy
- Auto-indexing for uploaded files
- deployed key vault
-  Chatbot frontend
