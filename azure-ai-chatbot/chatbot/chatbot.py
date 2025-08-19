import os
import sys
from dotenv import load_dotenv

# Load variables from .env if present (for local dev)
load_dotenv()

try:
    from openai import AzureOpenAI
except Exception as e:
    print("Please install the dependencies: pip install -r requirements.txt")
    raise

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o")

if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_KEY:
    print("Missing environment variables. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY.")
    print("Example (PowerShell):")
    print('  $env:AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"')
    print('  $env:AZURE_OPENAI_KEY="<your-key>"')
    sys.exit(1)

# Initialize client
client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-06-01-preview",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

def chat():
    print("🤖 Welcome to Azure GPT Chatbot")
    print("Type your message and press Enter. Type 'exit' to quit.")

    # Keep minimal history so the bot remembers context
    history = [{"role": "system", "content": "You are a helpful assistant."}]

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!"); break

        if user_input.lower() in {"exit", "quit", "bye"}:
            print("👋 Goodbye!"); break
        if not user_input:
            print("(Please type something or 'exit')")
            continue

        history.append({"role": "user", "content": user_input})

        try:
            resp = client.chat.completions.create(
                model=DEPLOYMENT_NAME,
                messages=history,
                temperature=0.7,
            )
            reply = resp.choices[0].message.content
            print("Bot:", reply)
            history.append({"role": "assistant", "content": reply})
        except Exception as e:
            print("⚠️ Error talking to Azure OpenAI:", e)
            print("Check: endpoint, key, model deployment name, and network connectivity.")

if __name__ == "__main__":
    chat()
