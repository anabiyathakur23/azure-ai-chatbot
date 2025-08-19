# Architecture (Lab 2.0)

This is the **basic architecture** for a command-line chatbot that uses **Azure OpenAI (GPT-4o)**.

## Components
- **User** — types messages in the terminal (CLI).
- **Chatbot Application (Python)** — sends the user’s message to Azure and prints the reply.
- **Azure OpenAI Resource** — hosts the GPT-4o (or GPT-4) deployment that generates answers.
- **Resource Group** — container in Azure that holds the OpenAI resource.

## Data Flow
1. **User** types a message in the terminal.
2. **Python app** sends it to **Azure OpenAI** using the endpoint + API key.
3. **Azure OpenAI (GPT-4o)** returns a response.
4. **Python app** prints the response back to the **User**.

## Azure Resources
- Resource Group: `rg-ai-chatbot` (example)
- Azure OpenAI Resource: `openai-lab` (example)
- Deployment name: `gpt-4o` (fallback: `gpt-4`)

> This diagram and document will be updated in future labs as we add features (logging, memory, storage, etc.).
