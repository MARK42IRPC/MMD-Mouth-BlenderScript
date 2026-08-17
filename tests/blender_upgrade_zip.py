"""Upgrade an enabled 0.3.1 add-on without restarting Blender."""

from __future__ import annotations

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OLD_ARCHIVE = ROOT / "dist-addon" / "MMDmouth-0.3.1.zip"
NEW_ARCHIVE = ROOT / "dist-addon" / "MMDmouth-0.4.2.zip"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def install(path: Path) -> None:
    require(path.is_file(), f"release archive is missing: {path}")
    result = bpy.ops.preferences.addon_install(
        filepath=str(path),
        overwrite=True,
    )
    require("FINISHED" in result, f"add-on install failed: {result}")


def main() -> None:
    install(OLD_ARCHIVE)
    require(
        "FINISHED" in bpy.ops.preferences.addon_enable(module="mmd_mouth"),
        "0.3.1 could not be enabled",
    )

    import mmd_mouth
    from mmd_mouth import blender_runtime as old_runtime

    require(
        tuple(mmd_mouth.bl_info["version"]) == (0, 3, 1),
        "upgrade fixture is not 0.3.1",
    )
    require(
        not hasattr(old_runtime, "register"),
        "upgrade fixture unexpectedly has the new runtime API",
    )

    install(NEW_ARCHIVE)
    require(
        "FINISHED" in bpy.ops.preferences.addon_enable(module="mmd_mouth"),
        "in-place upgrade to 0.4.2 failed",
    )

    from mmd_mouth import blender_runtime

    require(
        tuple(mmd_mouth.bl_info["version"]) == (0, 4, 2),
        "top-level add-on module was not upgraded",
    )
    require(
        hasattr(blender_runtime, "register"),
        "cached runtime submodule was not reloaded",
    )
    require(
        hasattr(bpy.context.scene, "mmd_mouth"),
        "upgraded Scene RNA was not registered",
    )
    require("FINISHED" in bpy.ops.mmd_mouth.add_model(), "model setup failed")
    require("FINISHED" in bpy.ops.mmd_mouth.add_clip(), "clip setup failed")
    settings = bpy.context.scene.mmd_mouth
    profile = settings.model_profiles[settings.active_model_index]
    clip = profile.clips[profile.active_clip_index]
    clip_properties = clip.bl_rna.properties
    require("audio_volume" in clip_properties, "new clip RNA was not registered")
    require("mouth_strength" in clip_properties, "mouth strength RNA is missing")
    require("easing_mode" in clip_properties, "easing mode RNA is missing")
    require(
        bpy.ops.mmd_mouth.regenerate.get_rna_type() is not None,
        "regenerate operator was not registered",
    )

    print(
        "MMD_UPGRADE_ZIP_OK "
        f"version={mmd_mouth.bl_info['version']} "
        f"addon={Path(mmd_mouth.__file__).resolve()}",
        flush=True,
    )


main()
