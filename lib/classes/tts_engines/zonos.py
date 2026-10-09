import json
from lib.classes.tts_engines.common.headers import *
from lib.classes.tts_engines.common.preset_loader import load_engine_presets
from lib.classes.subprocess_pipe import SubprocessPipe
from lib.conf import systems, default_pytorch_url
from lib.lang import legends

class Zonos(TTSUtils, TTSRegistry, name='zonos'):

    def __init__(self, session:DictProxy):
        try:
            self.session = session
            self.cache_dir = tts_dir
            self.speakers_path = None
            self.speaker = None
            self.tts_key = self.session['model_cache']
            self.pth_voice_file = None
            self.resampler_cache = {}
            self.resampled_wav_cache = {}
            self.audio_segments = []
            self.models = load_engine_presets(self.session['tts_engine'])
            self.params = {}
            tts_engine = self.session.get('tts_engine')
            # effective language for TTS (target when translating, else source)
            self.language = self.session.get('language')
            self.language_iso1 = self.session.get('language_iso1')
            if self.session.get('translate_enabled'):
                if self.session.get('translate'):
                    self.language = self.session['translate']
                if self.session.get('translate_iso1'):
                    self.language_iso1 = self.session['translate_iso1']
            if tts_engine not in default_engine_settings:
                error = legends['error_invalid_tts_engine'].format(engine=tts_engine)
                raise ValueError(error)
            settings = default_engine_settings[tts_engine]
            engine_langs = settings.get('languages', {})
            if self.language not in engine_langs:
                error = legends['error_language_not_supported_engine'].format(lang=self.language, engine=tts_engine)
                raise ValueError(error)
            self.language_espeak = engine_langs[self.language]
            fine_tuned = self.session.get('fine_tuned')
            if fine_tuned not in self.models:
                error = legends['error_invalid_fine_tuned'].format(model=fine_tuned, models=list(self.models.keys()))
                raise ValueError(error)
            model_cfg = self.models[fine_tuned]
            for required_key in ('repo', 'samplerate', 'voice'):
                if required_key not in model_cfg:
                    error = legends['error_fine_tuned_missing_key'].format(model=fine_tuned, key=required_key)
                    raise ValueError(error)
            self.params['samplerate'] = model_cfg['samplerate']
            self.model_repo = model_cfg['repo']
            self.xtts_speakers = self._load_xtts_builtin_list()
            self.device = devices['CUDA']['proc'] if self.session['device'] in [devices['CUDA']['proc'], devices['ROCM']['proc'], devices['JETSON']['proc']] else self.session['device']
            # upstream zonos disables MPS ("MPS breaks"), so macOS runs the worker on cpu
            self.worker_device = devices['CPU']['proc'] if self.device == devices['MPS']['proc'] else self.device
            self.fine_tuned_params = {
                key.removeprefix('zonos_'): cast_type(self.session[key]) if self.session.get(key) is not None else cast_type(settings[key.removeprefix('zonos_')])
                for key, cast_type in {
                    'zonos_emotion_enabled': bool,
                    'zonos_speaking_rate': float,
                    'zonos_pitch_std': float,
                    'zonos_fmax': float,
                    'zonos_cfg_scale': float,
                    'zonos_linear': float,
                    'zonos_max_new_tokens': int
                }.items()
            }
            # Happiness, Sadness, Disgust, Fear, Surprise, Anger, Other, Neutral: one session key
            # per slider (as xtts / bark), the list order zonos expects
            self.fine_tuned_params['emotion'] = [
                float(self.session[key]) if self.session.get(key) is not None else float(settings['emotion'][i])
                for i, key in enumerate(['zonos_emotion_happiness', 'zonos_emotion_sadness', 'zonos_emotion_disgust', 'zonos_emotion_fear', 'zonos_emotion_surprise', 'zonos_emotion_anger', 'zonos_emotion_other', 'zonos_emotion_neutral'])
            ]
            # --- own uv venv: lib/classes/tts_engines/venvs/zonos ---
            # torch/torchaudio are mirrored from python_env (same version, same local
            # tag, same index) so the worker gets the build device_installer already
            # validated for this machine; everything else zonos needs is pinned in
            # default_engine_settings. gradio is deliberately not installed.
            progress_bar = getattr(sys.modules.get('lib.gradio'), 'progress_bar', None)
            engine_dir = os.path.dirname(os.path.abspath(__file__))
            self.venv_dir = os.path.join(engine_dir, 'venvs', tts_engine)
            self.venv_python = os.path.join(self.venv_dir, 'Scripts', 'python.exe') if sys.platform == systems['WINDOWS'] else os.path.join(self.venv_dir, 'bin', 'python')
            self.worker_script = os.path.join(engine_dir, 'workers', f'{tts_engine}_worker.py')
            self.worker_env = {k: v for k, v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONSTARTUP', 'VIRTUAL_ENV', 'CONDA_PREFIX', 'CONDA_DEFAULT_ENV', 'CONDA_PYTHON_EXE', 'CONDA_SHLVL', '__PYVENV_LAUNCHER__')}
            self.worker_env['VIRTUAL_ENV'] = self.venv_dir
            self.worker_env['PATH'] = os.pathsep.join([os.path.dirname(self.venv_python), self.worker_env.get('PATH', '')])
            self.worker_env['PYTHONUNBUFFERED'] = '1'
            # a python uv has to download for the venv is kept with the venvs, so a docker volume
            # on lib/classes/tts_engines/venvs (or deleting that folder) covers everything
            self.worker_env['UV_PYTHON_INSTALL_DIR'] = os.path.join(engine_dir, 'venvs', '.python')
            if self.worker_device != devices['CUDA']['proc']:
                # keep the worker off the GPU entirely (zonos probes cuda at import)
                self.worker_env['CUDA_VISIBLE_DEVICES'] = '-1'
                self.worker_env['HIP_VISIBLE_DEVICES'] = '-1'
            import torch
            import torchaudio
            torch_base, _, torch_tag = torch.__version__.partition('+')
            torchaudio_tag = torchaudio.__version__.partition('+')[2]
            torch_version = tuple(int(x) for x in re.findall(r'\d+', torch_base)[:3])
            torch_min = tuple(int(x) for x in settings['torch_min'].split('.'))
            # only builds reachable from a plain index can be mirrored: PyPI (no tag),
            # download.pytorch.org cpu / cuXXX / xpu / linux rocmX.Y. Jetson and
            # Windows ROCm come from custom wheel URLs and are below torch_min anyway.
            index_ok = (
                torch_tag in ('', 'cpu', 'xpu')
                or bool(re.fullmatch(r'cu\d+', torch_tag))
                or (bool(re.fullmatch(r'rocm[\d.]+', torch_tag)) and sys.platform == systems['LINUX'])
            )
            if torch_version < torch_min or not index_ok:
                error = legends['error_venv_torch_unsupported'].format(engine=tts_engine, min=settings['torch_min'], version=torch.__version__)
                raise ValueError(error)
            marker_file = os.path.join(self.venv_dir, '.e2a_installed.json')
            installed = {}
            if os.path.exists(marker_file):
                try:
                    with open(marker_file, 'r', encoding='utf-8') as f:
                        installed = json.load(f)
                except Exception:
                    installed = {}
            expected = {'source': settings['source'], 'torch': torch.__version__, 'torchaudio': torchaudio.__version__}
            need_base = not os.path.exists(self.venv_python) or any(installed.get(k) != v for k, v in expected.items())
            hybrid_wanted = self.model_repo == settings['repo_hybrid']
            # one attempt per base install: mamba-ssm/flash-attn may compile for a long
            # time and fail, so a failure is recorded instead of retried on every run.
            need_hybrid = hybrid_wanted and (need_base or 'hybrid' not in installed)
            if need_base or need_hybrid:
                from lib.classes.device_installer import DeviceInstaller
                uv_bin = DeviceInstaller().uv_bin
                uv_pip = [uv_bin, 'pip', 'install', '--python', self.venv_python]
                steps = []
                if need_base:
                    installed = {}
                    if not os.path.exists(self.venv_python):
                        msg = legends['msg_venv_creating'].format(engine=tts_engine, dir=self.venv_dir)
                        # --clear: the dir can exist with a dead interpreter link (docker image rebuilt)
                        steps.append((msg, [uv_bin, 'venv', '--clear', '--python', settings['python'], self.venv_dir]))
                    msg = legends['msg_venv_installing'].format(engine=tts_engine, pkgs=f'torch {torch.__version__}, torchaudio {torchaudio.__version__}')
                    steps.append((msg, uv_pip + [f'torch=={torch.__version__}'] + (['--index-url', f'{default_pytorch_url}/{torch_tag}'] if torch_tag else [])))
                    steps.append((msg, uv_pip + ['--no-deps', f'torchaudio=={torchaudio.__version__}'] + (['--index-url', f'{default_pytorch_url}/{torchaudio_tag}'] if torchaudio_tag else [])))
                    msg = legends['msg_venv_installing'].format(engine=tts_engine, pkgs=f'{tts_engine} dependencies')
                    steps.append((msg, uv_pip + settings['packages']))
                    # upstream pyproject has packages.find include = ["zonos"], which matches the
                    # top-level package only: a regular wheel build drops zonos/backbone. Upstream
                    # installs editable (uv pip install -e .), so do the same from the pinned source
                    # extracted to venvs/zonos/src/Zonos (python_env's interpreter, stdlib only).
                    src_dir = os.path.join(self.venv_dir, 'src', 'Zonos')
                    extract_script = '\n'.join([
                        'import os, sys, shutil, tarfile, urllib.request',
                        'url, dst = sys.argv[1], sys.argv[2]',
                        'shutil.rmtree(dst, ignore_errors=True)',
                        'os.makedirs(dst)',
                        'archive = os.path.join(dst, "source.tar.gz")',
                        'urllib.request.urlretrieve(url, archive)',
                        'with tarfile.open(archive, "r:gz") as tar:',
                        '    root = tar.getmembers()[0].name.split("/")[0]',
                        '    tar.extractall(dst, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))',
                        'os.unlink(archive)',
                        'os.rename(os.path.join(dst, root), os.path.join(dst, "Zonos"))'
                    ])
                    msg = legends['msg_venv_installing'].format(engine=tts_engine, pkgs=tts_engine)
                    steps.append((msg, [sys.executable, '-c', extract_script, settings['source'], os.path.dirname(src_dir)]))
                    steps.append((msg, uv_pip + ['--no-deps', '-e', src_dir]))
                for msg, cmd in steps:
                    print(msg)
                    if progress_bar is not None:
                        progress_bar(0.0, desc=msg)
                    proc_pipe = SubprocessPipe(cmd, is_gui_process=self.session['is_gui_process'], total_duration=0, msg=msg, env=self.worker_env)
                    if not proc_pipe.result:
                        error = legends['error_venv_install_failed'].format(engine=tts_engine, step=' '.join(cmd))
                        raise RuntimeError(error)
                try:
                    import shutil
                    # Ask the venv's python where its site-packages directory is
                    site_packages = subprocess.check_output(
                        [self.venv_python, '-c', 'import sysconfig; print(sysconfig.get_paths()["purelib"])'],
                        text=True
                    ).strip()
                    
                    # Locate the source sitecustomize.py (3 levels up from lib/classes/tts_engines)
                    sitecustomize_src = os.path.abspath(os.path.join(engine_dir, '..', '..', '..', 'components', 'sitecustomize.py'))
                    sitecustomize_dst = os.path.join(site_packages, 'sitecustomize.py')
                    
                    if os.path.exists(sitecustomize_src):
                        shutil.copy2(sitecustomize_src, sitecustomize_dst)
                        print(f"Copied sitecustomize.py to {sitecustomize_dst}")
                    else:
                        print(f"Warning: sitecustomize.py not found at {sitecustomize_src}")
                except Exception as e:
                    print(f"Warning: Failed to copy sitecustomize.py: {e}")
                if need_base:
                    probe = subprocess.run([self.venv_python, '-c', 'import zonos.model'], env=self.worker_env, capture_output=True, text=True, timeout=600)
                    if probe.returncode != 0:
                        error = legends['error_venv_install_failed'].format(engine=tts_engine, step=f'import zonos.model: {probe.stderr.strip()[-500:]}')
                        raise RuntimeError(error)
                    installed.update(expected)
                if need_hybrid:
                    reason = None
                    if sys.platform != systems['LINUX']:
                        reason = sys.platform
                    elif self.session['device'] != devices['CUDA']['proc']:
                        reason = self.session['device']
                    else:
                        probe = subprocess.run([self.venv_python, '-c', 'import torch;print(torch.cuda.get_device_capability(0)[0] if torch.cuda.is_available() and torch.version.hip is None else 0)'], env=self.worker_env, capture_output=True, text=True, timeout=300)
                        cc_major = int(probe.stdout.strip() or 0) if probe.returncode == 0 else 0
                        if cc_major < 8:
                            reason = f'compute capability {cc_major}.x'
                    installed['hybrid'] = False
                    if reason is None:
                        msg = legends['msg_venv_hybrid_installing'].format(engine=tts_engine, pkgs=', '.join(settings['packages_hybrid']))
                        print(msg)
                        if progress_bar is not None:
                            progress_bar(0.0, desc=msg)
                        hybrid_ok = SubprocessPipe(uv_pip + ['wheel', 'ninja'], is_gui_process=self.session['is_gui_process'], total_duration=0, msg=msg, env=self.worker_env).result
                        if hybrid_ok:
                            hybrid_ok = SubprocessPipe(uv_pip + ['--no-build-isolation'] + settings['packages_hybrid'], is_gui_process=self.session['is_gui_process'], total_duration=0, msg=msg, env=self.worker_env).result
                        if hybrid_ok:
                            probe = subprocess.run([self.venv_python, '-c', 'import mamba_ssm, causal_conv1d, flash_attn'], env=self.worker_env, capture_output=True, text=True, timeout=600)
                            hybrid_ok = probe.returncode == 0
                        installed['hybrid'] = bool(hybrid_ok)
                        installed['hybrid_reason'] = None if hybrid_ok else 'mamba-ssm / causal-conv1d / flash-attn install failed'
                    else:
                        installed['hybrid_reason'] = reason
                with open(marker_file, 'w', encoding='utf-8') as f:
                    json.dump(installed, f, indent=2)
            if hybrid_wanted and not installed.get('hybrid'):
                # the pre-flight in convert_ebook() already switches unsupported hardware to
                # internal; this covers a first failed mamba-ssm/flash-attn install and the
                # sentence editor: same alert, same switch, and the worker is cached under the
                # internal key so cleanup_models_cache() keeps it as the session's model
                self.model_repo = settings['repo']
                self.session['fine_tuned'] = 'internal'
                self.session['model_cache'] = self.tts_key = f'{tts_engine}-internal'
                msg = legends['msg_venv_hybrid_fallback'].format(engine=tts_engine, reason=installed.get('hybrid_reason'))
                show_alert = getattr(sys.modules.get('lib.core'), 'show_alert', None)
                if show_alert is not None:
                    show_alert(self.session['id'], {'type': 'warning', 'msg': msg})
                else:
                    print(msg)
            self.engine = self.load_engine()
        except Exception as e:
            error = f'__init__() error: {e}'
            raise ValueError(error)

    def load_engine(self)->Any:
        try:
            msg = legends['msg_loading_tts_model'].format(model=self.tts_key)
            print(msg)
            self.cleanup_memory()
            cmd = [self.venv_python, '-u', self.worker_script, '--repo', self.model_repo, '--device', self.worker_device, '--compile']
            engine = loaded_tts.get(self.tts_key)
            if isinstance(engine, SubprocessPipe) and (engine.cmd != cmd or engine.process is None or engine.process.poll() is not None):
                # dead worker, or one serving another model/device under this key
                loaded_tts.pop(self.tts_key, None)
                engine.stop()
                engine = None
            if not engine:
                msg = legends['msg_worker_starting'].format(engine=self.session['tts_engine'], model=self.model_repo, device=self.worker_device)
                print(msg)
                progress_bar = getattr(sys.modules.get('lib.gradio'), 'progress_bar', None)
                if progress_bar is not None:
                    progress_bar(0.0, desc=msg)
                engine = SubprocessPipe(cmd, is_gui_process=self.session['is_gui_process'], total_duration=0, msg=msg, keep_alive=True, env=self.worker_env)
                if not engine.result:
                    error = legends['error_worker_failed'].format(engine=self.session['tts_engine'], error=engine.ready_info.get('error'))
                    raise RuntimeError(error)
                # always cached, whatever the free VRAM: the worker must stay reachable
                # by unload_tts_manager() / cleanup_models_cache(), which stop it.
                loaded_tts[self.tts_key] = engine
            self.params['samplerate'] = int(engine.ready_info.get('samplerate', self.params['samplerate']))
            msg = legends['msg_tts_loaded'].format(model=self.tts_key)
            print(msg)
            return engine
        except Exception as e:
            error = f'load_engine() error: {e}'
            raise RuntimeError(error) from e

    def convert(self, sentence_file:str, sentence:str, **kwargs)->tuple:
        part_file = f'{os.path.splitext(sentence_file)[0]}.{self.session["tts_engine"]}.wav'
        try:
            import torch
            import numpy as np
            import soundfile as sf
            from lib.classes.tts_engines.common.audio import trim_audio, is_audio_data_valid
            if self.engine:
                sentence_parts = self._split_sentence_on_sml(sentence)
                self.params['block_voice'] = kwargs.get('block_voice', self.session['voice'])
                if self.params.get('inline_voice'):
                    self.params['current_voice'] = self.params['inline_voice']
                else:
                    self.params['current_voice'], error = self._set_voice(self.params['block_voice'])
                    if self.params['current_voice'] is None and error is not None:
                        return False, error
                self.audio_segments = []
                for part in sentence_parts:
                    part = part.strip()
                    if not part:
                        continue
                    if SML_TAG_PATTERN.fullmatch(part):
                        success, error = self._convert_sml(part)
                        if not success:
                            return False, error
                        continue
                    if not any(c.isalnum() for c in part):
                        continue
                    else:
                        trim_audio_buffer = 0.006
                        # only the voice path crosses the pipe: the worker computes the
                        # speaker embedding once per voice file and keeps it.
                        reply = self.engine.send({
                            'op': 'tts',
                            'text': part,
                            'language': self.language_espeak,
                            'voice': self.params['current_voice'],
                            'file': part_file,
                            **self.fine_tuned_params,
                            # inside [emotion:...]...[/emotion] the tag wins over the panel
                            **({'emotion_enabled': True, 'emotion': self.params['inline_emotion']} if self.params.get('inline_emotion') else {})
                        })
                        if not reply.get('ok'):
                            # no retry: core.py unloads the engine, which stops the worker
                            error = f"convert() error: {reply.get('error')} segment: {part}"
                            print(error)
                            return False, error
                        audio_part, samplerate = sf.read(part_file, dtype='float32')
                        os.unlink(part_file)
                        if not is_audio_data_valid(audio_part):
                            error = 'audio_part not valid'
                            return False, error
                        self.params['samplerate'] = int(samplerate)
                        part_tensor = self._tensor_type(audio_part).reshape(1, -1)
                        if part_tensor.numel() == 0:
                            error = 'part_tensor not valid'
                            return False, error
                        if part[-1].isalnum() or part[-1] == '—':
                            part_tensor = trim_audio(part_tensor.squeeze(), self.params['samplerate'], 0.001, trim_audio_buffer).unsqueeze(0)
                        self.audio_segments.append(part_tensor)
                        if not re.search(r'\w$', part, flags=re.UNICODE) and part[-1] != '—':
                            silence_time = int(np.random.uniform(0.3, 0.6) * 100) / 100
                            self.audio_segments.append(torch.zeros(1, int(self.params['samplerate'] * silence_time)))
                if self.audio_segments:
                    segment_tensor = torch.cat(self.audio_segments, dim=-1)
                    if not self.audio_save(sentence_file, segment_tensor, self.params['samplerate']):
                        error = f'audio_save() error: cannot save {sentence_file}'
                        return False, error
                    self.audio_segments = []
                    if not os.path.exists(sentence_file):
                        error = legends['error_cannot_create'].format(file=sentence_file)
                        return False, error
                return True, None
            else:
                error = legends['error_tts_engine_load_failed'].format(engine=self.session['tts_engine'])
                return False, error
        except Exception as e:
            self.audio_segments = []
            return False, self.log_exception(f'{self.__class__.__name__}.convert()', e)
        finally:
            if os.path.exists(part_file):
                try:
                    os.unlink(part_file)
                except OSError:
                    pass

    def create_vtt(self, all_sentences:list)->bool:
        if self._build_vtt_file(all_sentences):
            return True
        return False