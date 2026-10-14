# Bingo Tools

[English](README.md) | [中文](README_ZH.md)

一组独立的 ComfyUI 工具节点。第一个工具为 H3 Motion Context 加载
RunningHub 托管的 MiniMax H3 音视频（AV）潜空间文件。

该节点加载 RunningHub 的 **MiniMax H3 Save AV Latent** 节点产出的完整
HTTPS URL，返回配对的视频/音频 latent，用于
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

- **latent_url** — 完整的 `.safetensors` 直链 URL（保留 RunningHub 的
  签名 query）。
- **refresh** — 强制重新下载，而不是复用 URL 缓存。
- **filename** — 下载文件的可选显示名，如 `clip_00002.safetensors`。
  留空则使用哈希命名的缓存文件。名称会被消毒并存放于下载缓存目录内
  （优先硬链接，不占额外磁盘）。
- **vae / audio_vae**（可选）— 把同一份文件解码为画面/音频，用于
  独立验证或 Video Merge 拼接。

输出：

- **latent** — 配对的视频/音频 latent，用于 `context_latent`；
  加载失败时为 `None`。
- **local_path** — 下载文件的绝对路径：设置了 `filename` 时为命名副本，
  否则为哈希命名的缓存文件。失败时为空。
- **status** — 成功时为 `ok:cached` / `ok:downloaded`；失败时为
  `error:url: ...`、`error:download: ...` 或 `error:file: ...` 并附原因。
  解码问题以 `decode:image:` / `decode:audio:` 注记追加。节点不会中断
  整个图；若缺少 latent 会导致下游出错，请用此输出做门控。
- **images** — 下载片段的解码帧（仅当连接了 `vae`），否则为 `None`。
- **audio** — 下载片段的解码音轨（仅当连接了 `audio_vae`），否则为
  `None`。

URL 必须是完整的 `.safetensors` 直链，包括 RunningHub 改写后的文件名
后缀。

另一个 `H3 Motion Context.latent` 输入仍然接"正在生成的片段"的 latent；
URL 加载的 latent 只代表上一段。

返回的 latent 是仅供上下文使用的配对 latent（`video` + `audio`），不是
通用的单流 ComfyUI latent。不要把它接到原生 VAE 解码或采样器输入上。

## 配置

默认只允许 `https://rh-images-tos.xiaoyaoyou.com`。其他主机可通过
`MINIMAX_H3_RUNNINGHUB_ALLOWED_HOSTS` 以逗号分隔列表提供。节点不支持
cookie 或认证头。RunningHub 必须允许执行容器出站 HTTPS。

下载缓存位于 `<ComfyUI>/temp/minimax_h3_runninghub/`（脱离 ComfyUI 运行时
为系统临时目录）。ComfyUI 重启时会清空 temp 目录，因此如需让 latent
跨重启保留，请把 `MINIMAX_H3_RUNNINGHUB_CACHE_DIR` 指向一个持久位置，例如：

```text
MINIMAX_H3_RUNNINGHUB_CACHE_DIR=F:\ComfyUI-Datasets\output\h3_context
```
