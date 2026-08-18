"""Install and enable the release ZIP through Blender's add-on operators."""

from __future__ import annotations

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "dist-addon" / "MMDmouth-0.6.2.zip"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    require(ARCHIVE.is_file(), f"release archive is missing: {ARCHIVE}")
    result = bpy.ops.preferences.addon_install(filepath=str(ARCHIVE))
    require("FINISHED" in result, f"add-on install failed: {result}")
    result = bpy.ops.preferences.addon_enable(module="mmd_mouth")
    require("FINISHED" in result, f"add-on enable failed: {result}")
    require(hasattr(bpy.context.scene, "mmd_mouth"), "scene RNA was not registered")
    settings = bpy.context.scene.mmd_mouth

    from mmd_mouth import bundled_models

    require(
        bpy.app.timers.is_registered(bundled_models._initialize_timer),
        "bundled-model initialization was not scheduled",
    )
    bpy.app.timers.unregister(bundled_models._initialize_timer)
    require(
        bundled_models._initialize_timer() is None,
        "bundled-model initialization did not complete with a ready Scene",
    )
    require(
        len(settings.recognizer_models) == 3,
        "bundled models were not registered automatically",
    )
    require(
        {model.language_code for model in settings.recognizer_models}
        == {"zh-CN", "ja-JP", "en-US"},
        "bundled language catalog is incomplete",
    )
    result = bpy.ops.mmd_mouth.check_worker()
    require("FINISHED" in result, settings.worker_last_error)

    import mmd_mouth

    require(
        tuple(mmd_mouth.bl_info["version"]) == (0, 6, 2),
        "installed add-on version is not 0.6.2",
    )
    require(
        str(Path(mmd_mouth.__file__).resolve()).startswith(
            str(Path(bpy.utils.user_resource("SCRIPTS")).resolve())
        ),
        "Blender loaded the source checkout instead of the installed add-on",
    )
    print(
        "MMD_INSTALL_ZIP_OK "
        f"addon={Path(mmd_mouth.__file__).resolve()} "
        f"worker={settings.worker_display_name}",
        flush=True,
    )


main()
