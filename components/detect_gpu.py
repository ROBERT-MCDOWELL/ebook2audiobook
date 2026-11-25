import json
import sys
import os
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DEVICE_INFO_JSON = os.path.normpath(os.path.join(ROOT_DIR, '.device_info.json'))
HSA_OVERRIDE_ENV = "HSA_OVERRIDE_GFX_VERSION"
# LLVM's generic processors (AMDGPUUsage): the targets one ISA family shares, a single build runs on all its members.
# An override inside a family runs (gfx1031 -> 10.3.0, gfx1103 -> 11.0.0); across families the ISA differs and torch's
# code crashes the GPU (crash report 8a1a1c471e8f6852: gfx1013 under 10.3.0). A target in none of them gets no verdict
GFX_FAMILIES = {
    'gfx9-generic': {'gfx900', 'gfx902', 'gfx904', 'gfx906', 'gfx909', 'gfx90c'},
    'gfx9-4-generic': {'gfx940', 'gfx941', 'gfx942'},
    'gfx10-1-generic': {'gfx1010', 'gfx1011', 'gfx1012', 'gfx1013'},
    'gfx10-3-generic': {'gfx1030', 'gfx1031', 'gfx1032', 'gfx1033', 'gfx1034', 'gfx1035', 'gfx1036'},
    'gfx11-generic': {'gfx1100', 'gfx1101', 'gfx1102', 'gfx1103', 'gfx1150', 'gfx1151', 'gfx1152', 'gfx1153'},
    'gfx12-generic': {'gfx1200', 'gfx1201'},
}

def gfx_family(target:str|None)->str|None:
    return next((family for family, members in GFX_FAMILIES.items() if target in members), None)

def crosses_family(native:str|None, target:str|None)->bool:
    """True when both targets belong to known ISA families, different ones: code for target cannot run on native."""
    native_family, target_family = gfx_family(native), gfx_family(target)
    return bool(native_family and target_family and native_family != target_family)

def override_target(override:str|None)->str|None:
    """The gfx target an HSA_OVERRIDE_GFX_VERSION value runs ('10.3.0' -> 'gfx1030', '9.0.10' -> 'gfx90a'), None when
    unset or malformed."""
    try:
        major, minor, step = map(int, str(override).split('.'))
    except ValueError:
        return None
    return f'gfx{major}{minor}{step:x}'

def rocm_arch_list()->set[str]|None:
    """GPU targets the installed ROCm torch was built for ('gfx1200', ...), read without starting the HIP runtime: HSA
    reads HSA_OVERRIDE_GFX_VERSION once, when torch first touches the GPU. torch.cuda.get_arch_list() would start it,
    torch._C._cuda_getArchFlags() is the build's own string (what torch.utils.cpp_extension reads on ROCm).
    None when torch cannot say: not a ROCm build, or no such string."""
    try:
        import torch
        flags = torch._C._cuda_getArchFlags() if getattr(torch.version, 'hip', None) else None
    except Exception:
        return None
    if not flags:
        return None
    # 'gfx90a:xnack-' -> 'gfx90a'
    return {flag.split(':', 1)[0] for flag in str(flags).split()}

