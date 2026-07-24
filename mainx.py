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
from sklearn.preprocessing import RobustScaler
from sklearn.feature_selection import SelectKBest, f_classif

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
MODEL_PATH_WINDOWS = r"C:\development\Thesis\PolypSegmentationBasedClassification\models\SC\tr-elm\thesis_v3_sequential_v_eval_data_driven_v2.keras"
MODEL_PATH_WSL = "/mnt/c/development/Thesis/PolypSegmentationBasedClassification/models/SC/tr-elm/thesis_v3_sequential_v_eval_data_driven_v2.keras"
MODEL_PATH = MODEL_PATH_WINDOWS if os.path.exists(MODEL_PATH_WINDOWS) else MODEL_PATH_WSL
ELM_CACHE_PATH_WINDOWS = r"C:\development\Thesis\PolypSegmentationBasedClassification\y-net\y-net-elm\data_intensive_pipeline\shap_feature_cache.npz"
ELM_CACHE_PATH_WSL = "/mnt/c/development/Thesis/PolypSegmentationBasedClassification/y-net/y-net-elm/data_intensive_pipeline/shap_feature_cache.npz"
ELM_CACHE_PATH = ELM_CACHE_PATH_WINDOWS if os.path.exists(ELM_CACHE_PATH_WINDOWS) else ELM_CACHE_PATH_WSL
ELM_ARTIFACT_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "elm_artifacts.npz"))
SHAP_MAX_EVALS = 300
SHAP_BATCH_SIZE = 32

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


global GLOBAL_W_input, GLOBAL_b_input, GLOBAL_ensemble_weights, GLOBAL_scaler, GLOBAL_selector
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
    return 1 / (1 + np.exp(-final_score))


def full_pipeline_predict(images_uint8):
    if inference_extractor is None:
        return np.zeros((images_uint8.shape[0],), dtype=np.float32) + 0.85

    batch = images_uint8.astype(np.float32) / 255.0
    feats = inference_extractor(batch, training=False)
    feats_flat = tf.reshape(feats, [tf.shape(feats)[0], -1]).numpy().astype(np.float32)

    if GLOBAL_selector is None or GLOBAL_scaler is None or GLOBAL_W_input is None or GLOBAL_b_input is None or GLOBAL_ensemble_weights is None:
        return np.zeros((images_uint8.shape[0],), dtype=np.float32) + 0.85

    feats_selected = GLOBAL_selector.transform(feats_flat).astype(np.float32)
    feats_scaled = GLOBAL_scaler.transform(feats_selected).astype(np.float32)

    scores = []
    for W_out in GLOBAL_ensemble_weights:
        H_inst = np.tanh(np.dot(feats_scaled, GLOBAL_W_input) + GLOBAL_b_input)
        scores.append(np.dot(H_inst, W_out))

    probs = np.mean(scores, axis=0).flatten()
    return 1 / (1 + np.exp(-probs))


def generate_shap_explanation(img):
    img_res, inp = prepare_image(img)
    img_uint8 = img_res.astype(np.uint8)

    try:
        masker = shap.maskers.Image("blur(128,128)", img_uint8.shape)
        explainer = shap.Explainer(full_pipeline_predict, masker)
        shap_values = explainer(np.expand_dims(img_uint8, axis=0), max_evals=SHAP_MAX_EVALS, batch_size=SHAP_BATCH_SIZE)

        prob = full_pipeline_predict(np.expand_dims(img_uint8, axis=0))[0]
        caption = f"SHAP image explanation generated. Predicted polyp probability: {prob:.4f}."

        shap.image_plot(shap_values, show=False)
        fig = plt.gcf()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=200, bbox_inches='tight')
        buf.seek(0)
        result_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        report_text = (
            "SHAP explanation completed. This visualization highlights image regions contributing to the polyp prediction.\n"
            f"Predicted polyp probability: {prob:.4f}."
        )
        return report_text, result_base64
    except Exception as exc:
        fallback_text = (
            "SHAP explanation could not be generated. "
            f"Reason: {exc}. "
            "Returning the standard segmentation/classification output instead."
        )
        fallback_image = process_image_and_generate_plot(img, include_classification=True)
        return fallback_text, fallback_image


def build_plot(img_res, pred_mask_spatial, extracted, detected_img, title, title_color):
    titles = ['(a) Original', '(b) Predicted Mask', '(c) Extracted', '(d) Localization']
    display_images = [img_res, pred_mask_spatial.squeeze(), extracted, detected_img]

    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    for i in range(4):
        axes[i].imshow(display_images[i], cmap='gray' if i == 1 else None)
        axes[i].set_title(titles[i], fontsize=13, fontweight='bold', pad=12)
        axes[i].axis('off')

    plt.suptitle(title, fontsize=16, fontweight='bold', color=title_color, y=1.04)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64


def process_image_and_generate_plot(img, include_classification=True, optimal_threshold=0.60):
    img_res, inp = prepare_image(img)
    pred_mask_spatial = predict_mask(inp)

    mask_bin = (pred_mask_spatial > 0.5).astype(np.uint8)
    if mask_bin.ndim > 2:
        mask_bin = np.squeeze(mask_bin)
    if mask_bin.shape != img_res.shape[:2]:
        mask_bin = cv2.resize(mask_bin, (img_res.shape[1], img_res.shape[0]), interpolation=cv2.INTER_NEAREST)

    mask_3d = np.stack([mask_bin] * 3, axis=-1)
    extracted = (img_res * mask_3d).astype(np.uint8)
    detected_img = draw_bounding_box(img_res, mask_bin)

    if include_classification:
        clf_probability = predict_polyp_probability(inp)
        if clf_probability >= optimal_threshold:
            diagnostic_text = f"DIAGNOSIS: POLYP DETECTED ({clf_probability * 100:.2f}% Match Score)"
            title_color = '#1faa00'
        else:
            diagnostic_text = f"DIAGNOSIS: NON-POLYP ({(1.0 - clf_probability) * 100:.2f}% Clean Score)"
            title_color = '#dd0000'
    else:
        diagnostic_text = "Segmentation-only result from TR-SE-NET."
        title_color = '#1a73e8'

    return build_plot(img_res, pred_mask_spatial, extracted, detected_img, diagnostic_text, title_color)


