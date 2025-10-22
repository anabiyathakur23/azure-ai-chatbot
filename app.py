import os
import sys
import json
import base64
import logging
import asyncio
import websockets
from fastapi import FastAPI, UploadFile, File, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Document Q&A imports (Assuming the path and modules are correct)
try:
    sys.path.append(r"C:\Users\anabi\Downloads\azure-ai-chatbot\chatbot")
    from chatbot import chatbot_response, add_file_to_index, UPLOADS_DIR
except ImportError:
    # Fallback/Placeholder if modules are not found
    UPLOADS_DIR = "uploads"
    def chatbot_response(msg): return "Chatbot stub response.", None
    def add_file_to_index(path): print(f"Stub: Indexing {path}")
    if not os.path.exists(UPLOADS_DIR): os.makedirs(UPLOADS_DIR)


# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("azure-rt-bot")

# -------------------- Azure Config --------------------
# WARNING: Exposing API keys in code is HIGHLY discouraged. Use environment variables.
AZURE_OPENAI_API_KEY = "DvKiz36Kj0gA37FWIsh5sAAY34Slit1XNyCGI1Wh96gNYaosKa7gJQQJ99BJACfhMk5XJ3w3AAABACOGLGNg"
AZURE_OPENAI_DEPLOYMENT = "gpt-realtime"
AZURE_REALTIME_URL = (
    f"wss://chatbot-azure-realtime.openai.azure.com/openai/realtime"
    f"?api-version=2024-10-01-preview"
    f"&deployment={AZURE_OPENAI_DEPLOYMENT}"
    f"&api-key={AZURE_OPENAI_API_KEY}"
)

# -------------------- FastAPI App --------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


# -------------------- Routes --------------------
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


# -------------------- Realtime Audio WebSocket --------------------
@app.websocket("/ws/realtime-audio")
async def realtime_audio(websocket: WebSocket):
    await websocket.accept()
    print("✅ Client connected (audio mode)")
    logger.info("Client connected (audio mode)")

    # Flag to track if a response request has been sent to Azure
    response_in_progress = False

    try:
        async with websockets.connect(AZURE_REALTIME_URL, subprotocols=["realtime"]) as azure_ws:
            print("✅ Connected to Azure GPT Realtime")
            logger.info("Connected to Azure GPT Realtime")

            # -------------------- Configure Session --------------------
            await azure_ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": "You are an English-only AI assistant. Respond only in English.",
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 200
                    }
                }
            }))

            last_transcript = None

            # -------------------- Frontend -> Azure --------------------
            async def frontend_to_azure():
                nonlocal response_in_progress
                while True:
                    try:
                        msg = await websocket.receive()
                        if "text" in msg:
                            data = json.loads(msg["text"])
                            ptype = data.get("type")

                            if ptype == "input_audio_buffer.commit":
                                if not response_in_progress:
                                    response_in_progress = True
                                    print("Committing audio to Azure, requesting response.create.")
                                    await azure_ws.send(json.dumps({
                                        "type": "response.create",
                                        "response": {"modalities": ["text", "audio"], "instructions": "Respond in English only."}
                                    }))
                                else:
                                    print("Commit blocked: Response already in progress.")
                            
                            elif ptype == "input_audio_buffer.append":
                                await azure_ws.send(msg["text"])
                            
                            elif ptype == "commit": # Legacy/alternative commit path
                                if last_transcript and len(last_transcript.split()) >= 2 and not response_in_progress:
                                    response_in_progress = True
                                    await azure_ws.send(json.dumps({
                                        "type": "response.create",
                                        "response": {"modalities": ["text", "audio"], "instructions": "Respond in English only."}
                                    }))
                                else:
                                    print(" Commit ignored: transcript empty/short or response in progress")
                            
                            else:
                                await azure_ws.send(msg["text"])

                        elif "bytes" in msg:
                            await azure_ws.send(msg["bytes"])

                    except Exception as e:
                        print(f"❌ Frontend->Azure loop error: {e}")
                        logger.error(f"Frontend->Azure loop error: {e}")
                        break

            # -------------------- Azure -> Frontend --------------------
            async def azure_to_frontend():
                nonlocal response_in_progress, last_transcript
                async for msg in azure_ws:
                    try:
                        if isinstance(msg, str):
                            data = json.loads(msg)
                            mtype = data.get("type")
                            
                            # End of response signal
                            if mtype in ("response.audio.done", "response.done"):
                                response_in_progress = False 
                                await websocket.send_text("[END]")

                            # Final user transcription
                            elif mtype == "conversation.item.input_audio_transcription.completed":
                                transcript = data.get("transcript", "").strip()
                                last_transcript = transcript
                                if transcript:
                                    await websocket.send_text(json.dumps({"type": "transcription", "transcript": transcript}))

                            # Partial transcript
                            elif mtype in ("response.audio_transcript.delta", "response.input_audio_transcription.delta"):
                                delta = data.get("delta", "")
                                if delta:
                                    await websocket.send_text(json.dumps({"type": "transcript_delta", "delta": delta}))

                            # Bot text response
                            elif mtype == "response_text":
                                await websocket.send_text(data.get("text", ""))

                            # Bot audio streaming
                            elif mtype == "response.audio.delta":
                                audio_b64 = data.get("delta", "")
                                if audio_b64:
                                    await websocket.send_bytes(base64.b64decode(audio_b64))

                            # Errors
                            elif mtype == "error":
                                error_msg = data.get("error", {}).get("message", "Unknown")
                                response_in_progress = False # Clear state on error
                                await websocket.send_text(json.dumps({"type": "error", "message": error_msg}))

                            # Speech events (forwarded but state managed on client)
                            elif mtype == "input_audio_buffer.speech_started":
                                await websocket.send_text(json.dumps({"type": "speech_started", "message": "Listening..."}))
                            elif mtype == "input_audio_buffer.speech_stopped":
                                await websocket.send_text(json.dumps({"type": "speech_stopped", "message": "Processing..."}))


                        elif isinstance(msg, (bytes, bytearray)):
                            await websocket.send_bytes(msg)

                    except Exception as e:
                        print(f"❌ Azure->Frontend loop broke: {e}")
                        logger.error(f"Azure->Frontend loop broke: {e}")
                        break

            # Run both loops concurrently
            await asyncio.gather(frontend_to_azure(), azure_to_frontend())

    except Exception as e:
        print(f"❌ Critical Azure connection error: {e}")
        logger.error(f"Critical Azure connection error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        print("❌ Client disconnected")
        logger.info("Client disconnected")
