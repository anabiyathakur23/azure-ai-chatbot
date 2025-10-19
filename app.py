import os
import sys
from fastapi import FastAPI, UploadFile, File, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Document Q&A chatbot imports
sys.path.append(r"C:\Users\anabi\Downloads\azure-ai-chatbot\chatbot")
from chatbot import chatbot_response, add_file_to_index, UPLOADS_DIR

import json
import base64
import logging
import asyncio
import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("azure-rt-bot")

AZURE_OPENAI_API_KEY = "DvKiz36Kj0gA37FWIsh5sAAY34Slit1XNyCGI1Wh96gNYaosKa7gJQQJ99BJACfhMk5XJ3w3AAABACOGLGNg"
AZURE_OPENAI_DEPLOYMENT = "gpt-realtime"
AZURE_REALTIME_URL = (
    f"wss://chatbot-azure-realtime.openai.azure.com/openai/realtime"
    f"?api-version=2024-10-01-preview"
    f"&deployment={AZURE_OPENAI_DEPLOYMENT}"
    f"&api-key={AZURE_OPENAI_API_KEY}"
)

def is_valid_user_transcript(transcript, prev_transcript=None, prev_bot_reply=None):
    if not transcript:
        return False
    t = transcript.strip().lower()
    if not t:
        return False
    # Block short, filler/generic/greetings, repeated transcript, repeated bot reply, single word, etc.
    invalids = {
        "...", ".", "-", "uh", "umm", "hm", "hmm", "uhh", "uhm", "okay", "ok", "yes", "no",
        "hi", "hello", "hey", "greetings", "good morning", "good evening", "good afternoon",
        "absolutely", "great", "perfect", "let's", "sure", "no problem", "of course", "no worries",
        "get started", "just let me know", "just", "let me know", "help", "thanks", "thank you", "alright",
        "awesome", "right", "fine", "cool", "nice", "yep", "yup", "yeah"
    }
    if prev_transcript and t == prev_transcript.strip().lower():
        logger.info(f"🛑 Transcript is repeat: '{t}'")
        return False
    if prev_bot_reply and t == prev_bot_reply.strip().lower():
        logger.info(f"🛑 Transcript matches last bot reply: '{t}'")
        return False
    # Block if in invalids, less than 7 chars, or less than 2 words
    if t in invalids or len(t) < 7 or len(t.split()) < 2:
        logger.info(f"🛑 Transcript is filler/greeting/too short: '{t}'")
        return False
    return True

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

