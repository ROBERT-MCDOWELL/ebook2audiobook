import os, sys
from multiprocessing.managers import DictProxy
from lib.classes.subprocess_pipe import SubprocessPipe
from lib.conf_models import TTS_VOICE_CONVERSION, default_vc_model_cpu
from lib.lang import legends

class KnnVC(SubprocessPipe):
    # The voice conversion of the built-in voice engines on a CPU device: kNN-VC (default_vc_model_cpu, TTS_VOICE_CONVERSION
    # "knnvc") in its own torch worker, workers/knnvc_worker.py. The audio.cpp models of VoiceConversion take seconds per
    # second of speech on CPU (Seed-VC's diffusion steps); kNN-VC is one WavLM pass, a nearest neighbour lookup and the
    # HiFi-GAN, faster than real time. The whole voice file is its matching set and mix 1.0 keeps nothing of the built-in
    # voice: 100% cloned voice.
    # The same interface as VoiceConversion (send(), vc_model, resynthesis, backend, package_name), so the engines take
    # either one from TTSUtils._load_engine_zs(). A SubprocessPipe itself, cached in loaded_tts under the engine's
    # tts_zs_key, so unload_tts_manager() / cleanup_models_cache() stop it like any worker.
    # The worker runs on e2a's python without conf.py's OMP_NUM_THREADS=1 (that one is for e2a's own torch): torch takes
    # every physical core for it. It serves a CPU device, and a GPU device none of whose audio.cpp packages runs the voice
    # conversion (VoiceConversion.GpuUnavailable): device_wanted
    def __init__(self, session:DictProxy)->None:
        try:
            self.session = session
            self.vc_model = default_vc_model_cpu.rsplit('/', 1)[-1]
            cfg = TTS_VOICE_CONVERSION[self.vc_model]
            # voice to voice only: the engine always speaks the sentence first
            self.resynthesis = False
            self.languages = None
            self.backend = 'cpu'
            self.package_name = 'torch'
            # the session device it serves (a GPU one when it took over from VoiceConversion): kept for that device only
            self.device_wanted = session['device']
            progress_bar = getattr(sys.modules.get('lib.gradio'), 'progress_bar', None)
            worker_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'workers', 'knnvc_worker.py')
            worker_env = {k: v for k, v in os.environ.items() if k != 'OMP_NUM_THREADS'}
            worker_env['PYTHONUNBUFFERED'] = '1'
            cmd = [
                sys.executable, '-u', worker_script, '--model', cfg['path'], '--device', self.backend,
                '--topk', str(cfg['topk']), '--mix', str(cfg['mix']), '--vad', str(cfg['vad']), '--window', str(cfg['window'])
            ]
            msg = legends['msg_worker_starting'].format(engine=self.vc_model, model='WavLM-Large + HiFi-GAN', device=self.backend)
            print(msg)
            if progress_bar is not None:
                progress_bar(0.0, desc=msg)
            SubprocessPipe.__init__(self, cmd, is_gui_process=session['is_gui_process'], total_duration=0, msg=msg, keep_alive=True, env=worker_env)
            if not self.result:
                error = legends['error_worker_failed'].format(engine=self.vc_model, error=self.ready_info.get('error'))
                raise RuntimeError(error)
        except Exception as e:
            if getattr(self, 'process', None) is not None:
                self.stop()
            error = f'KnnVC.__init__() error: {e}'
            raise RuntimeError(error) from e

    def send(self, request:dict)->dict:
        # the engines' request ({"op": "vc", "source", "voice", "file", "text", "language"}) -> the worker's: the source
        # converted to the voice file, text and language unused
        return SubprocessPipe.send(self, {'op': 'vc', 'source': request['source'], 'voice': request['voice'], 'file': request['file']})
