#chatbot.py

import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
import azure.cognitiveservices.speech as speechsdk
from docx import Document
import pdfplumber
from odf import text, teletype
from odf.opendocument import load
from PIL import Image
import pytesseract
import json
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from rich.console import Console
from rich.markdown import Markdown
import re
import time

# Azure Computer Vision
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# -----------------------------
# Callables
# -----------------------------
def get_weather(city: str):
    import requests
    API_KEY = "a97bd20b3e680822a8cfcc44f9818cbb"
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={API_KEY}"
    try:
        res = requests.get(url)
        data = res.json()
        if res.status_code != 200:
            return f"Could not retrieve weather for {city}. {data.get('message', '')}"
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"].capitalize()
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]
        return f"Weather in {city}: {temp}°C, {desc}, humidity {humidity}%, wind speed {wind} m/s."
    except Exception as e:
        return f"Error: {e}"

def get_time():
    return f"Current date and time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."

def calculate(expression: str):
    try:
        result = eval(expression)
        return f"Result of {expression} is {result}."
    except:
        return "Invalid calculation."

def fun_fact():
    return "Octopuses have three hearts. Two pump blood to the gills, one to the body."

CALLABLE_FUNCTIONS = {
    "get_weather": get_weather,
    "get_time": get_time,
    "calculate": calculate,
    "fun_fact": fun_fact
}

