"""Sidebar UI for the MMD Mouth add-on."""

from __future__ import annotations

import bpy
from bpy.types import Panel, UIList


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


class MMDMOUTH_UL_models(UIList):
    bl_idname = "MMDMOUTH_UL_models"

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        del context, data, icon, active_data, active_propname, index
        row = layout.row(align=True)
        row.label(text=item.display_name or "Unnamed Model", icon="OBJECT_DATA")
        status_icons = {
            "VALID": "CHECKMARK",
            "WARNING": "ERROR",
            "ERROR": "CANCEL",
        }
        row.label(text="", icon=status_icons.get(item.binding_status, "QUESTION"))


class MMDMOUTH_UL_clips(UIList):
    bl_idname = "MMDMOUTH_UL_clips"

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        del context, data, icon, active_data, active_propname, index
        row = layout.row(align=True)
        row.label(text=item.display_name or "Unnamed Clip", icon="SPEAKER")
        status_icons = {
            "RUNNING": "TIME",
            "RECOGNIZED": "CHECKMARK",
            "BAKED": "ACTION",
            "STALE": "FILE_REFRESH",
            "ERROR": "ERROR",
        }
        row.label(text="", icon=status_icons.get(item.status, "DOT"))


class MMDMOUTH_UL_events(UIList):
    bl_idname = "MMDMOUTH_UL_events"

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        del context, data, icon, active_data, active_propname
        row = layout.row(align=True)
        label = item.source_text or item.source_phoneme or item.phoneme or "Manual"
        row.label(text=f"{index + 1} {label[:12]}", icon="SPEAKER")
        row.prop(item, "viseme_id", text="")
        row.prop(item, "start_sec", text="")
        row.prop(item, "end_sec", text="")
        row.prop(item, "weight", text="")


