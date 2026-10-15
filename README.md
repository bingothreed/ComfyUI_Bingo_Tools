# Bingo Tools

[English](README.md) | [中文](README_ZH.md)

A collection of independent ComfyUI utility nodes. The first tool loads
MiniMax H3 AV latents from a direct HTTPS URL for H3 Motion Context.

This custom node downloads a complete HTTPS URL pointing to a MiniMax H3 AV
latent file — typically one produced by the **MiniMax H3 Save AV Latent**
node, but any direct file URL works — and returns the paired video/audio
latent for `H3 Motion Context.context_latent`.

## Screenshot

![H3 Motion Context Load Latent from URL in ComfyUI](images/H3%20Motion%20Context%20Load%20Latent%20from%20URL.png)

The node downloads the latent from the URL, decodes it with the MiniMax H3
video/audio VAEs (optional inputs), and previews the frames — the whole
verify loop stays inside ComfyUI.

## Installation

Copy this folder into ComfyUI's `custom_nodes` directory, or install it there
as a normal custom node package, then restart ComfyUI.

## Usage

```text
H3 Motion Context Load Latent from URL.latent
    -> H3 Motion Context.context_latent
H3 Motion Context Load Latent from URL.local_path
    -> (optional) MiniMax H3 Load AV Latent.latent_path, to also decode
       the previous clip's frames/audio for a Video Merge
H3 Motion Context Load Latent from URL.status
    -> (optional) a switch/if node to gate downstream work on success
```

Inputs:

- **latent_url** — complete direct `.safetensors` URL (query strings, e.g.
  signed ones, are preserved).
- **refresh** — force a re-download instead of reusing the URL cache.
- **filename** — optional display name for the downloaded file, e.g.
  `clip_00002.safetensors`; subdirectories like
  `video/clip_00002.safetensors` are allowed. Empty keeps the hash-named
  cache file.
- **save_to_temp** — where the named copy goes: on (default) keeps it in
  the download cache (ComfyUI's temp folder); off stores it in ComfyUI's
  output directory. Hardlinked from the download cache, so no extra disk
  space.
- **vae / audio_vae** (optional) — decode the same file to images/audio for
  standalone verification or a Video Merge.

Outputs:

- **latent** — the paired video/audio latent for `context_latent`, or `None`
  when the load failed.
- **local_path** — absolute path of the downloaded file: the named copy when
  `filename` is set (download cache by default, ComfyUI's output directory
  with `save_to_temp` off), otherwise the hash-named cache file. Empty on
  failure.
- **status** — `ok:cached` / `ok:downloaded` on success; on failure
  `error:url: ...`, `error:download: ...` or `error:file: ...` with the
  reason. Decode problems are appended as `decode:image:` / `decode:audio:`
  notes. The node does not abort the graph; gate downstream nodes on this
  output if a missing latent would otherwise break the workflow.
- **images** — decoded frames of the downloaded clip (only when `vae` is
  connected), or `None`.
- **audio** — decoded soundtrack of the downloaded clip (only when
  `audio_vae` is connected), or `None`.

The URL must be the complete direct `.safetensors` URL — a raw file URL, not
a share page that renders HTML (see Configuration).

The other `H3 Motion Context.latent` input remains the latent for the clip being
generated. The URL-loaded latent is the previous clip only.

The returned latent is a context-only paired latent (`video` plus `audio`), not
a general-purpose single-stream ComfyUI latent. Do not connect it to a stock
VAE decode or sampler input.

## Download URLs

The URL must be a direct file link, not a share page that renders HTML:
use GitHub `raw` links, Hugging Face resolve URLs, R2/S3 presigned download
links, etc. OneDrive/Google Drive share links are HTML pages — Google Drive
also adds a virus-scan confirmation page for files over ~100 MB, which the
node does not handle. The file must be public: the node does not send
cookies or authentication headers.