def handle_rocm_override(arch_list:set[str]|None=None)->str|None:
    """Sets HSA_OVERRIDE_GFX_VERSION in this process before torch touches the GPU.
    arch_list: the installed torch's GPU targets (rocm_arch_list()), None to decide from the DB alone.
    Returns the effective override (user-provided or resolved), or None."""
    if (override := os.environ.get(HSA_OVERRIDE_ENV)):
        return override
    try:
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)
        import rocmfix
        gpus = rocmfix.detect_gpus()
        if not gpus:
            return None
        # pass 0: offline lookup, bundled fallback DB + last downloaded cache, no network
        try:
            rocmfix.GPU_DATABASE.update(rocmfix._validate_db(json.loads(rocmfix.DB_CACHE_FILE.read_text(encoding='utf-8'))))
        except Exception:
            pass  # no cache yet or corrupt cache: keep the fallback DB
        # a GPU whose own target the installed torch was built for runs as itself, whatever the DB says: its entries
        # follow the ROCm releases that lacked the target (the bundled RX 9060 XT, gfx1200 -> '12.0.1', native since
        # ROCm 6.4.2), and a card the DB knows never gets the downloaded update. Under that override the first tensor
        # moved to the GPU killed e2a (crash report ec3a0208c4c44215: segfault in stanza's model.to('cuda'))
        for attempt in range(2):
            overrides:set[str] = set()
            native_targets:set[str] = set()
            has_unknown = False
            for gpu in gpus:
                info = rocmfix.GPU_DATABASE.get(gpu['pci_id'])
                if info is None:
                    has_unknown = True
                elif arch_list is not None and info.get('gfx_target') in arch_list:
                    native_targets.add(info['gfx_target'])
                # an entry overriding across ISA families (a gfx1010 put on 10.3.0) is never applied: the GPU runs as
                # itself, and gpu_test() tells whether torch has code for it
                elif info.get('override') and not crosses_family(info.get('gfx_target'), override_target(info['override'])):
                    overrides.add(info['override'])
                elif info.get('supported'):
                    native_targets.add(info['gfx_target'])
            override = None
            if len(overrides) == 1:
                override = overrides.pop()
                # HSA_OVERRIDE_GFX_VERSION is process-wide: it also retargets natively supported cards,
                # so only apply it when they share its target ('10.3.0' -> 'gfx1030', '12.0.1' -> 'gfx1201')
                major, minor, step = map(int, override.split('.'))
                if native_targets - {f"gfx{major}{minor}{step:x}"}:
                    override = None
            if not has_unknown or attempt == 1:
                break
            # pass 1: a card is not in the DB, download it now
            rocmfix.sync_gpu_database(force=True)
        if override:
            os.environ[HSA_OVERRIDE_ENV] = override
        return override
    except Exception:
        return None  # rocmfix missing, offline, or unwritable ~/.rocmfix: never block GPU detection

def kfd_gpu_targets()->dict[tuple[int, int, int], str]:
    """(PCI domain, bus, device) -> gfx target of each GPU the amdgpu kernel driver lists (KFD topology): the
    hardware's own, HSA_OVERRIDE_GFX_VERSION only changes what the ROCm runtime reports above it. Read from sysfs,
    without the runtime. {} off Linux, without KFD, or on a kernel too old to give gfx_target_version"""
    targets:dict[tuple[int, int, int], str] = {}
    for props_file in glob.glob('/sys/class/kfd/kfd/topology/nodes/*/properties'):
        props:dict[str, str] = {}
        try:
            with open(props_file, encoding='utf-8') as f:
                for line in f:
                    key, _, value = line.strip().partition(' ')
                    props[key] = value.strip()
            # major * 10000 + minor * 100 + stepping, decimal: 100103 -> gfx1013, 90010 -> gfx90a. 0 on a CPU node
            version = int(props.get('gfx_target_version') or 0)
            location = int(props.get('location_id') or 0)
            domain = int(props.get('domain') or 0)
        except (OSError, ValueError):
            continue
        if version:
            # location_id is the PCI id: bus << 8 | device << 3 | function
            targets[(domain, location >> 8, (location >> 3) & 0x1f)] = f'gfx{version // 10000}{version // 100 % 100}{version % 100:x}'
    return targets

def rocm_gfx_mismatch(torch, index:int, count:int, override:str|None, kfd:dict[tuple[int, int, int], str])->dict|None:
    """The details when HSA_OVERRIDE_GFX_VERSION puts ROCm device index on code of another ISA family, else None.
    Decided from the kernel's target (kfd_gpu_targets()), before anything runs on the GPU: the GPU test would kill this
    child, or pass on a small tensor and the model load crash later. The device is matched to its KFD node by PCI
    address; a torch without those properties is matched only when both list a single GPU"""
    target = override_target(override)
    if not kfd or not gfx_family(target):
        return None
    try:
        props = torch.cuda.get_device_properties(index)
        address = (getattr(props, 'pci_domain_id', None), getattr(props, 'pci_bus_id', None), getattr(props, 'pci_device_id', None))
    except Exception:
        address = (None, None, None)
    if None not in address:
        native = kfd.get(address)
    else:
        native = next(iter(kfd.values())) if len(kfd) == 1 and count == 1 else None
    if not crosses_family(native, target):
        return None
    return dict(device=f'cuda:{index}', native=native, native_family=gfx_family(native), override=override, target=target, target_family=gfx_family(target))

