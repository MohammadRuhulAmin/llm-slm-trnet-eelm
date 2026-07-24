from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
import httpx
import os
import cv2
import json
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import io
import base64
import time
from sklearn.preprocessing import RobustScaler
from sklearn.feature_selection import SelectKBest, f_classif
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
# ⚙️ MODEL / ELM SETUP  (unchanged core inference pipeline)
# ─────────────────────────────────────────────────────────────────────────────
IMG_SIZE = 256
MODEL_PATH_WINDOWS = r"C:\development\Thesis\PolypSegmentationBasedClassification\models\SC\tr-elm\thesis_v3_sequential_v_eval_data_driven_v2.keras"
MODEL_PATH_WSL = "/mnt/c/development/Thesis/PolypSegmentationBasedClassification/models/SC/tr-elm/thesis_v3_sequential_v_eval_data_driven_v2.keras"
MODEL_PATH = MODEL_PATH_WINDOWS if os.path.exists(MODEL_PATH_WINDOWS) else MODEL_PATH_WSL

ELM_CACHE_PATH_WINDOWS = r"C:\development\Thesis\PolypSegmentationBasedClassification\y-net\y-net-elm\data_intensive_pipeline\shap_feature_cache.npz"
ELM_CACHE_PATH_WSL = "/mnt/c/development/Thesis/PolypSegmentationBasedClassification/y-net/y-net-elm/data_intensive_pipeline/shap_feature_cache.npz"
ELM_CACHE_PATH = ELM_CACHE_PATH_WINDOWS if os.path.exists(ELM_CACHE_PATH_WINDOWS) else ELM_CACHE_PATH_WSL

ELM_ARTIFACT_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "elm_artifacts.npz"))


class NumpyFeatureSelector:
    def __init__(self, indices):
        self.indices = np.asarray(indices, dtype=np.int32)

    def transform(self, X):
        return X[:, self.indices]


def save_elm_artifacts(path, W_input, b_input, ensemble_weights, selector_indices, scaler):
    np.savez(
        path,
        W_input=W_input,
        b_input=b_input,
        ensemble_weights=np.stack(ensemble_weights),
        selector_support=np.asarray(selector_indices, dtype=np.int32),
        scaler_center_=scaler.center_,
        scaler_scale_=scaler.scale_,
    )


def load_elm_artifacts(path):
    data = np.load(path)
    ensemble_weights = [data['ensemble_weights'][i] for i in range(data['ensemble_weights'].shape[0])]
    scaler = RobustScaler()
    scaler.center_ = data['scaler_center_']
    scaler.scale_ = data['scaler_scale_']
    scaler.n_features_in_ = scaler.center_.shape[0]
    selector = NumpyFeatureSelector(data['selector_support'])
    return {
        'W_input': data['W_input'],
        'b_input': data['b_input'],
        'ensemble_weights': ensemble_weights,
        'selector': selector,
        'scaler': scaler,
    }


def train_elm_artifacts(cache_path, artifact_path, n_estimators=5, hidden_nodes=1024, k_best=500):
    data = np.load(cache_path)
    features = data['features']
    labels = data['labels']

    if features.ndim != 2:
        features = features.reshape(features.shape[0], -1)

    labels = np.asarray(labels, dtype=np.int32)
    if len(np.unique(labels)) < 2:
        raise ValueError("ELM cache requires at least two label classes.")

    labels_mapped = np.where(labels == 1, 1.0, -1.0).astype(np.float32)
    k_best = min(k_best, features.shape[1])
    selector = SelectKBest(score_func=f_classif, k=k_best)
    selected = selector.fit_transform(features, labels)
    scaler = RobustScaler().fit(selected)
    scaled = scaler.transform(selected).astype(np.float32)

    rng = np.random.RandomState(42)
    W_input = rng.normal(0, 0.05, (scaled.shape[1], hidden_nodes)).astype(np.float32)
    b_input = rng.normal(0, 0.05, (1, hidden_nodes)).astype(np.float32)
    H = np.tanh(np.dot(scaled, W_input) + b_input)

    ensemble_weights = []
    n_samples = scaled.shape[0]
    for i in range(n_estimators):
        idx = rng.choice(n_samples, size=n_samples, replace=True)
        H_boot = H[idx]
        y_boot = labels_mapped[idx]
        W_out = np.dot(np.linalg.pinv(H_boot), y_boot.reshape(-1, 1)).astype(np.float32)
        ensemble_weights.append(W_out)

    save_elm_artifacts(artifact_path, W_input, b_input, ensemble_weights, selector.get_support(indices=True), scaler)

    return {
        'W_input': W_input,
        'b_input': b_input,
        'ensemble_weights': ensemble_weights,
        'selector': NumpyFeatureSelector(selector.get_support(indices=True)),
        'scaler': scaler,
    }


