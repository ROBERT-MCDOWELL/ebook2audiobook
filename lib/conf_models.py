import os, re
from lib.conf import tts_dir, voices_dir

loaded_tts = {}
xtts_builtin_speakers_list = {}

TTS_ENGINES = {
    "ZONOS": "zonos",
    "GPTSOVITS": "gptsovits",
    "XTTS": "xtts",
    "BARK": "bark",
    "TORTOISE": "tortoise",
    "PIPER": "piper",
    "VITS": "vits",
    "FAIRSEQ": "fairseq",
    "GLOWTTS": "glowtts",
    "TACOTRON": "tacotron",
    "YOURTTS": "yourtts"
}

TTS_VOICE_CONVERSION = {
    "freevc24": {"path": "voice_conversion_models/multilingual/vctk/freevc24", "samplerate": 24000},
    "knnvc": {"path": "voice_conversion_models/multilingual/multi-dataset/knnvc", "samplerate": 16000},
    "openvoice_v1": {"path": "voice_conversion_models/multilingual/multi-dataset/openvoice_v1", "samplerate": 22050},
    "openvoice_v2": {"path": "voice_conversion_models/multilingual/multi-dataset/openvoice_v2", "samplerate": 22050}
}

TTS_SML = {
    "break": {"static": "[break]", "paired": False},
    "pause": {"static": "[pause]", "paired": False},
    "voice": {"paired": True},
    # zonos only (ignored by the other engines): [emotion:sadness]...[/emotion] or a mix
    # [emotion:sadness=0.7,neutral=0.3]; values in zonos order, aliases for the obvious words
    "emotion": {
        "paired": True,
        "values": ["happiness", "sadness", "disgust", "fear", "surprise", "anger", "other", "neutral"],
        "aliases": {"happy": "happiness", "joy": "happiness", "sad": "sadness", "disgusted": "disgust", "afraid": "fear", "scared": "fear", "surprised": "surprise", "angry": "anger"}
    }
}

sml_escape_tag = 0xE000
sml_tag_keys = '|'.join(map(re.escape, TTS_SML.keys()))

SML_TAG_PATTERN = re.compile(
    rf'''
    \[
        \s*
        (?P<close>/)?
        \s*
        (?P<tag>{sml_tag_keys})
        (?:\s*:\s*(?P<value>.*?))?
        \s*
    \]
    ''',
    re.VERBOSE | re.DOTALL
)

IPA_REMAINING_PATTERN = re.compile(
    r'['
    r'\u0250-\u02AF'  # IPA Extensions
    r'\u1D00-\u1D7F'  # Phonetic Extensions
    r'\u1D80-\u1DBF'  # Phonetic Extensions Supplement
    r'\u0300-\u036F'  # Combining Diacritical Marks
    r'\u02B0-\u02FF'  # Spacing Modifier Letters
    r'\u2070-\u209F'  # Superscripts (ⁿ etc.)
    r'\u0278\u0281'   # specific IPA symbols
    r'ʼ'
    r']+'
)

default_tts_engine = TTS_ENGINES['XTTS']
default_fine_tuned = 'internal'
default_vc_model = TTS_VOICE_CONVERSION['knnvc']['path']
default_voice_detection_model = 'drewThomasson/segmentation'
default_speaker = os.path.join(voices_dir, 'eng', 'adult', 'male', 'KumarDahl.wav')

tts_engines_from_coqui = [TTS_ENGINES['XTTS'], TTS_ENGINES['BARK'], TTS_ENGINES['TORTOISE'], TTS_ENGINES['VITS'], TTS_ENGINES['FAIRSEQ'], TTS_ENGINES['GLOWTTS'], TTS_ENGINES['TACOTRON'], TTS_ENGINES['YOURTTS']]
tts_engines_with_inner_speaker = [TTS_ENGINES['PIPER'], TTS_ENGINES['VITS'], TTS_ENGINES['FAIRSEQ'], TTS_ENGINES['GLOWTTS'], TTS_ENGINES['TACOTRON'], TTS_ENGINES['YOURTTS']]
tts_engines_with_custom_model = (TTS_ENGINES['PIPER'], TTS_ENGINES['XTTS'], TTS_ENGINES['VITS'], TTS_ENGINES['FAIRSEQ'])

max_custom_model = 100
max_custom_voices = 1000

