"""Regression checks for Blender's read-only panel drawing context."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


UI_MODULE = Path(__file__).resolve().parents[1] / "mmd_mouth" / "ui.py"


class UiContractTests(unittest.TestCase):
    def test_draw_code_does_not_initialize_bundled_models(self) -> None:
        tree = ast.parse(UI_MODULE.read_text(encoding="utf-8"))
        draw_nodes = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and (node.name == "draw" or node.name.startswith("_draw_"))
        ]
        called_names = {
            node.func.id
            for draw_node in draw_nodes
            for node in ast.walk(draw_node)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        self.assertNotIn(
            "ensure_settings_models",
            called_names,
            "Panel drawing must not mutate Scene RNA",
        )

    def test_clip_draw_exposes_easing_control(self) -> None:
        source = UI_MODULE.read_text(encoding="utf-8")
        self.assertIn(
            'box.prop(clip, "easing_mode", text="Mouth Blend")',
            source,
        )

    def test_clip_draw_exposes_editable_timeline_and_transition_controls(self) -> None:
        source = UI_MODULE.read_text(encoding="utf-8")
        self.assertIn('row.prop(clip, "attack_ms", text="In")', source)
        self.assertIn('row.prop(clip, "release_ms", text="Out")', source)
        self.assertIn('"show_timeline",', source)
        self.assertIn('"MMDMOUTH_UL_events"', source)
        self.assertIn('"mmd_mouth.transcode_audio"', source)

    def test_regenerate_uses_existing_timeline(self) -> None:
        operators = UI_MODULE.parents[0] / "operators.py"
        source = operators.read_text(encoding="utf-8")
        self.assertIn(
            'return _execute_generate(self, context, reuse_timeline=True)',
            source,
        )
        self.assertIn(
            'if clip.events and (reuse_timeline or clip.status != "STALE"):',
            source,
        )


if __name__ == "__main__":
    unittest.main()
