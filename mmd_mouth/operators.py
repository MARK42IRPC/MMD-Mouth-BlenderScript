"""Blender operators for the first usable MMD Mouth workflow."""

from __future__ import annotations

from uuid import uuid4

import bpy
from bpy.types import Operator

from .animation import (
    AnimationError,
    generate_clip,
    remove_generated_assets,
    scan_mmd_bindings,
)
from .audio import remove_clip_audio
from .blender_runtime import (
    cancel_active,
    check_worker,
    is_recognition_active,
    reconcile_runtime_state,
    start_recognition,
)
from .constants import DEFAULT_BACKEND_ID, DEFAULT_LANGUAGE_CODE
from .recognition.runtime import WorkerRuntimeError


def _active_profile(settings):
    if not settings.model_profiles:
        return None
    index = min(
        max(0, settings.active_model_index),
        len(settings.model_profiles) - 1,
    )
    return settings.model_profiles[index]


def _active_clip(profile):
    if profile is None or not profile.clips:
        return None
    index = min(max(0, profile.active_clip_index), len(profile.clips) - 1)
    return profile.clips[index]


def _suggest_model_root(context):
    active = context.active_object
    if active is None:
        return None
    lineage = []
    current = active
    while current is not None:
        lineage.append(current)
        current = current.parent
    return next(
        (obj for obj in lineage if getattr(obj, "mmd_type", "") == "ROOT"),
        lineage[-1],
    )


class MMDMOUTH_OT_add_model(Operator):
    bl_idname = "mmd_mouth.add_model"
    bl_label = "Add Model"
    bl_description = "Add an MMD model profile"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.mmd_mouth
        profile = settings.model_profiles.add()
        profile.profile_id = uuid4().hex
        root = _suggest_model_root(context)
        profile.display_name = root.name if root is not None else (
            f"Model {len(settings.model_profiles)}"
        )
        profile.root_object = root
        profile.auto_discovered = False
        settings.active_model_index = len(settings.model_profiles) - 1
        return {"FINISHED"}


class MMDMOUTH_OT_remove_model(Operator):
    bl_idname = "mmd_mouth.remove_model"
    bl_label = "Remove Model"
    bl_description = "Remove the selected MMD model profile"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.mmd_mouth.model_profiles)

    def execute(self, context):
        settings = context.scene.mmd_mouth
        if is_recognition_active():
            self.report({"ERROR"}, "Cannot remove a model while recognition is running")
            return {"CANCELLED"}
        reconcile_runtime_state(context.scene)
        index = min(
            max(0, settings.active_model_index),
            len(settings.model_profiles) - 1,
        )
        profile = settings.model_profiles[index]
        for clip in list(profile.clips):
            remove_generated_assets(clip)
            remove_clip_audio(context.scene, clip)
        settings.model_profiles.remove(index)
        settings.active_model_index = min(
            index,
            max(0, len(settings.model_profiles) - 1),
        )
        return {"FINISHED"}


class MMDMOUTH_OT_add_clip(Operator):
    bl_idname = "mmd_mouth.add_clip"
    bl_label = "Add Clip"
    bl_description = "Add a speech clip to the selected model"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_profile(context.scene.mmd_mouth) is not None

    def execute(self, context):
        settings = context.scene.mmd_mouth
        profile = _active_profile(settings)
        clip = profile.clips.add()
        clip.clip_id = uuid4().hex
        clip.display_name = f"Clip {len(profile.clips)}"
        clip.backend_id = DEFAULT_BACKEND_ID
        clip.language_code = settings.default_language_code or DEFAULT_LANGUAGE_CODE
        clip.generation_mode = settings.default_generation_mode
        clip.start_frame = context.scene.frame_start
        clip.render_fps = context.scene.render.fps
        clip.render_fps_base = context.scene.render.fps_base
        profile.active_clip_index = len(profile.clips) - 1
        return {"FINISHED"}


