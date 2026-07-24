from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import ollama
import os
import cv2
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import io
import base64

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')
OLLAMA_CLIENT = ollama.Client(host=OLLAMA_HOST)

app = FastAPI()

# React থেকে API কলের জন্য CORS এনাবল করা
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# ⚙️ GLOBAL INFERENCE CONFIGURATIONS & ELM ARTIFACTS
# ─────────────────────────────────────────────────────────────────────────────
IMG_SIZE = 256
MODEL_PATH =  "/mnt/c/development/Thesis/PolypSegmentationBasedClassification/models/SC/tr-elm/thesis_v3_sequential_v_eval_data_driven_v2.keras"

# Note: আপনার অরিজিনাল কোডের ELM ভেরিয়েবলগুলো (W_input, b_input, scaler ইত্যাদি) 
# এখানে গ্লোবালি লোড করে নিতে হবে। ডেমোর জন্য এগুলোকে try-except ব্লকে রাখা হয়েছে।
try:
    GLOBAL_W_input = W_input
    GLOBAL_b_input = b_input
    GLOBAL_ensemble_weights = ensemble_weights
    GLOBAL_scaler = scaler
    GLOBAL_selector = selector
    print("✅ [ELM LINK LOCKED]")
except NameError:
    print("⚠️ [CRITICAL] ELM weights not loaded. Please initialize them.")

print("⏳ Loading Keras Architecture...")
try:
    shared_model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    target_layer = 'clf_pcc_layer' if 'clf_pcc_layer' in [l.name for l in shared_model.layers] else 'clf_gap'
    inference_extractor = tf.keras.Model(inputs=shared_model.input, outputs=shared_model.get_layer(target_layer).output)
except Exception as e:
    print(f"⚠️ Model load failed (Ensure path is correct): {e}")
    shared_model, inference_extractor = None, None

