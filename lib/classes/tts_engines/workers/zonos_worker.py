# Runs inside lib/classes/tts_engines/venvs/zonos, never inside e2a's python_env:
# it must not import anything from e2a. Driven by SubprocessPipe(keep_alive=True).
#
# protocol (one JSON object per line):
#   stdout <- {"ready": true, "samplerate": 44100, "backbone": "...", "device": "..."} once loaded
#             {"ready": false, "error": "..."} then exit 1 if loading failed
#   stdin  -> {"op": "tts", "text", "language", "voice", "file", "emotion_enabled", "emotion",
#              "speaking_rate", "pitch_std", "fmax", "cfg_scale", "linear", "max_new_tokens"}
#   stdout <- {"ok": true, "file": "...", "samplerate": 44100, "samples": n}
#             {"ok": false, "error": "...", "oom": bool}
#   EOF on stdin -> exit 0 (that is how e2a unloads the model and frees its VRAM)
import os, sys, json, argparse, faulthandler, inspect

def main()->int:
    # the protocol owns a private copy of fd 1; fd 1 itself is pointed at stderr so
    # zonos, phonemizer, tqdm and C extensions can never write into the reply stream.
    proto = os.fdopen(os.dup(1), 'w', encoding='utf-8', buffering=1)
    # a native crash (SIGSEGV...) prints the python stack to stderr, which e2a shows in its log
    faulthandler.enable()
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--compile', action='store_true')
    args = parser.parse_args()
    try:
        import torch
        import soundfile as sf
        from zonos.model import Zonos
        from zonos.conditioning import make_cond_dict
        from zonos.speaker_cloning import SpeakerEmbeddingLDA
        device = args.device
        if device == 'cuda':
            torch.backends.cudnn.benchmark = False
        model = Zonos.from_pretrained(args.repo, device=device)
        model.requires_grad_(False).eval()
        # upstream builds the speaker model lazily on its own DEFAULT_DEVICE (cuda if
        # visible, else cpu); pin it to the device e2a selected instead.
        model.spk_clone_model = SpeakerEmbeddingLDA(device=device)
        # torch.compile only where inductor/triton are dependable: CUDA (not ROCm),
        # Linux, Ampere+. The hybrid backbone uses CUDA graphs and skips it anyway.
        use_compile = bool(
            args.compile and device == 'cuda' and sys.platform == 'linux'
            and getattr(torch.version, 'hip', None) is None
            and torch.cuda.get_device_capability(0)[0] >= 8
        )
        # zonos' own sampling default (generate()'s sampling_params, min_p 0.1 today): passing any
        # dict replaces it, so requests only ever add to a copy of it
        default_sampling = dict(inspect.signature(model.generate).parameters['sampling_params'].default)
        sampling_rate = int(model.autoencoder.sampling_rate)
        backbone = model.backbone.__class__.__name__
    except Exception as e:
        proto.write(json.dumps({'ready': False, 'error': f'{type(e).__name__}: {e}'}) + '\n')
        return 1
    proto.write(json.dumps({'ready': True, 'samplerate': sampling_rate, 'backbone': backbone, 'device': str(model.device), 'compile': use_compile}) + '\n')
    speakers = {}
    while True:
        raw = sys.stdin.buffer.readline()
        if not raw:
            break
        try:
            req = json.loads(raw)
        except Exception as e:
            proto.write(json.dumps({'ok': False, 'error': f'bad request: {e}', 'oom': False}) + '\n')
            continue
        if req.get('op') != 'tts':
            proto.write(json.dumps({'ok': False, 'error': f"unknown op {req.get('op')!r}", 'oom': False}) + '\n')
            continue
        try:
            speaker = None
            voice = req.get('voice')
            if voice:
                # keyed by path + mtime: a voice file rebuilt in place gets a new embedding
                voice_key = f'{voice}:{os.path.getmtime(voice)}'
                speaker = speakers.get(voice_key)
                if speaker is None:
                    data, sr = sf.read(voice, dtype='float32', always_2d=True)
                    wav = torch.from_numpy(data.T.copy())
                    speaker = model.make_speaker_embedding(wav, sr).to(device, dtype=torch.bfloat16)
                    speakers[voice_key] = speaker
            # Happiness, Sadness, Disgust, Fear, Surprise, Anger, Other, Neutral. Neutral is the anchor:
            # its share of the mix keeps the emotion-off delivery, the other seven pull toward the
            # conditional mix, so the default (Neutral only) sounds like emotion off
            emotion = [max(float(v), 0.0) for v in req['emotion']]
            emotion_total = sum(emotion)
            emotion_strength = (emotion_total - emotion[7]) / emotion_total if req.get('emotion_enabled', True) and emotion_total > 0.0 else 0.0
            cond_kwargs = dict(
                text=req['text'],
                language=req['language'],
                speaker=speaker,
                emotion=emotion if emotion_total > 0.0 else [0.0] * 7 + [1.0],
                fmax=float(req['fmax']),
                pitch_std=float(req['pitch_std']),
                speaking_rate=float(req['speaking_rate']),
                device=device
            )
            # reference = zonos' default unconditional keys plus emotion, i.e. emotion off
            conditioning = model.prepare_conditioning(make_cond_dict(**cond_kwargs, unconditional_keys=['vqscore_8', 'dnsmos_ovrl', 'emotion']))
            if emotion_strength > 0.0:
                # the prefix is one token per conditioner (project + LayerNorm are per token), so the
                # two prefixes differ only on the emotion token and the CFG half is identical:
                # lerp moves the delivery continuously from emotion off (0) to the full mix (1)
                conditioning_emotion = model.prepare_conditioning(make_cond_dict(**cond_kwargs, unconditional_keys=['vqscore_8', 'dnsmos_ovrl']))
                conditioning = torch.lerp(conditioning, conditioning_emotion, emotion_strength)
                del conditioning_emotion
            # zonos missing its end token babbles up to the cap (30 s by default): bound it by the text,
            # 0.25 s per character is far above normal speech (~0.07-0.12), 86 frames per second
            max_new_tokens = min(int(req['max_new_tokens']), int(86 * max(2.0, len(req['text']) * 0.25)))
            codes = model.generate(
                conditioning,
                max_new_tokens=max_new_tokens,
                cfg_scale=float(req['cfg_scale']),
                sampling_params={**default_sampling, **({'linear': float(req['linear'])} if float(req.get('linear', 0.0)) > 0.0 else {})},
                progress_bar=False,
                disable_torch_compile=not use_compile
            )
            wavs = model.autoencoder.decode(codes).cpu()
            audio = wavs[0].reshape(-1).float().numpy()
            sf.write(req['file'], audio, sampling_rate, subtype='FLOAT')
            reply = {'ok': True, 'file': req['file'], 'samplerate': sampling_rate, 'samples': int(audio.shape[0])}
        except Exception as e:
            # no retry here: e2a's convert() returns False and core.py unloads the
            # engine, which closes stdin and ends this process.
            error = f'{type(e).__name__}: {e}'
            reply = {'ok': False, 'error': error, 'oom': 'out of memory' in error.lower()}
            try:
                if device == 'cuda':
                    torch.cuda.empty_cache()
                elif device == 'xpu':
                    torch.xpu.empty_cache()
            except Exception:
                pass
        proto.write(json.dumps(reply) + '\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())