# backend.py

import sys
import os
sys.path.append(r"C:\Users\anabi\Downloads\azure-ai-chatbot\chatbot")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from azure.identity import AzureCliCredential, DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import openai
from chatbot import chatbot_response  # your existing chatbot.py

app = FastAPI()

# Allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # your Vite frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to Azure Key Vault
VAULT_URL = "https://chatbotkeyvault29.vault.azure.net/"

# Try AzureCliCredential first, fallback to DefaultAzureCredential
try:
    credential = AzureCliCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)
    secret = client.get_secret("openaikey")  # make sure this matches your vault secret name
    openai.api_key = secret.value
    print("✅ OpenAI key fetched from Key Vault via Azure CLI login")
except Exception as e:
    print(f"⚠️ Failed to get secret from Key Vault: {e}")
    openai.api_key = os.environ.get("OPENAI_API_KEY")  # fallback to .env variable
    if openai.api_key:
        print("✅ OpenAI key fetched from environment variable")
    else:
        print("❌ No OpenAI key found! Chatbot will not work until set.")

@app.post("/message")
async def send_message(data: dict):
    user_message = data.get("message", "")
    try:
        reply, _ = chatbot_response(user_message)
        # Fallback if reply is empty or echoes user
        if reply.strip().lower() == user_message.strip().lower() or not reply.strip():
            reply = "Sorry, I don't have an answer for that."
        return {"reply": reply}
    except Exception as e:
        print("❌ Chatbot error:", str(e))
        return {"reply": f"Error: {str(e)}"}
