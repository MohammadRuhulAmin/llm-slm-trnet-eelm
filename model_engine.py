import os
import sys
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers
import cv2

physical_devices = tf.config.list_physical_devices('GPU')
if physical_devices:
    try:
        tf.config.experimental.set_memory_growth(physical_devices[0], True)
        print(f"✅ GPU Active: {physical_devices[0]}", file=sys.stderr)
    except RuntimeError as e:
        print(e, file=sys.stderr)
else:
    print("GPU did not found", file=sys.stderr)


@tf.keras.utils.register_keras_serializable()
class KerasPCCLayer(layers.Layer):
    def call(self, inputs):
        epsilon = 1e-8
        mean = tf.reduce_mean(inputs, axis=-1, keepdims=True)
        std = tf.math.reduce_std(inputs, axis=-1, keepdims=True) + epsilon
        norm_inputs = (inputs - mean) / std
        pcc_matrix = tf.matmul(tf.expand_dims(norm_inputs, -1), tf.expand_dims(norm_inputs, 1))
        return layers.Flatten()(pcc_matrix)

def tnr_metric(y_true, y_pred):
    return tf.constant(1.0)

def f2_segmentation(y_true, y_pred):
    return tf.constant(1.0)

CUSTOM_OBJECTS = {
    "KerasPCCLayer": KerasPCCLayer,
    "Custom>tnr_metric": tnr_metric,
    "Custom>f2_segmentation": f2_segmentation,
}

MODEL_PATH = "/mnt/c/development/Thesis/PolypSegmentationBasedClassification/models/SC/tr-elm/thesis_v3_sequential_v_eval_data_driven_v2.keras"


class SegmentationEngine:
    def __init__(self, model_path: str, img_size: int = 256):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model path not found: {model_path}")
        full_model = tf.keras.models.load_model(
            model_path, custom_objects=CUSTOM_OBJECTS, compile=False,
        )
        self.model = tf.keras.models.Model(inputs=full_model.input, outputs=full_model.outputs[0])
        self.img_size = img_size
        dummy = np.zeros((1, img_size, img_size, 3), dtype=np.float32)
        self.model.predict(dummy, verbose=0)
        print("✅ Model has been loaded an wormedup successfully", file=sys.stderr)

    def predict(self, image_bytes: bytes) -> bytes:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image")

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_res = cv2.resize(img_rgb, (self.img_size, self.img_size))
        inp = np.expand_dims(img_res / 255.0, axis=0).astype(np.float32)

        pred = self.model.predict(inp, verbose=0)[0]
        pred_spatial = pred[:, :, 0] if pred.ndim == 3 else pred
        pred_bin = (pred_spatial > 0.5).astype(np.uint8) * 255

        overlay = img_res.copy()
        green_mask = np.zeros_like(img_res)
        green_mask[:, :, 1] = pred_bin
        cv2.addWeighted(green_mask, 0.4, overlay, 1.0, 0, overlay)

        overlay_bgr = cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode(".png", overlay_bgr)
        if not ok:
            raise RuntimeError("Failed to display output image")
        return buf.tobytes()