import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CLITests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def call(self, *args):
        return subprocess.run([sys.executable, "-m", "rei0", *map(str, args)],
                              cwd=self.ROOT, capture_output=True, text=True, check=False)

    def test_cli_demo_and_saved_graph(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "graph.json"
            demo = self.call("demo", "--save", path)
            self.assertEqual(demo.returncode, 0, demo.stderr)
            self.assertEqual(json.loads(demo.stdout)["saved_graph"], str(path))
            self.assertTrue(path.exists())
            replay = self.call("verify", path)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertTrue(json.loads(replay.stdout)["valid"])
            assessment = self.call("assess", path, "disputed")
            self.assertEqual(assessment.returncode, 0, assessment.stderr)
            self.assertEqual(json.loads(assessment.stdout)["state"], "BOTH")

    def test_cli_rejects_missing_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "graph.json"
            self.assertEqual(self.call("demo", "--save", path).returncode, 0)
            result = self.call("assess", path, "not-there")
            self.assertEqual(result.returncode, 2)
            self.assertIn("assessment requires", result.stderr)


if __name__ == "__main__":
    unittest.main()
