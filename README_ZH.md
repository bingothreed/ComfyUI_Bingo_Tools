# Bingo Tools

[English](README.md) | [中文](README_ZH.md)

一组独立的 ComfyUI 工具节点。第一个工具为 H3 Motion Context 从直链
HTTPS URL 加载 MiniMax H3 音视频（AV）潜空间文件。

该节点下载指向 MiniMax H3 AV latent 文件的完整 HTTPS 直链——通常是
**MiniMax H3 Save AV Latent** 节点产出的文件，但任何直链文件 URL 都
可以——返回配对的视频/音频 latent，用于
`H3 Motion Context.context_latent`。

## 截图

![ComfyUI 中的 H3 Motion Context Load Latent from URL 节点](images/H3%20Motion%20Context%20Load%20Latent%20from%20URL.png)

节点从 URL 下载 latent，用 MiniMax H3 的视频/音频 VAE（可选输入）解码，
并在 ComfyUI 内直接预览画面——整个验证流程不出 ComfyUI。

## 安装

把本文件夹复制到 ComfyUI 的 `custom_nodes` 目录下，或作为普通自定义节点
包安装，然后重启 ComfyUI。

## 用法

```text
H3 Motion Context Load Latent from URL.latent
    -> H3 Motion Context.context_latent
H3 Motion Context Load Latent from URL.local_path
    ->（可选）MiniMax H3 Load AV Latent.latent_path，
       用于顺带解码上一段的画面/音频给 Video Merge 拼接
H3 Motion Context Load Latent from URL.status
    ->（可选）接字符串判断节点，成功时才继续下游工作
```

输入：

- **latent_url** — 完整的 `.safetensors` 直链 URL（query 参数原样保留，
  包括签名 query）。
- **refresh** — 强制重新下载，而不是复用 URL 缓存。
- **filename** — 下载文件的可选显示名，如 `clip_00002.safetensors`；
  支持子目录，如 `video/clip_00002.safetensors`。留空则使用哈希命名的
  缓存文件。
- **save_to_temp** — 命名副本的存放位置：开（默认）留在下载缓存
  （ComfyUI 的 temp 目录）；关则存到 ComfyUI 的 output 目录。从下载
  缓存硬链接，不占额外磁盘。
- **vae / audio_vae**（可选）— 把同一份文件解码为画面/音频，用于
  独立验证或 Video Merge 拼接。

输出：

- **latent** — 配对的视频/音频 latent，用于 `context_latent`；
  加载失败时为 `None`。
- **local_path** — 下载文件的绝对路径：设置了 `filename` 时为命名副本
  （默认在下载缓存，`save_to_temp` 关闭时在 ComfyUI output 目录），
  否则为哈希命名的缓存文件。失败时为空。
- **status** — 成功时为 `ok:cached` / `ok:downloaded`；失败时为
  `error:url: ...`、`error:download: ...` 或 `error:file: ...` 并附原因。
  解码问题以 `decode:image:` / `decode:audio:` 注记追加。节点不会中断
  整个图；若缺少 latent 会导致下游出错，请用此输出做门控。
- **images** — 下载片段的解码帧（仅当连接了 `vae`），否则为 `None`。
- **audio** — 下载片段的解码音轨（仅当连接了 `audio_vae`），否则为
  `None`。

URL 必须是完整的 `.safetensors` 直链——是文件本身，而不是渲染网页的
分享页（见"配置"一节）。

另一个 `H3 Motion Context.latent` 输入仍然接"正在生成的片段"的 latent；
URL 加载的 latent 只代表上一段。

返回的 latent 是仅供上下文使用的配对 latent（`video` + `audio`），不是
通用的单流 ComfyUI latent。不要把它接到原生 VAE 解码或采样器输入上。

## 下载链接

URL 必须是文件直链，不是渲染网页的分享页：用 GitHub 的 `raw` 链接、
Hugging Face 的 resolve 链接、R2/S3 预签名下载链接等。OneDrive /
Google Drive 的分享链接是网页——Google Drive 对超过约 100 MB 的文件
还会插入病毒扫描确认页，本节点不处理该情况。文件必须是公开的：节点
不会携带 cookie 或认证头。
