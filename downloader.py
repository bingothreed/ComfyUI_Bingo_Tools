"""Safe, cached HTTPS downloading for H3 latent artifacts."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

DEFAULT_ALLOWED_HOSTS = ("rh-images-tos.xiaoyaoyou.com",)
MAX_DOWNLOAD_BYTES = 4 * 1024 * 1024 * 1024
READ_CHUNK_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 3


class URLPolicyError(ValueError):
    pass


class DownloadError(RuntimeError):
    pass


def allowed_hosts() -> tuple[str, ...]:
    raw = os.environ.get("MINIMAX_H3_RUNNINGHUB_ALLOWED_HOSTS", "")
    configured = tuple(x.strip().lower().rstrip(".") for x in raw.split(",") if x.strip())
    return configured or DEFAULT_ALLOWED_HOSTS


def _host_allowed(host: str, hosts: tuple[str, ...]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == item or host.endswith("." + item) for item in hosts)


def _resolve_public(host: str) -> None:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise URLPolicyError("could not resolve the latent URL host") from exc
    if not addresses:
        raise URLPolicyError("latent URL host has no address")
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise URLPolicyError("latent URL resolved to an invalid address") from exc
        if (address.is_private or address.is_loopback or address.is_link_local
                or address.is_reserved or address.is_multicast or address.is_unspecified):
            raise URLPolicyError("latent URL resolves to a non-public address")


def validate_url(url: str, hosts: tuple[str, ...] | None = None) -> str:
    if not isinstance(url, str) or not url.strip():
        raise URLPolicyError("latent URL is empty")
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme.lower() != "https":
        raise URLPolicyError("latent URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise URLPolicyError("latent URL must not contain credentials")
    if parsed.fragment:
        raise URLPolicyError("latent URL must not contain a fragment")
    if not parsed.hostname:
        raise URLPolicyError("latent URL has no hostname")
    if parsed.port not in (None, 443):
        raise URLPolicyError("latent URL must use the default HTTPS port")
    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise URLPolicyError("latent URL hostname is invalid") from exc
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise URLPolicyError("latent URL must use an allowlisted hostname")
    hosts = hosts or allowed_hosts()
    if not _host_allowed(host, hosts):
        raise URLPolicyError("latent URL hostname is not allowlisted")
    _resolve_public(host)
    # Keep the query exactly as supplied: RunningHub URLs may be signed.
    return urllib.parse.urlunsplit(("https", host, parsed.path, parsed.query, ""))


def _cache_dir() -> Path:
    try:
        import folder_paths
        root = Path(folder_paths.get_temp_directory())
    except (ImportError, AttributeError):
        root = Path(tempfile.gettempdir())
    target = root / "minimax_h3_runninghub"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _request(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "ComfyUI-MiniMax-H3-RunningHub/0.1"})
    return _OPENER.open(request, timeout=60)


def _download_once(url: str, max_bytes: int):
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        try:
            response = _request(current)
        except urllib.error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                raise DownloadError("latent URL returned HTTP %s" % exc.code) from exc
            location = exc.headers.get("Location")
            if not location:
                raise DownloadError("latent URL redirect has no destination")
            current = validate_url(urllib.parse.urljoin(current, location))
            continue
        if 300 <= getattr(response, "status", 200) < 400:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise DownloadError("latent URL redirect has no destination")
            current = validate_url(urllib.parse.urljoin(current, location))
            continue
        return response
    raise DownloadError("latent URL redirected too many times")


def download_cached(url: str, *, refresh: bool = False, max_bytes: int = MAX_DOWNLOAD_BYTES) -> Path:
    current = validate_url(url)
    key = hashlib.sha256(current.encode("utf-8")).hexdigest()
    directory = _cache_dir()
    destination = directory / (key + ".safetensors")
    if destination.is_file() and not refresh:
        return destination

    part = directory / (key + ".part")
    try:
        with _download_once(current, max_bytes) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                raise DownloadError("latent URL returned HTTP %s" % status)
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise DownloadError("latent download exceeds the size limit")
            total = 0
            with part.open("wb") as output:
                while True:
                    block = response.read(READ_CHUNK_BYTES)
                    if not block:
                        break
                    total += len(block)
                    if total > max_bytes:
                        raise DownloadError("latent download exceeds the size limit")
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
        if total == 0:
            raise DownloadError("latent download was empty")
        os.replace(part, destination)
        return destination
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise DownloadError("could not download the latent URL") from exc
    finally:
        try:
            part.unlink()
        except FileNotFoundError:
            pass
