# Bingo Tools

A collection of independent ComfyUI utility nodes. The first tool loads
RunningHub-hosted MiniMax H3 AV latents for H3 Motion Context.

This custom node loads a complete HTTPS URL produced by RunningHub's
**MiniMax H3 Save AV Latent** node and returns the paired video/audio latent
for `H3 Motion Context.context_latent`.

## Installation

Copy this folder into ComfyUI's `custom_nodes` directory, or install it there
as a normal custom node package, then restart ComfyUI.

## Usage

```text
H3 Motion Context Load Latent from URL.latent
    -> H3 Motion Context.context_latent
```

The URL must be the complete direct `.safetensors` URL, including RunningHub's
rewritten filename suffix. The node downloads into ComfyUI's temporary cache,
not the output directory, so RunningHub cannot rename the cache file during the
same execution.

The other `H3 Motion Context.latent` input remains the latent for the clip being
generated. The URL-loaded latent is the previous clip only.

By default only `https://rh-images-tos.xiaoyaoyou.com` is allowed. Additional
hosts can be supplied with `MINIMAX_H3_RUNNINGHUB_ALLOWED_HOSTS`, as a
comma-separated list. The node does not support cookies or authentication
headers. RunningHub must permit outbound HTTPS from the execution container.

The returned latent is a context-only paired latent (`video` plus `audio`), not
a general-purpose single-stream ComfyUI latent. Do not connect it to a stock
VAE decode or sampler input.
