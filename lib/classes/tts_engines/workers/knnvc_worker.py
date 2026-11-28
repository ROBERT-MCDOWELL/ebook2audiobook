# Runs in e2a's python_env (coqui-tts, torch, soundfile), started by common/knnvc.py (KnnVC) with SubprocessPipe(keep_alive=True)
# without conf.py's OMP_NUM_THREADS=1 (that one is for e2a's own torch): torch takes its default pool, the physical cores.
#
# protocol (one JSON object per line):
#   stdout <- {"ready": true, "samplerate": 16000, "device": "cpu", "threads": n} once loaded
#             {"ready": false, "error": "..."} then exit 1 if loading failed
#   stdin  -> {"op": "vc", "source", "voice", "file"}
#   stdout <- {"ok": true, "file": "...", "samplerate": the source's, "samples": n}
#             {"ok": false, "error": "...", "oom": bool}
#   EOF on stdin -> exit 0 (that is how e2a unloads the model)
#
# kNN-VC as bshall/knn-vc runs it, on coqui-tts' knnvc model (WavLM-Large, layer 6) and its prematched HiFi-GAN: each
# WavLM frame of the source is replaced by the mean of its topk nearest frames (cosine) in the voice file's. The matching
# set is the whole voice file, no clip cut from it: kNN-VC's timbre and intelligibility grow with the reference length (5
# to 8 min reach its paper's best scores), and its frames are all the vocoder speaks with. WavLM runs on window seconds
# pieces (its attention grows with the square of the length), the voice file VAD trimmed at both ends first (vad: knn-vc's
# trigger level for the matching set). mix: the cloned voice's share in the features the vocoder speaks (1.0: 100% cloned
# voice). The vocoder's 16 kHz goes back to the source's samplerate: the engine keeps its own one for every part of a
# sentence, its built-in voice ones included. Audio is read with soundfile, never torchaudio.load (torchcodec, see
# components/sitecustomize.py)
import os, sys, json, shutil, argparse, faulthandler

