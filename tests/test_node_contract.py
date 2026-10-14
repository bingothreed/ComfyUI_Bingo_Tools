import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class NodeContractTests(unittest.TestCase):
    def test_mapping_has_url_loader(self):
        from nodes import (
            MiniMaxH3LoadAVLatentFromURL,
            NODE_CLASS_MAPPINGS,
            NODE_DISPLAY_NAME_MAPPINGS,
        )

        self.assertIs(NODE_CLASS_MAPPINGS["MiniMaxH3LoadAVLatentFromURL"], MiniMaxH3LoadAVLatentFromURL)
        self.assertEqual(
            NODE_DISPLAY_NAME_MAPPINGS["MiniMaxH3LoadAVLatentFromURL"],
            "H3 Motion Context Load Latent from URL",
        )
        self.assertEqual(
            MiniMaxH3LoadAVLatentFromURL.RETURN_TYPES,
            ("LATENT", "STRING", "STRING", "IMAGE", "AUDIO"),
        )
        self.assertEqual(
            MiniMaxH3LoadAVLatentFromURL.RETURN_NAMES,
            ("latent", "local_path", "status", "images", "audio"),
        )

    def test_load_soft_fails_with_status(self):
        from nodes import MiniMaxH3LoadAVLatentFromURL

        latent, path, status, images, audio = MiniMaxH3LoadAVLatentFromURL().load("")
        self.assertIsNone(latent)
        self.assertEqual(path, "")
        self.assertTrue(status.startswith("error:url:"))
        self.assertIsNone(images)
        self.assertIsNone(audio)

    def test_load_with_filename_materializes_named_path(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        import nodes

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "hash.safetensors"
            source.write_bytes(b"x")  # load() never parses it: download mocked
            named = Path(temporary) / "clip_00002.safetensors"
            with mock.patch.object(
                nodes, "download_cached", return_value=(source, True)
            ), mock.patch.object(
                nodes, "materialize_named", return_value=named
            ) as materialize, mock.patch.object(
                nodes, "_load_streams", return_value={"samples": ["video", "audio"]}
            ):
                latent, path, status, images, audio = nodes.MiniMaxH3LoadAVLatentFromURL().load(
                    "https://example.invalid/a.safetensors", filename="clip_00002"
                )
            materialize.assert_called_once_with(source, "clip_00002")
            self.assertEqual(path, str(named))
            self.assertEqual(status, "ok:cached")
            self.assertEqual(latent, {"samples": ["video", "audio"]})
            self.assertIsNone(images)
            self.assertIsNone(audio)

    def test_load_with_vae_decodes_images(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        import nodes

        class FakeImages:
            ndim = 5
            shape = (1, 2, 4, 4, 3)

            def reshape(self, *dims):
                return self

        class FakeVideo:
            ndim = 5
            shape = (1, 16, 2, 4, 4)

        class FakeVAE:
            def __init__(self, result):
                self.result = result
                self.calls = []

            def decode(self, latent):
                self.calls.append(latent)
                return self.result

        marker = FakeImages()

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "hash.safetensors"
            source.write_bytes(b"x")
            vae = FakeVAE(marker)
            with mock.patch.object(
                nodes, "download_cached", return_value=(source, True)
            ), mock.patch.object(
                nodes, "_load_streams",
                return_value={"samples": [FakeVideo(), "audio"]},
            ):
                latent, path, status, images, audio = nodes.MiniMaxH3LoadAVLatentFromURL().load(
                    "https://example.invalid/a.safetensors", vae=vae
                )
            self.assertIs(images, marker)
            self.assertIsNone(audio)
            self.assertEqual(status, "ok:cached")
            self.assertEqual(vae.calls, [latent["samples"][0]])

    def test_load_audio_decode_failure_reported_in_status(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        import nodes

        class FakeAudioLatent:
            ndim = 4

        class FakeAudioVAE:
            def decode(self, latent):
                raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "hash.safetensors"
            source.write_bytes(b"x")
            with mock.patch.object(
                nodes, "download_cached", return_value=(source, True)
            ), mock.patch.object(
                nodes, "_load_streams",
                return_value={"samples": ["video", FakeAudioLatent()]},
            ), mock.patch.object(
                nodes, "torch", object()  # pass the torch-availability guard
            ):
                _latent, _path, status, images, audio = nodes.MiniMaxH3LoadAVLatentFromURL().load(
                    "https://example.invalid/a.safetensors", audio_vae=FakeAudioVAE()
                )
            self.assertIsNone(images)
            self.assertIsNone(audio)
            self.assertTrue(status.startswith("ok:cached; decode:audio: boom"))

    def test_load_audio_decode_happy_path(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        import numpy as np

        import nodes

        class Arr:
            def __init__(self, data):
                self.data = np.asarray(data)

            @property
            def ndim(self):
                return self.data.ndim

            @property
            def shape(self):
                return self.data.shape

            def movedim(self, a, b):
                return Arr(np.moveaxis(self.data, a, b))

            def __truediv__(self, other):
                if isinstance(other, Arr):
                    other = other.data
                return Arr(self.data / other)

        class FakeTorch:
            @staticmethod
            def std(tensor, dim, keepdim):
                # numpy wants axis as a tuple (torch accepts a list).
                return np.std(tensor.data, axis=tuple(dim), keepdims=keepdim)

        class FakeAudioVAE:
            audio_sample_rate_output = 32000

            def __init__(self, result):
                self.result = result

            def decode(self, latent):
                self.calls = getattr(self, "calls", []) + [latent]
                return self.result

        audio_latent = Arr(np.ones((1, 16, 2, 8)))
        # decode returns [B, T, C]; movedim(-1, 1) -> [B, C, T]
        vae = FakeAudioVAE(Arr(np.ones((1, 8, 2)) * 2.0))
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "hash.safetensors"
            source.write_bytes(b"x")
            with mock.patch.object(
                nodes, "download_cached", return_value=(source, False)
            ), mock.patch.object(
                nodes, "_load_streams",
                return_value={"samples": ["video", audio_latent]},
            ), mock.patch.object(nodes, "torch", FakeTorch):
                _latent, _path, status, _images, audio = nodes.MiniMaxH3LoadAVLatentFromURL().load(
                    "https://example.invalid/a.safetensors", audio_vae=vae
                )
        self.assertEqual(status, "ok:downloaded")
        self.assertEqual(audio["sample_rate"], 32000)
        # Constant signal of 2.0 -> std 0 -> clamped to 1.0 -> unchanged.
        self.assertTrue(np.allclose(audio["waveform"].data, 2.0))
        self.assertEqual(vae.calls, [audio_latent])


if __name__ == "__main__":
    unittest.main()
