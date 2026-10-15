# Bingo Tools

[English](README.md) | [中文](README_ZH.md)

A collection of independent ComfyUI utility nodes. The first tool loads
MiniMax H3 AV latents from a direct HTTPS URL for H3 Motion Context.

This custom node downloads a complete HTTPS URL pointing to a MiniMax H3 AV
latent file — typically one produced by the **MiniMax H3 Save AV Latent**
node, but any direct file URL works — and returns the paired video/audio
latent for `H3 Motion Context.context_latent`. It works on RunningHub and
local ComfyUI alike.

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
  `clip_00002.safetensors`. Empty keeps the hash-named cache file. The name
  is sanitized and stored inside the download cache directory (hardlinked,
  no extra disk space).
- **vae / audio_vae** (optional) — decode the same file to images/audio for
  standalone verification or a Video Merge.

Outputs:

- **latent** — the paired video/audio latent for `context_latent`, or `None`
  when the load failed.
- **local_path** — absolute path of the downloaded file: the named copy when
  `filename` is set, otherwise the hash-named cache file. Empty on failure.
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

## Configuration

The node accepts any direct HTTPS URL (GitHub raw, Hugging Face, R2/S3
presigned URLs, ...). By default the host allowlist contains only
`rh-images-tos.xiaoyaoyou.com`, the host that usually serves H3 latents;
add more hosts with `MINIMAX_H3_URL_ALLOWED_HOSTS` (comma-separated),
or set it to `*` to accept any host. Every URL must still use HTTPS and
resolve to a public address (localhost/private-network URLs stay blocked).
The node does not support cookies or authentication headers, so use public
direct file hosts. The ComfyUI host or execution container must permit
outbound HTTPS. The older `MINIMAX_H3_RUNNINGHUB_*` variable names still
work.

Note: OneDrive/Google Drive share links are HTML pages, not the file itself —
use a direct download URL. Google Drive adds a virus-scan confirmation page
for files over ~100 MB, which this node does not handle; prefer direct file
hosts (GitHub Releases, Hugging Face, R2/S3 presigned URLs) for latents.

Downloads are cached in `<ComfyUI>/temp/minimax_h3_url/` (system temp
directory outside ComfyUI). ComfyUI wipes its temp folder on restart, so
point `MINIMAX_H3_URL_CACHE_DIR` at a persistent location to keep
latents across restarts, e.g.:

```text
MINIMAX_H3_URL_CACHE_DIR=F:\ComfyUI-Datasets\output\h3_context
```
