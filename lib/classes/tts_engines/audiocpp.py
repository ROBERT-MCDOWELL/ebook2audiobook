import json
from lib.classes.tts_engines.common.headers import *
from lib.classes.tts_engines.common.preset_loader import load_engine_presets
from lib.classes.subprocess_pipe import SubprocessPipe
from lib.conf import systems
from lib.conf_models import audiocpp_packages, audiocpp_asr, audiocpp_vc, audiocpp_engines, audiocpp_repo
from lib.lang import legends

class AudioCpp(TTSUtils):
    # GPU packages whose server died during a conversion, per e2a process: package -> crash count (shared by every
    # audio.cpp engine, they run the same packages). One crash restarts the same package, a second one drops it until
    # e2a restarts (next GPU package, else CPU)
    gpu_crashes = {}

    def __init__(self, session:DictProxy):
        # audio.cpp (0xShug0/audio.cpp): a native audiocpp_server package per platform (audiocpp_packages, shared by
        # every audio.cpp engine) plus the GGUF weights of the fine_tuned preset, driven by workers/audiocpp_worker.py.
        # No torch, no venv
        try:
            import platform, tarfile, zipfile, urllib.request
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
            fine_tuned = self.session.get('fine_tuned')
            show_alert = getattr(sys.modules.get('lib.core'), 'show_alert', None)
            progress_bar = getattr(sys.modules.get('lib.gradio'), 'progress_bar', None)
            if fine_tuned not in self.models:
               error = legends['error_invalid_fine_tuned'].format(model=fine_tuned, models=list(self.models.keys()))
               raise ValueError(error)
            model_cfg = self.models[fine_tuned]
            for required_key in ('repo', 'files', 'samplerate', 'voice'):
               if required_key not in model_cfg:
                  error = legends['error_fine_tuned_missing_key'].format(model=fine_tuned, key=required_key)
                  raise ValueError(error)
            self.family_cfg = settings['audiocpp']
            self.family = self.family_cfg['family']
            # a preset may speak fewer languages than its engine (IndexTTS2 v2)
            languages = model_cfg.get('languages') or settings['languages']
            if self.language not in languages:
               error = legends['error_language_not_supported_engine'].format(lang=self.language, engine=f'{tts_engine} ({fine_tuned})')
               raise ValueError(error)
            self.language_code = languages[self.language]
            # built-in voice for this language (engines that do not clone)
            self.voice_id = self.family_cfg['voice_ids'].get(self.language, self.family_cfg['voice_ids'].get('*', ''))
            # one package per language (PocketTTS), with its load options
            model_files = model_cfg.get('files_by_language', {}).get(self.language, model_cfg['files'])
            self.load_options = {**self.family_cfg['load'], **self.family_cfg['load_by_language'].get(self.language, {})}
            self.params['samplerate'] = model_cfg['samplerate']
            self.model_repo = model_cfg['repo']
            self.xtts_speakers = self._load_xtts_builtin_list()
            self.device = devices['CUDA']['proc'] if self.session['device'] in [devices['CUDA']['proc'], devices['ROCM']['proc'], devices['JETSON']['proc']] else self.session['device']
            # --- the audiocpp_server package for this machine ---
            machine = platform.machine().lower()
            gpu_wanted = self.session['device'] != devices['CPU']['proc']
            # CUDA packages for NVIDIA devices only: ROCm and XPU go to Vulkan, MPS to Metal
            cuda_wanted = self.session['device'] in [devices['CUDA']['proc'], devices['JETSON']['proc']]
            packages = audiocpp_packages
            jetpack = board_sm = None
            if sys.platform == systems['LINUX'] and os.path.exists('/etc/nv_tegra_release'):
               # L4T release -> JetPack major (R35 = 5, R36 = 6, R38+ = 7); board -> GPU architecture
               with open('/etc/nv_tegra_release', 'r', encoding='utf-8', errors='replace') as f:
                  l4t = re.search(r'R(\d+)', f.read())
               jetpack = {35: 5, 36: 6}.get(int(l4t.group(1)), 7 if int(l4t.group(1)) >= 38 else None) if l4t else None
               try:
                  with open('/proc/device-tree/model', 'r', encoding='utf-8', errors='replace') as f:
                     board = f.read()
                  board_sm = 110 if 'Thor' in board else 87 if 'Orin' in board else 72 if 'Xavier' in board else None
               except OSError:
                  board_sm = None
            if sys.platform == systems['LINUX'] and machine in ('x86_64', 'amd64'):
               # own builds first (older glibc, bundled CUDA runtime), audio.cpp's official ones (glibc 2.38+) after
               candidates = (['linux-x64-cuda13', 'linux-x64-cuda12'] if cuda_wanted else []) + (['linux-x64-vulkan', 'linux-x64-vulkan-acpp'] if gpu_wanted else []) + ['linux-x64-cpu', 'linux-x64-cpu-acpp']
            elif sys.platform == systems['LINUX'] and machine in ('aarch64', 'arm64'):
               if jetpack is not None:
                  candidates = [k for k, v in packages.items() if v.get('jetpack') == jetpack and board_sm in v.get('sm', [])]
               else:
                  candidates = ['linux-aarch64-cuda13', 'linux-aarch64-cuda12'] if cuda_wanted else []
               candidates = (candidates if gpu_wanted else []) + ['linux-aarch64']
            elif sys.platform == systems['WINDOWS'] and machine in ('amd64', 'x86_64'):
               candidates = (['windows-x64-cuda13-acpp', 'windows-x64-cuda12-acpp'] if cuda_wanted else []) + (['windows-x64-vulkan-acpp'] if gpu_wanted else []) + ['windows-x64-cpu-acpp']
            elif sys.platform == systems['MACOS']:
               # arm64: official Metal build (the same archive runs --backend cpu). x86_64: official build is CPU only
               candidates = ((['macos-arm64-acpp'] if gpu_wanted else []) + ['macos-arm64-cpu-acpp']) if machine == 'arm64' else ((['macos-x86_64-vulkan'] if gpu_wanted else []) + ['macos-x86_64-acpp'])
            else:
               candidates = []
            # CPU features the packages may need, with /proc/cpuinfo names on every OS
            cpu_flags = set()
            if os.path.exists('/proc/cpuinfo'):
               with open('/proc/cpuinfo', 'r', encoding='utf-8', errors='replace') as f:
                  features = re.search(r'^(?:Features|flags)\s*:\s*(.*)$', f.read(), re.M)
               cpu_flags = set(features.group(1).split()) if features else set()
            elif sys.platform == systems['WINDOWS']:
               import ctypes
               present = ctypes.windll.kernel32.IsProcessorFeaturePresent
               cpu_flags = ({'sse4_2'} if present(38) else set()) | ({'avx2', 'fma', 'f16c', 'bmi2'} if present(40) else set())
            glibc = platform.libc_ver()
            glibc_version = tuple(int(x) for x in re.findall(r'\d+', glibc[1])[:2]) if glibc[0] == 'glibc' and glibc[1] else (0, 0)
            mac_version = tuple(int(x) for x in (platform.mac_ver()[0] or '0').split('.')[:2]) if sys.platform == systems['MACOS'] else (0, 0)
            machine_desc = f'{sys.platform} {machine}' + (f' JetPack {jetpack}' if jetpack else '') + (f' sm_{board_sm}' if board_sm else '')
            usable = [
               k for k in dict.fromkeys(candidates)
               if k in packages and packages[k].get('enabled', True) and set(packages[k].get('cpu_flags', [])) <= cpu_flags
               and AudioCpp.gpu_crashes.get(k, 0) < 2
               and glibc_version >= tuple(int(x) for x in packages[k].get('glibc_min', '0.0').split('.'))
               and mac_version >= tuple(int(x) for x in packages[k].get('macos_min', '0.0').split('.'))
            ]
            if not usable:
               if sys.platform == systems['MACOS'] and any(k in packages and packages[k].get('enabled', True) for k in candidates):
                  error = legends['error_zonos2_macos_min'].format(engine=tts_engine, min=min(packages[k].get('macos_min', '0') for k in candidates if k in packages and packages[k].get('enabled', True)), version=platform.mac_ver()[0])
               else:
                  error = legends['error_zonos2_no_package'].format(engine=tts_engine, machine=machine_desc)
               raise ValueError(error)
            # first choice, then the other GPU packages, then one CPU package to fall back on if a GPU one cannot start
            attempts = [usable[0]]
            if packages[usable[0]]['gpu']:
               attempts = [k for k in usable if packages[k]['gpu']] + [k for k in usable if not packages[k]['gpu']][:1]
            if gpu_wanted and not packages[usable[0]]['gpu'] and not any(n >= 2 for n in AudioCpp.gpu_crashes.values()):
               msg = legends['msg_zonos2_cpu_fallback'].format(engine=tts_engine, machine=machine_desc)
               if show_alert is not None:
                  show_alert(self.session['id'], {'type': 'warning', 'msg': msg})
               else:
                  print(msg)
            # --- GGUF weights through e2a's Hugging Face cache (tts_dir) ---
            from huggingface_hub import hf_hub_download
            # cloning engines taking a reference transcript also get the ASR model, loaded by the worker only for a voice it
            # has never transcribed, then unloaded. Built-in voice engines get Seed-VC for a picked voice file
            asr_files = audiocpp_asr['files'] if self.family_cfg['clone'] and self.family_cfg['ref_text'] else []
            vc_files = audiocpp_vc['files'] if not self.family_cfg['clone'] else []
            msg = legends['msg_zonos2_models'].format(engine=tts_engine, files=', '.join(os.path.basename(f) for f in model_files + asr_files + vc_files))
            print(msg)
            if progress_bar is not None:
               progress_bar(0.0, desc=msg)
            # the snapshot keeps the repo layout, so sidecars (pocket_tts embeddings/) land beside the model file
            self.model_path = [hf_hub_download(repo_id=self.model_repo, filename=f, cache_dir=self.cache_dir) for f in model_files][0]
            self.asr_path = [hf_hub_download(repo_id=audiocpp_repo, filename=f, cache_dir=self.cache_dir) for f in asr_files][0] if asr_files else ''
            self.vc_path = [hf_hub_download(repo_id=audiocpp_repo, filename=f, cache_dir=self.cache_dir) for f in vc_files][0] if vc_files else ''
            engine_dir = os.path.dirname(os.path.abspath(__file__))
            self.worker_script = os.path.join(engine_dir, 'workers', 'audiocpp_worker.py')
            # the worker is stdlib only. conf.py's OMP_NUM_THREADS=1 is for e2a's torch: the server (OpenMP build) sizes its own pool
            self.worker_env = {k: v for k, v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONSTARTUP', '__PYVENV_LAUNCHER__', 'OMP_NUM_THREADS')}
            self.worker_env['PYTHONUNBUFFERED'] = '1'
            if self.family_cfg['espeak']:
               # Kokoro phonemizes through eSpeak-ng: the library and data e2a's launchers export (else eSpeak's own defaults)
               espeak_library = os.environ.get('PHONEMIZER_ESPEAK_LIBRARY', '')
               espeak_data = os.environ.get('ESPEAK_DATA_PATH', '')
               if espeak_library and os.path.isfile(espeak_library):
                  self.worker_env['AUDIOCPP_ESPEAK_LIBRARY'] = espeak_library
               if espeak_data and os.path.isfile(os.path.join(espeak_data, 'phontab')):
                  self.worker_env['AUDIOCPP_ESPEAK_DATA'] = espeak_data
            for attempt, self.package_name in enumerate(attempts):
               package = packages[self.package_name]
               self.backend = package.get('backend', 'cpu') if package['gpu'] and gpu_wanted else 'cpu'
               try:
                  package_dir = os.path.join(engine_dir, 'venvs', 'audiocpp', self.package_name)
                  marker_file = os.path.join(package_dir, '.e2a_installed.json')
                  # downloaded once: a package folder with its install record is used as it is from then on; a record
                  # naming other urls (version bump, package moved to another build) is downloaded again
                  try:
                     with open(marker_file, 'r', encoding='utf-8') as f:
                        installed_urls = json.load(f).get('urls')
                  except Exception:
                     installed_urls = None
                  if installed_urls != package['urls']:
                     msg = legends['msg_zonos2_downloading'].format(engine=tts_engine, package=self.package_name)
                     print(msg)
                     if progress_bar is not None:
                        progress_bar(0.0, desc=msg)
                     shutil.rmtree(package_dir, ignore_errors=True)
                     os.makedirs(package_dir, exist_ok=True)
                     try:
                        # Windows CUDA: the bin archive and its cudart archive unpack into the same folder
                        for url in package['urls']:
                           archive = os.path.join(package_dir, os.path.basename(url))
                           # urllib: no quarantine flag on macOS, so the unsigned binaries start without a Gatekeeper prompt
                           with urllib.request.urlopen(url, timeout=60) as r, open(archive, 'wb') as f:
                              total = int(r.headers.get('Content-Length') or 0)
                              done = 0
                              while True:
                                 chunk = r.read(1 << 20)
                                 if not chunk:
                                    break
                                 f.write(chunk)
                                 done += len(chunk)
                                 if progress_bar is not None and total:
                                    progress_bar(done / total, desc=msg)
                           if archive.endswith('.zip'):
                              with zipfile.ZipFile(archive) as z:
                                 z.extractall(package_dir)
                           else:
                              with tarfile.open(archive, 'r:gz') as t:
                                 t.extractall(package_dir, **({'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}))
                           os.unlink(archive)
                     except Exception as e:
                        shutil.rmtree(package_dir, ignore_errors=True)
                        error = legends['error_zonos2_download'].format(engine=tts_engine, package=self.package_name, error=e)
                        raise RuntimeError(error)
                     with open(marker_file, 'w', encoding='utf-8') as f:
                        json.dump({'urls': package['urls']}, f, indent=2)
                  server_name = 'audiocpp_server.exe' if sys.platform == systems['WINDOWS'] else 'audiocpp_server'
                  self.server_bin = next((os.path.join(root, server_name) for root, _, files in os.walk(package_dir) if server_name in files), None)
                  if self.server_bin is None:
                     shutil.rmtree(package_dir, ignore_errors=True)
                     error = legends['error_zonos2_download'].format(engine=tts_engine, package=self.package_name, error=f'{server_name} not found in the package')
                     raise RuntimeError(error)
                  if sys.platform != systems['WINDOWS']:
                     os.chmod(self.server_bin, os.stat(self.server_bin).st_mode | 0o755)
                  # own macOS Vulkan package: it carries its loader and MoltenVK in lib/, unless the user set a driver list
                  icd = os.path.join(os.path.dirname(self.server_bin), 'lib', 'MoltenVK_icd.json')
                  if os.path.isfile(icd) and not (os.environ.get('VK_DRIVER_FILES') or os.environ.get('VK_ICD_FILENAMES')):
                     self.worker_env['VK_DRIVER_FILES'] = icd
                     self.worker_env['VK_ICD_FILENAMES'] = icd
                  self.engine = self.load_engine()
                  break
               except Exception as e:
                  if attempt + 1 >= len(attempts):
                     raise
                  msg = legends['msg_zonos2_gpu_failed'].format(engine=tts_engine, package=self.package_name, error=e)
                  if show_alert is not None:
                     show_alert(self.session['id'], {'type': 'warning', 'msg': msg})
                  else:
                     print(msg)
        except Exception as e:
            error = f'__init__() error: {e}'
            raise ValueError(error)

    def load_engine(self)->Any:
        try:
            msg = legends['msg_loading_tts_model'].format(model=self.tts_key)
            print(msg)
            self.cleanup_memory()
            cmd = [
               sys.executable, '-u', self.worker_script, '--server', self.server_bin, '--model', self.model_path, '--family', self.family, '--backend', self.backend,
               '--load-options', json.dumps(self.load_options), '--session-options', json.dumps(self.family_cfg['session']), '--request-options', json.dumps(self.family_cfg['request']),
               '--ref-min', str(self.family_cfg['ref_min']), '--ref-max', str(self.family_cfg['ref_max']), '--ref-text', self.family_cfg['ref_text'] or 'none', '--ref-fallback', json.dumps(self.family_cfg['ref_fallback']),
               '--asr-model', self.asr_path, '--asr-family', audiocpp_asr['family'], '--vc-model', self.vc_path, '--vc-family', audiocpp_vc['family'], '--samplerate', str(self.params['samplerate'])
            ] + (['--language-option'] if self.family_cfg['language_option'] else []) + (['--clone'] if self.family_cfg['clone'] else []) + (['--speaker-label'] if self.family_cfg['speaker_label'] else [])
            engine = loaded_tts.get(self.tts_key)
            if isinstance(engine, SubprocessPipe) and (engine.cmd != cmd or engine.process is None or engine.process.poll() is not None):
               # dead worker, or one serving another model/package/backend under this key
               loaded_tts.pop(self.tts_key, None)
               engine.stop()
               engine = None
            if not engine:
               msg = legends['msg_worker_starting'].format(engine=self.session['tts_engine'], model=os.path.basename(self.model_path), device=f'{self.package_name}, {self.backend}')
               print(msg)
               progress_bar = getattr(sys.modules.get('lib.gradio'), 'progress_bar', None)
               if progress_bar is not None:
                  progress_bar(0.0, desc=msg)
               engine = SubprocessPipe(cmd, is_gui_process=self.session['is_gui_process'], total_duration=0, msg=msg, keep_alive=True, env=self.worker_env)
               if not engine.result:
                  error = legends['error_worker_failed'].format(engine=self.session['tts_engine'], error=engine.ready_info.get('error'))
                  raise RuntimeError(error)
               # always cached, whatever the free VRAM: the worker must stay reachable by
               # unload_tts_manager() / cleanup_models_cache(), which stop it
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
            from lib.classes.tts_engines.common.audio import is_audio_data_valid
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
                      # only the voice path crosses the pipe: the worker cuts one reference clip per voice file and keeps it.
                      # Built-in voice engines: voice None = their own voice (voice_id), a voice file = converted to it
                      reply = self.engine.send({
                         'op': 'tts',
                         'text': part,
                         'language': self.language_code,
                         'voice': self.params['current_voice'],
                         'voice_id': self.voice_id,
                         'file': part_file
                      })
                      if not reply.get('ok') and reply.get('server_exited') and self.backend != 'cpu':
                         # the GPU server died mid-sentence (driver abort): restart it once, drop the package on its second
                         # death, and redo the whole sentence with a fresh engine (__init__ picks the package, CPU last)
                         crashes = AudioCpp.gpu_crashes[self.package_name] = AudioCpp.gpu_crashes.get(self.package_name, 0) + 1
                         error = str(reply.get('error') or '')
                         error = (error.split(': ', 1)[0] + ': ' + error.split(' | ')[-1]) if ' | ' in error else error
                         msg = legends['msg_zonos2_gpu_restart' if crashes < 2 else 'msg_zonos2_gpu_dropped'].format(engine=self.session['tts_engine'], package=self.package_name, error=error)
                         show_alert = getattr(sys.modules.get('lib.core'), 'show_alert', None)
                         if show_alert is not None:
                            show_alert(self.session['id'], {'type': 'warning', 'msg': msg})
                         else:
                            print(msg)
                         loaded_tts.pop(self.tts_key, None)
                         self.engine.stop()
                         self.engine = None
                         self.__init__(self.session)
                         return self.convert(sentence_file, sentence, **kwargs)
                      if not reply.get('ok'):
                         # no retry: core.py unloads the engine, which stops the worker
                         error = f"convert() error: {reply.get('error')} segment: {part}"
                         print(error)
                         return False, error
                      audio_part, samplerate = sf.read(part_file, dtype='float32')
                      os.unlink(part_file)
                      if audio_part.ndim > 1:
                         audio_part = audio_part.mean(axis=1)
                      if not is_audio_data_valid(audio_part):
                         error = 'audio_part not valid'
                         return False, error
                      if int(samplerate) != self.params['samplerate']:
                         # the preset's rate was a guess: silences already queued ([break] before the first reply) are
                         # rebuilt at the real one
                         self.audio_segments = [torch.zeros(1, int(seg.shape[-1] * int(samplerate) / self.params['samplerate'])) for seg in self.audio_segments]
                         self.params['samplerate'] = int(samplerate)
                      part_tensor = self._tensor_type(audio_part).reshape(1, -1)
                      if part_tensor.numel() == 0:
                         error = 'part_tensor not valid'
                         return False, error
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

# one registered engine per audio.cpp family (TTS_ENGINES), all run by AudioCpp
for _acpp_engine in audiocpp_engines:
    type(f"AudioCpp_{_acpp_engine}", (AudioCpp, TTSRegistry), {}, name=_acpp_engine)
