# from fastapi import FastAPI, Form
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import StreamingResponse
# import httpx
# import os
# import json
# from system_prompt.basic_prompts import SYSTEM_PROMPT
# import subprocess
# OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')
# OLLAMA_CHAT_URL = f"{OLLAMA_HOST}/api/chat"
# CHAT_MODEL = "gemma3:12b"

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ─────────────────────────────────────────────────────────────────────────────
# # 💬 CONVERSATION MEMORY
# # ─────────────────────────────────────────────────────────────────────────────
# # Full chat history sent to the LLM on every call. The system prompt stays at
# # index 0 so it always frames how the model should behave; every user/assistant
# # turn after that is appended here and persists for the life of the process.
# conversation_history = [
#     {"role": "system", "content": SYSTEM_PROMPT}
# ]

# # ─────────────────────────────────────────────────────────────────────────────
# # 🚀 API ENDPOINTS
# # ─────────────────────────────────────────────────────────────────────────────
# @app.get("/")
# async def hellow():
#     return {"message": "Welcome to the Chat API!"}


# def sse_pack(event: str, data: dict) -> str:
#     """Formats one Server-Sent-Event frame."""
#     return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# async def generate_chat_stream(message_text: str):
#     """Async generator: appends the user's message to conversation_history,
#     then streams the LLM's reply token-by-token as SSE frames, straight from
#     Ollama's HTTP response."""
#     global conversation_history

#     user_message = message_text.strip()
#     if user_message:
#         conversation_history.append({"role": "user", "content": user_message})

#     full_reply = ""
#     payload = {"model": CHAT_MODEL, "messages": conversation_history, "stream": True}
#     if "segmentation report" in user_message.lower():
#         # Call the external script to generate the segmentation report
#         try:
#             result = subprocess.run(
#                 ["python3", "/mnt/c/development/Thesis/PolypSegmentationBasedClassification/y-net/y-net-elm/python_profiler/generate_segmentation_report.py"],
#                 capture_output=True,
#                 text=True,
#                 check=True
#             )
#             segmentation_report = result.stdout.strip()
#             full_reply += segmentation_report
#             yield sse_pack("token", {"text": segmentation_report})
#         except subprocess.CalledProcessError as e:
#             error_message = f"Error generating segmentation report: {e.stderr}"
#             yield sse_pack("error", {"text": error_message})
#             return

#     try:
#         async with httpx.AsyncClient(timeout=None) as client:
#             async with client.stream("POST", OLLAMA_CHAT_URL, json=payload) as response:
#                 response.raise_for_status()
#                 async for line in response.aiter_lines():
#                     if not line:
#                         continue
#                     chunk = json.loads(line)
#                     token = chunk.get("message", {}).get("content", "")
#                     if token:
#                         full_reply += token
#                         yield sse_pack("token", {"text": token})
#                     if chunk.get("done"):
#                         break
#     except Exception as e:
#         yield sse_pack("error", {"text": str(e)})
#         return

#     conversation_history.append({"role": "assistant", "content": full_reply})
#     yield sse_pack("done", {})


# @app.post("/chat")
# async def chat_endpoint(message: str = Form(...)):
#     return StreamingResponse(
#         generate_chat_stream(message),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "Connection": "keep-alive",
#             "X-Accel-Buffering": "no",  # disable nginx buffering if present
#         },
#     )


# @app.post("/reset")
# async def reset_endpoint():
#     global conversation_history
#     conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
#     return {"reply": "Conversation memory cleared.", "action": "NONE"}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import os
import json
import base64
import tempfile
import subprocess
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

async def generate_chat_stream(message_text: str, input_image_path: str = None):
    global conversation_history

    user_message = message_text.strip()
    full_reply = ""

    # 🟢 1. IF AN IMAGE WAS UPLOADED, PROCESS IT FIRST
    if input_image_path:
        # Define where the script should save the output image
        output_image_path = f"{input_image_path}_output.png"
        
        try:
            # Path to your segmentation script
            script_path = "/mnt/c/development/Thesis/PolypSegmentationBasedClassification/y-net/y-net-elm/python_profiler/generate_segmentation_report.py"
            
            # Call script with CLI arguments (Input Path & Output Path)
            subprocess.run(
                [
                    "python3", script_path, 
                    "--input", input_image_path, 
                    "--output", output_image_path
                ],
                capture_output=True,
                text=True,
                check=True
            )

            # Check if output image was generated successfully
            if os.path.exists(output_image_path):
                # Read output image and convert to Base64
                with open(output_image_path, "rb") as img_file:
                    b64_encoded = base64.b64encode(img_file.read()).decode('utf-8')
                
                # Send the generated image to the frontend FIRST via 'meta' event
                yield sse_pack("meta", {"image_data": f"data:image/png;base64,{b64_encoded}"})
                
                # Enhance the text prompt so Ollama knows an image was processed
                image_context = "[System: The user uploaded a polyp image. The segmentation model successfully processed it and returned an overlay.]\n"
                user_message = image_context + (user_message if user_message else "Please provide a brief report on this segmentation.")
            else:
                yield sse_pack("error", {"text": "⚠️ Segmentation script ran, but output image was not found."})

        except subprocess.CalledProcessError as e:
            error_message = f"⚠️ Error running segmentation model:\n{e.stderr}"
            yield sse_pack("error", {"text": error_message})
            return
        finally:
            # Clean up temporary files so your hard drive doesn't fill up
            if os.path.exists(input_image_path):
                os.remove(input_image_path)
            if os.path.exists(output_image_path):
                os.remove(output_image_path)

    # 🟢 2. PROCEED WITH NORMAL CHAT GENERATION (OLLAMA)
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


# 👇 UPDATED CHAT ENDPOINT TO ACCEPT FILE UPLOADS
@app.post("/chat")
async def chat_endpoint(
    message: str = Form(""), 
    file: UploadFile = File(None)
):
    file_path = None
    
    # If a file was uploaded from React, save it to a temporary location
    if file:
        ext = os.path.splitext(file.filename)[1]
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        temp_input.write(await file.read())
        temp_input.close()
        file_path = temp_input.name

    return StreamingResponse(
        generate_chat_stream(message, file_path),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no", 
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