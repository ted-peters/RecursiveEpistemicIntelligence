"""Host-app smoke tests (do not require external models)."""
import importlib.util
from pathlib import Path
import sys
import unittest

SPACE = Path(__file__).resolve().parents[1] / "space"

class SpaceTests(unittest.TestCase):
    def test_app_python_syntax(self):
        compile((SPACE / "app.py").read_text(encoding="utf-8"), str(SPACE / "app.py"), "exec")
    def test_space_card(self):
        txt = (SPACE / "README.md").read_text(encoding="utf-8")
        self.assertIn("sdk: gradio", txt)
        self.assertIn("app_file: app.py", txt)
    def test_hosted_graph_history(self):
        if importlib.util.find_spec("gradio") is None:
            self.skipTest("gradio not installed (host UI is optional for engine tests)")
        sys.path.insert(0, str(SPACE))
        try:
            spec = importlib.util.spec_from_file_location("rei_host_app", SPACE / "app.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            values = [module.make_history(i)["state"] for i in range(1,7)]
            self.assertEqual(values,["NEITHER","SUPPORT_ONLY","BOTH","ATTACK_ONLY","BOTH","SUPPORT_ONLY"])
            self.assertEqual(module.make_history(2)["independent_positive_groups"],1)
            self.assertTrue(module.make_history(6)["audit_chain_replays"])
        finally:
            sys.path.remove(str(SPACE))
