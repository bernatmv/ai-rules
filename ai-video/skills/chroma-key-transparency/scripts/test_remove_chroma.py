"""Small regression suite; run with python3 -m unittest discover -s scripts."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from remove_chroma import remove_key, previews


class ChromaTests(unittest.TestCase):
    def test_background_gaps_and_foreground(self):
        image = Image.new("RGB", (3, 3), "red")
        image.putpixel((0, 0), (0, 255, 0))
        image.putpixel((1, 1), (0, 255, 0))
        result = remove_key(image, (0, 255, 0))
        self.assertEqual(result.size, image.size)
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0, 0))
        self.assertEqual(result.getpixel((1, 1)), (0, 0, 0, 0))
        self.assertEqual(result.getpixel((2, 2)), (255, 0, 0, 255))

    def test_soft_edge_and_preserved_alpha(self):
        image = Image.new("RGBA", (3, 1))
        image.putdata([(0, 180, 0, 255), (255, 0, 0, 128), (0, 0, 255, 0)])
        result = remove_key(image, (0, 255, 0))
        edge = result.getpixel((0, 0))
        self.assertTrue(0 < edge[3] < 255)
        self.assertLess(edge[1], 180)
        self.assertEqual(result.getpixel((1, 0)), (255, 0, 0, 128))
        self.assertEqual(result.getpixel((2, 0)), (0, 0, 0, 0))

    def test_hard_edges_and_alternate_key(self):
        image = Image.new("RGB", (2, 1), "magenta")
        image.putpixel((1, 0), (0, 255, 0))
        result = remove_key(image, (255, 0, 255), hard=True)
        self.assertEqual(list(result.getchannel("A").getdata()), [0, 255])
        self.assertEqual(result.getpixel((1, 0)), (0, 255, 0, 255))

    def test_invalid_thresholds(self):
        for inner, outer in [(30, 20), (-1, 150), (20, float("nan"))]:
            with self.assertRaises(ValueError):
                remove_key(Image.new("RGB", (1, 1)), (0, 255, 0), inner, outer)

    def test_despill_removes_fringe_preserves_red(self):
        image = Image.new("RGB", (2, 1))
        image.putdata([(90, 130, 85), (190, 80, 40)])
        result = remove_key(image, (0, 255, 0), despill=True)
        self.assertEqual(result.getpixel((0, 0)), (90, 90, 85, 255))
        self.assertEqual(result.getpixel((1, 0)), (190, 80, 40, 255))
        with self.assertRaises(ValueError):
            remove_key(image, (255, 0, 255), despill=True)

    def test_previews(self):
        result = dict(previews(Image.new("RGBA", (2, 2), (0, 0, 0, 0))))
        self.assertEqual(result["light"].getpixel((0, 0)), (240, 240, 240))
        self.assertEqual(result["dark"].getpixel((0, 0)), (24, 24, 32))

    def test_cli_rgba_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            output = Path(directory) / "asset.png"
            image = Image.new("RGB", (2, 1), "lime")
            image.putpixel((1, 0), (255, 0, 0))
            image.save(source)
            command = [sys.executable, str(Path(__file__).with_name("remove_chroma.py")), str(source), str(output), "--key", "#00FF00", "--previews"]
            run = subprocess.run(command, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            with Image.open(output) as asset:
                self.assertEqual(asset.mode, "RGBA")
                self.assertEqual(asset.getchannel("A").getextrema(), (0, 255))
            self.assertTrue(output.with_name("asset.dark.png").exists())
            before = output.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