class MMDMOUTH_OT_remove_clip(Operator):
    bl_idname = "mmd_mouth.remove_clip"
    bl_label = "Delete Clip"
    bl_description = "Delete the selected clip and all output owned by it"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_clip(_active_profile(context.scene.mmd_mouth)) is not None

    def execute(self, context):
        settings = context.scene.mmd_mouth
        profile = _active_profile(settings)
        if is_recognition_active():
            self.report({"ERROR"}, "Cannot remove a clip while recognition is running")
            return {"CANCELLED"}
        reconcile_runtime_state(context.scene)
        index = min(max(0, profile.active_clip_index), len(profile.clips) - 1)
        clip = profile.clips[index]
        remove_generated_assets(clip)
        remove_clip_audio(context.scene, clip)
        profile.clips.remove(index)
        profile.active_clip_index = min(index, max(0, len(profile.clips) - 1))
        return {"FINISHED"}


class MMDMOUTH_OT_add_recognizer_model(Operator):
    bl_idname = "mmd_mouth.add_recognizer_model"
    bl_label = "Add Vosk Model"
    bl_description = "Register a local Vosk language model"

    def execute(self, context):
        settings = context.scene.mmd_mouth
        model = settings.recognizer_models.add()
        model.model_id = f"model-{len(settings.recognizer_models)}"
        model.display_name = "Vosk Model"
        model.language_code = settings.default_language_code or DEFAULT_LANGUAGE_CODE
        model.enabled = True
        return {"FINISHED"}


class MMDMOUTH_OT_remove_recognizer_model(Operator):
    bl_idname = "mmd_mouth.remove_recognizer_model"
    bl_label = "Remove Vosk Model"
    bl_description = "Remove the last registered Vosk model"

    @classmethod
    def poll(cls, context):
        return any(
            not model.is_bundled
            for model in context.scene.mmd_mouth.recognizer_models
        )

    def execute(self, context):
        settings = context.scene.mmd_mouth
        index = next(
            index
            for index in range(len(settings.recognizer_models) - 1, -1, -1)
            if not settings.recognizer_models[index].is_bundled
        )
        settings.recognizer_models.remove(index)
        return {"FINISHED"}


class MMDMOUTH_OT_check_worker(Operator):
    bl_idname = "mmd_mouth.check_worker"
    bl_label = "Check Runtime"
    bl_description = "Check the bundled speech runtime"

    def execute(self, context):
        settings = context.scene.mmd_mouth
        if check_worker(settings):
            self.report({"INFO"}, f"Worker ready: {settings.worker_display_name}")
            return {"FINISHED"}
        self.report({"ERROR"}, settings.worker_last_error or "Worker unavailable")
        return {"CANCELLED"}


