"""Shared identifiers for the persisted MMD Mouth schema."""

ADDON_ID = "mmd_mouth"
ADDON_VERSION = (0, 4, 2)
SCHEMA_VERSION = 5
TIMELINE_VERSION = 4
CANDIDATE_SCORING_VERSION = 2
IPA_NORMALIZATION_VERSION = 1
MIN_BLENDER_VERSION = (5, 2, 0)
WORKER_PROTOCOL_VERSION = 2

DEFAULT_BACKEND_ID = "vosk"
DEFAULT_LANGUAGE_CODE = "zh-CN"
DEFAULT_GENERATION_MODE = "BAKE"
DEFAULT_WORKER_MODE = "AUTO"
DEFAULT_ATTACK_MS = 70.0
DEFAULT_RELEASE_MS = 90.0
DEFAULT_HOLD_RATIO = 0.55

LANGUAGE_ITEMS = (
    ("zh-CN", "Chinese", "Use the bundled Chinese Vosk model"),
    ("ja-JP", "Japanese", "Use the bundled Japanese Vosk model"),
    ("en-US", "English (US)", "Use the bundled US English Vosk model"),
    (
        "AUTO",
        "Auto Compare",
        "Run enabled language models and select one whole-clip candidate",
    ),
)

WORKER_MODE_ITEMS = (
    (
        "AUTO",
        "Automatic",
        "Use the packaged worker, then the development worker if available",
    ),
    (
        "PACKAGED",
        "Packaged Worker",
        "Require the worker shipped with the add-on",
    ),
    (
        "PYTHON",
        "Development Python",
        "Run the worker module with a dedicated Python interpreter",
    ),
    (
        "CUSTOM",
        "Custom Executable",
        "Run a manually selected worker executable",
    ),
)

WORKER_STATUS_ITEMS = (
    ("UNKNOWN", "Unknown", "The worker has not been checked"),
    ("READY", "Ready", "The worker can be started"),
    ("RUNNING", "Running", "A worker job is active"),
    ("MISSING", "Missing", "No usable worker was found"),
    ("ERROR", "Error", "The worker failed its last check or job"),
)

VISEME_ITEMS = (
    ("REST", "Rest", "Neutral or silent mouth state"),
    ("CLOSED", "Closed", "Closed-mouth consonant state"),
    ("A", "A", "Open A vowel"),
    ("I", "I", "Spread I vowel"),
    ("U", "U", "Rounded U vowel"),
    ("E", "E", "E vowel"),
    ("O", "O", "Rounded O vowel"),
)

SOURCE_ITEMS = (
    ("ASR", "ASR", "Produced from speech recognition"),
    ("G2P", "G2P", "Produced by grapheme-to-phoneme conversion"),
    ("ALIGNER", "Aligner", "Produced by forced alignment"),
    ("MANUAL", "Manual", "Edited by the user"),
)

LANGUAGE_SEGMENT_SOURCE_ITEMS = (
    ("CLIP_DEFAULT", "Clip Default", "Inherited from the clip language"),
    ("LID", "Language ID", "Detected by a future language router"),
    ("MODEL_SCORE", "Model Score", "Selected from language-model candidates"),
    ("MANUAL", "Manual", "Specified by the user"),
)

PHONEME_TYPE_ITEMS = (
    ("VOWEL", "Vowel", "A vowel phoneme"),
    ("CONSONANT", "Consonant", "A consonant phoneme"),
    ("SILENCE", "Silence", "Silence or non-speech"),
    ("UNKNOWN", "Unknown", "An unclassified phoneme"),
)

PHONEME_PLACE_ITEMS = (
    ("BILABIAL", "Bilabial", "Both lips"),
    ("LABIODENTAL", "Labiodental", "Lower lip and upper teeth"),
    ("DENTAL", "Dental", "Tongue and teeth"),
    ("ALVEOLAR", "Alveolar", "Tongue and alveolar ridge"),
    ("POSTALVEOLAR", "Postalveolar", "Behind the alveolar ridge"),
    ("PALATAL", "Palatal", "Tongue and hard palate"),
    ("VELAR", "Velar", "Tongue and soft palate"),
    ("GLOTTAL", "Glottal", "Glottis"),
    ("VOWEL", "Vowel", "Vowel resonance region"),
    ("UNKNOWN", "Unknown", "Unknown place"),
)

PHONEME_MANNER_ITEMS = (
    ("VOWEL", "Vowel", "Vowel"),
    ("STOP", "Stop", "Plosive or stop"),
    ("NASAL", "Nasal", "Nasal"),
    ("FRICATIVE", "Fricative", "Fricative"),
    ("AFFRICATE", "Affricate", "Affricate"),
    ("APPROXIMANT", "Approximant", "Approximant or glide"),
    ("LATERAL", "Lateral", "Lateral"),
    ("SILENCE", "Silence", "Silence or non-speech"),
    ("UNKNOWN", "Unknown", "Unknown manner"),
)

PHONEME_VOICING_ITEMS = (
    ("VOICED", "Voiced", "Voiced"),
    ("VOICELESS", "Voiceless", "Voiceless"),
    ("UNKNOWN", "Unknown", "Unknown voicing"),
)

BINDING_STATUS_ITEMS = (
    ("UNSCANNED", "Unscanned", "The model has not been inspected"),
    ("VALID", "Valid", "All enabled bindings are valid"),
    ("WARNING", "Warning", "The model can generate with warnings"),
    ("ERROR", "Error", "The model cannot generate safely"),
)

TARGET_KIND_ITEMS = (
    ("SHAPE_KEY", "Shape Key", "A shape-key value on an object"),
    ("CUSTOM_PROPERTY", "Custom Property", "An object custom property"),
    ("DATA_PATH", "RNA Data Path", "An explicit Blender RNA data path"),
)

GENERATION_MODE_ITEMS = (
    ("BAKE", "Bake", "Write animation curves to model targets"),
    ("DRIVER", "Driver", "Animate controller properties and use drivers"),
)

EASING_MODE_ITEMS = (
    (
        "LINEAR",
        "Linear",
        "Keep direct linear attack/release without vowel crossfade",
    ),
    (
        "SMOOTHSTEP",
        "Smoothstep",
        "Cubic smooth transition with adjacent-vowel crossfade",
    ),
    (
        "SINE",
        "Sine",
        "Cosine smooth transition with adjacent-vowel crossfade",
    ),
    (
        "EASE_IN",
        "Ease In",
        "Slow entry and faster exit with adjacent-vowel crossfade",
    ),
    (
        "EASE_OUT",
        "Ease Out",
        "Faster entry and slower exit with adjacent-vowel crossfade",
    ),
)

CLIP_STATUS_ITEMS = (
    ("DRAFT", "Draft", "The clip has not been recognized"),
    ("QUEUED", "Queued", "The recognition job is waiting to run"),
    ("RUNNING", "Running", "The recognition job is running"),
    ("RECOGNIZED", "Recognized", "A timeline exists but is not baked"),
    ("BAKED", "Baked", "Animation assets were generated"),
    ("STALE", "Stale", "Inputs or algorithm versions changed"),
    ("ERROR", "Error", "The last generation attempt failed"),
)

ASSET_KIND_ITEMS = (
    ("ACTION", "Action", "A generated Blender Action"),
    ("NLA_STRIP", "NLA Strip", "A generated NLA strip"),
    ("CONTROLLER", "Controller", "A generated controller object"),
)