@app.get("/")
async def root():
    return {"status": "running"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOADS_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        add_file_to_index(file_path)
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/message")
async def get_message(data: dict):
    try:
        user_msg = data.get("message", "")
        if not user_msg:
            return JSONResponse({"reply": {"type": "text", "content": "No message provided"}})
        bot_reply, _ = chatbot_response(user_msg)
        if isinstance(bot_reply, str):
            return JSONResponse({"reply": {"type": "text", "content": bot_reply}})
        return JSONResponse({"reply": bot_reply})
    except Exception as e:
        logger.error(f"Message error: {e}")
        return JSONResponse({"reply": {"type": "text", "content": f"Error: {e}"}})

@app.websocket("/ws/realtime-audio")
async def realtime_audio(websocket: WebSocket):
    await websocket.accept()
    logger.info("✅ Client connected (audio mode)")
    try:
        async with websockets.connect(AZURE_REALTIME_URL, subprotocols=["realtime"]) as azure_ws:
            logger.info("✅ Connected to Azure GPT Realtime")

            # Session config
            await azure_ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": "You are an English-only AI assistant. You MUST respond ONLY in English.",
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 200
                    },
                    "tools": [],
                    "tool_choice": "auto"
                }
            }))
            await azure_ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": "Respond in English only. Be natural and conversational, but always speak in English. Never use any other language."
                }
            }))

            last_transcript = None
            last_bot_reply = None

            async def frontend_to_azure():
                while True:
                    try:
                        msg = await websocket.receive()
                        if "text" in msg:
                            try:
                                data = json.loads(msg["text"])
                                if data.get("type") in ["input_audio_buffer", "input_text"]:
                                    await azure_ws.send(msg["text"])
                            except Exception:
                                logger.exception("Error forwarding frontend text to Azure.")
                        elif "bytes" in msg:
                            await azure_ws.send(msg["bytes"])
                    except Exception as e:
                        logger.error(f"Frontend->Azure loop broke: {e}")
                        break

            async def azure_to_frontend():
                nonlocal last_transcript, last_bot_reply
                async for msg in azure_ws:
                    try:
                        if isinstance(msg, str):
                            try:
                                data = json.loads(msg)
                                msg_type = data.get("type")
                                if msg_type == "response_text":
                                    last_bot_reply = data.get("text", "")
                                    await websocket.send_text(data.get("text", ""))
                                elif msg_type == "response_completed":
                                    await websocket.send_text("[END]")
                                elif msg_type == "input_audio_buffer.speech_started":
                                    await websocket.send_text(json.dumps({"type": "speech_started", "message": "Listening..."}))
                                elif msg_type == "input_audio_buffer.speech_stopped":
                                    await websocket.send_text(json.dumps({"type": "speech_stopped", "message": "Processing..."}))
                                elif msg_type == "conversation.item.input_audio_transcription.completed":
                                    transcript = data.get("transcript", "")
                                    logger.info(f"📝 Transcript received: '{transcript}'")
                                    await websocket.send_text(json.dumps({"type": "transcription", "transcript": transcript}))
                                    if is_valid_user_transcript(transcript, last_transcript, last_bot_reply):
                                        logger.info(f"✅ Valid transcript, sending response.create: '{transcript}'")
                                        last_transcript = transcript
                                        await azure_ws.send(json.dumps({
                                            "type": "response.create",
                                            "response": {
                                                "modalities": ["text", "audio"],
                                                "instructions": "Respond in English only. Be natural and conversational, but always speak in English. Never use any other language."
                                            }
                                        }))
                                    else:
                                        logger.info(f"🛑 Ignored transcript: '{transcript}'")
                                        last_transcript = transcript
                                elif msg_type == "response.audio_transcript.delta":
                                    transcript_delta = data.get("delta", "")
                                    if transcript_delta:
                                        await websocket.send_text(json.dumps({"type": "transcript_delta", "delta": transcript_delta}))
                                elif msg_type == "response.audio_transcript.done":
                                    transcript = data.get("transcript", "")
                                    logger.info(f"📝 Transcript done: '{transcript}'")
                                    await websocket.send_text(json.dumps({"type": "transcription", "transcript": transcript}))
                                    if is_valid_user_transcript(transcript, last_transcript, last_bot_reply):
                                        logger.info(f"✅ Valid transcript, sending response.create: '{transcript}'")
                                        last_transcript = transcript
                                        await azure_ws.send(json.dumps({
                                            "type": "response.create",
                                            "response": {
                                                "modalities": ["text", "audio"],
                                                "instructions": "Respond in English only. Be natural and conversational, but always speak in English. Never use any other language."
                                            }
                                        }))
                                    else:
                                        logger.info(f"🛑 Ignored transcript: '{transcript}'")
                                        last_transcript = transcript
                                elif msg_type == "response.audio.delta":
                                    audio_data = data.get("delta", "")
                                    if audio_data:
                                        audio_bytes = base64.b64decode(audio_data)
                                        await websocket.send_bytes(audio_bytes)
                                elif msg_type == "response.audio.done":
                                    pass
                                elif msg_type == "response.done":
                                    await websocket.send_text("[END]")
                                elif msg_type == "error":
                                    error_msg = data.get("error", {}).get("message", "Unknown error")
                                    await websocket.send_text(json.dumps({"type": "error", "message": error_msg}))
                            except Exception:
                                logger.exception("Error processing Azure message.")
                        elif isinstance(msg, bytes):
                            await websocket.send_bytes(msg)
                    except Exception as e:
                        logger.error(f"Azure->Frontend loop broke: {e}")

            await asyncio.gather(frontend_to_azure(), azure_to_frontend())

    except Exception as e:
        logger.error(f"❌ Critical Azure connection error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        logger.info("❌ Client disconnected")
