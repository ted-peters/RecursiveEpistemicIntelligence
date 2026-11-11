"""Reproducible CI checks for the free browser-hosted REI graph demonstration."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "space-static"
GRADIO = ROOT / "space"

class BrowserSpaceTests(unittest.TestCase):
    def test_original_rei_modules_match_gradio_demo(self):
        for name in ("__init__.py", "demo.py", "graph.py", "models.py"):
            self.assertEqual((STATIC / "rei0" / name).read_bytes(),
                             (GRADIO / "rei0" / name).read_bytes(), name)

    def test_space_manifest_and_browser_runtime(self):
        readme = (STATIC / "README.md").read_text(encoding="utf8")
        html = (STATIC / "index.html").read_text(encoding="utf8")
        self.assertIn("sdk: static", readme)
        self.assertIn("app_file: index.html", readme)
        self.assertIn("cdn.jsdelivr.net/pyodide/v0.29.5/full/pyodide.js", html)
        self.assertIn("./'+path", html)
        self.assertNotIn("HF_TOKEN", html)

    def test_six_stage_actual_graph_and_audit_replay(self):
        code = """import json;from driver import history; print(json.dumps([history(i) for i in range(1, 7)]))"""
        r = subprocess.run([sys.executable, "-c", code],
                           cwd=STATIC, check=True, capture_output=True, text=True)
        stages = json.loads(r.stdout)
        self.assertEqual([x["state"] for x in stages],
                         ["NEITHER", "SUPPORT_ONLY", "BOTH", "ATTACK_ONLY", "BOTH", "SUPPORT_ONLY"])
        self.assertEqual([x["positive_groups"] for x in stages], [0, 1, 1, 0, 1, 1])
        self.assertEqual([x["negative_groups"] for x in stages], [0, 0, 1, 1, 1, 0])
        self.assertTrue(all(x["audit_replays"] and x["fictional"] for x in stages))
        self.assertTrue(all(x["confidence"] is None for x in stages))

    def test_four_state_examples(self):
        code = """import json;from driver import example;print(json.dumps([example(n)[\"state\"] for n in ['unassessed','supported','opposed','disputed','isolated']]))"""
        r = subprocess.run([sys.executable, "-c", code], cwd=STATIC,
                           check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(r.stdout),
                         ["NEITHER", "SUPPORT_ONLY", "ATTACK_ONLY", "BOTH", "NEITHER"])

    def test_javascript_syntax(self):
        html = (STATIC / "index.html").read_text(encoding="utf8")
        inline = html.split("<script>\n", 1)[1].split("</script>", 1)[0]
        with self.subTest("Node.js installed on CI"):
            r = subprocess.run(["node", "--check", "--input-type=commonjs"],
                               input=inline, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

if __name__ == "__main__":
    unittest.main()