class MMDMOUTH_PT_main(Panel):
    bl_idname = "MMDMOUTH_PT_main"
    bl_label = "MMD Mouth"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MMD Mouth"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.mmd_mouth
        profile = self._draw_models(layout, settings)
        self._draw_clips(layout, settings, scene, profile)
        self._draw_runtime(layout, settings)
        self._draw_recognizer_models(layout, settings)

    @staticmethod
    def _draw_models(layout, settings):
        box = layout.box()
        header = box.row(align=True)
        header.label(text="MMD Models")
        header.operator("mmd_mouth.add_model", text="", icon="ADD")
        header.operator("mmd_mouth.remove_model", text="", icon="REMOVE")
        box.template_list(
            "MMDMOUTH_UL_models",
            "",
            settings,
            "model_profiles",
            settings,
            "active_model_index",
            rows=3,
        )

        profile = _active_profile(settings)
        if profile is None:
            return None
        box.prop(profile, "display_name", text="Name")
        box.prop(profile, "root_object", text="Root")
        row = box.row(align=True)
        row.label(text="Mouth Morphs:")
        row.label(text=profile.binding_status.title())
        row.operator("mmd_mouth.scan_bindings", text="Scan", icon="SHAPEKEY_DATA")
        return profile

    @staticmethod
    def _draw_clips(layout, settings, scene, profile):
        box = layout.box()
        header = box.row(align=True)
        header.label(text="Mouth Clips")
        header.operator("mmd_mouth.add_clip", text="", icon="ADD")
        header.operator("mmd_mouth.remove_clip", text="", icon="REMOVE")
        if profile is None:
            return
        box.template_list(
            "MMDMOUTH_UL_clips",
            "",
            profile,
            "clips",
            profile,
            "active_clip_index",
            rows=4,
        )

        clip = _active_clip(profile)
        if clip is None:
            return
        box.prop(clip, "display_name", text="Name")
        audio_row = box.row(align=True)
        audio_row.prop(clip, "audio_path", text="Audio")
        audio_row.operator(
            "mmd_mouth.transcode_audio",
            text="",
            icon="FILE_REFRESH",
        )
        if clip.transcoded_audio_path:
            box.label(text="Converted PCM WAV ready", icon="CHECKMARK")
        box.prop(clip, "audio_volume", slider=True)
        row = box.row(align=True)
        row.prop(clip, "start_frame")
        row.prop(clip, "language_code", text="Language")
        row = box.row(align=True)
        row.prop(clip, "audio_offset_sec")
        row.prop(clip, "duration_sec")
        row = box.row(align=True)
        row.label(text="Render FPS:")
        row.label(text=f"{scene.render.fps / scene.render.fps_base:g}")
        box.prop(clip, "generation_mode", expand=True)
        box.prop(clip, "easing_mode", text="Mouth Blend")
        box.label(text="Transition")
        row = box.row(align=True)
        row.prop(clip, "attack_ms", text="In")
        row.prop(clip, "release_ms", text="Out")
        box.prop(clip, "hold_ratio", text="Hold")
        box.prop(clip, "mouth_strength", slider=True)

        timeline = box.row(align=True)
        timeline_icon = "TRIA_DOWN" if clip.show_timeline else "TRIA_RIGHT"
        timeline.prop(
            clip,
            "show_timeline",
            text="Mouth Timeline",
            icon=timeline_icon,
            emboss=False,
        )
        timeline.label(text=str(len(clip.events)))
        if clip.show_timeline:
            if clip.events:
                box.template_list(
                    "MMDMOUTH_UL_events",
                    "",
                    clip,
                    "events",
                    clip,
                    "active_event_index",
                    rows=min(max(len(clip.events), 3), 8),
                )
            else:
                box.label(text="No timeline events")
            timeline_controls = box.row(align=True)
            timeline_controls.operator(
                "mmd_mouth.add_event",
                text="",
                icon="ADD",
            )
            timeline_controls.operator(
                "mmd_mouth.remove_event",
                text="",
                icon="REMOVE",
            )
            timeline_controls.operator(
                "mmd_mouth.sort_events",
                text="",
                icon="SORTALPHA",
            )

        primary = box.row()
        primary.scale_y = 1.35
        if settings.is_busy:
            primary.operator("mmd_mouth.cancel", icon="CANCEL")
        else:
            primary.operator("mmd_mouth.generate", icon="PLAY")
        secondary = box.row(align=True)
        secondary.operator(
            "mmd_mouth.regenerate",
            text="Regenerate",
            icon="FILE_REFRESH",
        )
        secondary.operator(
            "mmd_mouth.recognize",
            text="Recognize Only",
            icon="SPEAKER",
        )
        cleanup = box.row(align=True)
        cleanup.operator(
            "mmd_mouth.clear_generated",
            text="Clear Animation",
            icon="X",
        )
        cleanup.operator(
            "mmd_mouth.remove_clip",
            text="Delete Clip",
            icon="TRASH",
        )

        row = box.row(align=True)
        row.label(text="Status:")
        row.label(text=clip.status.title())
        if clip.source_transcript:
            box.prop(clip, "source_transcript", text="Transcript")
        if clip.audio_preview_error:
            box.label(text=clip.audio_preview_error[:120], icon="ERROR")
        if clip.audio_transcode_error:
            box.label(text=clip.audio_transcode_error[:120], icon="ERROR")
        if clip.last_error:
            box.label(text=clip.last_error[:120], icon="ERROR")

    @staticmethod
    def _draw_runtime(layout, settings):
        box = layout.box()
        expanded = settings.show_advanced_runtime or settings.worker_status in {
            "MISSING",
            "ERROR",
        }
        icon = "TRIA_DOWN" if expanded else "TRIA_RIGHT"
        row = box.row(align=True)
        row.prop(
            settings,
            "show_advanced_runtime",
            text="Runtime",
            icon=icon,
            emboss=False,
        )
        row.label(text=settings.worker_status.title())
        if not expanded:
            return
        row = box.row(align=True)
        row.label(text=settings.worker_display_name)
        row.operator("mmd_mouth.check_worker", text="", icon="FILE_REFRESH")
        if settings.worker_last_error:
            box.label(text=settings.worker_last_error[:120], icon="ERROR")
        box.prop(settings, "worker_mode")
        if settings.worker_mode in {"AUTO", "CUSTOM"}:
            box.prop(settings, "worker_executable")
        if settings.worker_mode in {"AUTO", "PYTHON"}:
            box.prop(settings, "worker_python")
        box.prop(settings, "cache_directory")

    @staticmethod
    def _draw_recognizer_models(layout, settings):
        box = layout.box()
        icon = "TRIA_DOWN" if settings.show_advanced_models else "TRIA_RIGHT"
        row = box.row(align=True)
        row.prop(
            settings,
            "show_advanced_models",
            text="Recognition Models",
            icon=icon,
            emboss=False,
        )
        if not settings.show_advanced_models:
            return
        controls = box.row(align=True)
        controls.operator("mmd_mouth.add_recognizer_model", text="Add Custom", icon="ADD")
        controls.operator("mmd_mouth.remove_recognizer_model", text="", icon="REMOVE")
        for model in settings.recognizer_models:
            model_box = box.box()
            row = model_box.row(align=True)
            row.prop(model, "enabled", text="")
            if model.is_bundled:
                row.label(text=model.display_name, icon="PACKAGE")
                row.label(text=model.language_code)
                continue
            row.prop(model, "display_name", text="")
            model_box.prop(model, "model_id")
            model_box.prop(model, "language_code")
            model_box.prop(model, "model_path")
            row = model_box.row(align=True)
            row.prop(model, "priority")
            row.prop(model, "calibration_bias")
            row.prop(model, "calibration_temperature")


CLASSES = (
    MMDMOUTH_UL_models,
    MMDMOUTH_UL_clips,
    MMDMOUTH_UL_events,
    MMDMOUTH_PT_main,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


__all__ = ["register", "unregister"]
