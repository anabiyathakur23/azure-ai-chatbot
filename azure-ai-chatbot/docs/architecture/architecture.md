# Architecture (Lab 2.0)

This is the **basic architecture** for a command-line chatbot that uses **Azure OpenAI (GPT-4o)**.

## Components
- **User** — interacts with the chatbot via CLI, web, or Teams.
- **Chatbot Application (Python)** — manages session, sends messages to Azure OpenAI, retrieves knowledge from Cosmos DB and Azure AI Search, and prints the response.
- **Azure OpenAI Resource** — hosts GPT-4o for generating chatbot responses.
- **Cosmos DB** — stores session data (user inputs and bot responses) and knowledge base documents.
- **Azure AI Search** — enables semantic search to retrieve relevant documents for RAG

## Data Flow
1. **User** types a message in the CLI/web/Teams.
2. **Python app** sends it to **Azure OpenAI** and retrieves the response.
3. **Azure OpenAI** generates a response using the user input and the retrieved knowledge.
4. **Python app** queries Cosmos DB and Azure AI Search for relevant documents (RAG).
5. **Python app** stores the conversation in Cosmos DB.
6. **User** sees the response.


## Azure Resources
- Resource Group: rg-ai-chatbot (example)
- Azure OpenAI Resource: openai-lab (example)
- Cosmos DB: ChatbotDB
- Containers: Sessions (session data), KnowledgeBase (documents)
- Azure AI Search: For document retrieval (RAG).

> This diagram and document will be updated in future labs as we add features (logging, memory, storage, etc.).