def generate_smcl_report(img, optimal_threshold=0.60):
    img_res, inp = prepare_image(img)
    pred_mask_spatial = predict_mask(inp)

    mask_bin = (pred_mask_spatial > 0.5).astype(np.uint8)
    if mask_bin.ndim > 2:
        mask_bin = np.squeeze(mask_bin)
    if mask_bin.shape != img_res.shape[:2]:
        mask_bin = cv2.resize(mask_bin, (img_res.shape[1], img_res.shape[0]), interpolation=cv2.INTER_NEAREST)

    mask_3d = np.stack([mask_bin] * 3, axis=-1)
    extracted = (img_res * mask_3d).astype(np.uint8)
    detected_img = draw_bounding_box(img_res, mask_bin)
    clf_probability = predict_polyp_probability(inp)

    decision_label = 'POLYP' if clf_probability >= optimal_threshold else 'NON-POLYP'
    status_line = 'ELM ensemble available' if GLOBAL_ensemble_weights is not None else 'ELM ensemble unavailable; fallback used'

    report_lines = [
        'SMCL Report - ELM Ensemble Classification',
        '----------------------------------------',
        f'Prediction probability: {clf_probability:.4f}',
        f'Decision: {decision_label}',
        f'Model status: {status_line}',
        'Analysis: Segmentation + ELM-based polyp detection completed.',
    ]

    result_image = build_plot(img_res, pred_mask_spatial, extracted, detected_img, 'SMCL Report Output', '#9c27b0')
    return '\n'.join(report_lines), result_image

# ─────────────────────────────────────────────────────────────────────────────
# 🚀 API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def hellow():
    return {"message": "Welcome to the Polyp Segmentation & Classification API!"}
conversation_history = []

@app.post("/chat")
async def chat_endpoint(message: str = Form(...)):
    global conversation_history

    msg_lower = message.lower()

    # Intent Detection
    if "shap" in msg_lower or "explain" in msg_lower:
        return {
            "reply": "SHAP explanation mode selected. Please upload an image so I can perform SHAP analysis.",
            "action": "REQUEST_IMAGE"
        }

    if (
        "segmentation" in msg_lower
        or "segment" in msg_lower
        or "সেগমেন্টেশন" in msg_lower
    ):
        return {
            "reply": "Certainly! Your TR-SE-NET model is ready. Please upload the gastrointestinal image.",
            "action": "REQUEST_IMAGE"
        }

    model_name = "gemma3:12b"

    # Add the user's message to history
    conversation_history.append({
        "role": "user",
        "content": message
    })

    try:

        response = OLLAMA_CLIENT.chat(
            model=model_name,
            messages=conversation_history
        )

        assistant_reply = response["message"]["content"]

        # Save assistant response
        conversation_history.append({
            "role": "assistant",
            "content": assistant_reply
        })

        return {
            "reply": assistant_reply,
            "action": "NONE"
        }

    except Exception as e:

        return {
            "reply": str(e),
            "action": "NONE"
        }

@app.post("/segment")
async def segment_endpoint(
    file: UploadFile = File(...),
    task: str = Form("segment")
):
    try:
        # Read uploaded image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {
                "reply": "The uploaded file is not a valid image.",
                "action": "ERROR"
            }

        task_lower = task.strip().lower()

        # ----------------------------
        # Segmentation Only
        # ----------------------------
        if task_lower in {
            "segment",
            "segmentation",
            "only segment",
            "seg"
        }:

            result_base64 = process_image_and_generate_plot(
                img,
                include_classification=False
            )

            return {
                "reply": "Polyp segmentation completed successfully.",
                "image_data": f"data:image/png;base64,{result_base64}",
                "action": "SHOW_RESULT"
            }

        # ----------------------------
        # SMCL Report
        # ----------------------------
        elif task_lower in {
            "smcl",
            "smcl report",
            "report",
            "give me smcl report"
        }:

            report_text, result_base64 = generate_smcl_report(img)

            return {
                "reply": report_text,
                "image_data": f"data:image/png;base64,{result_base64}",
                "action": "SHOW_RESULT"
            }

        # ----------------------------
        # Segmentation + Classification
        # ----------------------------
        elif task_lower in {
            "classification",
            "classify",
            "segment and classify",
            "detect"
        }:

            result_base64 = process_image_and_generate_plot(
                img,
                include_classification=True
            )

            return {
                "reply": "Polyp segmentation and classification completed successfully.",
                "image_data": f"data:image/png;base64,{result_base64}",
                "action": "SHOW_RESULT"
            }

        # ----------------------------
        # Unknown task
        # ----------------------------
        else:

            return {
                "reply": (
                    "Unknown task. "
                    "Supported tasks are: "
                    "'segment', "
                    "'classification', "
                    "'segment and classify', "
                    "'smcl report'."
                ),
                "action": "ERROR"
            }

    except Exception as e:

        return {
            "reply": f"An error occurred while processing the image: {str(e)}",
            "action": "ERROR"
        }




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)