default_engine_settings = {
    TTS_ENGINES['ZONOS']: {
        # runs in its own uv venv (lib/classes/tts_engines/venvs/zonos) behind a persistent worker
        "repo": "Zyphra/Zonos-v0.1-transformer",
        "repo_hybrid": "Zyphra/Zonos-v0.1-hybrid",
        "source": "https://github.com/Zyphra/Zonos/archive/bc40d98e1e1ab54fc65c483be127a90e3c7c0645.tar.gz",
        "python": "3.12",
        "torch_min": "2.2.2",
        # robust languages only (most of the 200k h are en, then zh, ja, fr, es, de); values are espeak codes
        "languages": {"eng": "en-us", "deu": "de", "fra": "fr-fr", "jpn": "ja", "spa": "es", "zho": "cmn"},
        "samplerate": 44100,
        # conditioning and sampling defaults are zonos' own make_cond_dict() / generate() defaults
        # (fmax 22050 is upstream's value for voice cloning, which e2a always does)
        "emotion_enabled": True,
        # Happiness, Sadness, Disgust, Fear, Surprise, Anger, Other, Neutral
        "emotion": [0.3077, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.2564, 0.3077],
        "speaking_rate": 15.0,
        "pitch_std": 20.0,
        "fmax": 22050.0,
        "cfg_scale": 2.0,
        # sampling is zonos' own generate() default; linear > 0 adds the unified sampler's
        # linear term on top (below 1 = more varied delivery), 0 leaves zonos untouched
        "linear": 0.0,
        "max_new_tokens": 86 * 30,
        "files": [],
        "voice": default_speaker,
        "voices": {},
        "rating": {"VRAM": 6, "CPU": 1, "RAM": 8, "Realism": 5}
    },
    TTS_ENGINES['GPTSOVITS']: {
        "repo": "lj1995/GPT-SoVITS",
        "source": "https://github.com/RVC-Boss/GPT-SoVITS/archive/e7cd61ec3dcc9a34089f50ed169e3103a16ad675.tar.gz",
        "python": "3.12",
        "torch_min": "2.2.2",
        "torch": "2.7.1",
        "torch_rocm": "rocm6.3",
        "packages": ["scipy", "librosa==0.10.2", "numba", "pytorch-lightning>=2.4", "ffmpeg-python", "onnxruntime", "tqdm", "cn2an", "pypinyin", "pyopenjtalk-plus", "g2p_en", "sentencepiece", "transformers>=4.51,<5", "peft<0.18.0", "chardet", "PyYAML", "psutil", "jieba", "split-lang", "fast_langdetect>=0.3.1", "wordsegment", "rotary_embedding_torch", "ToJyutping", "g2pk2", "ko_pron", "opencc", "python_mecab_ko; sys_platform != 'win32'", "x_transformers", "torchmetrics<=1.5", "pydantic<=2.10.6", "av>=11", "einops", "huggingface_hub", "loguru", "rich", "resampy", "soundfile", "nltk", "faster-whisper", "ctranslate2>=4.0,<5"],
        "packages_sdist": ["jieba", "g2p-en", "distance"],
        "weights": ["chinese-roberta-wwm-ext-large/*", "chinese-hubert-base/*", "s1v3.ckpt", "sv/pretrained_eres2netv2w24s4ep4.ckpt"],
        "ref_min": 3.2,
        "ref_max": 9.5,
        "asr_model": "large-v3-turbo",
        "languages": {"eng": "en", "zho": "zh", "jpn": "ja", "kor": "ko"},
        "samplerate": 32000,
        "speed": 1.0,
        "top_k": 15,
        "top_p": 1.0,
        "temperature": 1.0,
        "repetition_penalty": 1.35,
        "files": [],
        "voice": default_speaker,
        "voices": {},
        "rating": {"VRAM": 4, "CPU": 2, "RAM": 8, "Realism": 4}
    },
    TTS_ENGINES['XTTS']: {
        "repo": "coqui/XTTS-v2",
        "languages": {"ara": "ar", "ces": "cs", "deu": "de", "eng": "en", "fra": "fr", "hin": "hi", "hun": "hu", "ita": "it", "jpn": "ja", "kor": "ko", "nld": "nl", "pol": "pl", "por": "pt", "rus": "ru", "spa": "es", "tur": "tr", "zho": "zh-cn"},
        "samplerate": 24000,
        "temperature": 0.75,
        "length_penalty": 1.0,
        "num_beams": 1,
        "repetition_penalty": 2.0,
        "top_k": 40,
        "top_p": 0.95,
        "speed": 1.0,
        "enable_text_splitting": False,
        "files": ['config.json', 'model.pth', 'vocab.json', 'ref.wav'],
        "voice": default_speaker,
        "voices": {
            "ClaribelDervla": "Claribel Dervla", "DaisyStudious": "Daisy Studious", "GracieWise": "Gracie Wise",
            "TammieEma": "Tammie Ema", "AlisonDietlinde": "Alison Dietlinde", "AnaFlorence": "Ana Florence",
            "AnnmarieNele": "Annmarie Nele", "AsyaAnara": "Asya Anara", "BrendaStern": "Brenda Stern",
            "GittaNikolina": "Gitta Nikolina", "HenrietteUsha": "Henriette Usha", "SofiaHellen": "Sofia Hellen",
            "TammyGrit": "Tammy Grit", "TanjaAdelina": "Tanja Adelina", "VjollcaJohnnie": "Vjollca Johnnie",
            "AndrewChipper": "Andrew Chipper", "BadrOdhiambo": "Badr Odhiambo", "DionisioSchuyler": "Dionisio Schuyler",
            "RoystonMin": "Royston Min", "ViktorEka": "Viktor Eka", "AbrahanMack": "Abrahan Mack",
            "AddeMichal": "Adde Michal", "BaldurSanjin": "Baldur Sanjin", "CraigGutsy": "Craig Gutsy",
            "DamienBlack": "Damien Black", "GilbertoMathias": "Gilberto Mathias", "IlkinUrbano": "Ilkin Urbano",
            "KazuhikoAtallah": "Kazuhiko Atallah", "LudvigMilivoj": "Ludvig Milivoj", "SuadQasim": "Suad Qasim",
            "TorcullDiarmuid": "Torcull Diarmuid", "ViktorMenelaos": "Viktor Menelaos", "ZacharieAimilios": "Zacharie Aimilios",
            "NovaHogarth": "Nova Hogarth", "MajaRuoho": "Maja Ruoho", "UtaObando": "Uta Obando",
            "LidiyaSzekeres": "Lidiya Szekeres", "ChandraMacFarland": "Chandra MacFarland", "SzofiGranger": "Szofi Granger",
            "CamillaHolmström": "Camilla Holmström", "LilyaStainthorpe": "Lilya Stainthorpe", "ZofijaKendrick": "Zofija Kendrick",
            "NarelleMoon": "Narelle Moon", "BarboraMacLean": "Barbora MacLean", "AlexandraHisakawa": "Alexandra Hisakawa",
            "AlmaMaría": "Alma María", "RosemaryOkafor": "Rosemary Okafor", "IgeBehringer": "Ige Behringer",
            "FilipTraverse": "Filip Traverse", "DamjanChapman": "Damjan Chapman", "WulfCarlevaro": "Wulf Carlevaro",
            "AaronDreschner": "Aaron Dreschner", "KumarDahl": "Kumar Dahl", "EugenioMataracı": "Eugenio Mataracı",
            "FerranSimen": "Ferran Simen", "XavierHayasaka": "Xavier Hayasaka", "LuisMoray": "Luis Moray",
            "MarcosRudaski": "Marcos Rudaski"
        },
        "rating": {"VRAM": 4, "CPU": 2, "RAM": 4, "Realism": 5}
    },
    TTS_ENGINES['BARK']: {
        "languages": {"deu": "de", "eng": "en", "fra": "fr", "hin": "hi", "ita": "it", "jpn": "ja", "kor": "ko", "pol": "pl", "por": "pt", "rus": "ru", "spa": "es", "tur": "tr", "zho": "zh-cn"},
        "samplerate": 24000,
        "text_temp": 0.22,
        "waveform_temp": 0.44,
        "files": [],
        "speakers_path": os.path.join(voices_dir, '__bark'),
        "voice": default_speaker,
        "voices": {
            "de_speaker_0": "Speaker 0", "de_speaker_1": "Speaker 1", "de_speaker_2": "Speaker 2",
            "de_speaker_3": "Speaker 3", "de_speaker_4": "Speaker 4", "de_speaker_5": "Speaker 5",
            "de_speaker_6": "Speaker 6", "de_speaker_7": "Speaker 7", "de_speaker_8": "Speaker 8",
            "de_speaker_9": "Speaker 9", "en_speaker_0": "Speaker 0", "en_speaker_1": "Speaker 1",
            "en_speaker_2": "Speaker 2", "en_speaker_3": "Speaker 3", "en_speaker_4": "Speaker 4",
            "en_speaker_5": "Speaker 5", "en_speaker_6": "Speaker 6", "en_speaker_7": "Speaker 7",
            "en_speaker_8": "Speaker 8", "en_speaker_9": "Speaker 9", "es_speaker_0": "Speaker 0",
            "es_speaker_1": "Speaker 1", "es_speaker_2": "Speaker 2", "es_speaker_3": "Speaker 3",
            "es_speaker_4": "Speaker 4", "es_speaker_5": "Speaker 5", "es_speaker_6": "Speaker 6",
            "es_speaker_7": "Speaker 7", "es_speaker_8": "Speaker 8", "es_speaker_9": "Speaker 9",
            "fr_speaker_0": "Speaker 0", "fr_speaker_1": "Speaker 1", "fr_speaker_2": "Speaker 2",
            "fr_speaker_3": "Speaker 3", "fr_speaker_4": "Speaker 4", "fr_speaker_5": "Speaker 5",
            "fr_speaker_6": "Speaker 6", "fr_speaker_7": "Speaker 7", "fr_speaker_8": "Speaker 8",
            "fr_speaker_9": "Speaker 9", "hi_speaker_0": "Speaker 0", "hi_speaker_1": "Speaker 1",
            "hi_speaker_2": "Speaker 2", "hi_speaker_3": "Speaker 3", "hi_speaker_4": "Speaker 4",
            "hi_speaker_5": "Speaker 5", "hi_speaker_6": "Speaker 6", "hi_speaker_7": "Speaker 7",
            "hi_speaker_8": "Speaker 8", "hi_speaker_9": "Speaker 9", "it_speaker_0": "Speaker 0",
            "it_speaker_1": "Speaker 1", "it_speaker_2": "Speaker 2", "it_speaker_3": "Speaker 3",
            "it_speaker_4": "Speaker 4", "it_speaker_5": "Speaker 5", "it_speaker_6": "Speaker 6",
            "it_speaker_7": "Speaker 7", "it_speaker_8": "Speaker 8", "it_speaker_9": "Speaker 9",
            "ja_speaker_0": "Speaker 0", "ja_speaker_1": "Speaker 1", "ja_speaker_2": "Speaker 2",
            "ja_speaker_3": "Speaker 3", "ja_speaker_4": "Speaker 4", "ja_speaker_5": "Speaker 5",
            "ja_speaker_6": "Speaker 6", "ja_speaker_7": "Speaker 7", "ja_speaker_8": "Speaker 8",
            "ja_speaker_9": "Speaker 9", "ko_speaker_0": "Speaker 0", "ko_speaker_1": "Speaker 1",
            "ko_speaker_2": "Speaker 2", "ko_speaker_3": "Speaker 3", "ko_speaker_4": "Speaker 4",
            "ko_speaker_5": "Speaker 5", "ko_speaker_6": "Speaker 6", "ko_speaker_7": "Speaker 7",
            "ko_speaker_8": "Speaker 8", "ko_speaker_9": "Speaker 9", "pl_speaker_0": "Speaker 0",
            "pl_speaker_1": "Speaker 1", "pl_speaker_2": "Speaker 2", "pl_speaker_3": "Speaker 3",
            "pl_speaker_4": "Speaker 4", "pl_speaker_5": "Speaker 5", "pl_speaker_6": "Speaker 6",
            "pl_speaker_7": "Speaker 7", "pl_speaker_8": "Speaker 8", "pl_speaker_9": "Speaker 9",
            "pt_speaker_0": "Speaker 0", "pt_speaker_1": "Speaker 1", "pt_speaker_2": "Speaker 2",
            "pt_speaker_3": "Speaker 3", "pt_speaker_4": "Speaker 4", "pt_speaker_5": "Speaker 5",
            "pt_speaker_6": "Speaker 6", "pt_speaker_7": "Speaker 7", "pt_speaker_8": "Speaker 8",
            "pt_speaker_9": "Speaker 9", "ru_speaker_0": "Speaker 0", "ru_speaker_1": "Speaker 1",
            "ru_speaker_2": "Speaker 2", "ru_speaker_3": "Speaker 3", "ru_speaker_4": "Speaker 4",
            "ru_speaker_5": "Speaker 5", "ru_speaker_6": "Speaker 6", "ru_speaker_7": "Speaker 7",
            "ru_speaker_8": "Speaker 8", "ru_speaker_9": "Speaker 9", "tr_speaker_0": "Speaker 0",
            "tr_speaker_1": "Speaker 1", "tr_speaker_2": "Speaker 2", "tr_speaker_3": "Speaker 3",
            "tr_speaker_4": "Speaker 4", "tr_speaker_5": "Speaker 5", "tr_speaker_6": "Speaker 6",
            "tr_speaker_7": "Speaker 7", "tr_speaker_8": "Speaker 8", "tr_speaker_9": "Speaker 9",
            "zh_speaker_0": "Speaker 0", "zh_speaker_1": "Speaker 1", "zh_speaker_2": "Speaker 2",
            "zh_speaker_3": "Speaker 3", "zh_speaker_4": "Speaker 4", "zh_speaker_5": "Speaker 5",
            "zh_speaker_6": "Speaker 6", "zh_speaker_7": "Speaker 7", "zh_speaker_8": "Speaker 8",
            "zh_speaker_9": "Speaker 9"
        },
        "rating": {"VRAM": 6, "CPU": 1, "RAM": 6, "Realism": 4}
    },
    TTS_ENGINES['TORTOISE']: {
        "languages": {"eng": "en"},
        "samplerate": 24000,
        "files": [],
        "voice": default_speaker,
        "voices": {},
        "rating": {"VRAM": 6, "CPU": 2, "RAM": 6, "Realism": 4}
    },
    TTS_ENGINES['PIPER']: {
        "languages": {
            "ara": "ar_JO", "cat": "ca_ES", "ces": "cs_CZ", "cym": "cy_GB", "dan": "da_DK",
            "deu": "de_DE", "ell": "el_GR", "eng": "en_GB", "spa": "es_ES", "fas": "fa_IR",
            "fin": "fi_FI", "fra": "fr_FR", "hun": "hu_HU", "isl": "is_IS", "ita": "it_IT",
            "kat": "ka_GE", "kaz": "kk_KZ", "ltz": "lb_LU", "lav": "lv_LV", "nep": "ne_NP",
            "nld": "nl_NL", "nob": "no_NO", "pol": "pl_PL", "por": "pt_PT", "ron": "ro_RO",
            "rus": "ru_RU", "slk": "sk_SK", "slv": "sl_SI", "srp": "sr_RS", "swe": "sv_SE",
            "swa": "sw_CD", "tur": "tr_TR", "ukr": "uk_UA", "urd": "ur_PK", "vie": "vi_VN",
            "zho": "zh_CN"
        },
        "samplerate": 22050,
        "files": ['config.onnx.json', 'model.onnx', 'ref.wav'],
        "speakers_path": os.path.join(voices_dir, '__piper'),
        "voice": None,
        "voices": {
            "ar_JO-kareem-medium":              "Kareem",
            "ca_ES-upc_ona-medium":             "Ona",
            "cs_CZ-jirka-medium":               "Jirka",
            "cy_GB-gwryw_gogleddol-medium":     "Gwryw Gogleddol",
            "cy_GB-bu_tts-medium":              "Bu",
            "da_DK-talesyntese-medium":         "Talesyntese",
            "de_DE-thorsten-medium":            "Thorsten",
            "de_DE-thorsten_emotional-medium":  "Thorsten Emotional",
            "de_DE-mls-medium":                 "Mls",
            "el_GR-rapunzelina-low":            "Rapunzelina",
            "en_GB-alan-medium":                "Alan",
            "en_GB-cori-high":                  "Cori",
            "es_ES-davefx-medium":              "DaveFX",
            "es_ES-sharvard-medium":            "Sharvard",
            "fa_IR-amir-medium":                "Amir",
            "fi_FI-harri-medium":               "Harri",
            "fr_FR-tom-medium":                 "Tom",
            "fr_FR-siwis-medium":               "Siwis",
            "hu_HU-anna-medium":                "Anna",
            "is_IS-bui-medium":                 "Bui",
            "is_IS-salka-medium":               "Salka",
            "it_IT-riccardo-x_low":             "Riccardo",
            "it_IT-paola-medium":               "Paola",
            "ka_GE-natia-medium":               "Natia",
            "kk_KZ-issai-high":                 "Issai",
            "kk_KZ-iseke-x_low":                "Iseke",
            "lb_LU-marylux-medium":             "MaryLux",
            "lv_LV-aivars-medium":              "Aivars",
            "ne_NP-google-medium":              "Google",
            "nl_NL-mls-medium":                 "Mls",
            "no_NO-talesyntese-medium":         "Talesyntese",
            "pl_PL-darkman-medium":             "Darkman",
            "pl_PL-gosia-medium":               "Gosia",
            "pt_PT-tug%C3%A3o-medium":          "Tugão",
            "ro_RO-mihai-medium":               "Mihai",
            "ru_RU-denis-medium":               "Denis",
            "ru_RU-irina-medium":               "Irina",
            "sk_SK-lili-medium":                "Lili",
            "sl_SI-artur-medium":               "Artur",
            "sr_RS-serbski_institut-medium":    "Serbski",
            "sv_SE-nst-medium":                 "Nst",
            "sw_CD-lanfrica-medium":            "Lanfrica",
            "tr_TR-dfki-medium":                "Dfki",
            "uk_UA-ukrainian_tts-medium":       "Ukrainian",
            "ur_PK-fasih-medium":               "Fasih",
            "vi_VN-vais1000-medium":            "Vais",
            "zh_CN-huayan-medium":              "Huayan"
        },
        "rating": {"VRAM": 1, "CPU": 5, "RAM": 2, "Realism": 4}
    },
    TTS_ENGINES['VITS']: {
        "languages": {"ben": "bn", "bul": "bg", "cat": "ca", "ces": "cs", "dan": "da", "deu": "de", "ell": "el", "eng": "en", "est": "et", "ewe": "ewe", "fas": "fa", "fin": "fi", "fra": "fr", "gle": "ga", "hau": "hau", "hrv": "hr", "hun": "hu", "ita": "it", "lav": "lv", "lin": "lin", "lit": "lt", "mlt": "mt", "nld": "nl", "pol": "pl", "por": "pt", "rom": "ro", "slk": "sk", "sln": "sl", "spa": "es", "swe": "sv", "tw_akuapem": "tw_akuapem", "tw_asante": "tw_asante", "ukr": "uk", "yor": "yor"},
        "samplerate": 22050,
        "files": ['config.json', 'best_model.pth', 'ref.wav'],
        "voice": None,
        "voices": {},
        "rating": {"VRAM": 2, "CPU": 4, "RAM": 4, "Realism": 4}
    },
    TTS_ENGINES['FAIRSEQ']: {
        "languages": {"ara": "ar", "ben": "bn", "eng": "en", "fas": "fa", "fra": "fr", "deu": "de", "hin": "hi", "hun": "hu", "ind": "id", "jav": "jv", "kor": "ko", "pol": "pl", "por": "pt", "rus": "ru", "spa": "es", "tam": "ta", "tel": "te", "tur": "tr", "yor": "yo"},
        "samplerate": 16000,
        "files": ['config.json', 'G_100000.pth', 'vocab.txt', 'ref.wav'],
        "voice": None,
        "voices": {},
        "rating": {"VRAM": 2, "CPU": 4, "RAM": 4, "Realism": 4}
    },
    TTS_ENGINES['GLOWTTS']: {
        "languages": {"eng": "en", "ukr": "uk", "tur": "tr", "ita": "it", "fas": "fa", "bel": "be"},
        "samplerate": 22050,
        "files": [],
        "voice": None,
        "voices": {},
        "rating": {"VRAM": 1, "CPU": 4, "RAM": 2, "Realism": 3}
    },
    TTS_ENGINES['TACOTRON']: {
        "languages": {"deu": "de", "eng": "en", "fra": "fr", "spa": "es"},
        "samplerate": 22050,
        "files": [],
        "voice": None,
        "voices": {},
        "rating": {"VRAM": 1, "CPU": 5, "RAM": 2, "Realism": 3}
    },
    TTS_ENGINES['YOURTTS']: {
        "languages": {"eng": "en", "fra": "fr", "por": "pt"},
        "samplerate": 16000,
        "files": [],
        "voice": None,
        "voices": {"Machinella-5": "female-en-5", "ElectroMale-2": "male-en-2", 'Machinella-4': 'female-pt-4\n', 'ElectroMale-3': 'male-pt-3\n'},
        "rating": {"VRAM": 1, "CPU": 5, "RAM": 1, "Realism": 2}
    }
}