FUNCTIONS = [
    {"name": "get_weather","description": "Get weather in a city","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}},
    {"name": "get_time","description":"Get current date and time","parameters":{"type":"object","properties":{}}},
    {"name": "calculate","description":"Calculate a math expression","parameters":{"type":"object","properties":{"expression":{"type":"string"}}}},
    {"name": "fun_fact","description":"Provide a fun fact","parameters":{"type":"object","properties":{}}}
]

# -----------------------------
# Azure setup
# -----------------------------
try:
    KV_URI = "https://chatbotkeyvault29.vault.azure.net/"
    credential = DefaultAzureCredential()
    kv_client = SecretClient(vault_url=KV_URI, credential=credential)
    
    AZURE_OPENAI_API_KEY = kv_client.get_secret("openaikey").value
    AZURE_OPENAI_ENDPOINT = kv_client.get_secret("AZURE-OPENAI-ENDPOINT").value
    AZURE_OPENAI_DEPLOYMENT = kv_client.get_secret("AZURE-OPENAI-DEPLOYMENT").value
    AZURE_SPEECH_KEY = kv_client.get_secret("AZURE-SPEECH-KEY").value
    AZURE_SPEECH_REGION = kv_client.get_secret("AZURE-SPEECH-REGION").value
    AZURE_CV_KEY = kv_client.get_secret("AZURE-CV-KEY").value
    AZURE_CV_ENDPOINT = kv_client.get_secret("AZURE-CV-ENDPOINT").value
except Exception as e:
    print(f"Warning: Using mock values. Error: {e}")
    AZURE_OPENAI_API_KEY = "mock_key"
    AZURE_OPENAI_ENDPOINT = "mock_endpoint"
    AZURE_OPENAI_DEPLOYMENT = "gpt-4-deployment"
    AZURE_SPEECH_KEY = "mock_speech_key"
    AZURE_SPEECH_REGION = "eastus"
    AZURE_CV_KEY = "mock_cv_key"
    AZURE_CV_ENDPOINT = "mock_cv_endpoint"

# Initialize clients
client = None
cv_client = None
try:
    client = AzureOpenAI(api_key=AZURE_OPENAI_API_KEY, api_version="2023-05-15", azure_endpoint=AZURE_OPENAI_ENDPOINT)
    cv_client = ComputerVisionClient(AZURE_CV_ENDPOINT, CognitiveServicesCredentials(AZURE_CV_KEY))
    print("[Info] Azure clients initialized successfully.")
except Exception as e:
    print(f"[Error] Azure clients init failed: {e}")

# -----------------------------
# Paths & FAISS setup
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
INDEX_PATH = os.path.join(BASE_DIR, "faiss_index.index")
DOC_NAMES_PATH = os.path.join(BASE_DIR, "doc_names.npy")
DOCS_PATH = os.path.join(BASE_DIR, "docs.npy")

model = SentenceTransformer('all-MiniLM-L6-v2')
index = faiss.read_index(INDEX_PATH) if os.path.isfile(INDEX_PATH) else faiss.IndexFlatL2(384)
docs = np.load(DOCS_PATH, allow_pickle=True) if os.path.isfile(DOCS_PATH) else np.array([])
doc_names = np.load(DOC_NAMES_PATH, allow_pickle=True) if os.path.isfile(DOC_NAMES_PATH) else np.array([])

# -----------------------------
# OCR + File reading
# -----------------------------
def azure_ocr_read(file_path):
    try:
        if not cv_client: return None
        with open(file_path, "rb") as f:
            read_op = cv_client.read_in_stream(f, raw=True)
        operation_location = read_op.headers["Operation-Location"]
        operation_id = operation_location.split("/")[-1]
        while True:
            read_result = cv_client.get_read_result(operation_id)
            if read_result.status not in ['notstarted','running']:
                break
            time.sleep(1)
        full_text = []
        if read_result.status == 'succeeded':
            for page in read_result.analyze_result.read_results:
                for line in page.lines:
                    full_text.append(line.text)
            return "\n".join(full_text)
        return None
    except Exception as e:
        print(f"[Error] Azure OCR failed: {e}")
        return None

def read_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f: return f.read()
    elif ext == ".docx":
        doc = Document(file_path)
        return "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])
    elif ext in [".odt",".odf"]:
        odt_doc = load(file_path)
        return "\n".join([teletype.extractText(elem) for elem in odt_doc.getElementsByType(text.P)])
    elif ext in [".pdf",".png",".jpg",".jpeg",".tiff",".bmp"]:
        text_content = azure_ocr_read(file_path)
        if text_content and text_content.strip(): return text_content
        if ext == ".pdf":
            try:
                with pdfplumber.open(file_path) as pdf:
                    content = "\n".join([page.extract_text() or "" for page in pdf.pages]).strip()
                    if content: return content
            except Exception as e: 
                print(f"[Warning] pdfplumber fallback failed on {file_path}: {e}")
        if ext in [".png",".jpg",".jpeg",".tiff",".bmp"]: 
            return f"[image]{file_path}"
    return ""

def chunk_text(text, max_len=500):
    paragraphs = text.split("\n")
    chunks, chunk = [], ""
    for p in paragraphs:
        if len(chunk)+len(p)+1 < max_len: chunk += p+" "
        else:
            if chunk.strip(): chunks.append(chunk.strip())
            chunk = p+" "
    if chunk.strip(): chunks.append(chunk.strip())
    return chunks

def add_file_to_index(file_path):
    global docs, doc_names
    file_name = os.path.basename(file_path)
    if file_name in doc_names: return
    text_content = read_file(file_path)
    if not text_content.strip(): return
    if text_content.startswith("[image]"):
        docs = np.append(docs, text_content)
        doc_names = np.append(doc_names, file_name)
    else:
        chunks = chunk_text(text_content)
        for chunk in chunks:
            vec = model.encode([chunk]).astype('float32')
            index.add(vec)
            docs = np.append(docs, chunk)
            doc_names = np.append(doc_names, file_name)
    faiss.write_index(index, INDEX_PATH)
    np.save(DOCS_PATH, docs)
    np.save(DOC_NAMES_PATH, doc_names)

# Auto-index existing files
for f in os.listdir(UPLOADS_DIR):
    path = os.path.join(UPLOADS_DIR, f)
    if os.path.isfile(path): add_file_to_index(path)

# Watcher
class UploadsHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            time.sleep(1)
            add_file_to_index(event.src_path)

observer = Observer()
observer.schedule(UploadsHandler(), path=UPLOADS_DIR, recursive=False)
observer.start()

# -----------------------------
# RAG Retrieval
# -----------------------------
def retrieve_documents(query, k=5, threshold=0.4):
    if not docs.any(): return []
    q_vec = np.array([model.encode(query)]).astype('float32')
    search_k = min(k, index.ntotal)
    D, I = index.search(q_vec, search_k)
    results = []
    for dist, idx in zip(D[0], I[0]):
        if idx >= len(docs): continue
        similarity = 1 / (1 + dist)
        if similarity >= threshold:
            results.append({
                "document_name": doc_names[idx],
                "text": docs[idx],
                "similarity": round(similarity,3)
            })
    return sorted(results, key=lambda x: x["similarity"], reverse=True)

STOP_PREFIXES = ["hi","hello","hey","can you tell me","let me know","please","could you"]
def multi_topic_search(query):
    query_clean = query.lower().strip()
    for p in STOP_PREFIXES:
        if query_clean.startswith(p): query_clean = query_clean[len(p):].strip()
    return retrieve_documents(query_clean)

def format_references(docs_results, top_n=3):
    if not docs_results: return "None"
    seen = set()
    top_docs = []
    for r in docs_results:
        if r["document_name"] not in seen:
            seen.add(r["document_name"])
            top_docs.append(r)
        if len(top_docs) >= top_n: break
    return ", ".join([r["document_name"] for r in top_docs])

# -----------------------------
# Chatbot
# -----------------------------
conversation_history = []
GREETINGS = ["hi","hello","hey","hi there","hello there","hey there"]

PROMPT_TEMPLATE = """
You are an AI assistant. Answer **ONLY using the Context below**. You may summarize or infer from the text.

Context:
{documents}

Question:
{question}

- Do not use general knowledge.
- Use Markdown and short paragraphs.
- If context has no info, reply: "I cannot answer this question as it is out of scope."
"""

def generate_simple_answer(prompt, max_tokens=2000, temperature=0.2):
    if not client: return "Error: OpenAI client not initialized.", "Error"
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role":"user","content":prompt}],
            max_tokens=max_tokens, temperature=temperature
        )
        content = response.choices[0].message.content
        return content, content
    except Exception as e:
        return f"Error: {e}", f"Error: {e}"