def main()->int:
    # the protocol owns a private copy of fd 1; fd 1 itself is pointed at stderr so coqui's logs, tqdm and C extensions
    # can never write into the reply stream
    proto = os.fdopen(os.dup(1), 'w', encoding='utf-8', buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    # a native crash (SIGSEGV...) prints the python stack to stderr, which e2a shows in its log
    faulthandler.enable()
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--topk', type=int, default=4)
    parser.add_argument('--mix', type=float, default=1.0)
    parser.add_argument('--vad', type=float, default=7.0)
    parser.add_argument('--window', type=float, default=30.0)
    args = parser.parse_args()
    try:
        import urllib.request
        import soundfile as sf
        import torch
        import torchaudio
        from tqdm import tqdm
        from TTS.api import TTS
        from TTS.utils.manage import ModelManager
        from TTS.vc.layers.freevc import wavlm as wavlm_module
        # WavLM-Large (1.2 GB) as coqui's get_wavlm() would fetch it, but through a .part file: get_wavlm() writes
        # straight to the final path, so a cut download stays there broken. tqdm lines on stderr move e2a's bar
        wavlm_file = os.path.join(wavlm_module.get_user_data_dir('tts'), 'wavlm', 'WavLM-Large.pt')
        if not os.path.exists(wavlm_file):
            os.makedirs(os.path.dirname(wavlm_file), exist_ok=True)
            with tqdm(unit='B', unit_scale=True, desc='WavLM-Large.pt', file=sys.stderr) as bar:
                def hook(blocks:int, block_size:int, total:int)->None:
                    bar.total = total if total > 0 else None
                    bar.update(blocks * block_size - bar.n)
                urllib.request.urlretrieve(wavlm_module.model_uri, f'{wavlm_file}.part', reporthook=hook)
            os.replace(f'{wavlm_file}.part', wavlm_file)
        # coqui treats any existing model folder as downloaded: a vocoder folder left half-written by a cut download
        # is wiped and fetched again (knnvc itself has no files, its config is written by the manager)
        manager = ModelManager(progress_bar=True)
        vocoder_name = manager._set_model_item(args.model)[0].get('default_vocoder')
        if vocoder_name:
            vocoder_path = manager.output_prefix / manager._set_model_item(vocoder_name)[1]
            if vocoder_path.is_dir():
                try:
                    manager._find_files(vocoder_path)
                except ValueError:
                    shutil.rmtree(vocoder_path, ignore_errors=True)
        engine = TTS(args.model).to(args.device)
        model = engine.voice_converter.vc_model
        vocoder = engine.voice_converter.vocoder_model
        samplerate = int(model.config.audio.sample_rate)
        vocoder_config = engine.voice_converter.vocoder_config
        output_samplerate = int(vocoder_config.audio['sample_rate']) if vocoder_config is not None else samplerate
        window = max(1, int(args.window * samplerate))
        # voice file -> ((mtime, size), its WavLM frames), kept for the worker's life
        matching_sets = {}

        def load(path:str)->tuple:
            # mono float32 at WavLM's rate, shape (1, samples), and the file's own rate
            audio, sr = sf.read(path, dtype='float32', always_2d=True)
            wave = torch.from_numpy(audio.mean(axis=1)).unsqueeze(0)
            if sr != samplerate:
                wave = torchaudio.functional.resample(wave, sr, samplerate)
            return wave, sr

        def features(wave:'torch.Tensor')->'torch.Tensor':
            # WavLM frames (frames, 1024) of the whole wave, in pieces of about window samples of equal length (no short
            # tail WavLM's feature encoder could not read)
            pieces = torch.tensor_split(wave, max(1, -(-wave.shape[-1] // window)), dim=-1)
            return torch.cat([model.get_features(piece) for piece in pieces], dim=0)

        def matching_set(voice:str)->'torch.Tensor':
            stat = os.stat(voice)
            stamp = (stat.st_mtime_ns, stat.st_size)
            cached = matching_sets.get(voice)
            if cached is not None and cached[0] == stamp:
                return cached[1]
            wave, _ = load(voice)
            if args.vad > 1e-3:
                # silence trimmed front and back as knn-vc's get_matching_set() does; a file the VAD finds no speech in
                # (or a torchaudio without it) keeps every sample
                try:
                    vad = torchaudio.transforms.Vad(sample_rate=samplerate, trigger_level=args.vad)
                    trimmed = torch.flip(vad(torch.flip(vad(wave), (-1,))), (-1,))
                    if trimmed.shape[-1] >= samplerate // 2:
                        wave = trimmed
                except Exception as e:
                    print(f'knnvc: no VAD trim for {voice}: {e}', file=sys.stderr)
            frames = features(wave).cpu()
            matching_sets[voice] = (stamp, frames)
            print(f'knnvc: matching set of {os.path.basename(voice)}: {frames.shape[0]} frames ({wave.shape[-1] / samplerate:.1f} s, all of it)', file=sys.stderr)
            return frames

        # WavLM and the vocoder run once at load: a broken install shows as a load error instead of failing the first
        # sentence, and oneDNN builds its kernels before the first reply
        with torch.inference_mode():
            vocoder.inference(features(torch.zeros(1, samplerate)).unsqueeze(0))
    except Exception as e:
        proto.write(json.dumps({'ready': False, 'error': f'{type(e).__name__}: {e}'}) + '\n')
        return 1
    proto.write(json.dumps({'ready': True, 'samplerate': output_samplerate, 'device': args.device, 'threads': torch.get_num_threads()}) + '\n')
    while True:
        raw = sys.stdin.buffer.readline()
        if not raw:
            break
        try:
            req = json.loads(raw)
        except Exception as e:
            proto.write(json.dumps({'ok': False, 'error': f'bad request: {e}', 'oom': False}) + '\n')
            continue
        if req.get('op') != 'vc':
            proto.write(json.dumps({'ok': False, 'error': f"unknown op {req.get('op')!r}", 'oom': False}) + '\n')
            continue
        try:
            with torch.inference_mode():
                matching = matching_set(req['voice']).to(model.device)
                source, source_samplerate = load(req['source'])
                query = features(source)
                distances = model.fast_cosine_dist(query, matching)
                nearest = distances.topk(k=min(args.topk, matching.shape[0]), largest=False, dim=-1)
                converted = matching[nearest.indices].mean(dim=1)
                if args.mix < 1.0:
                    converted = args.mix * converted + (1.0 - args.mix) * query
                audio = vocoder.inference(converted.unsqueeze(0)).reshape(1, -1).float().cpu()
                if source_samplerate != output_samplerate:
                    audio = torchaudio.functional.resample(audio, output_samplerate, source_samplerate)
                audio = audio.squeeze(0).numpy()
            if audio.shape[0] == 0:
                raise ValueError(f"no audio converted from {req['source']}")
            sf.write(req['file'], audio, source_samplerate, subtype='FLOAT')
            reply = {'ok': True, 'file': req['file'], 'samplerate': source_samplerate, 'samples': int(audio.shape[0])}
        except Exception as e:
            # no retry here: e2a's convert() returns False and core.py unloads the engine, which closes stdin and ends
            # this process
            error = f'{type(e).__name__}: {e}'
            reply = {'ok': False, 'error': error, 'oom': 'out of memory' in error.lower()}
        proto.write(json.dumps(reply) + '\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())
