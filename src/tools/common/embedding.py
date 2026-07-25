from __future__ import annotations

import logging
import os
import urllib.request
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# 接続先はここに固定値として持つ（huggingface-hubは使わず urllib で直接取得する）。
_MODEL_BASE_URL = (
    "https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/resolve/main"
)
_MODEL_FILES = {
    "model.onnx": f"{_MODEL_BASE_URL}/onnx/model_quantized.onnx",
    "tokenizer.json": f"{_MODEL_BASE_URL}/tokenizer.json",
}

DEFAULT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


class ModelDownloadError(RuntimeError):
    """Raised when the embedding model can't be downloaded."""


def _model_cache_dir(model_name: str) -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "tools" / "models" / model_name


def ensure_model(model_name: str = DEFAULT_MODEL_NAME) -> Path:
    """Download the embedding model (ONNX + tokenizer.json) if not already cached.

    Downloads from Hugging Face (`huggingface.co`) via `urllib`, not the
    `huggingface-hub` client library, so the connection target is a plain
    constant in this module rather than resolved by a third-party library.
    """
    if model_name != DEFAULT_MODEL_NAME:
        raise ModelDownloadError(
            f"未対応のモデル名です: {model_name}（対応済み: {DEFAULT_MODEL_NAME}）"
        )

    cache_dir = _model_cache_dir(model_name)
    cache_dir.mkdir(parents=True, exist_ok=True)

    for filename, url in _MODEL_FILES.items():
        dest = cache_dir / filename
        if dest.exists():
            continue
        logger.info("埋め込みモデルをダウンロードします: %s -> %s", url, dest)
        try:
            urllib.request.urlretrieve(url, dest)
        except OSError as exc:
            raise ModelDownloadError(
                f"モデルのダウンロードに失敗しました: {url}"
            ) from exc
        size_mb = dest.stat().st_size / (1024 * 1024)
        logger.info("ダウンロード完了: %s (%.1f MB)", dest, size_mb)

    return cache_dir


def embed_sentences(
    sentences: list[str], model_name: str = DEFAULT_MODEL_NAME
) -> NDArray[np.float64]:
    """Embed sentences with mean pooling + L2 normalization. Returns (n, dim) float64 array."""
    import onnxruntime as ort  # 遅延インポート: --similar 指定時のみ読み込む
    from tokenizers import Tokenizer

    cache_dir = ensure_model(model_name)
    tokenizer = Tokenizer.from_file(str(cache_dir / "tokenizer.json"))
    tokenizer.enable_padding()
    session = ort.InferenceSession(
        str(cache_dir / "model.onnx"), providers=["CPUExecutionProvider"]
    )

    encodings = tokenizer.encode_batch(sentences)
    input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    token_type_ids = np.zeros_like(input_ids)

    outputs = session.run(
        None,
        {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        },
    )
    last_hidden = outputs[0]

    mask = attention_mask[:, :, None].astype(np.float64)
    summed = (last_hidden * mask).sum(axis=1)
    counts = mask.sum(axis=1)
    pooled = summed / counts

    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    normalized: NDArray[np.float64] = pooled / norms
    return normalized