def chatbot_response(user_query):
    global conversation_history
    q_lower = user_query.lower().strip()
    if q_lower in GREETINGS:
        resp = "Hello! How can I assist you?"
        conversation_history.append(f"You: {user_query}\nChatbot: {resp}")
        return resp, resp
    if q_lower == "history":
        return "\n".join(conversation_history) if conversation_history else "No history yet.", ""
    if q_lower == "clear":
        conversation_history.clear()
        return "Conversation cleared.", ""

    # Image match
    cleaned_query = re.sub(r'[\s_\-]', '', q_lower)
    for f in os.listdir(UPLOADS_DIR):
        ext = os.path.splitext(f)[1].lower()
        if ext in [".png",".jpg",".jpeg",".bmp",".tiff"]:
            fname_no_ext = os.path.splitext(f)[0].lower()
            cleaned_fname = re.sub(r'[\s_\-]', '', fname_no_ext)
            if cleaned_fname in cleaned_query or any(w in q_lower for w in ["show","image","photo","display","picture"]):
                res = {"type":"image","content":f"http://127.0.0.1:8000/uploads/{f}"}
                conversation_history.append(f"You: {user_query}\nChatbot: [image]{f}")
                return res, f

    # Function call
    try:
        if client:
            func_prompt = f"Call function if needed: {user_query}"
            response = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role":"user","content":func_prompt}],
                max_tokens=2000, temperature=0.2, functions=FUNCTIONS
            )
            message = response.choices[0].message
            if hasattr(message,"function_call") and message.function_call:
                func_name = message.function_call.name
                func_args = json.loads(message.function_call.arguments or "{}")
                if func_name in CALLABLE_FUNCTIONS:
                    result = CALLABLE_FUNCTIONS[func_name](**func_args)
                    conversation_history.append(f"You: {user_query}\nChatbot: {result}")
                    return result, result
    except Exception: pass

    # RAG
    docs_results = multi_topic_search(user_query)
    OUT_OF_SCOPE = "I cannot answer this question as it is out of scope."
    
    if docs_results:
        context_text = "\n\n".join([r["text"] for r in docs_results])
        references_text = format_references(docs_results)
        prompt = PROMPT_TEMPLATE.format(documents=context_text, question=user_query)
        answer, spoken_answer_base = generate_simple_answer(prompt)
        if OUT_OF_SCOPE in answer.strip(): 
            final_resp = OUT_OF_SCOPE
            spoken_answer = final_resp
        else: 
            final_resp = f"{answer.strip()}\n\n---\n**References**: {references_text}"
            spoken_answer = spoken_answer_base
        conversation_history.append(f"You: {user_query}\nChatbot: {final_resp}")
        return final_resp, spoken_answer
    
    conversation_history.append(f"You: {user_query}\nChatbot: {OUT_OF_SCOPE}")
    return OUT_OF_SCOPE, OUT_OF_SCOPE