def gpu_test(torch, accel, prefix:str, index:int)->str|None:
    """Why GPU index of a torch backend (accel: torch.cuda for CUDA and ROCm, torch.xpu, prefix their device type)
    does not run torch's code, None when it does.
    A device count never runs GPU code: a GPU the runtime lists but cannot run passed with count 1, and the first model
    moved to it killed e2a (crash report 8a1a1c471e8f6852: a BC-250, gfx1013, which no ROCm supports, under the user's
    HSA_OVERRIDE_GFX_VERSION=10.3.0, the gfx1030 code of another ISA family; Aborted in a ROCm thread at XTTS
    module.to()). The device gets what a model load starts with: a host tensor copied over (Module.to()), kernels on it,
    the result read back. A native fault kills this child: usable_devices() says which device it tests first"""
    size = 1 << 22
    device = f'{prefix}:{index}'
    try:
        on_gpu = torch.ones(size).to(device)
        # 3 * 2**22 stays below 2**24: every partial sum of the reduction is exact in float32
        total = (on_gpu * 2 + 1).sum().item()
        accel.synchronize(index)
    except Exception as e:
        return f'{device} GPU test failed: {type(e).__name__}: {e}'
    if total != 3 * size:
        return f'{device} GPU test failed: computed {total:g} instead of {3 * size}'
    return None

def usable_devices(torch, backend:str, count:int, override:str|None, skip:set[int])->tuple[list[int], list[str], dict|None]:
    """The GPUs of backend ('cuda', 'rocm', 'xpu') torch runs on, each judged alone: a rejected one never hides the
    others (an unsupported iGPU listed before a working card). Returns (their indices, why each other one is not, the
    first ISA family mismatch, ROCm only). skip: devices whose GPU test killed an earlier probe or hung
    (DeviceInstaller.probe_gpus() runs it again without them). Each GPU test is announced on stdout first and its end
    after, so a native crash or a GPU that hangs (no end within DeviceInstaller.first_gpu_test_timeout for the first test,
    gpu_test_timeout after) tells which it was"""
    accel, prefix = (torch.xpu, 'xpu') if backend == 'xpu' else (torch.cuda, 'cuda')
    try:
        # the runtime's own start-up, before the GPU tests and their time limit
        if (init := getattr(accel, 'init', None)):
            init()
    except Exception as e:
        return [], [f'torch.{prefix}.init() failed: {type(e).__name__}: {e}'], None
    kfd = kfd_gpu_targets() if backend == 'rocm' and gfx_family(override_target(override)) else {}
    usable:list[int] = []
    reasons:list[str] = []
    first_gfx:dict|None = None
    for index in range(count):
        if index in skip:
            continue
        if backend == 'rocm' and (gfx := rocm_gfx_mismatch(torch, index, count, override, kfd)):
            first_gfx = first_gfx or gfx
            reasons.append(f"{gfx['device']} is a {gfx['native']} ({gfx['native_family']}), {HSA_OVERRIDE_ENV}={gfx['override']} runs {gfx['target']} code ({gfx['target_family']}) on it: another ISA family")
            continue
        print(json.dumps({'gpu_testing': index, 'gpu_count': count, 'device': f'{prefix}:{index}', 'backend': backend}), flush=True)
        reason = gpu_test(torch, accel, prefix, index)
        print(json.dumps({'gpu_tested': index}), flush=True)
        if reason:
            reasons.append(reason)
            continue
        usable.append(index)
    return usable, reasons, first_gfx

