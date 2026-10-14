"""ComfyUI nodes for loading MiniMax H3 AV latents from HTTPS URLs."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from safetensors.torch import load_file as _st_load
except ImportError:  # ComfyUI normally provides safetensors.
    _st_load = None

try:
    from .downloader import DownloadError, URLPolicyError, download_cached
except ImportError:  # Allows direct loading by lightweight unit-test runners.
    from downloader import DownloadError, URLPolicyError, download_cached


MAX_TENSOR_ELEMENTS = 2_000_000_000


def _load_streams(path: Path):
    if _st_load is None:
        raise RuntimeError("safetensors is unavailable; cannot load H3 AV latents")
    try:
        data = _st_load(str(path), device="cpu")
    except Exception as exc:
        raise ValueError("downloaded file is not a readable safetensors file") from exc
    if "video" not in data or "audio" not in data:
        raise ValueError("file must contain both video and audio tensors")
    video = data["video"].contiguous().clone()
    audio = data["audio"].contiguous().clone()
    if video.ndim != 5:
        raise ValueError("video tensor must have shape [B, C, T, H, W]")
    if audio.ndim != 4:
        raise ValueError("audio tensor must have shape [B, C, 2, T]")
    if video.shape[0] != audio.shape[0]:
        raise ValueError("video and audio batch sizes do not match")
    if audio.shape[2] != 2:
        raise ValueError("audio tensor must have stereo latent axis of size 2")
    if any(int(size) <= 0 for size in video.shape + audio.shape):
        raise ValueError("video and audio tensors must have positive dimensions")
    if int(video.numel()) > MAX_TENSOR_ELEMENTS or int(audio.numel()) > MAX_TENSOR_ELEMENTS:
        raise ValueError("video or audio tensor is too large")
    if not video.is_floating_point() or not audio.is_floating_point():
        raise ValueError("video and audio tensors must be floating point tensors")
    return {"samples": [video, audio]}


class MiniMaxH3LoadAVLatentFromURL:
    """Download a RunningHub AV safetensors file for Motion Context only."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent_url": ("STRING", {
                    "default": "https://rh-images-tos.xiaoyaoyou.com/",
                    "multiline": True,
                    "tooltip": "Complete HTTPS CDN URL of a MiniMax H3 Save AV Latent file.",
                }),
                "refresh": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Download again instead of using the validated local URL cache.",
                }),
            },
        }

    RETURN_TYPES = ("LATENT", "STRING")
    RETURN_NAMES = ("latent", "local_path")
    FUNCTION = "load"
    CATEGORY = "Bingo Tools/H3"
    DESCRIPTION = (
        "Download a MiniMax H3 AV safetensors file from a complete HTTPS URL "
        "and expose its paired video/audio latent for H3 Motion Context.context_latent."
    )

    @classmethod
    def IS_CHANGED(cls, latent_url, refresh=False):
        if not str(latent_url or "").strip():
            return "empty"
        if refresh:
            return float("NaN")
        try:
            path = download_cached(latent_url)
            return "%s:%d:%d" % (path, path.stat().st_size, path.stat().st_mtime_ns)
        except Exception:
            return float("NaN")

    def load(self, latent_url, refresh=False):
        try:
            path = download_cached(latent_url, refresh=bool(refresh))
        except (URLPolicyError, DownloadError) as exc:
            raise RuntimeError("MiniMax H3 URL latent: %s" % exc) from exc
        latent = _load_streams(path)
        return latent, str(path)


NODE_CLASS_MAPPINGS = {
    "MiniMaxH3LoadAVLatentFromURL": MiniMaxH3LoadAVLatentFromURL,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3LoadAVLatentFromURL": "H3 Motion Context Load Latent from URL",
}
