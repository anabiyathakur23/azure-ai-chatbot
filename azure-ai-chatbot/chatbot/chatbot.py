# chatbot.py

import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
import difflib
from langdetect import detect

# -----------------------------
# 0️⃣ Azure OpenAI environment setup
# -----------------------------
os.environ["AZURE_OPENAI_API_KEY"] = "1jiytLtW3XtSb2eakFpwQwl939kglgu9w5Nw5gF1pLYtDhwzDByHJQQJ99BHACfhMk5XJ3w3AAAAACOGyHV0"
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://anabi-meobtnsg-swedencentral.openai.azure.com/"
os.environ["AZURE_OPENAI_DEPLOYMENT"] = "gpt-4o"
os.environ["OPENAI_API_VERSION"] = "2023-05-15"

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["OPENAI_API_VERSION"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"]
)

# -----------------------------
# 1️⃣ Paths setup
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "faiss_index.index")
DOC_NAMES_PATH = os.path.join(BASE_DIR, "doc_names.npy")
DOCS_PATH = os.path.join(BASE_DIR, "docs.npy")

# -----------------------------
# 2️⃣ Verify files exist
# -----------------------------
for path in [INDEX_PATH, DOC_NAMES_PATH, DOCS_PATH]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

# -----------------------------
# 3️⃣ Load FAISS index and documents
# -----------------------------
index = faiss.read_index(INDEX_PATH)
doc_names = np.load(DOC_NAMES_PATH, allow_pickle=True)
docs = np.load(DOCS_PATH, allow_pickle=True)
print(f"✅ Loaded FAISS index with {index.ntotal} vectors and {len(docs)} documents")

# -----------------------------
# 4️⃣ Load embedding model
# -----------------------------
model = SentenceTransformer('all-MiniLM-L6-v2')

# -----------------------------
# 5️⃣ Prompt template for RAG
# -----------------------------
PROMPT_TEMPLATE = """
You are an AI assistant. Only answer questions using the following documents:
{documents}

Question: {question}

- If the question is unrelated to these documents, respond: "I cannot answer this question as it is out of scope."
- Provide references using the document names.
- Be concise and clear.
"""

# -----------------------------
# 6️⃣ Search / retrieval functions
# -----------------------------
def retrieve_documents(query, k=3, threshold=0.5):
    q_vec = np.array([model.encode(query)]).astype('float32')
    D, I = index.search(q_vec, k)
    results = []
    for dist, idx in zip(D[0], I[0]):
        similarity = 1 / (1 + dist)  # L2 to similarity
        if similarity >= threshold:
            results.append({
                "document_name": doc_names[idx],
                "text": docs[idx],
                "similarity": round(similarity, 3)
            })
    return results

def multi_topic_search(user_query, k=3, threshold=0.5):
    topics = [t.strip() for t in user_query.lower().replace(",", " and ").split(" and ")]
    combined_results = []
    seen_docs = set()

    for topic in topics:
        # Exact match in names
        exact_docs = [
            {"document_name": doc_names[i], "text": docs[i], "similarity": 1.0}
            for i in range(len(doc_names))
            if topic in doc_names[i].lower()
        ]

        # Fuzzy match in names
        if not exact_docs:
            matches = difflib.get_close_matches(topic, [dn.lower() for dn in doc_names], n=3, cutoff=0.6)
            exact_docs = [
                {"document_name": doc_names[i], "text": docs[i], "similarity": 0.9}
                for i, dn in enumerate(doc_names) if dn.lower() in matches
            ]

        # Fuzzy match in content
        if not exact_docs:
            matches = difflib.get_close_matches(topic, [d.lower()[:200] for d in docs], n=3, cutoff=0.6)
            exact_docs = [
                {"document_name": doc_names[i], "text": docs[i], "similarity": 0.85}
                for i, d in enumerate(docs) if d.lower()[:200] in matches
            ]

        # Add results
        for r in exact_docs:
            if r['document_name'] not in seen_docs:
                combined_results.append(r)
                seen_docs.add(r['document_name'])

        # Always fallback to FAISS if nothing matched
        if not exact_docs:
            results = retrieve_documents(topic, k, threshold)
            for r in results:
                if r['document_name'] not in seen_docs:
                    combined_results.append(r)
                    seen_docs.add(r['document_name'])

    return combined_results

# -----------------------------
# 7️⃣ Azure OpenAI answer generation
# -----------------------------
def generate_answer(prompt, max_tokens=500, temperature=0.2):
    try:
        response = client.chat.completions.create(
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating answer: {e}"

# -----------------------------
# 8️⃣ Chatbot response (Bilingual)
# -----------------------------
conversation_history = []

def chatbot_response(user_query):
    # Handle history & clear
    if user_query.lower() == "history":
        return "\n".join(conversation_history) if conversation_history else "No history yet.", []
    if user_query.lower() == "clear":
        conversation_history.clear()
        return "Conversation history cleared.", []

    # Detect language
    try:
        lang = detect(user_query)
    except:
        lang = "en"

    results = multi_topic_search(user_query, k=3, threshold=0.6)

    # If no relevant docs, fallback to translation/definition
    if not results:
        if lang == "ar":
            prompt = f"Translate or define this in Arabic: {user_query}"
        else:
            prompt = f"Translate or define this in English: {user_query}"
        answer = generate_answer(prompt)
        conversation_history.append(f"You: {user_query}\nChatbot: {answer}")
        return answer, []

    # Build context for RAG
    context_text = "\n\n".join([f"[{r['document_name']}] {r['text']}" for r in results])
    
    if lang == "ar":
        prompt = f"Answer this question in Arabic using the following documents:\n{context_text}\n\nQuestion: {user_query}"
    else:
        prompt = PROMPT_TEMPLATE.format(documents=context_text, question=user_query)

    answer = generate_answer(prompt, max_tokens=500)
    references = [r['document_name'] for r in results]
    answer_with_refs = f"{answer}\n\n[Reference: {', '.join(references)}]"

    # Save to history
    conversation_history.append(f"You: {user_query}\nChatbot: {answer_with_refs}")
    return answer_with_refs, references

# -----------------------------
# 9️⃣ Chatbot loop
# -----------------------------
if __name__ == "__main__":
    print("✅ Loaded FAISS index with", index.ntotal, "vectors")
    print("✅ Chatbot ready! Type 'exit' or 'quit' to stop.\n")

    while True:
        user_query = input("You: ").strip()
        if user_query.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        if not user_query:
            continue

        response, refs = chatbot_response(user_query)
        print(f"\nChatbot:\n{response}\n")
