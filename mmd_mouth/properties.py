"""Blender RNA properties for the MMD Mouth add-on."""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .constants import (
    ASSET_KIND_ITEMS,
    BINDING_STATUS_ITEMS,
    CANDIDATE_SCORING_VERSION,
    CLIP_STATUS_ITEMS,
    DEFAULT_ATTACK_MS,
    DEFAULT_BACKEND_ID,
    DEFAULT_GENERATION_MODE,
    DEFAULT_HOLD_RATIO,
    DEFAULT_LANGUAGE_CODE,
    DEFAULT_RELEASE_MS,
    GENERATION_MODE_ITEMS,
    IPA_NORMALIZATION_VERSION,
    LANGUAGE_ITEMS,
    LANGUAGE_SEGMENT_SOURCE_ITEMS,
    PHONEME_MANNER_ITEMS,
    PHONEME_PLACE_ITEMS,
    PHONEME_TYPE_ITEMS,
    PHONEME_VOICING_ITEMS,
    SCHEMA_VERSION,
    SOURCE_ITEMS,
    TARGET_KIND_ITEMS,
    TIMELINE_VERSION,
    VISEME_ITEMS,
    DEFAULT_WORKER_MODE,
    EASING_MODE_ITEMS,
    WORKER_MODE_ITEMS,
    WORKER_STATUS_ITEMS,
    WORKER_PROTOCOL_VERSION,
)


def _mark_timeline_stale(clip, _context):
    if clip.status in {"RECOGNIZED", "BAKED"}:
        clip.status = "STALE"


