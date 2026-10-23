# Runs inside lib/classes/tts_engines/venvs/styletts2, never inside e2a's python_env:
# it must not import anything from e2a. Driven by SubprocessPipe(keep_alive=True).
#
# protocol (one JSON object per line):
#   stdout <- {"ready": true, "samplerate": 24000, "device": "...", "custom": bool} once loaded
#             {"ready": false, "error": "..."} then exit 1 if loading failed
#   stdin  -> {"op": "tts", "text", "language" (espeak-ng voice), "voice", "file", "alpha", "beta",
#              "diffusion_steps", "embedding_scale"}
#   stdout <- {"ok": true, "file": "...", "samplerate": 24000, "samples": n}
#             {"ok": false, "error": "...", "oom": bool}
#   EOF on stdin -> exit 0 (that is how e2a unloads the model and frees its VRAM)
import os, sys, re, json, argparse, hashlib, faulthandler

SYMBOLS = (
    ['$'] + list(';:,.!?¡¿—…"«»“” ') + list('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
    + list("ɑɐɒæɓʙβɔɕçɗɖðʤəɘɚɛɜɝɞɟʄɡɠɢʛɦɧħɥʜɨɪʝɭɬɫɮʟɱɯɰŋɳɲɴøɵɸθœɶʘɹɺɾɻʀʁɽʂʃʈʧʉʊʋⱱʌɣɤʍχʎʏʑʐʒʔʡʕʢǀǁǂǃˈˌːˑʼʴʰʱʲʷˠˤ˞↓↑→↗↘'̩'ᵻ")
)
SYMBOL_INDEX = {symbol: index for index, symbol in enumerate(SYMBOLS)}
PUNCTUATION = re.compile(r'([;:,.!?¡¿—…"«»“”])')
SAMPLERATE = 24000

def main()->int:
    # the protocol owns a private copy of fd 1; fd 1 itself is pointed at stderr so
    # upstream's prints, tqdm and C extensions can never write into the reply stream.
    proto = os.fdopen(os.dup(1), 'w', encoding='utf-8', buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    # a native crash (SIGSEGV...) prints the python stack to stderr, which e2a shows in its log
    faulthandler.enable()
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--src', required=True)
    parser.add_argument('--model_dir', required=True)
    parser.add_argument('--model_files', required=True)
    parser.add_argument('--plbert_repo', default='')
    parser.add_argument('--plbert_dir', required=True)
    parser.add_argument('--plbert_config_file', default='config.yml')
    parser.add_argument('--custom', default='')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--cache_dir', required=True)
    parser.add_argument('--ref_max', type=float, default=15.0)
    args = parser.parse_args()
    try:
        os.makedirs(args.cache_dir, exist_ok=True)
        from huggingface_hub import snapshot_download
        import yaml
        import numpy as np
        import torch
        import torchaudio
        import soundfile as sf
        from collections import OrderedDict
        from munch import Munch
        from transformers import AlbertConfig, AlbertModel
        import espeakng_loader
        from phonemizer.backend import EspeakBackend
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        # upstream is not a package: it runs from its source tree (models.py, Modules/, Utils/)
        sys.path.insert(0, args.src)
        from models import build_model, load_ASR_models, load_F0_models
        from Modules.diffusion.sampler import DiffusionSampler, ADPM2Sampler, KarrasSchedule
        device = args.device
        if device == 'cuda' and not torch.cuda.is_available():
            device = 'cpu'
        # plain-folder downloads (local_dir): the HF cache layout symlinks, and huggingface_hub's symlink
        # probe races under threaded downloads (WinError 1314 on windows without symlink rights)
        if args.custom:
            config_path = os.path.join(args.custom, 'config.yml')
            checkpoint_path = os.path.join(args.custom, 'model.pth')
            # a custom checkpoint is trained with the multilingual PL-BERT (its weights come with the checkpoint,
            # the architecture and the config from here)
            snapshot_download(args.plbert_repo, local_dir=args.plbert_dir, allow_patterns=[args.plbert_config_file, 'step_*.t7'])
            plbert_dir = args.plbert_dir
        else:
            snapshot_download(args.repo, local_dir=args.model_dir, allow_patterns=json.loads(args.model_files))
            config_path, checkpoint_path = (os.path.join(args.model_dir, f) for f in json.loads(args.model_files))
            if args.plbert_repo:
                snapshot_download(args.plbert_repo, local_dir=args.plbert_dir, allow_patterns=[args.plbert_config_file, 'step_*.t7'])
                plbert_dir = args.plbert_dir
            else:
                plbert_dir = os.path.join(args.src, 'Utils', 'PLBERT')

        def recursive_munch(d):
            if isinstance(d, dict):
                return Munch((k, recursive_munch(v)) for k, v in d.items())
            if isinstance(d, list):
                return [recursive_munch(v) for v in d]
            return d

        class CustomAlbert(AlbertModel):
            def forward(self, *a, **kw):
                return super().forward(*a, **kw).last_hidden_state

        def load_plbert(log_dir):
            with open(os.path.join(log_dir, args.plbert_config_file), 'r', encoding='utf-8') as f:
                plbert_config = yaml.safe_load(f)
            bert = CustomAlbert(AlbertConfig(**plbert_config['model_params']))
            steps = [
                (int(match.group(1)), name)
                for name in os.listdir(log_dir)
                if (match := re.match(r'^step_(\d+)(?:_[^.]+)?\.t7$', name))
            ]
            if not steps:
                raise FileNotFoundError(f'No PL-BERT step checkpoint found in {log_dir}')
            _, checkpoint_name = max(steps, key=lambda item: item[0])
            checkpoint = torch.load(os.path.join(log_dir, checkpoint_name), map_location='cpu', weights_only=True)
            state = OrderedDict()
            for k, v in checkpoint['net'].items():
                name = k[7:] if k.startswith('module.') else k
                if name.startswith('encoder.'):
                    state[name[8:]] = v
            state.pop('embeddings.position_ids', None)
            bert.load_state_dict(state, strict=False)
            return bert

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        # the ASR aligner and the pitch extractor only shape the architecture here: their weights are in the
        # checkpoint, whatever paths the training config names
        text_aligner = load_ASR_models(os.path.join(args.src, 'Utils', 'ASR', 'epoch_00080.pth'), os.path.join(args.src, 'Utils', 'ASR', 'config.yml'))
        pitch_extractor = load_F0_models(os.path.join(args.src, 'Utils', 'JDC', 'bst.t7'))
        bert = load_plbert(plbert_dir)
        model_params = recursive_munch(config['model_params'])
        model = build_model(model_params, text_aligner, pitch_extractor, bert)
        style_dim = int(model_params.style_dim)
        params = torch.load(checkpoint_path, map_location='cpu', weights_only=True)['net']
        for key in model:
            if key in params:
                try:
                    model[key].load_state_dict(params[key])
                except Exception:
                    state = OrderedDict((k[7:] if k.startswith('module.') else k, v) for k, v in params[key].items())
                    model[key].load_state_dict(state, strict=False)
        for key in model:
            model[key].eval().to(device)
        sampler = DiffusionSampler(
            model.diffusion.diffusion,
            sampler=ADPM2Sampler(),
            sigma_schedule=KarrasSchedule(sigma_min=0.0001, sigma_max=3.0, rho=9.0),
            clamp=False
        )
        to_mel = torchaudio.transforms.MelSpectrogram(n_mels=80, n_fft=2048, win_length=1200, hop_length=300).to(device)
        multispeaker = bool(model_params.get('multispeaker', True))
    except Exception as e:
        proto.write(json.dumps({'ready': False, 'error': f'{type(e).__name__}: {e}'}) + '\n')
        return 1
    proto.write(json.dumps({'ready': True, 'samplerate': SAMPLERATE, 'device': device, 'custom': bool(args.custom)}) + '\n')
    backends = {}
    styles = {}
    model_tag = hashlib.sha1(os.path.abspath(checkpoint_path).encode('utf-8')).hexdigest()[:8]

    def length_to_mask(lengths):
        mask = torch.arange(lengths.max()).unsqueeze(0).expand(lengths.shape[0], -1).type_as(lengths)
        return torch.gt(mask + 1, lengths.unsqueeze(1))

    def phonemize(text, language):
        if language not in backends:
            backends[language] = EspeakBackend(language, preserve_punctuation=True, with_stress=True)
        ps = backends[language].phonemize([text])[0]
        ps = ' '.join(PUNCTUATION.sub(r' \1 ', ps).split())
        tokens = [SYMBOL_INDEX[c] for c in ps if c in SYMBOL_INDEX]
        # PL-BERT's positions stop at 512, the pad symbol opens the sequence
        return [0] + tokens[:510]

    def load_reference(voice):
        data, sr = sf.read(voice, dtype='float32', always_2d=True)
        wave = torch.from_numpy(data.mean(axis=1))
        if sr != SAMPLERATE:
            wave = torchaudio.functional.resample(wave, sr, SAMPLERATE)
        wave = wave.numpy()
        # trim the silence on both ends (30 dB under the loudest 25 ms frame), as upstream's librosa trim does
        frame = int(0.025 * SAMPLERATE)
        n = len(wave) // frame
        if n > 1:
            rms = np.sqrt((wave[:n * frame].reshape(n, frame) ** 2).mean(axis=1)) + 1e-10
            keep = np.where(20 * np.log10(rms / rms.max()) > -30)[0]
            if len(keep):
                wave = wave[keep[0] * frame:(keep[-1] + 1) * frame]
        return wave[:int(args.ref_max * SAMPLERATE)]

    def compute_style(voice):
        wave = torch.from_numpy(load_reference(voice)).float().to(device)
        mel = (torch.log(1e-5 + to_mel(wave)) + 4) / 4
        with torch.no_grad():
            ref_s = model.style_encoder(mel.unsqueeze(0).unsqueeze(1))
            ref_p = model.predictor_encoder(mel.unsqueeze(0).unsqueeze(1))
        return torch.cat([ref_s, ref_p], dim=1)

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
            voice = req['voice']
            voice_key = f'{model_tag}:{voice}:{os.path.getmtime(voice)}'
            if voice_key not in styles:
                styles[voice_key] = compute_style(voice)
            ref_s = styles[voice_key]
            alpha = float(req.get('alpha', 0.3))
            beta = float(req.get('beta', 0.7))
            tokens = phonemize(req['text'].strip(), req['language'])
            if len(tokens) < 2:
                raise ValueError('no phonemes for this text')
            tokens = torch.LongTensor(tokens).to(device).unsqueeze(0)
            with torch.no_grad():
                input_lengths = torch.LongTensor([tokens.shape[-1]]).to(device)
                text_mask = length_to_mask(input_lengths).to(device)
                t_en = model.text_encoder(tokens, input_lengths, text_mask)
                bert_dur = model.bert(tokens, attention_mask=(~text_mask).int())
                d_en = model.bert_encoder(bert_dur).transpose(-1, -2)
                s_pred = sampler(
                    noise=torch.randn((1, 2 * style_dim)).unsqueeze(1).to(device),
                    embedding=bert_dur,
                    embedding_scale=float(req.get('embedding_scale', 1.0)),
                    features=ref_s,
                    num_steps=int(req.get('diffusion_steps', 5))
                ).squeeze(1)
                s = s_pred[:, style_dim:]
                ref = s_pred[:, :style_dim]
                ref = alpha * ref + (1 - alpha) * ref_s[:, :style_dim]
                s = beta * s + (1 - beta) * ref_s[:, style_dim:]
                d = model.predictor.text_encoder(d_en, s, input_lengths, text_mask)
                x, _ = model.predictor.lstm(d)
                duration = torch.sigmoid(model.predictor.duration_proj(x)).sum(axis=-1)
                pred_dur = torch.round(duration.squeeze()).clamp(min=1)
                pred_aln_trg = torch.zeros(input_lengths, int(pred_dur.sum().data))
                c_frame = 0
                for i in range(pred_aln_trg.size(0)):
                    pred_aln_trg[i, c_frame:c_frame + int(pred_dur[i].data)] = 1
                    c_frame += int(pred_dur[i].data)
                pred_aln_trg = pred_aln_trg.unsqueeze(0).to(device)
                en = d.transpose(-1, -2) @ pred_aln_trg
                asr = t_en @ pred_aln_trg
                if model_params.decoder.type == 'hifigan':
                    # hifigan decoders take the features shifted by one frame
                    en_shifted = torch.zeros_like(en)
                    en_shifted[:, :, 0] = en[:, :, 0]
                    en_shifted[:, :, 1:] = en[:, :, 0:-1]
                    en = en_shifted
                    asr_shifted = torch.zeros_like(asr)
                    asr_shifted[:, :, 0] = asr[:, :, 0]
                    asr_shifted[:, :, 1:] = asr[:, :, 0:-1]
                    asr = asr_shifted
                F0_pred, N_pred = model.predictor.F0Ntrain(en, s)
                out = model.decoder(asr, F0_pred, N_pred, ref.squeeze().unsqueeze(0))
            # upstream trims the decoder's last 50 samples (a click)
            audio = out.squeeze().cpu().numpy().astype(np.float32).reshape(-1)[:-50]
            sf.write(req['file'], audio, SAMPLERATE, subtype='FLOAT')
            reply = {'ok': True, 'file': req['file'], 'samplerate': SAMPLERATE, 'samples': int(audio.shape[0])}
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