# -----------------------------
# TTS
# -----------------------------
def text_to_speech(text:str):
    if not text.strip(): return
    cfg = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    audio_cfg = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio_cfg)
    synthesizer.speak_text_async(text)

def speech_to_text():
    cfg = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    audio_cfg = speechsdk.audio.AudioConfig(use_default_microphone=True)
    recognizer = speechsdk.SpeechRecognizer(speech_config=cfg, audio_config=audio_cfg)
    result = recognizer.recognize_once_async().get()
    return result.text if result.reason == speechsdk.ResultReason.RecognizedSpeech else ""

# -----------------------------
# Main loop
# -----------------------------
if __name__ == "__main__":
    console = Console()
    console.print("[bold green]✅ Chatbot ready! (Advanced OCR Enabled)[/bold green]\nType 'exit', 'voice', 'speak on/off', or drop files in 'uploads/'.")
    SPEAK_MODE = False
    try:
        while True:
            user_query = console.input("[bold yellow]You:[/bold yellow] ").strip()
            if user_query.lower() in ["exit","quit"]:
                console.print("[bold red]👋 Goodbye![/bold red]"); break
            if user_query.lower() == "speak on": SPEAK_MODE=True; console.print("[bold green]🔊 Speak mode enabled.[/bold green]"); continue
            if user_query.lower() == "speak off": SPEAK_MODE=False; console.print("[bold red]🔇 Speak mode disabled.[/bold red]"); continue
            if user_query.lower() == "voice": 
                user_query = speech_to_text()
                if not user_query: console.print("[bold red]⚠️ No voice input detected.[/bold red]"); continue
                console.print(f"[bold yellow]You (voice):[/bold yellow] {user_query}")
            display_answer, spoken_answer = chatbot_response(user_query)
            console.print("\n[bold cyan]Chatbot:[/bold cyan]")
            if isinstance(display_answer, dict) and display_answer.get("type")=="image":
                console.print(f'[bold magenta] Displaying image:[/bold magenta] {display_answer["content"]}')
                if SPEAK_MODE: text_to_speech(f"Displaying image: {os.path.basename(display_answer['content'])}")
            else:
                console.print(Markdown(display_answer))
                if SPEAK_MODE: text_to_speech(spoken_answer)
    except KeyboardInterrupt:
        console.print("[bold red]\n👋 Chatbot stopped by user.[/bold red]")
    finally:
        observer.stop()
        observer.join()
