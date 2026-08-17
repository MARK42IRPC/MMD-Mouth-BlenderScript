"""MMD Mouth Blender add-on entry point."""

from __future__ import annotations

import importlib
import sys

bl_info = {
    "name": "MMD Mouth",
    "author": "MMD Mouth contributors",
    "version": (0, 4, 2),
    "blender": (5, 2, 0),
    "location": "3D View > Sidebar > MMD Mouth",
    "description": "Speech-driven MMD mouth animation",
    "category": "Animation",
    "support": "COMMUNITY",
}


_MODULE_LOAD_ORDER = (
    "constants",
    "audio",
    "animation",
    "bundled_models",
    "migrations",
    "properties",
    "blender_runtime",
    "operators",
    "translations",
    "ui",
)


def _load_modules():
    """Import fresh modules or reload submodules retained by an in-place upgrade."""

    modules = {}
    for short_name in _MODULE_LOAD_ORDER:
        full_name = f"{__name__}.{short_name}"
        module = sys.modules.get(full_name)
        if module is None:
            module = importlib.import_module(f".{short_name}", __name__)
        else:
            module = importlib.reload(module)
        modules[short_name] = module
    return modules


def register():
    modules = _load_modules()
    modules["translations"].register()
    modules["properties"].register()
    modules["migrations"].register()
    modules["bundled_models"].register()
    modules["blender_runtime"].register()
    modules["operators"].register()
    modules["ui"].register()


def unregister():
    from .blender_runtime import unregister as unregister_runtime
    from .bundled_models import unregister as unregister_bundled_models
    from .migrations import unregister as unregister_migrations
    from .properties import unregister as unregister_properties
    from .operators import unregister as unregister_operators
    from .translations import unregister as unregister_translations
    from .ui import unregister as unregister_ui

    unregister_ui()
    unregister_operators()
    unregister_runtime()
    unregister_bundled_models()
    unregister_migrations()
    unregister_properties()
    unregister_translations()


if __name__ == "__main__":
    register()
