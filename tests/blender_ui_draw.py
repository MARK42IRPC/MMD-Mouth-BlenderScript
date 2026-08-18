"""Exercise the release add-on inside Blender's real UI draw context."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
import time
import traceback

import bpy


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "dist-addon" / "MMDmouth-0.6.2.zip"
STATE = {"draws": 0, "error": ""}
STARTED_AT = time.monotonic()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class MMDMOUTH_PT_draw_probe(bpy.types.Panel):
    bl_idname = "MMDMOUTH_PT_draw_probe"
    bl_label = "MMD Mouth Draw Probe"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        from mmd_mouth.ui import MMDMOUTH_PT_main

        proxy = SimpleNamespace(
            layout=self.layout,
            _draw_models=MMDMOUTH_PT_main._draw_models,
            _draw_clips=MMDMOUTH_PT_main._draw_clips,
            _draw_runtime=MMDMOUTH_PT_main._draw_runtime,
            _draw_recognizer_models=MMDMOUTH_PT_main._draw_recognizer_models,
        )
        try:
            MMDMOUTH_PT_main.draw(proxy, context)
        except Exception:
            STATE["error"] = traceback.format_exc()
        finally:
            STATE["draws"] += 1


def finish_when_drawn() -> float | None:
    if STATE["error"]:
        print(f"MMD_UI_DRAW_FAILED\n{STATE['error']}", flush=True)
        os._exit(2)

    settings = bpy.context.scene.mmd_mouth
    if STATE["draws"] > 0 and len(settings.recognizer_models) == 3:
        print(
            "MMD_UI_DRAW_OK "
            f"draws={STATE['draws']} models={len(settings.recognizer_models)}",
            flush=True,
        )
        bpy.ops.wm.quit_blender()
        return None

    if time.monotonic() - STARTED_AT > 10.0:
        print(
            "MMD_UI_DRAW_TIMEOUT "
            f"draws={STATE['draws']} models={len(settings.recognizer_models)}",
            flush=True,
        )
        os._exit(3)
    return 0.1


def main() -> None:
    require(ARCHIVE.is_file(), f"release archive is missing: {ARCHIVE}")
    require(
        "FINISHED" in bpy.ops.preferences.addon_install(filepath=str(ARCHIVE)),
        "add-on install failed",
    )
    require(
        "FINISHED" in bpy.ops.preferences.addon_enable(module="mmd_mouth"),
        "add-on enable failed",
    )
    require("FINISHED" in bpy.ops.mmd_mouth.add_model(), "model setup failed")
    require("FINISHED" in bpy.ops.mmd_mouth.add_clip(), "clip setup failed")

    properties_areas = [
        area
        for window in bpy.context.window_manager.windows
        for area in window.screen.areas
        if area.type == "PROPERTIES"
    ]
    require(properties_areas, "factory startup has no Properties area")
    bpy.utils.register_class(MMDMOUTH_PT_draw_probe)

    for area in properties_areas:
        area.spaces.active.context = "SCENE"
        area.tag_redraw()

    bpy.app.timers.register(finish_when_drawn, first_interval=0.1)


try:
    main()
except Exception:
    print(f"MMD_UI_DRAW_STARTUP_FAILED\n{traceback.format_exc()}", flush=True)
    os._exit(4)
