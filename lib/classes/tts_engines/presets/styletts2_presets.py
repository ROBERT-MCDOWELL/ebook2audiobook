from lib.conf_models import TTS_ENGINES, default_engine_settings

# "internal" is upstream's LibriTTS model (English, multi-speaker, zero-shot voice cloning through its style encoders).
# The other languages of the multilingual PL-BERT need a checkpoint trained with it: upload one as a custom model.
models = {
    "internal": {
        "lang": "multi",
        "repo": default_engine_settings[TTS_ENGINES['STYLETTS2']]['repo'],
        "sub": "",
        "voice": default_engine_settings[TTS_ENGINES['STYLETTS2']]['voice'],
        "files": default_engine_settings[TTS_ENGINES['STYLETTS2']]['files'],
        "samplerate": default_engine_settings[TTS_ENGINES['STYLETTS2']]['samplerate']
    }
}
