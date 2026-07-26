from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from contextlib import asynccontextmanager
import httpx, os, json, base64
from system_prompt.basic_prompts import SYSTEM_PROMPT
from model_engine import SegmentationEngine, MODEL_PATH

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')
OLLAMA_CHAT_URL = f"{OLLAMA_HOST}/api/chat"
CHAT_MODEL = "gemma3:12b"

engine: SegmentationEngine | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = SegmentationEngine(MODEL_PATH)   # 🟢 সার্ভার শুরুর সময় একবারই লোড হবে
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

@app.get("/")
async def hellow():
    return {"message": "Welcome to the Chat API!"}

def sse_pack(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

async def generate_chat_stream(message_text: str, image_bytes: bytes = None):
    global conversation_history
    user_message = message_text.strip()
    full_reply = ""

    if image_bytes:
        try:
            # 🚀 subprocess নেই, cold-start নেই — সরাসরি লোড হয়ে থাকা মডেল দিয়ে inference
            output_png_bytes = await run_in_threadpool(engine.predict, image_bytes)
            b64_encoded = base64.b64encode(output_png_bytes).decode('utf-8')
            yield sse_pack("meta", {"image_data": f"data:image/png;base64,{b64_encoded}"})
    
            image_context = "[System: The user uploaded a polyp image. The segmentation model successfully processed it and returned an overlay.]\n"
            user_message = image_context + (user_message if user_message else "Please provide a brief report on this segmentation.")
        except Exception as e:
            yield sse_pack("error", {"text": f"⚠️ Segmentation Error: {str(e)}"})
            return

    if user_message:
        conversation_history.append({"role": "user", "content": user_message})

    payload = {"model": CHAT_MODEL, "messages": conversation_history, "stream": True}
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", OLLAMA_CHAT_URL, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_reply += token
                        yield sse_pack("token", {"text": token})
                    if chunk.get("done"):
                        break
    except Exception as e:
        yield sse_pack("error", {"text": f"Ollama Error: {str(e)}"})
        return

    conversation_history.append({"role": "assistant", "content": full_reply})
    yield sse_pack("done", {})

@app.post("/chat")
async def chat_endpoint(message: str = Form(""), file: UploadFile = File(None)):
    image_bytes = await file.read() if file else None
    return StreamingResponse(
        generate_chat_stream(message, image_bytes),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )

@app.post("/reset")
async def reset_endpoint():
    global conversation_history
    conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    return {"reply": "Conversation memory cleared.", "action": "NONE"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)