def _sync_audio_preview(clip, context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    from .audio import AudioPreviewError, sync_clip_audio

    try:
        sync_clip_audio(scene, clip)
        clip.audio_preview_error = ""
    except AudioPreviewError as exc:
        clip.audio_preview_error = str(exc)


def _update_audio_path(clip, context):
    clip.transcoded_audio_path = ""
    clip.audio_transcode_error = ""
    _mark_timeline_stale(clip, context)
    _sync_audio_preview(clip, context)


def _update_audio_window(clip, context):
    _mark_timeline_stale(clip, context)
    _sync_audio_preview(clip, context)


def _update_start_frame(clip, context):
    _sync_audio_preview(clip, context)
    from .animation import move_generated_assets

    move_generated_assets(clip)


def _update_audio_volume(clip, context):
    _sync_audio_preview(clip, context)


def _reset_model_bindings(profile, _context):
    profile.bindings.clear()
    profile.binding_status = "UNSCANNED"


def _find_event_clip(event):
    pointer = event.as_pointer()
    for scene in getattr(bpy.data, "scenes", ()):
        settings = getattr(scene, "mmd_mouth", None)
        if settings is None:
            continue
        for profile in settings.model_profiles:
            for clip in profile.clips:
                if any(item.as_pointer() == pointer for item in clip.events):
                    return clip
    return None


def sort_clip_events(clip) -> None:
    """Keep the editable event collection in chronological order."""

    if len(clip.events) < 2:
        return
    active_pointer = None
    active_index = int(getattr(clip, "active_event_index", 0))
    if 0 <= active_index < len(clip.events):
        active_pointer = clip.events[active_index].as_pointer()
    ordered = sorted(
        list(clip.events),
        key=lambda item: (
            float(item.start_sec),
            float(item.end_sec),
            int(item.source_index),
            item.viseme_id,
        ),
    )
    for target_index, item in enumerate(ordered):
        current_index = next(
            index
            for index, current in enumerate(clip.events)
            if current.as_pointer() == item.as_pointer()
        )
        if current_index != target_index:
            clip.events.move(current_index, target_index)
    if active_pointer is not None:
        clip.active_event_index = next(
            index
            for index, item in enumerate(clip.events)
            if item.as_pointer() == active_pointer
        )


def _update_event_timeline(event, context):
    clip = _find_event_clip(event)
    if clip is None:
        return
    if event.end_sec < event.start_sec:
        event.end_sec = event.start_sec
    sort_clip_events(clip)
    _mark_timeline_stale(clip, context)


class MMDMouthVisemeEvent(PropertyGroup):
    viseme_id: EnumProperty(
        name="Viseme",
        items=VISEME_ITEMS,
        default="REST",
        update=_update_event_timeline,
    )
    start_sec: FloatProperty(
        name="Start (s)",
        min=0.0,
        default=0.0,
        precision=4,
        update=_update_event_timeline,
    )
    end_sec: FloatProperty(
        name="End (s)",
        min=0.0,
        default=0.0,
        precision=4,
        update=_update_event_timeline,
    )
    weight: FloatProperty(
        name="Weight",
        min=0.0,
        max=1.0,
        default=1.0,
        precision=4,
        update=_update_event_timeline,
    )
    confidence: FloatProperty(
        name="Confidence",
        min=0.0,
        max=1.0,
        default=0.0,
        precision=4,
    )
    source: EnumProperty(
        name="Source",
        items=SOURCE_ITEMS,
        default="G2P",
    )
    source_index: IntProperty(name="Source Index", default=-1)
    source_text: StringProperty(name="Source Text", default="")
    phoneme: StringProperty(name="Phoneme", default="")
    language_code: StringProperty(name="Language", default="")
    source_phoneme: StringProperty(name="Source Phoneme", default="")
    articulation_class: StringProperty(
        name="Articulation Class",
        default="",
    )
    priority: IntProperty(name="Priority", default=0)


class MMDMouthPhonemeSegment(PropertyGroup):
    phoneme: StringProperty(name="Canonical IPA", default="")
    source_phoneme: StringProperty(name="Source Phoneme", default="")
    start_sec: FloatProperty(
        name="Start (s)",
        min=0.0,
        default=0.0,
        precision=4,
    )
    end_sec: FloatProperty(
        name="End (s)",
        min=0.0,
        default=0.0,
        precision=4,
    )
    phoneme_type: EnumProperty(
        name="Phoneme Type",
        items=PHONEME_TYPE_ITEMS,
        default="UNKNOWN",
    )
    place: EnumProperty(
        name="Place",
        items=PHONEME_PLACE_ITEMS,
        default="UNKNOWN",
    )
    manner: EnumProperty(
        name="Manner",
        items=PHONEME_MANNER_ITEMS,
        default="UNKNOWN",
    )
    voicing: EnumProperty(
        name="Voicing",
        items=PHONEME_VOICING_ITEMS,
        default="UNKNOWN",
    )
    articulation_class: StringProperty(
        name="Articulation Class",
        default="",
    )
    viseme_id: EnumProperty(
        name="Viseme",
        items=VISEME_ITEMS,
        default="REST",
    )
    close_strength: FloatProperty(
        name="Close Strength",
        min=0.0,
        max=1.0,
        default=0.0,
        precision=4,
    )
    vowel_suppression: FloatProperty(
        name="Vowel Suppression",
        min=0.0,
        max=1.0,
        default=0.0,
        precision=4,
    )
    confidence: FloatProperty(
        name="Confidence",
        min=0.0,
        max=1.0,
        default=0.0,
        precision=4,
    )
    source_text: StringProperty(name="Source Text", default="")
    language_code: StringProperty(name="Language", default="")


class MMDMouthRecognitionCandidate(PropertyGroup):
    candidate_id: StringProperty(name="Candidate ID", default="")
    segment_id: StringProperty(name="Segment ID", default="")
    language_code: StringProperty(name="Language", default="")
    model_id: StringProperty(name="Model ID", default="")
    start_sec: FloatProperty(
        name="Start (s)",
        min=0.0,
        default=0.0,
        precision=4,
    )
    end_sec: FloatProperty(
        name="End (s)",
        min=0.0,
        default=0.0,
        precision=4,
    )
    raw_score: FloatProperty(name="Raw Score", default=0.0, precision=6)
    normalized_score: FloatProperty(
        name="Normalized Score",
        min=0.0,
        max=1.0,
        default=0.0,
        precision=6,
    )
    selection_score: FloatProperty(
        name="Selection Score",
        min=0.0,
        max=1.0,
        default=0.0,
        precision=6,
    )
    selected: BoolProperty(name="Selected", default=False)
    word_count: IntProperty(name="Word Count", min=0, default=0)
    cache_path: StringProperty(
        name="Cache Path",
        subtype="FILE_PATH",
        default="",
    )
    last_error: StringProperty(name="Last Error", default="")


class MMDMouthLanguageSegment(PropertyGroup):
    start_sec: FloatProperty(
        name="Start (s)",
        min=0.0,
        default=0.0,
        precision=4,
    )
    end_sec: FloatProperty(
        name="End (s)",
        min=0.0,
        default=0.0,
        precision=4,
    )
    language_code: StringProperty(name="Language", default="")
    model_id: StringProperty(name="Model ID", default="")
    confidence: FloatProperty(
        name="Confidence",
        min=0.0,
        max=1.0,
        default=0.0,
        precision=4,
    )
    source: EnumProperty(
        name="Source",
        items=LANGUAGE_SEGMENT_SOURCE_ITEMS,
        default="CLIP_DEFAULT",
    )
    candidate_id: StringProperty(name="Candidate ID", default="")


class MMDMouthBinding(PropertyGroup):
    viseme_id: EnumProperty(
        name="Viseme",
        items=VISEME_ITEMS,
        default="A",
    )
    enabled: BoolProperty(name="Enabled", default=True)
    target_kind: EnumProperty(
        name="Target Kind",
        items=TARGET_KIND_ITEMS,
        default="SHAPE_KEY",
    )
    target_object: PointerProperty(name="Target Object", type=bpy.types.Object)
    target_key_name: StringProperty(name="Shape Key Name", default="")
    target_property_name: StringProperty(name="Custom Property", default="")
    target_data_path: StringProperty(name="Data Path", default="")
    scale: FloatProperty(name="Scale", default=1.0, precision=4)
    offset: FloatProperty(name="Offset", default=0.0, precision=4)
    minimum: FloatProperty(name="Minimum", default=0.0, precision=4)
    maximum: FloatProperty(name="Maximum", default=1.0, precision=4)
    invert: BoolProperty(name="Invert", default=False)
    note: StringProperty(name="Note", default="")


class MMDMouthGeneratedAsset(PropertyGroup):
    asset_id: StringProperty(name="Asset ID", default="")
    asset_kind: EnumProperty(
        name="Asset Kind",
        items=ASSET_KIND_ITEMS,
        default="ACTION",
    )
    owner_object: PointerProperty(name="Owner Object", type=bpy.types.Object)
    action_name: StringProperty(name="Action Name", default="")
    strip_name: StringProperty(name="NLA Strip Name", default="")
    controller_object: PointerProperty(
        name="Controller Object",
        type=bpy.types.Object,
    )
    generated_at_schema: IntProperty(
        name="Generated Schema",
        default=SCHEMA_VERSION,
    )


class MMDMouthRecognizerModel(PropertyGroup):
    model_id: StringProperty(name="Model ID", default="")
    display_name: StringProperty(name="Display Name", default="Vosk Model")
    language_code: StringProperty(name="Language", default="")
    is_bundled: BoolProperty(name="Bundled", default=False)
    model_path: StringProperty(
        name="Model Directory",
        subtype="DIR_PATH",
        default="",
    )
    enabled: BoolProperty(name="Enabled", default=True)
    priority: IntProperty(name="Priority", default=0)
    calibration_bias: FloatProperty(
        name="Calibration Bias",
        default=0.0,
        precision=6,
    )
    calibration_temperature: FloatProperty(
        name="Calibration Temperature",
        min=0.000001,
        default=1.0,
        precision=6,
    )


class MMDMouthClip(PropertyGroup):
    clip_id: StringProperty(name="Clip ID", default="")
    display_name: StringProperty(name="Display Name", default="New Clip")
    audio_path: StringProperty(
        name="Audio",
        subtype="FILE_PATH",
        default="",
        update=_update_audio_path,
    )
    audio_hash: StringProperty(name="Audio Hash", default="")
    transcoded_audio_path: StringProperty(
        name="Converted Audio",
        subtype="FILE_PATH",
        default="",
    )
    audio_transcode_error: StringProperty(name="Audio Conversion Error", default="")
    start_frame: IntProperty(
        name="Start Frame",
        min=0,
        default=1,
        update=_update_start_frame,
    )
    audio_offset_sec: FloatProperty(
        name="Audio Offset (s)",
        default=0.0,
        precision=4,
        update=_update_audio_window,
    )
    duration_sec: FloatProperty(
        name="Duration (s)",
        min=0.0,
        default=0.0,
        precision=4,
        update=_update_audio_window,
    )
    audio_volume: FloatProperty(
        name="Preview Volume",
        description="Playback volume of the owned sequencer audio strip",
        min=0.0,
        max=10.0,
        soft_max=2.0,
        default=1.0,
        precision=3,
        update=_update_audio_volume,
    )
    mouth_strength: FloatProperty(
        name="Mouth Strength",
        description="Multiplier applied when baking mouth animation",
        min=0.0,
        max=2.0,
        soft_max=1.5,
        default=1.0,
        precision=3,
    )
    attack_ms: FloatProperty(
        name="Transition In (ms)",
        description="Time for a mouth shape to blend in before its event",
        min=0.0,
        max=1000.0,
        default=DEFAULT_ATTACK_MS,
        precision=1,
        update=_mark_timeline_stale,
    )
    release_ms: FloatProperty(
        name="Transition Out (ms)",
        description="Time for a mouth shape to blend out after its event",
        min=0.0,
        max=1000.0,
        default=DEFAULT_RELEASE_MS,
        precision=1,
        update=_mark_timeline_stale,
    )
    hold_ratio: FloatProperty(
        name="Hold Ratio",
        description="Preferred portion of an event kept at full strength",
        min=0.0,
        max=1.0,
        default=DEFAULT_HOLD_RATIO,
        precision=3,
        update=_mark_timeline_stale,
    )
    easing_mode: EnumProperty(
        name="Mouth Blend",
        description="Envelope easing and adjacent-vowel blending mode",
        items=EASING_MODE_ITEMS,
        default="SMOOTHSTEP",
        update=_mark_timeline_stale,
    )
    audio_strip_name: StringProperty(name="Audio Strip", default="")
    audio_preview_error: StringProperty(name="Audio Preview Error", default="")
    language_code: EnumProperty(
        name="Language",
        items=LANGUAGE_ITEMS,
        default=DEFAULT_LANGUAGE_CODE,
        update=_mark_timeline_stale,
    )
    backend_id: StringProperty(
        name="Backend",
        default=DEFAULT_BACKEND_ID,
        update=_mark_timeline_stale,
    )
    recognizer_model_id: StringProperty(
        name="Recognizer Model",
        default="",
    )
    recognizer_model_filter: StringProperty(
        name="Model Filter",
        default="",
        update=_mark_timeline_stale,
    )
    selected_candidate_id: StringProperty(
        name="Selected Candidate",
        default="",
    )
    candidate_scoring_version: IntProperty(
        name="Candidate Scoring Version",
        default=CANDIDATE_SCORING_VERSION,
    )
    status: EnumProperty(
        name="Status",
        items=CLIP_STATUS_ITEMS,
        default="DRAFT",
    )
    generation_mode: EnumProperty(
        name="Generation Mode",
        items=GENERATION_MODE_ITEMS,
        default=DEFAULT_GENERATION_MODE,
    )
    timeline_version: IntProperty(
        name="Timeline Version",
        default=TIMELINE_VERSION,
    )
    ipa_normalization_version: IntProperty(
        name="IPA Normalization Version",
        default=IPA_NORMALIZATION_VERSION,
    )
    render_fps: IntProperty(name="Render FPS", min=0, default=0)
    render_fps_base: FloatProperty(
        name="Render FPS Base",
        min=0.0,
        default=0.0,
        precision=6,
    )
    event_count: IntProperty(name="Event Count", default=0)
    source_transcript: StringProperty(name="Transcript", default="")
    cache_path: StringProperty(
        name="Cache Path",
        subtype="FILE_PATH",
        default="",
    )
    last_error: StringProperty(name="Last Error", default="")
    phoneme_count: IntProperty(name="Phoneme Count", min=0, default=0)
    events: CollectionProperty(type=MMDMouthVisemeEvent)
    phonemes: CollectionProperty(type=MMDMouthPhonemeSegment)
    recognition_candidates: CollectionProperty(
        type=MMDMouthRecognitionCandidate,
    )
    language_segments: CollectionProperty(type=MMDMouthLanguageSegment)
    assets: CollectionProperty(type=MMDMouthGeneratedAsset)
    show_timeline: BoolProperty(name="Show Timeline", default=False)
    active_event_index: IntProperty(name="Active Timeline Event", min=0, default=0)


class MMDMouthModelProfile(PropertyGroup):
    profile_id: StringProperty(name="Profile ID", default="")
    display_name: StringProperty(name="Display Name", default="New Model")
    root_object: PointerProperty(
        name="Root Object",
        type=bpy.types.Object,
        update=_reset_model_bindings,
    )
    adapter_id: StringProperty(
        name="Adapter",
        default="generic_shape_key",
    )
    binding_status: EnumProperty(
        name="Binding Status",
        items=BINDING_STATUS_ITEMS,
        default="UNSCANNED",
    )
    auto_discovered: BoolProperty(name="Auto Discovered", default=False)
    bindings: CollectionProperty(type=MMDMouthBinding)
    clips: CollectionProperty(type=MMDMouthClip)
    active_clip_index: IntProperty(name="Active Clip", default=0)


class MMDMouthSceneSettings(PropertyGroup):
    schema_version: IntProperty(
        name="Schema Version",
        default=SCHEMA_VERSION,
    )
    active_model_index: IntProperty(name="Active Model", default=0)
    default_backend_id: StringProperty(
        name="Default Backend",
        default=DEFAULT_BACKEND_ID,
    )
    default_language_code: EnumProperty(
        name="Default Language",
        items=LANGUAGE_ITEMS,
        default=DEFAULT_LANGUAGE_CODE,
    )
    default_generation_mode: EnumProperty(
        name="Default Generation Mode",
        items=GENERATION_MODE_ITEMS,
        default=DEFAULT_GENERATION_MODE,
    )
    default_attack_ms: FloatProperty(
        name="Attack (ms)",
        min=0.0,
        max=1000.0,
        default=DEFAULT_ATTACK_MS,
        precision=2,
    )
    default_release_ms: FloatProperty(
        name="Release (ms)",
        min=0.0,
        max=1000.0,
        default=DEFAULT_RELEASE_MS,
        precision=2,
    )
    default_hold_ratio: FloatProperty(
        name="Hold Ratio",
        min=0.0,
        max=1.0,
        default=DEFAULT_HOLD_RATIO,
        precision=3,
    )
    cache_directory: StringProperty(
        name="Cache Directory",
        subtype="DIR_PATH",
        default="",
    )
    worker_mode: EnumProperty(
        name="Worker Mode",
        items=WORKER_MODE_ITEMS,
        default=DEFAULT_WORKER_MODE,
    )
    worker_executable: StringProperty(
        name="Worker Executable",
        subtype="FILE_PATH",
        default="",
    )
    worker_python: StringProperty(
        name="Worker Python",
        subtype="FILE_PATH",
        default="",
    )
    worker_status: EnumProperty(
        name="Worker Status",
        items=WORKER_STATUS_ITEMS,
        default="UNKNOWN",
    )
    worker_protocol_version: IntProperty(
        name="Worker Protocol",
        default=WORKER_PROTOCOL_VERSION,
    )
    worker_display_name: StringProperty(
        name="Worker",
        default="Not checked",
    )
    worker_last_check: StringProperty(
        name="Worker Last Check",
        default="",
    )
    worker_last_error: StringProperty(
        name="Worker Error",
        default="",
    )
    worker_task_id: StringProperty(
        name="Worker Task",
        default="",
    )
    show_advanced_runtime: BoolProperty(
        name="Advanced Runtime Settings",
        default=False,
    )
    show_advanced_models: BoolProperty(
        name="Advanced Recognition Models",
        default=False,
    )
    is_busy: BoolProperty(name="Busy", default=False)
    last_error: StringProperty(name="Last Error", default="")
    model_profiles: CollectionProperty(type=MMDMouthModelProfile)
    recognizer_models: CollectionProperty(type=MMDMouthRecognizerModel)


CLASSES = (
    MMDMouthVisemeEvent,
    MMDMouthPhonemeSegment,
    MMDMouthRecognitionCandidate,
    MMDMouthLanguageSegment,
    MMDMouthBinding,
    MMDMouthGeneratedAsset,
    MMDMouthRecognizerModel,
    MMDMouthClip,
    MMDMouthModelProfile,
    MMDMouthSceneSettings,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mmd_mouth = PointerProperty(type=MMDMouthSceneSettings)


def unregister():
    if hasattr(bpy.types.Scene, "mmd_mouth"):
        del bpy.types.Scene.mmd_mouth
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
