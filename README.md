
# Azure AI Chatbot

A very simple command-line chatbot that uses **Azure OpenAI (GPT-4o)**.

## Folder Structure
```
azure-ai-chatbot/
├─ chatbot/
│  ├─ chatbot.py              # CLI chatbot with RAG and multi-lang support
│  ├─ upload_embeddings.py    # Uploads documents from Azure Storage and builds FAISS index
├─ docs/
│  └─ architecture/
│     ├─ architecture_v1.0.png  # Lab 2 architecture
│     ├─ architecture_v1.1.png  # Lab 3 architecture (session + storage)
│     ├─ architecture_lab4.png  # Lab 4 updated architecture (Document Intelligence + multi-lang)
│     └─ architecture.md
├─ requirements.txt
└─ README.md


```

## Prerequisites
- Python 3.9+
- Azure subscription with:
- Azure OpenAI resource (gpt-4o deployment)
- Azure Blob Storage for document storage
   - Optional: Azure Function App for hosting

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

     ```
4. Upload documents to Azure Blob Storage (kb-docs container) if not already uploaded.
5. Run upload_embeddings.py to download docs and create FAISS index:

```powershell
python chatbot/upload_embeddings.py
  ```

## Run
```bash
python chatbot/chatbot.py
```

Type `exit` to quit.
Ask questions from your uploaded documents.
Ask bilingual queries (English or Arabic).
If a query is not in the documents, the bot will attempt to translate or define using Azure OpenAI.


## Testing
-English: “Explain the rules of badminton”
- Arabic: “ما هو شات بوت؟”
- Multi-topic queries: “badminton and cricket”
- Unknown queries: “What is chatbot?” → Fallback to translation/definition

## Deliverables (for Lab 3)
- /docs/architecture/architecture_lab4.png → Lab 4 updated architecture
- chatbot/chatbot.py → CLI chatbot with RAG + multi-language support
- chatbot/upload_embeddings.py → FAISS index creation and document embedding
- FAISS index files: faiss_index.index, docs.npy, doc_names.npy
- Multilingual document support: English + Arabic .txt files in Azure Storage
- Public GitHub repo: azure-ai-chatbot

