import os
from lib.conf import voices_dir
from lib.conf_models import TTS_ENGINES, default_engine_settings

models = {
    "internal": {
        "lang": "multi",
        "repo": default_engine_settings[TTS_ENGINES['ZONOS']]['repo'],
        "sub": "",
        "voice": default_engine_settings[TTS_ENGINES['ZONOS']]['voice'],
        "files": default_engine_settings[TTS_ENGINES['ZONOS']]['files'],
        "samplerate": default_engine_settings[TTS_ENGINES['ZONOS']]['samplerate']
    },
    "hybrid": {
        "lang": "multi",
        "repo": default_engine_settings[TTS_ENGINES['ZONOS']]['repo_hybrid'],
        "sub": "",
        "voice": default_engine_settings[TTS_ENGINES['ZONOS']]['voice'],
        "files": default_engine_settings[TTS_ENGINES['ZONOS']]['files'],
        "samplerate": default_engine_settings[TTS_ENGINES['ZONOS']]['samplerate']
    }
}