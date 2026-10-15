import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import downloader


class _Response:
    status = 200

    def __init__(self, data):
        self.data = data
        self.headers = {"Content-Length": str(len(data))}

    def read(self, size):
        if not self.data:
            return b""
        data, self.data = self.data[:size], self.data[size:]
        return data

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class DownloaderTests(unittest.TestCase):
    URL = "https://rh-images-tos.xiaoyaoyou.com/output/clip.safetensors?sig=abc"

    def test_url_policy_preserves_signed_query(self):
        with mock.patch.object(downloader, "_resolve_public"):
            result = downloader.validate_url(self.URL)
        self.assertEqual(result, self.URL)

    def test_url_policy_rejects_unsafe_inputs(self):
        for value in (
            "http://rh-images-tos.xiaoyaoyou.com/a",
            "https://user:pass@rh-images-tos.xiaoyaoyou.com/a",
            "https://rh-images-tos.xiaoyaoyou.com/a#fragment",
            "https://rh-images-tos.xiaoyaoyou.com:8443/a",
        ):
            with self.subTest(value=value):
                with self.assertRaises(downloader.URLPolicyError):
                    with mock.patch.object(downloader, "_resolve_public"):
                        downloader.validate_url(value)

    def test_default_policy_allows_any_public_host(self):
        with mock.patch.object(downloader, "_resolve_public"):
            result = downloader.validate_url(
                "https://cdn.example.com/clip.safetensors?sig=1"
            )
        self.assertEqual(
            result, "https://cdn.example.com/clip.safetensors?sig=1"
        )

    def test_env_restricts_hosts(self):
        with mock.patch.object(downloader, "_resolve_public"):
            with mock.patch.dict(
                "os.environ",
                {"MINIMAX_H3_URL_ALLOWED_HOSTS": "rh-images-tos.xiaoyaoyou.com"},
            ):
                with self.assertRaises(downloader.URLPolicyError):
                    downloader.validate_url(
                        "https://cdn.example.com/clip.safetensors"
                    )

    def test_wildcard_allows_any_public_host(self):
        with mock.patch.object(downloader, "_resolve_public"):
            with mock.patch.dict(
                "os.environ", {"MINIMAX_H3_URL_ALLOWED_HOSTS": "*"}
            ):
                result = downloader.validate_url(
                    "https://cdn.example.com/clip.safetensors?sig=1"
                )
        self.assertEqual(
            result, "https://cdn.example.com/clip.safetensors?sig=1"
        )

    def test_wildcard_allows_public_ip_literal(self):
        with mock.patch.dict(
            "os.environ", {"MINIMAX_H3_URL_ALLOWED_HOSTS": "*"}
        ):
            result = downloader.validate_url(
                "https://8.8.8.8/clip.safetensors"
            )
        self.assertEqual(result, "https://8.8.8.8/clip.safetensors")

    def test_wildcard_still_blocks_private_addresses(self):
        for value in (
            "https://127.0.0.1/clip.safetensors",
            "https://192.168.1.5/clip.safetensors",
            "https://169.254.169.254/latest/meta-data",
        ):
            with self.subTest(value=value):
                with mock.patch.dict(
                    "os.environ", {"MINIMAX_H3_URL_ALLOWED_HOSTS": "*"}
                ):
                    with self.assertRaises(downloader.URLPolicyError):
                        downloader.validate_url(value)

    def test_download_is_atomic_and_cached(self):
        with self.subTest("download"):
            with mock.patch.object(downloader, "_resolve_public"), \
                    mock.patch.object(downloader, "_cache_dir") as cache_dir, \
                    mock.patch.object(downloader, "_request", return_value=_Response(b"latent")) as request:
                with self.create_temp_dir() as temporary:
                    directory = __import__("pathlib").Path(temporary)
                    cache_dir.return_value = directory
                    result, cached = downloader.download_cached(self.URL)
                    self.assertEqual(result.read_bytes(), b"latent")
                    self.assertFalse(cached)
                    self.assertFalse((directory / (result.stem + ".part")).exists())
                    _again, cached_again = downloader.download_cached(self.URL)
                    self.assertTrue(cached_again)
                    request.assert_called_once()

    def test_sanitize_filename(self):
        for raw, expected in (
            ("clip_2.safetensors", "clip_2.safetensors"),
            ("clip_2", "clip_2.safetensors"),
            ("../clip_2.safetensors", "clip_2.safetensors"),
            # basename first drops the directory part, then illegal chars.
            ('sub/dir?clip*2.safetensors', "dirclip2.safetensors"),
            ("  ", ValueError),
            ("", ValueError),
        ):
            with self.subTest(raw=raw):
                if expected is ValueError:
                    with self.assertRaises(ValueError):
                        downloader.sanitize_filename(raw)
                else:
                    self.assertEqual(downloader.sanitize_filename(raw), expected)

    def test_materialize_named(self):
        with mock.patch.object(downloader, "_cache_dir") as cache_dir:
            with self.create_temp_dir() as temporary:
                directory = __import__("pathlib").Path(temporary)
                cache_dir.return_value = directory
                source = directory / "source.safetensors"
                source.write_bytes(b"latent")
                target = downloader.materialize_named(source, "clip_2.safetensors")
                self.assertEqual(target.name, "clip_2.safetensors")
                self.assertEqual(target.read_bytes(), b"latent")
                # Same source again: no error, same target.
                again = downloader.materialize_named(source, "clip_2.safetensors")
                self.assertEqual(again, target)

    def test_cache_dir_env_override(self):
        with self.create_temp_dir() as temporary:
            custom = __import__("pathlib").Path(temporary) / "my_cache"
            with mock.patch.dict(
                "os.environ", {"MINIMAX_H3_URL_CACHE_DIR": str(custom)}
            ):
                self.assertEqual(downloader._cache_dir(), custom)
                self.assertTrue(custom.is_dir())
        with mock.patch.dict(
            "os.environ",
            {"MINIMAX_H3_URL_CACHE_DIR": "", "MINIMAX_H3_RUNNINGHUB_CACHE_DIR": ""},
        ):
            default = downloader._cache_dir()
            self.assertEqual(default.name, "minimax_h3_url")

    def test_legacy_env_names_still_work(self):
        with mock.patch.dict(
            "os.environ",
            {
                "MINIMAX_H3_RUNNINGHUB_ALLOWED_HOSTS": "cdn.example.com",
                "MINIMAX_H3_URL_ALLOWED_HOSTS": "",
                "MINIMAX_H3_RUNNINGHUB_CACHE_DIR": "",
                "MINIMAX_H3_URL_CACHE_DIR": "",
            },
        ):
            self.assertEqual(downloader.allowed_hosts(), ("cdn.example.com",))

    def test_download_reports_uncreatable_cache_dir(self):
        bad = __import__("pathlib").Path(__file__).resolve()  # an existing FILE
        with mock.patch.object(downloader, "_resolve_public"), \
                mock.patch.dict(
                    "os.environ",
                    {"MINIMAX_H3_URL_CACHE_DIR": str(bad)},
                ):
            with self.assertRaises(downloader.DownloadError):
                downloader.download_cached(self.URL)

    def create_temp_dir(self):
        import tempfile
        return tempfile.TemporaryDirectory()


if __name__ == "__main__":
    unittest.main()