class MMDMOUTH_OT_recognize(Operator):
    bl_idname = "mmd_mouth.recognize"
    bl_label = "Recognize Audio"
    bl_description = "Recognize the selected clip without blocking Blender"

    @classmethod
    def poll(cls, context):
        settings = context.scene.mmd_mouth
        return (
            not is_recognition_active()
            and _active_clip(_active_profile(settings)) is not None
        )

    def execute(self, context):
        settings = context.scene.mmd_mouth
        profile = _active_profile(settings)
        clip = _active_clip(profile)
        try:
            task_id = start_recognition(context.scene, profile, clip)
        except (ValueError, WorkerRuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Recognition started: {task_id[:8]}")
        return {"FINISHED"}


class MMDMOUTH_OT_scan_bindings(Operator):
    bl_idname = "mmd_mouth.scan_bindings"
    bl_label = "Scan Mouth Morphs"
    bl_description = "Find MMD A, I, U, E, O, and optional closed-mouth shape keys"

    @classmethod
    def poll(cls, context):
        settings = context.scene.mmd_mouth
        profile = _active_profile(settings)
        return (
            not is_recognition_active()
            and profile is not None
            and profile.root_object is not None
        )

    def execute(self, context):
        profile = _active_profile(context.scene.mmd_mouth)
        try:
            count = scan_mmd_bindings(profile)
        except AnimationError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Found {count} mouth morph bindings")
        return {"FINISHED"}


def _execute_generate(operator, context):
    scene = context.scene
    settings = scene.mmd_mouth
    profile = _active_profile(settings)
    clip = _active_clip(profile)
    try:
        if not profile.bindings or profile.binding_status == "UNSCANNED":
            scan_mmd_bindings(profile)
        if clip.events and clip.status != "STALE":
            generated = generate_clip(scene, profile, clip)
            operator.report({"INFO"}, f"Generated {generated} animation owner(s)")
            return {"FINISHED"}
        task_id = start_recognition(
            scene,
            profile,
            clip,
            generate_after_recognition=True,
        )
    except (AnimationError, ValueError, WorkerRuntimeError) as exc:
        clip.status = "ERROR"
        clip.last_error = str(exc)
        operator.report({"ERROR"}, str(exc))
        return {"CANCELLED"}
    operator.report({"INFO"}, f"Mouth generation started: {task_id[:8]}")
    return {"FINISHED"}


def _can_generate(context):
    settings = context.scene.mmd_mouth
    return (
        not is_recognition_active()
        and _active_clip(_active_profile(settings)) is not None
    )


class MMDMOUTH_OT_generate(Operator):
    bl_idname = "mmd_mouth.generate"
    bl_label = "Generate Mouth"
    bl_description = "Recognize audio when needed, then generate MMD mouth animation"

    @classmethod
    def poll(cls, context):
        return _can_generate(context)

    def execute(self, context):
        return _execute_generate(self, context)


class MMDMOUTH_OT_regenerate(Operator):
    bl_idname = "mmd_mouth.regenerate"
    bl_label = "Regenerate Mouth"
    bl_description = "Replace the selected clip's generated mouth animation"

    @classmethod
    def poll(cls, context):
        return _can_generate(context)

    def execute(self, context):
        return _execute_generate(self, context)


class MMDMOUTH_OT_clear_generated(Operator):
    bl_idname = "mmd_mouth.clear_generated"
    bl_label = "Clear Generated Animation"
    bl_description = "Remove animation assets owned by the selected clip"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        settings = context.scene.mmd_mouth
        clip = _active_clip(_active_profile(settings))
        return not is_recognition_active() and clip is not None and bool(clip.assets)

    def execute(self, context):
        clip = _active_clip(_active_profile(context.scene.mmd_mouth))
        remove_generated_assets(clip)
        clip.status = "RECOGNIZED" if clip.events else "DRAFT"
        clip.last_error = ""
        self.report({"INFO"}, "Generated mouth animation cleared")
        return {"FINISHED"}


class MMDMOUTH_OT_cancel(Operator):
    bl_idname = "mmd_mouth.cancel"
    bl_label = "Cancel"
    bl_description = "Cancel the running recognition task"

    @classmethod
    def poll(cls, context):
        return (
            is_recognition_active()
            or context.scene.mmd_mouth.is_busy
        )

    def execute(self, context):
        if cancel_active(context.scene):
            self.report({"INFO"}, "Recognition cancelled")
            return {"FINISHED"}
        return {"CANCELLED"}


CLASSES = (
    MMDMOUTH_OT_add_model,
    MMDMOUTH_OT_remove_model,
    MMDMOUTH_OT_add_clip,
    MMDMOUTH_OT_remove_clip,
    MMDMOUTH_OT_add_recognizer_model,
    MMDMOUTH_OT_remove_recognizer_model,
    MMDMOUTH_OT_check_worker,
    MMDMOUTH_OT_recognize,
    MMDMOUTH_OT_scan_bindings,
    MMDMOUTH_OT_generate,
    MMDMOUTH_OT_regenerate,
    MMDMOUTH_OT_clear_generated,
    MMDMOUTH_OT_cancel,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


__all__ = ["register", "unregister"]
