from lib.conf_models import TTS_ENGINES, default_engine_settings

# "internal" resolves to a language-specific checkpoint when one is available.
# French and Spanish internal voices use a reference WAV named internal.wav under voices/<lang>/.
models = {
    "internal": {
        "repo": default_engine_settings[TTS_ENGINES['STYLETTS2']]['repo'],
        "sub": "",
        "voice": default_engine_settings[TTS_ENGINES['STYLETTS2']]['voice'],
        "files": default_engine_settings[TTS_ENGINES['STYLETTS2']]['files'],
        "samplerate": default_engine_settings[TTS_ENGINES['STYLETTS2']]['samplerate'],
        "languages": default_engine_settings[TTS_ENGINES['STYLETTS2']]['languages'],
        "language_models": {
            "eng": {
                "repo": "yl4579/StyleTTS2-LibriTTS",
                "model_files": ["Models/LibriTTS/config.yml", "Models/LibriTTS/epochs_2nd_00020.pth"],
                "phonemizer": "en-us",
                "voice": default_engine_settings[TTS_ENGINES['STYLETTS2']]['voice']
            },
            "fra": {
                "repo": "Scralius/StyleTTS2_French",
                "model_files": ["config.yml", "epoch_2nd_00050.pth"],
                "phonemizer": "fr-fr",
                "voice": None,
                "internal_voice": True
            },
            "spa": {
                "repo": "BSC-LT/styletts2-spanish-multispeaker",
                "model_files": [
                    "styletts2-spanish-multispeaker_2nd_phase_config.yml",
                    "styletts2-spanish-multispeaker_2nd_phase_epoch_86.pth"
                ],
                "plbert_repo": "BSC-LT/PL-BERT-wp-es",
                "plbert_config_file": "config_es.yml",
                "phonemizer": "es-419",
                "voice": None,
                "internal_voice": True
            }
        }
    }
}
