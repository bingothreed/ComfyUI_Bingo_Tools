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
            "https://evilrh-images-tos.xiaoyaoyou.com/a",
            "https://127.0.0.1/a",
        ):
            with self.subTest(value=value):
                with self.assertRaises(downloader.URLPolicyError):
                    with mock.patch.object(downloader, "_resolve_public"):
                        downloader.validate_url(value)

    def test_download_is_atomic_and_cached(self):
        with self.subTest("download"):
            with mock.patch.object(downloader, "_resolve_public"), \
                    mock.patch.object(downloader, "_cache_dir") as cache_dir, \
                    mock.patch.object(downloader, "_request", return_value=_Response(b"latent")) as request:
                with self.create_temp_dir() as temporary:
                    directory = __import__("pathlib").Path(temporary)
                    cache_dir.return_value = directory
                    result = downloader.download_cached(self.URL)
                    self.assertEqual(result.read_bytes(), b"latent")
                    self.assertFalse((directory / (result.stem + ".part")).exists())
                    downloader.download_cached(self.URL)
                    request.assert_called_once()

    def create_temp_dir(self):
        import tempfile
        return tempfile.TemporaryDirectory()


if __name__ == "__main__":
    unittest.main()
