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
        self.assertEqual(MiniMaxH3LoadAVLatentFromURL.RETURN_TYPES, ("LATENT", "STRING"))
        self.assertEqual(
            MiniMaxH3LoadAVLatentFromURL.RETURN_NAMES,
            ("latent", "local_path"),
        )


if __name__ == "__main__":
    unittest.main()
