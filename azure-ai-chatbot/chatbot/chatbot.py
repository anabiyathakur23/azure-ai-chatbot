import uuid
from datetime import datetime, timezone
from openai import AzureOpenAI
from azure.cosmos import CosmosClient, PartitionKey
import math
import tiktoken

AZURE_OPENAI_KEY = "1jiytLtW3XtSb2eakFpwQwl939kglgu9w5Nw5gF1pLYtDhwzDByHJQQJ99BHACfhMk5XJ3w3AAAAACOGyHV0"
AZURE_OPENAI_ENDPOINT = "https://anabi-meobtnsg-swedencentral.cognitiveservices.azure.com"
AZURE_DEPLOYMENT_NAME = "gpt-4o"       
AZURE_EMBEDDINGS_DEPLOYMENT_NAME = "embedding-small"  

COSMOS_ENDPOINT = "https://chatbot-cosmos1.documents.azure.com:443"
COSMOS_KEY = "BFSFICHE15c5XFOE0eBYti0EQPL5LkuggUZ4TZRqEV6UKK3A56krnExV8CZN0WtOFWRPK67VbszHACDbKXthnQ=="
COSMOS_DB_NAME = "ChatbotDB"
COSMOS_CONTAINER_SESSIONS = "Sessions"
COSMOS_CONTAINER_KB = "KnowledgeBase"

client = AzureOpenAI(api_key=AZURE_OPENAI_KEY,
                     api_version="2024-08-01-preview",
                     azure_endpoint=AZURE_OPENAI_ENDPOINT)

cosmos_client = CosmosClient(url=COSMOS_ENDPOINT, credential=COSMOS_KEY)
database = cosmos_client.create_database_if_not_exists(id=COSMOS_DB_NAME)
session_container = database.create_container_if_not_exists(
    id=COSMOS_CONTAINER_SESSIONS,
    partition_key=PartitionKey(path="/session_id")
)
kb_container = database.create_container_if_not_exists(
    id=COSMOS_CONTAINER_KB,
    partition_key=PartitionKey(path="/doc_id")
)

# -----------------------------
# Helper functions
# -----------------------------
def cosine_similarity(vec1, vec2):
    dot = sum(a*b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a*a for a in vec1))
    norm2 = math.sqrt(sum(b*b for b in vec2))
    if norm1 == 0 or norm2 == 0: return 0
    return dot / (norm1 * norm2)

def retrieve_kb(user_input, top_k=3):
    embedding_resp = client.embeddings.create(
        model=AZURE_EMBEDDINGS_DEPLOYMENT_NAME,
        input=user_input
    )
    query_vector = embedding_resp.data[0].embedding
    docs = list(kb_container.read_all_items())
    similarities = []
    for doc in docs:
        doc_vector = doc.get("embedding", [])
        if doc_vector:
            similarities.append((cosine_similarity(query_vector, doc_vector), doc["content"]))
    top_docs = sorted(similarities, key=lambda x: x[0], reverse=True)[:top_k]
    return "\n".join([doc for _, doc in top_docs])

def summarize_conversation(history):
    if not history: return ""
    messages = [{"role": "system", "content": "Summarize the following conversation briefly, keeping only important points:"}]
    for msg in history:
        messages.append({"role": "user", "content": msg["user_input"]})
        messages.append({"role": "assistant", "content": msg["bot_response"]})
    response = client.chat.completions.create(
        model=AZURE_DEPLOYMENT_NAME,
        messages=messages,
        max_tokens=150
    )
    return response.choices[0].message.content

def count_tokens(messages, model="gpt-4o"):
    encoding = tiktoken.encoding_for_model(model)
    total_tokens = 0
    for msg in messages:
        for value in msg.values():
            total_tokens += len(encoding.encode(str(value)))
    return total_tokens

# -----------------------------
# Start session
# -----------------------------
session_id = str(uuid.uuid4())
print(f"\n✅ New session started: {session_id}")
print("💬 Chatbot ready! Type 'exit', 'clear', or 'history'.")
print("⏱️ Current UTC:", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z"))

MAX_TOKENS = 3000  # adjust based on model limits

# -----------------------------
# Main chat loop
# -----------------------------
while True:
    user_input = input("You: ")

    if user_input.lower() in ["exit", "quit"]:
        print("👋 Goodbye!")
        break

    if user_input.lower() == "clear":
        session_id = str(uuid.uuid4())
        print(f"🗑 Conversation cleared. New session started: {session_id}")
        continue

    if user_input.lower() == "history":
        history = list(session_container.query_items(
            query="SELECT * FROM c WHERE c.session_id=@sid ORDER BY c.timestamp ASC",
            parameters=[{"name": "@sid", "value": session_id}],
            enable_cross_partition_query=True
        ))
        if not history:
            print("No conversation history yet.")
        else:
            print("📜 Conversation History:")
            for msg in history:
                print(f"You: {msg['user_input']}")
                print(f"Bot: {msg['bot_response']}")
        continue

    # Fetch previous conversation
    history = list(session_container.query_items(
        query="SELECT * FROM c WHERE c.session_id=@sid ORDER BY c.timestamp ASC",
        parameters=[{"name": "@sid", "value": session_id}],
        enable_cross_partition_query=True
    ))

    # -----------------------------
    # Build messages with token-based context
    # -----------------------------
    messages = [{"role": "system", "content": "You are a helpful assistant specialized in teaching."}]
    kb_context = retrieve_kb(user_input)
    if kb_context:
        messages.append({"role": "system", "content": f"Use the following knowledge base info:\n{kb_context}"})

    for msg in history:
        user_msg = {"role": "user", "content": msg["user_input"]}
        bot_msg = {"role": "assistant", "content": msg["bot_response"]}

        temp_messages = messages + [user_msg, bot_msg]
        temp_tokens = count_tokens(temp_messages, model=AZURE_DEPLOYMENT_NAME)

        if temp_tokens > MAX_TOKENS:
            summary_text = summarize_conversation(messages[1:])  # skip system prompt
            messages = [{"role": "system", "content": "Conversation summary:\n" + summary_text}]
            break
        else:
            messages.append(user_msg)
            messages.append(bot_msg)

    # Add current user input
    messages.append({"role": "user", "content": user_input})

    # Get GPT response
    response = client.chat.completions.create(
        model=AZURE_DEPLOYMENT_NAME,
        messages=messages,
        max_tokens=300
    )
    reply = response.choices[0].message.content
    print("Bot:", reply)

    # Store conversation
    session_container.upsert_item({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "user_input": user_input,
        "bot_response": reply,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
