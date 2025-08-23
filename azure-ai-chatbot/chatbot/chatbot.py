from openai import AzureOpenAI

AZURE_OPENAI_KEY = "1jiytLtW3XtSb2eakFpwQwl939kglgu9w5Nw5gF1pLYtDhwzDByHJQQJ99BHACfhMk5XJ3w3AAAAACOGyHV0"
AZURE_OPENAI_ENDPOINT = "https://anabi-meobtnsg-swedencentral.openai.azure.com"  # no trailing slash
AZURE_DEPLOYMENT_NAME = "gpt-4o"             # deployment name

client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version="2024-12-01-preview"
)
print("✅ AzureOpenAI client initialized successfully!")

# 🔹 Chat loop
print("\n💬 Chatbot is ready! Type 'exit' to quit.\n")
while True:
    user_input = input("You: ")
    if user_input.lower() in ["exit", "quit"]:
        print("👋 Goodbye!")
        break

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_input}
    ]

    response = client.chat.completions.create(
        model=AZURE_DEPLOYMENT_NAME,
        messages=messages,
        temperature=0.7,
        max_tokens=200
    )

    bot_reply = response.choices[0].message.content.strip()
    print(f"Bot: {bot_reply}\n")
