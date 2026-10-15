"""ComfyUI nodes for loading MiniMax H3 AV latents from HTTPS URLs."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from safetensors.torch import load_file as _st_load
except ImportError:  # ComfyUI normally provides safetensors.
    _st_load = None

try:
    import torch
except ImportError:  # Lightweight unit-test runners may not have torch.
    torch = None

try:
    from .downloader import (
        DownloadError,
        URLPolicyError,
        download_cached,
        materialize_named,
        named_output_path,
    )
except ImportError:  # Allows direct loading by lightweight unit-test runners.
    from downloader import (
        DownloadError,
        URLPolicyError,
        download_cached,
        materialize_named,
        named_output_path,
    )


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
    """Download a MiniMax H3 AV safetensors file for Motion Context only.

    Soft-fails: download or parse problems are reported through the
    ``status`` output ("error:...") instead of aborting the graph, with
    ``latent`` set to None and ``local_path`` empty (or pointing at the
    downloaded file when it exists but failed to parse).

    With ``filename`` set, the downloaded file is also exposed under that
    sanitized name inside the cache directory (hardlink, no extra disk)
    and ``local_path`` points at the named copy.

    Optional ``vae`` / ``audio_vae`` inputs additionally decode the
    downloaded clip to ``images`` / ``audio`` outputs for standalone
    verification or a Video Merge. Decode failures are appended to
    ``status`` and leave that output None.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent_url": ("STRING", {
                    "default": "https://rh-images-tos.xiaoyaoyou.com/",
                    "multiline": True,
                    "tooltip": "Complete direct HTTPS URL of a MiniMax H3 Save AV Latent file.",
                }),
                "refresh": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Download again instead of using the validated local URL cache.",
                }),
                "filename": ("STRING", {
                    "default": "",
                    "tooltip": "Optional name for the downloaded file, e.g. clip_00002.safetensors "
                               "or video/clip_00002.safetensors. Empty keeps the hash-named cache "
                               "file. The name is sanitized and stored inside ComfyUI's output "
                               "directory; local_path points at it.",
                }),
            },
            "optional": {
                "vae": ("VAE", {
                    "tooltip": "Optional video VAE. When connected, decodes and "
                               "outputs the downloaded clip's frames as IMAGE.",
                }),
                "audio_vae": ("VAE", {
                    "tooltip": "Optional audio VAE. When connected, decodes and "
                               "outputs the downloaded clip's soundtrack as AUDIO.",
                }),
            },
        }

    RETURN_TYPES = ("LATENT", "STRING", "STRING", "IMAGE", "AUDIO")
    RETURN_NAMES = ("latent", "local_path", "status", "images", "audio")
    OUTPUT_TOOLTIPS = (
        "The downloaded paired video/audio latent for context_latent, "
        "or None when the download or parse failed.",
        "Absolute path of the cached safetensors file, or empty on failure.",
        "ok:cached / ok:downloaded on success; error:<category>: <reason> "
        "on failure (category: url, download or file). Decode problems are "
        "appended as decode:image: / decode:audio: notes.",
        "Decoded frames of the downloaded clip (only when vae is connected), or None.",
        "Decoded soundtrack of the downloaded clip (only when audio_vae is connected), or None.",
    )
    FUNCTION = "load"
    CATEGORY = "Bingo Tools/H3"
    DESCRIPTION = (
        "Download a MiniMax H3 AV safetensors file from a complete HTTPS URL "
        "and expose its paired video/audio latent for H3 Motion Context.context_latent. "
        "Optional VAEs decode the same file to images/audio for verification. "
        "Failures are returned as an error status instead of aborting the graph."
    )

    @classmethod
    def IS_CHANGED(cls, latent_url, refresh=False, filename="", vae=None, audio_vae=None):
        if not str(latent_url or "").strip():
            return "empty"
        if refresh:
            return float("NaN")
        try:
            path, _cached = download_cached(latent_url)
            name = str(filename or "").strip()
            if name:
                named = named_output_path(name)
                if not named.is_file():
                    # The named copy does not exist yet: force execution so
                    # load() materializes it instead of serving a stale cache.
                    return float("NaN")
                path = named
            extra = ""
            if vae is not None or audio_vae is not None:
                # Decode outputs depend on which VAE objects are wired.
                extra = "|vae:%s|audio_vae:%s" % (id(vae), id(audio_vae))
            return "%s|%s:%d:%d%s" % (
                name, path, path.stat().st_size, path.stat().st_mtime_ns, extra
            )
        except Exception:
            return float("NaN")

    @staticmethod
    def _decode_av(latent, vae=None, audio_vae=None):
        """Best-effort decode of a parsed AV latent; returns (images, audio, notes)."""
        video, audio = latent["samples"]
        notes = []

        images = None
        if vae is not None:
            try:
                v_in = video if video.ndim == 5 else video.unsqueeze(0)
                images = vae.decode(v_in)
                if images is not None and images.ndim == 5:
                    images = images.reshape(
                        -1, images.shape[-3], images.shape[-2], images.shape[-1]
                    )
            except Exception as exc:
                notes.append("decode:image: %s" % exc)

        audio_out = None
        if audio_vae is not None:
            try:
                if torch is None:
                    raise RuntimeError("torch is unavailable")
                a_in = audio if audio.ndim == 4 else audio.unsqueeze(0)
                raw = audio_vae.decode(a_in).movedim(-1, 1)
                # Mirror H3's native audio decode normalization.
                std = torch.std(raw, dim=[1, 2], keepdim=True) * 5.0
                std[std < 1.0] = 1.0
                raw = raw / std
                sr = int(
                    getattr(
                        audio_vae,
                        "audio_sample_rate_output",
                        getattr(audio_vae, "audio_sample_rate", 32000),
                    )
                )
                audio_out = {"waveform": raw, "sample_rate": sr}
            except Exception as exc:
                notes.append("decode:audio: %s" % exc)
        return images, audio_out, notes

    def load(self, latent_url, refresh=False, filename="", vae=None, audio_vae=None):
        if not str(latent_url or "").strip():
            return (None, "", "error:url: latent URL is empty", None, None)
        try:
            path, cached = download_cached(latent_url, refresh=bool(refresh))
        except URLPolicyError as exc:
            return (None, "", "error:url: %s" % exc, None, None)
        except DownloadError as exc:
            return (None, "", "error:download: %s" % exc, None, None)
        try:
            if str(filename or "").strip():
                path = materialize_named(path, filename)
        except (ValueError, OSError) as exc:
            return (None, str(path), "error:file: %s" % exc, None, None)
        try:
            latent = _load_streams(path)
        except Exception as exc:
            # The file is on disk; keep its path so the caller can inspect it.
            return (None, str(path), "error:file: %s" % exc, None, None)
        images, audio, notes = self._decode_av(latent, vae=vae, audio_vae=audio_vae)
        status = "ok:cached" if cached else "ok:downloaded"
        if notes:
            status += "; " + "; ".join(notes)
        return (latent, str(path), status, images, audio)


NODE_CLASS_MAPPINGS = {
    "MiniMaxH3LoadAVLatentFromURL": MiniMaxH3LoadAVLatentFromURL,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3LoadAVLatentFromURL": "H3 Motion Context Load Latent from URL",
}