def initialize_elm_engine():
    if os.path.exists(ELM_ARTIFACT_PATH):
        try:
            print(f"⏳ Loading ELM artifacts from {ELM_ARTIFACT_PATH}")
            return load_elm_artifacts(ELM_ARTIFACT_PATH)
        except Exception as exc:
            print(f"⚠️ Failed to load saved ELM artifacts: {exc}")

    if os.path.exists(ELM_CACHE_PATH):
        try:
            print(f"⏳ Building ELM artifacts from cache {ELM_CACHE_PATH}")
            artifacts = train_elm_artifacts(ELM_CACHE_PATH, ELM_ARTIFACT_PATH)
            print(f"✅ Built and saved ELM artifacts to {ELM_ARTIFACT_PATH}")
            return artifacts
        except Exception as exc:
            print(f"⚠️ Failed to train fallback ELM artifacts: {exc}")

    print("⚠️ No ELM artifacts available; classification will use fallback probabilities.")
    return None


GLOBAL_W_input = None
GLOBAL_b_input = None
GLOBAL_ensemble_weights = None
GLOBAL_scaler = None
GLOBAL_selector = None

print("⏳ Loading Keras Architecture...")
try:
    shared_model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    target_layer = 'clf_pcc_layer' if 'clf_pcc_layer' in [l.name for l in shared_model.layers] else 'clf_gap'
    inference_extractor = tf.keras.Model(inputs=shared_model.input, outputs=shared_model.get_layer(target_layer).output)
except Exception as e:
    print(f"⚠️ Model load failed (Ensure path is correct): {e}")
    shared_model, inference_extractor = None, None

elm_artifacts = initialize_elm_engine()
if elm_artifacts is not None:
    GLOBAL_W_input = elm_artifacts['W_input']
    GLOBAL_b_input = elm_artifacts['b_input']
    GLOBAL_ensemble_weights = elm_artifacts['ensemble_weights']
    GLOBAL_scaler = elm_artifacts['scaler']
    GLOBAL_selector = elm_artifacts['selector']

OPTIMAL_THRESHOLD = 0.60