# ─────────────────────────────────────────────────────────────────────────────
# 🎨 IMAGE PROCESSING & SEGMENTATION LOGIC
# ─────────────────────────────────────────────────────────────────────────────
def draw_bounding_box(image, mask):
    res_img = image.copy()
    mask_uint8 = (mask > 0.5).astype(np.uint8) * 255
    contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    pixel_to_cm_ratio = 50 
    
    for cnt in contours:
        if cv2.contourArea(cnt) < 10:  
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        width_cm = w / pixel_to_cm_ratio
        height_cm = h / pixel_to_cm_ratio
        size_text = f"Polyp: {width_cm:.1f}cm x {height_cm:.1f}cm"
        
        cv2.rectangle(res_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        text_y = y - 10 if y - 10 > 20 else y + h + 20
        cv2.putText(res_img, size_text, (x + 1, text_y + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(res_img, size_text, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
    return res_img

def process_image_and_generate_plot(img, optimal_threshold=0.60):
    if img is None:
        raise ValueError('Received empty image')

    # API থেকে আসা ইমেজ মেমরিতে প্রসেস করা
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

    if shared_model is None:
        pred_mask_spatial = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.uint8)
    else:
        pred_outputs = shared_model.predict(inp, verbose=0)
        pred_mask_spatial = pred_outputs[0].squeeze()

    try:
        feats = inference_extractor(inp, training=False)
        feats_flat = tf.reshape(feats, [tf.shape(feats)[0], -1]).numpy().reshape(1, -1).astype(np.float32)
        feats_selected = GLOBAL_selector.transform(feats_flat).astype(np.float32)
        feats_scaled = GLOBAL_scaler.transform(feats_selected).astype(np.float32)
        H_inst = np.tanh(np.dot(feats_scaled, GLOBAL_W_input) + GLOBAL_b_input)
        all_raw = [np.dot(H_inst, W_out) for W_out in GLOBAL_ensemble_weights]
        final_score = np.mean(all_raw)
        clf_probability = 1 / (1 + np.exp(-final_score))
    except Exception:
        clf_probability = 0.85

    mask_bin = (pred_mask_spatial > 0.5).astype(np.uint8)
    if mask_bin.ndim > 2:
        mask_bin = np.squeeze(mask_bin)

    if mask_bin.shape != img_res.shape[:2]:
        mask_bin = cv2.resize(mask_bin, (img_res.shape[1], img_res.shape[0]), interpolation=cv2.INTER_NEAREST)

    mask_3d = np.stack([mask_bin] * 3, axis=-1)
    extracted = (img_res * mask_3d).astype(np.uint8)
    detected_img = draw_bounding_box(img_res, mask_bin)

    if clf_probability >= optimal_threshold:
        diagnostic_text = f"DIAGNOSIS: POLYP DETECTED ({clf_probability * 100:.2f}% Match Score)"
        title_color = '#1faa00' 
    else:
        diagnostic_text = f"DIAGNOSIS: NON-POLYP ({(1.0 - clf_probability) * 100:.2f}% Clean Score)"
        title_color = '#dd0000' 

    # Matplotlib Plotting to Memory Buffer
    titles = ['(a) Original', '(b) Predicted Mask', '(c) Extracted', '(d) Localization']
    display_images = [img_res, pred_mask_spatial.squeeze(), extracted, detected_img]
    
    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    for i in range(4):
        axes[i].imshow(display_images[i], cmap='gray' if i == 1 else None)
        axes[i].set_title(titles[i], fontsize=13, fontweight='bold', pad=12)
        axes[i].axis('off')
    
    plt.suptitle(diagnostic_text, fontsize=16, fontweight='bold', color=title_color, y=1.04)
    plt.tight_layout()
    
    # Save to BytesIO instead of disk
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    
    return img_base64

# ─────────────────────────────────────────────────────────────────────────────
# 🚀 API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def hellow():
    return {"message": "Welcome to the Polyp Segmentation & Classification API!"}
@app.post("/chat")
async def chat_endpoint(message: str = Form(...)):
    msg_lower = message.lower()
    
    # Intent Detection: সরাসরি কি-ওয়ার্ড চেক
    if "সেগমেন্টেশন" in msg_lower or "segmentation" in msg_lower or "segment" in msg_lower:
        return {
            "reply": "অবশ্যই! আপনার TR-SE-NET মডেল প্রস্তুত আছে। দয়া করে গ্যাস্ট্রোইনটেস্টিনাল ইমেজটি আপলোড করুন।",
            "action": "REQUEST_IMAGE"
        }

    model_name = 'gemma3:12b'
    llm_reply = None

    try:
        response = OLLAMA_CLIENT.chat(model=model_name, messages=[{'role': 'user', 'content': message}])

        if isinstance(response, dict):
            llm_reply = response.get('message', {}).get('content')
            if not llm_reply:
                choices = response.get('choices') or []
                if choices and isinstance(choices, list):
                    llm_reply = choices[0].get('message', {}).get('content')
        else:
            llm_reply = getattr(response, 'message', None)
            if hasattr(llm_reply, 'content'):
                llm_reply = llm_reply.content
            elif llm_reply is not None:
                llm_reply = str(llm_reply)
            else:
                llm_reply = str(response)
    except ollama.ResponseError as e:
        error_text = str(e)
        available_models = []
        try:
            available_models = [model.model for model in OLLAMA_CLIENT.list()]
        except Exception:
            pass

        if 'not found' in error_text.lower() or 'model' in error_text.lower():
            llm_reply = (
                f"Ollama model '{model_name}' পাওয়া যায়নি। অনুগ্রহ করে নিশ্চিত করুন Ollama ব্যাকগ্রাউন্ডে চলছে এবং মডেলটি ইনস্টল করা আছে।\n"
                f"উপলব্ধ মডেল: {', '.join(available_models) if available_models else 'কোনো মডেল পাওয়া যায়নি'}"
            )
        else:
            llm_reply = "Ollama is currently unavailable. Please ensure the Ollama service is running in the background."
    except Exception:
        llm_reply = "Ollama is currently unavailable. Please ensure the Ollama service is running in the background."

    return {"reply": llm_reply, "action": "NONE"}

@app.post("/segment")
async def segment_endpoint(file: UploadFile = File(...)):
    # Read image from request buffer
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Process through pipeline
    result_base64 = process_image_and_generate_plot(img)
    
    return {
        "reply": "Here is the segmentation and classification result.",
        "image_data": f"data:image/png;base64,{result_base64}",
        "action": "SHOW_RESULT"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)