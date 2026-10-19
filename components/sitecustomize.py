"""
Global environment initialization hook.
Executed automatically on Python startup before user code.
Use this for lightweight, idempotent environment patches.
"""

import sys, os, importlib
import importlib.machinery
from types import ModuleType

debug = os.environ.get('DEBUG_SITECUSTOMIZE') == '1'
def warn(msg: str) -> None:
    if debug:
        print(f'[sitecustomize] {msg}')

inactive = any(os.environ.get(v) == '1' for v in [
    'TORCH_BUILD', 'PYTORCH_BUILD', 'DISABLE_SITECUSTOMIZE'
])

if inactive:
    patch_enabled = False
else:
    patch_enabled = True

def patch_torchaudio(mod: ModuleType) -> None:
    if getattr(getattr(mod, 'load', None), '__name__', '') == '_load_via_soundfile':
        return
    try:
        import soundfile as sf
        import torch
    except ImportError as e:
        warn(f'torchaudio.load patch skipped: {e!r}')
        return

    def _load_via_soundfile(uri, frame_offset:int=0, num_frames:int=-1,
                           normalize:bool=True, channels_first:bool=True,
                           **_ignored):
        start = int(frame_offset) if frame_offset else 0
        frames = -1 if (num_frames is None or num_frames<0) else int(num_frames)
        dtype = 'float32' if normalize else 'int16'
        data, sr = sf.read(uri, start=start, frames=frames,
                           dtype=dtype, always_2d=True)
        tensor = torch.from_numpy(data)
        if channels_first:
            tensor = tensor.T.contiguous()
        return tensor, sr

    mod.load = _load_via_soundfile
    warn('patched torchaudio.load → soundfile')

def patch_torch(mod: ModuleType) -> None:
    """Allowlist Coqui-TTS classes for PyTorch 2.6+ weights_only=True loading."""
    try:
        import torch
        from TTS.tts.configs.xtts_config import XttsConfig
        if hasattr(torch.serialization, 'add_safe_globals'):
            torch.serialization.add_safe_globals([XttsConfig])
            warn('added XttsConfig to torch safe globals')
    except Exception as e:
        warn(f'failed to add torch safe globals: {e!r}')


if patch_enabled:

    class WrappedLoader:
        def __init__(self, orig):
            self._orig = orig

        def create_module(self, spec):
            if hasattr(self._orig, 'create_module'):
                return self._orig.create_module(spec)
            return None

        def exec_module(self, module):
            self._orig.exec_module(module)
            name = module.__name__
            if name == 'torchaudio':
                patch_torchaudio(module)
            elif name == 'torch':
                patch_torch(module)

    class LazyPatchHook:
        def find_spec(self, fullname, path, target=None):
            if fullname not in ('torchaudio', 'torch'):
                return None
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if not spec or not spec.loader:
                return spec
            spec.loader = WrappedLoader(spec.loader)
            return spec

    sys.meta_path.insert(0, LazyPatchHook())