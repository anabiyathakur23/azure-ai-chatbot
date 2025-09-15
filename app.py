import sys
import os
sys.path.append(r"C:\Users\anabi\Downloads\azure-ai-chatbot\chatbot")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from chatbot import chatbot_response  # your existing chatbot.py

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # your Vite frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/message")
async def send_message(data: dict):
    user_message = data.get("message", "")
    reply, _ = chatbot_response(user_message)
    # If reply is empty or just echoes the user, send fallback
    if reply.strip().lower() == user_message.strip().lower() or not reply.strip():
        reply = "Sorry, I don't have an answer for that."
    return {"reply": reply}