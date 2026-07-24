from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import os
import json
from system_prompt.basic_prompts import SYSTEM_PROMPT

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')
OLLAMA_CHAT_URL = f"{OLLAMA_HOST}/api/chat"
CHAT_MODEL = "gemma3:12b"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# 💬 CONVERSATION MEMORY
# ─────────────────────────────────────────────────────────────────────────────
# Full chat history sent to the LLM on every call. The system prompt stays at
# index 0 so it always frames how the model should behave; every user/assistant
# turn after that is appended here and persists for the life of the process.
conversation_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

# ─────────────────────────────────────────────────────────────────────────────
# 🚀 API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
async def hellow():
    return {"message": "Welcome to the Chat API!"}


def sse_pack(event: str, data: dict) -> str:
    """Formats one Server-Sent-Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def generate_chat_stream(message_text: str):
    """Async generator: appends the user's message to conversation_history,
    then streams the LLM's reply token-by-token as SSE frames, straight from
    Ollama's HTTP response."""
    global conversation_history

    user_message = message_text.strip()
    if user_message:
        conversation_history.append({"role": "user", "content": user_message})

    full_reply = ""
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
        yield sse_pack("error", {"text": str(e)})
        return

    conversation_history.append({"role": "assistant", "content": full_reply})
    yield sse_pack("done", {})


@app.post("/chat")
async def chat_endpoint(message: str = Form(...)):
    return StreamingResponse(
        generate_chat_stream(message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering if present
        },
    )


@app.post("/reset")
async def reset_endpoint():
    global conversation_history
    conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    return {"reply": "Conversation memory cleared.", "action": "NONE"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)