def rocm_denied_nodes()->list[str]:
    """Returns the ROCm device nodes this process cannot open read/write.
    ROCm opens /dev/kfd plus the render node of every amdgpu device, and udev rules can put them in different groups."""
    nodes:list[str] = ['/dev/kfd']
    for sys_node in sorted(glob.glob('/sys/class/drm/renderD*')):
        # hybrid boxes: skip Intel/NVIDIA render nodes, ROCm never opens them
        if os.path.basename(os.path.realpath(os.path.join(sys_node, 'device', 'driver'))) == 'amdgpu':
            nodes.append(os.path.join('/dev/dri', os.path.basename(sys_node)))
    return [node for node in nodes if os.path.exists(node) and not os.access(node, os.R_OK | os.W_OK)]

def hip_runtime(candidates:list[str])->dict:
    """The system HIP runtime's device count and version ('--hip-runtime', from DeviceInstaller.check_hardware). Asked
    here, in a child: a libamdhip64 loaded in e2a's process stays there, and torch imported later binds its own ROCm
    libraries to it by soname (libamdhip64.so.7), running torch built for one ROCm on the system's other one.
    The DB override is set first, as the system probe always had it; it does not leave this process"""
    handle_rocm_override()
    import ctypes
    for lib_name in candidates:
        try:
            libhip = ctypes.CDLL(lib_name)
        except OSError:
            continue
        try:
            count = ctypes.c_int()
            version = ctypes.c_int()
            return {
                'count': count.value if libhip.hipGetDeviceCount(ctypes.byref(count)) == 0 else 0,
                'version': version.value if libhip.hipRuntimeGetVersion(ctypes.byref(version)) == 0 else None,
            }
        except AttributeError:
            continue
    return {}

def main()->None:
    result = {'count': 0, 'backend': None, 'hsa_override': None, 'error': None}
    try:
        if not os.path.exists(DEVICE_INFO_JSON):
            result['error'] = f'device_info_json not found: {DEVICE_INFO_JSON}'
            print(json.dumps(result))
            sys.exit(1)

        with open(DEVICE_INFO_JSON, 'r', encoding='utf-8') as f:
            device_info = json.load(f)

        backend = device_info.get('name')
        result['backend'] = backend

        # Run ROCm check & fallback before PyTorch loads
        if backend == 'rocm':
            result['hsa_override'] = handle_rocm_override(rocm_arch_list())
            if (denied := rocm_denied_nodes()):
                result['error'] = f"no read/write access to {', '.join(denied)}: user not in its group (render or video), relaunch ebook2audiobook.command or log out and back in"

        # torch import costs seconds: only pay it when there is a device count to read
        if backend in ('cuda', 'rocm', 'xpu') and result['error'] is None:
            import torch
            match backend:
                case 'cuda' | 'rocm' if torch.cuda.is_available() and bool(getattr(torch.version, 'hip', None)) == (backend == 'rocm'):
                    # wheel vendor must match the tag: a CUDA wheel on a rocm tag (or the reverse) keeps count at 0
                    result['count'] = torch.cuda.device_count()
                case 'xpu' if hasattr(torch, 'xpu') and torch.xpu.is_available():
                    result['count'] = torch.xpu.device_count()
            # E2A_GPU_TEST=0: the count alone (DeviceInstaller.cuda_torch_crashes, which judges wheels, not GPUs)
            if result['count'] > 0 and os.environ.get('E2A_GPU_TEST') != '0':
                # torch's own count, before the tests: a verdict about these GPUs, not about a runtime that sees none
                result['listed'] = result['count']
                skip = {int(index) for index in os.environ.get('E2A_GPU_SKIP', '').split(',') if index.strip().isdigit()}
                usable, reasons, gfx = usable_devices(torch, backend, result['count'], result['hsa_override'], skip)
                result['count'] = len(usable)
                result['devices'] = usable
                result['error'] = '; '.join(reasons) or None
                if gfx:
                    result['gfx'] = gfx
        # mps, jetson, cpu → no torch import, count stays 0 (single-device or no-device)
    except Exception as e:
        result['error'] = str(e)

    print(json.dumps(result))

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--hip-runtime':
        print(json.dumps(hip_runtime(json.loads(sys.argv[2]))))
    else:
        main()