# ─────────────────────────────────────────────────────────────────────────────
# 🎨 IMAGE PROCESSING & INFERENCE
# ─────────────────────────────────────────────────────────────────────────────
def draw_bounding_box(image, mask):
    res_img = image.copy()
    mask_uint8 = (mask > 0.5).astype(np.uint8) * 255
    contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    pixel_to_cm_ratio = 50
    boxes = []

    for cnt in contours:
        if cv2.contourArea(cnt) < 10:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        width_cm = w / pixel_to_cm_ratio
        height_cm = h / pixel_to_cm_ratio
        boxes.append({"width_cm": round(width_cm, 2), "height_cm": round(height_cm, 2)})

        size_text = f"Polyp: {width_cm:.1f}cm x {height_cm:.1f}cm"
        cv2.rectangle(res_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        text_y = y - 10 if y - 10 > 20 else y + h + 20
        cv2.putText(res_img, size_text, (x + 1, text_y + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(res_img, size_text, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)

    return res_img, boxes


def prepare_image(img):
    if img is None:
        raise ValueError('Received empty image')

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_res = cv2.resize(img_rgb, (IMG_SIZE, IMG_SIZE))
    lab = cv2.cvtColor(img_res, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l_channel)
    limg = cv2.merge((cl, a_channel, b_channel))
    enhanced_img = cv2.cvtColor(limg, cv2.COLOR_LAB2RGB)
    median_blur = cv2.medianBlur(enhanced_img, 3)
    sharpened = cv2.addWeighted(enhanced_img, 1.5, median_blur, -0.5, 0)
    inp = np.expand_dims(sharpened / 255.0, axis=0).astype(np.float32)
    return img_res, inp


def predict_mask(inp):
    if shared_model is None:
        return np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)
    pred_outputs = shared_model.predict(inp, verbose=0)
    return np.squeeze(pred_outputs[0])


def predict_polyp_probability(inp):
    if inference_extractor is None or GLOBAL_selector is None or GLOBAL_scaler is None or GLOBAL_W_input is None or GLOBAL_b_input is None or GLOBAL_ensemble_weights is None:
        return 0.85

    feats = inference_extractor(inp, training=False)
    feats_flat = tf.reshape(feats, [tf.shape(feats)[0], -1]).numpy().astype(np.float32)
    feats_selected = GLOBAL_selector.transform(feats_flat).astype(np.float32)
    feats_scaled = GLOBAL_scaler.transform(feats_selected).astype(np.float32)
    H_inst = np.tanh(np.dot(feats_scaled, GLOBAL_W_input) + GLOBAL_b_input)
    all_raw = [np.dot(H_inst, W_out) for W_out in GLOBAL_ensemble_weights]
    final_score = np.mean(all_raw)
    return float(1 / (1 + np.exp(-final_score)))


def build_annotated_image_base64(img_res, mask_bin, detected_img, title, title_color):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    panels = [img_res, mask_bin, detected_img]
    titles = ['(a) Original', '(b) Predicted Mask', '(c) Localization']

    for i in range(3):
        axes[i].imshow(panels[i], cmap='gray' if i == 1 else None)
        axes[i].set_title(titles[i], fontsize=13, fontweight='bold', pad=12)
        axes[i].axis('off')

    plt.suptitle(title, fontsize=16, fontweight='bold', color=title_color, y=1.04)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64


def analyze_image(img):
    """Runs the TR-SE-NET segmentation + ELM classification pipeline on one image
    and returns both a structured summary (for the LLM) and an annotated preview."""
    img_res, inp = prepare_image(img)
    pred_mask_spatial = predict_mask(inp)

    mask_bin = (pred_mask_spatial > 0.5).astype(np.uint8)
    if mask_bin.ndim > 2:
        mask_bin = np.squeeze(mask_bin)
    if mask_bin.shape != img_res.shape[:2]:
        mask_bin = cv2.resize(mask_bin, (img_res.shape[1], img_res.shape[0]), interpolation=cv2.INTER_NEAREST)

    detected_img, boxes = draw_bounding_box(img_res, mask_bin)
    probability = predict_polyp_probability(inp)
    is_polyp = probability >= OPTIMAL_THRESHOLD

    diagnosis = "POLYP DETECTED" if is_polyp else "NON-POLYP"
    title_color = '#1faa00' if is_polyp else '#dd0000'
    title = f"DIAGNOSIS: {diagnosis} ({probability * 100:.2f}% confidence)"

    annotated_base64 = build_annotated_image_base64(img_res, mask_bin, detected_img, title, title_color)

    summary = {
        "diagnosis": diagnosis,
        "probability": round(probability, 4),
        "mask_pixel_coverage_percent": round(float(mask_bin.mean() * 100), 2),
        "detected_regions": boxes,
        "model_status": "ELM ensemble active" if GLOBAL_ensemble_weights is not None else "ELM ensemble unavailable, fallback probability used",
    }
    return summary, annotated_base64

# ─────────────────────────────────────────────────────────────────────────────
# 💬 CONVERSATION MEMORY
# ─────────────────────────────────────────────────────────────────────────────
# Full chat history sent to the LLM (user + assistant turns, plus system notes
# describing any image that was analyzed, so later questions can refer back to it).
conversation_history = []

# Keeps the last few analyzed images (base64 + summary) so the frontend/LLM can
# refer to "the image I uploaded earlier" without re-uploading it.
image_memory = []
MAX_IMAGE_MEMORY = 5


def image_summary_to_text(summary):
    lines = [
        f"- Diagnosis: {summary['diagnosis']}",
        f"- Model confidence: {summary['probability'] * 100:.2f}%",
        f"- Mask coverage of image: {summary['mask_pixel_coverage_percent']}%",
        f"- Detected regions: {summary['detected_regions'] if summary['detected_regions'] else 'none'}",
        f"- Model status: {summary['model_status']}",
    ]
    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# 🚀 API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
async def hellow():
    return {"message": "Welcome to the Polyp Segmentation & Classification Chat API!"}


def sse_pack(event: str, data: dict) -> str:
    """Formats one Server-Sent-Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def generate_chat_stream(message_text: str, file_bytes: bytes | None):
    """Async generator: does the (optional) image analysis, then streams the
    LLM's reply token-by-token as SSE frames, straight from Ollama's HTTP
    response — no threadpool wrapping, so nothing gets buffered before it
    reaches the browser."""
    global conversation_history, image_memory

    image_data_url = None

    # ── Optional image analysis (CPU/GPU-bound, runs off the event loop) ───
    if file_bytes is not None:
        try:
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                yield sse_pack("error", {"text": "The uploaded file is not a valid image."})
                return

            summary, annotated_base64 = await run_in_threadpool(analyze_image, img)
            image_data_url = f"data:image/png;base64,{annotated_base64}"

            image_id = f"image_{int(time.time())}"
            image_memory.append({"id": image_id, "summary": summary, "image_data": image_data_url})
            image_memory[:] = image_memory[-MAX_IMAGE_MEMORY:]

            conversation_history.append({
                "role": "system",
                "content": (
                    f"[Image '{image_id}' uploaded and analyzed by the TR-SE-NET/ELM pipeline]\n"
                    f"{image_summary_to_text(summary)}\n"
                    "Use these findings to answer any questions the user asks about this image, "
                    "now or later in the conversation."
                ),
            })
        except Exception as e:
            yield sse_pack("error", {"text": f"An error occurred while processing the image: {str(e)}"})
            return

    # Tell the frontend right away whether an annotated image should be shown.
    yield sse_pack("meta", {"image_data": image_data_url, "action": "SHOW_RESULT" if image_data_url else "NONE"})

    # ── Add the user's message ─────────────────────────────────────────────
    user_message = message_text.strip() or (
        "I uploaded an image. Please explain what you found in it." if file_bytes is not None else ""
    )
    if user_message:
        conversation_history.append({"role": "user", "content": user_message})

    # ── Stream the LLM reply token-by-token, straight from Ollama's HTTP API ─
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
async def chat_endpoint(
    message: str = Form(""),
    file: UploadFile = File(None),
):
    # UploadFile.read() is async, so read the bytes here before handing off
    # to the async generator that does the (blocking) model inference + streaming.
    file_bytes = await file.read() if file is not None else None

    return StreamingResponse(
        generate_chat_stream(message, file_bytes),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering if present
        },
    )

conversation_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]
@app.post("/reset")
async def reset_endpoint():
    global conversation_history, image_memory
    conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    image_memory = []
    return {"reply": "Conversation memory cleared.", "action": "NONE"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)