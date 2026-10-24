import os, sys, json, shutil, zipfile, argparse, importlib.util, urllib.request, urllib.parse
from pathlib import Path
from typing import Callable
root_dir = str(Path(__file__).resolve().parents[1])
os.chdir(root_dir)
sys.path.insert(0, root_dir)
categories = ['common', 'xtts', 'bark', 'tortoise', 'vits', 'fairseq', 'glowtts', 'tacotron', 'yourtts', 'piper', 'zonos', 'audiocpp', 'gptsovits', 'f5tts', 'omnivoice', 'orpheus', 'stanza', 'pyannote', 'demucs', 'interlude', 'argos', 'tessdata', 'jieba', 'voices']
parser = argparse.ArgumentParser(description='Download every model e2a uses into one folder laid out exactly like ./models (i.e. a USB key for offline installs).')
parser.add_argument('models_dir', type=str, help='Target folder, i.e. /media/user/KEY/models or E:\\models')
parser.add_argument('--only', type=str, default='', help=f"Comma list of categories: {','.join(categories)}")
parser.add_argument('--skip', type=str, default='', help='Comma list of categories to leave out')
parser.add_argument('--languages', type=str, default='', help='Comma list of e2a ISO-639-3 codes (eng,fra,ita...): single-language models and fine-tunes for these only, multilingual models only for engines speaking one of them')
parser.add_argument('--refresh', action='store_true', help='Run every job again, even those already marked done (files already there are still not downloaded twice)')
parser.add_argument('--dry_run', action='store_true', help='List every download job with its state (done, interrupted, todo) and exit')
args = parser.parse_args()
import lib.conf as conf
target_dir = os.path.abspath(os.path.expanduser(args.models_dir))
os.makedirs(target_dir, exist_ok=True)
for key, value in list(os.environ.items()):
    if value == conf.models_dir or value.startswith(conf.models_dir + '/') or value.startswith(conf.models_dir + os.sep):
        os.environ[key] = target_dir + value[len(conf.models_dir):]
models_dir = target_dir
tts_dir = os.path.join(models_dir, 'tts')
os.makedirs(tts_dir, exist_ok=True)
if not os.environ.get('HF_TOKEN'):
    from cryptography.fernet import Fernet
    os.environ['HF_TOKEN'] = Fernet(conf.fernet_key.encode('utf-8')).decrypt(conf.fernet_data).decode('utf-8')
from lib.conf_models import TTS_ENGINES, TTS_VOICE_CONVERSION, default_engine_settings, default_voice_detection_model, audiocpp_engines, audiocpp_repo, audiocpp_asr, audiocpp_vc
from lib.conf_lang import year_to_decades_languages
from lib.conf_interlude import interlude_classifier_repo
languages = {lang.strip().lower() for lang in args.languages.split(',') if lang.strip()}
skip = {c for c in args.skip.split(',') if c}
only = [c for c in args.only.split(',') if c] or categories
unknown = [c for c in only + list(skip) if c not in categories]
if unknown:
    parser.error(f"unknown categories: {', '.join(unknown)}")
selected = [c for c in only if c not in skip]
jobs:list = []
labels:set = set()
# every finished job is recorded in models/.e2a_downloads.json: a rerun skips it without touching the network. A job still
# marked started was cut (ctrl-c, crash, unplugged key) or failed: its partial folders (the clean list) are removed first
ledger_file = os.path.join(models_dir, '.e2a_downloads.json')
try:
    with open(ledger_file, 'r', encoding='utf-8') as f:
        ledger = json.load(f)
except (OSError, ValueError):
    ledger = {}
interrupted = {label for label, state in ledger.items() if state == 'started'}

def mark(label:str, state:str)->None:
    ledger[label] = state
    with open(f'{ledger_file}.tmp', 'w', encoding='utf-8') as f:
        json.dump(ledger, f, indent=1, sort_keys=True)
    os.replace(f'{ledger_file}.tmp', ledger_file)

def add(category:str, label:str, fn:Callable[[], None], clean:tuple=())->None:
    if category in selected and label not in labels:
        labels.add(label)
        jobs.append((category, label, fn, clean))

def wanted(lang:str)->bool:
    return not languages or lang in languages

def engine_wanted(engine:str)->bool:
    return not languages or bool(languages & set(default_engine_settings[engine]['languages']))

def engine_isos(engine:str)->set|None:
    if not languages:
        return None
    engine_langs = default_engine_settings[engine]['languages']
    return {engine_langs[lang] for lang in languages if lang in engine_langs} | languages

def load_presets(name:str)->dict:
    spec = importlib.util.spec_from_file_location(f'e2a_presets_{name}', os.path.join(root_dir, 'lib', 'classes', 'tts_engines', 'presets', f'{name}_presets.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.models

def hf_file(repo:str, filename:str, local_dir:str|None=None)->None:
    from huggingface_hub import hf_hub_download
    if local_dir:
        hf_hub_download(repo_id=repo, filename=filename, cache_dir=tts_dir, local_dir=local_dir)
    else:
        hf_hub_download(repo_id=repo, filename=filename, cache_dir=tts_dir)

def hf_folder(repo:str, local_dir:str, patterns:list|None=None, marker:bool=False)->None:
    from huggingface_hub import snapshot_download
    marker_file = os.path.join(local_dir, '.e2a_complete')
    if marker and os.path.exists(marker_file):
        return
    snapshot_download(repo, local_dir=local_dir, allow_patterns=patterns)
    if marker:
        open(marker_file, 'w').close()

def hf_cache_repo(repo:str)->None:
    from huggingface_hub import snapshot_download
    snapshot_download(repo, cache_dir=tts_dir, allow_patterns=['*.json', '*.model', '*.txt', 'model.safetensors', 'model-*-of-*.safetensors'], ignore_patterns=['*/*'])

def url_file(url:str, dest:str)->None:
    if os.path.exists(dest):
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = f'{dest}.part'
    urllib.request.urlretrieve(url, part)
    os.replace(part, dest)

def coqui_model(name:str)->None:
    from TTS.utils.manage import ModelManager
    manager = ModelManager(progress_bar=True)
    # coqui treats any existing model folder as downloaded, even a half-written one: a cut job is wiped first (models
    # fetched from a Hugging Face repo_id live in the HF cache, which resumes by itself)
    model_item, full_name, _ = manager._set_model_item(name)
    vocoder = model_item.get('default_vocoder')
    if name in interrupted:
        for item, item_name in [(model_item, full_name)] + ([manager._set_model_item(vocoder)[:2]] if vocoder else []):
            if 'repo_id' not in item:
                shutil.rmtree(manager.output_prefix / item_name, ignore_errors=True)
    manager.download_model(name)
    if vocoder:
        manager.download_model(vocoder)

def wavlm()->None:
    from TTS.vc.layers.freevc.wavlm import model_uri
    from trainer.io import get_user_data_dir
    url_file(model_uri, str(get_user_data_dir('tts') / 'wavlm' / 'WavLM-Large.pt'))

def freevc_encoder()->None:
    from trainer.io import load_fsspec
    load_fsspec('https://github.com/coqui-ai/TTS/releases/download/v0.13.0_models/speaker_encoder.pt', map_location='cpu')

def bark_extras(bark_repo:str)->None:
    from transformers import BertTokenizer, EncodecModel, AutoProcessor, HubertModel
    from TTS.utils.manage import ModelManager
    from TTS.tts.layers.bark.hubert.hubert_manager import HubertManager
    BertTokenizer.from_pretrained('bert-base-multilingual-cased', cache_dir=tts_dir)
    EncodecModel.from_pretrained('facebook/encodec_24khz', cache_dir=tts_dir)
    AutoProcessor.from_pretrained('facebook/encodec_24khz', cache_dir=tts_dir)
    HubertModel.from_pretrained('facebook/hubert-base-ls960', cache_dir=tts_dir)
    bark_dir = os.path.join(str(ModelManager().output_prefix), bark_repo.replace('/', '--'))
    HubertManager.make_sure_tokenizer_installed(model_path=os.path.join(bark_dir, 'tokenizer.pth'))

def piper_voice(name:str)->None:
    from piper.download_voices import download_voice
    voice_dir = Path(tts_dir) / 'piper' / name
    voice_dir.mkdir(parents=True, exist_ok=True)
    download_voice(name, voice_dir)

def tashkeel(url:str, dest:str)->None:
    if all(os.path.exists(os.path.join(dest, item)) for item in ('encoder.onnx', 'decoder.onnx')):
        return
    os.makedirs(dest, exist_ok=True)
    archive = os.path.join(dest, 'model.zip')
    urllib.request.urlretrieve(url, archive)
    with zipfile.ZipFile(archive) as zip_ref:
        zip_ref.extractall(dest)
    os.remove(archive)

def g2pw(dest:str)->None:
    if os.path.isdir(dest):
        return
    parent = os.path.dirname(dest)
    os.makedirs(parent, exist_ok=True)
    archive = os.path.join(parent, 'G2PWModel_1.1.zip')
    urllib.request.urlretrieve('https://www.modelscope.cn/models/kamiorinn/g2pw/resolve/master/G2PWModel_1.1.zip', archive)
    with zipfile.ZipFile(archive) as zip_ref:
        zip_ref.extractall(parent)
    os.remove(archive)
    os.rename(os.path.join(parent, 'G2PWModel_1.1'), dest)

def nltk_data(dest:str)->None:
    import nltk
    for package in ('averaged_perceptron_tagger_eng', 'averaged_perceptron_tagger', 'cmudict'):
        if not nltk.download(package, download_dir=dest, quiet=True):
            raise RuntimeError(f'nltk {package} failed')

def stanza_lang(iso1:str)->None:
    import stanza
    from stanza.pipeline.core import DownloadMethod
    from stanza.resources.common import download_resources_json, load_resources_json
    stanza_dir = os.environ['STANZA_RESOURCES_DIR']
    download_resources_json(stanza_dir)
    resources = load_resources_json(stanza_dir)
    processors = 'tokenize,mwt,ner' if 'mwt' in resources.get(iso1, {}) else 'tokenize,ner'
    stanza.Pipeline(iso1, processors=processors, use_gpu=False, download_method=DownloadMethod.REUSE_RESOURCES, dir=stanza_dir)

def pyannote_model()->None:
    from pyannote.audio import Model
    Model.from_pretrained(default_voice_detection_model, cache_dir=tts_dir)

def demucs_model()->None:
    from demucs.pretrained import get_model
    get_model(name='htdemucs')

def argos_packages()->None:
    import argostranslate.package, argostranslate.settings, argostranslate.translate
    from iso639 import Lang
    argostranslate.settings.local_package_index = argostranslate.settings.package_data_dir.parent / 'index.json'
    iso1s = set()
    for lang in languages:
        try:
            if Lang(lang).pt1:
                iso1s.add(Lang(lang).pt1)
        except Exception:
            pass
    argostranslate.package.update_package_index()
    installed = {(pkg.from_code, pkg.to_code) for pkg in argostranslate.package.get_installed_packages()}
    errors = []
    for pkg in argostranslate.package.get_available_packages():
        codes = {pkg.from_code, pkg.to_code}
        pair = f'argos {pkg.from_code}->{pkg.to_code}'
        # installed and never cut here (or installed by e2a itself): kept. argos unzips straight into its packages
        # folder, so a pair cut mid-install shows as installed: its folder is removed and the pair installed again
        if ledger.get(pair) == 'done' or ((pkg.from_code, pkg.to_code) in installed and pair not in ledger) or (iso1s and not ((codes & iso1s) and codes <= (iso1s | {'en'}))):
            continue
        print(f'    {pair}', flush=True)
        try:
            download_path = pkg.download()
            with zipfile.ZipFile(download_path) as zip_ref:
                package_dir = argostranslate.settings.package_data_dir / zip_ref.namelist()[0].split('/')[0]
            shutil.rmtree(package_dir, ignore_errors=True)
            mark(pair, 'started')
            argostranslate.package.install_from_path(download_path)
            mark(pair, 'done')
            os.remove(download_path)
        except Exception as e:
            errors.append(f'{pkg.from_code}->{pkg.to_code}: {e}')
    if errors:
        raise RuntimeError('; '.join(errors))

def tessdata()->None:
    tess_dir = os.environ['TESSDATA_PREFIX']
    with urllib.request.urlopen('https://api.github.com/repos/tesseract-ocr/tessdata_best/contents/', timeout=60) as r:
        names = [item['name'] for item in json.load(r) if item['name'].endswith('.traineddata')]
    for name in names:
        if languages and name.split('.')[0].split('_')[0] not in languages | {'osd'}:
            continue
        url_file(f'https://github.com/tesseract-ocr/tessdata_best/raw/main/{name}', os.path.join(tess_dir, name))

def voices(dest_root:str)->None:
    from huggingface_hub import hf_hub_download, get_hf_file_metadata, hf_hub_url
    parts = Path(urllib.parse.unquote(urllib.parse.urlparse(conf.voices_url).path)).parts
    repo_id = f"{parts[parts.index('datasets') + 1]}/{parts[parts.index('datasets') + 2]}"
    filename = '/'.join(parts[parts.index('resolve') + 2:])
    voices_dir = os.path.join(dest_root, 'voices')
    version_file = os.path.join(voices_dir, '.version.json')
    remote_etag = get_hf_file_metadata(hf_hub_url(repo_id, filename, repo_type='dataset')).etag
    # .version.json is e2a's own check_voices() record (etag), plus the languages kept here (absent = all of them):
    # same zip and every language asked for already there = nothing to do
    if os.path.exists(version_file):
        with open(version_file, 'r') as f:
            version = json.load(f)
        if version.get('etag') == remote_etag and (version.get('e2a_languages') is None or (languages and languages <= set(version['e2a_languages']))):
            return
    zip_path = hf_hub_download(repo_id=repo_id, filename=filename, repo_type='dataset', local_dir=dest_root)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dest_root)
    os.remove(zip_path)
    if languages:
        for item in os.listdir(voices_dir):
            if os.path.isdir(os.path.join(voices_dir, item)) and not item.startswith('__') and item != 'eng' and item not in languages:
                shutil.rmtree(os.path.join(voices_dir, item))
    with open(version_file, 'w') as f:
        json.dump({'etag': remote_etag, 'e2a_languages': sorted(languages | {'eng'}) if languages else None}, f)

def jieba_cache()->None:
    import jieba
    jieba.dt.cache_file = os.path.join(models_dir, 'jieba.cache')
    jieba.initialize()

xtts_repo = default_engine_settings[TTS_ENGINES['XTTS']]['repo']
add('common', f'{xtts_repo}/speakers_xtts.pth', lambda: hf_file(xtts_repo, 'speakers_xtts.pth'))
for vc in TTS_VOICE_CONVERSION.values():
    add('common', vc['path'], lambda name=vc['path']: coqui_model(name))
add('common', 'WavLM-Large.pt', wavlm)
add('common', 'freevc speaker_encoder.pt', freevc_encoder)
for name, cfg in load_presets('xtts').items():
    if not engine_wanted(TTS_ENGINES['XTTS']) or (name != 'internal' and languages and cfg['lang'] not in languages):
        continue
    sub = '' if name == 'internal' else cfg['sub']
    for file in cfg['files'][:3]:
        add('xtts', f"{cfg['repo']}/{sub}{file}", lambda repo=cfg['repo'], filename=f'{sub}{file}': hf_file(repo, filename))
bark_repo = load_presets('bark')['internal']['repo']
if engine_wanted(TTS_ENGINES['BARK']):
    add('bark', bark_repo, lambda: coqui_model(bark_repo))
    add('bark', 'bark bert / encodec / hubert / tokenizer.pth', lambda: bark_extras(bark_repo))
for engine in ('tortoise', 'vits', 'glowtts', 'tacotron'):
    cfg = load_presets(engine)['internal']
    isos = engine_isos(TTS_ENGINES[engine.upper()])
    for sub, iso_list in cfg['sub'].items():
        for iso in iso_list:
            if isos is None or iso in isos:
                name = cfg['repo'].replace('[lang_iso1]', iso).replace('[xxx]', sub)
                add(engine, name, lambda name=name: coqui_model(name))
yourtts_repo = load_presets('yourtts')['internal']['repo']
if engine_wanted(TTS_ENGINES['YOURTTS']):
    add('yourtts', yourtts_repo, lambda: coqui_model(yourtts_repo))
fairseq_repo = load_presets('fairseq')['internal']['repo']
for lang in default_engine_settings[TTS_ENGINES['FAIRSEQ']]['languages']:
    if wanted(lang):
        name = fairseq_repo.replace('[lang]', lang)
        add('fairseq', name, lambda name=name: coqui_model(name))
piper_isos = engine_isos(TTS_ENGINES['PIPER'])
piper_names = [n for locale, names in load_presets('piper')['internal']['sub'].items() if piper_isos is None or locale in piper_isos for n in names]
for n in dict.fromkeys(piper_names):
    if not any(o != n and urllib.parse.unquote(o) == n for o in piper_names):
        add('piper', f'piper {n}', lambda n=n: piper_voice(n), (os.path.join(tts_dir, 'piper', n),))
if engine_wanted(TTS_ENGINES['ZONOS']):
    zonos_repo = default_engine_settings[TTS_ENGINES['ZONOS']]['repo']
    for file in dict.fromkeys(f for cfg in load_presets('zonos').values() for f in cfg['files']):
        add('zonos', f'{zonos_repo}/{file}', lambda file=file: hf_file(zonos_repo, file))
audiocpp_presets = load_presets('audiocpp')
for engine in audiocpp_engines:
    if not engine_wanted(engine):
        continue
    for name, cfg in audiocpp_presets[engine].items():
        if languages and cfg.get('languages') and not (languages & set(cfg['languages'])):
            continue
        files = list(cfg['files']) + [f for lang, lang_files in cfg.get('files_by_language', {}).items() if wanted(lang) for f in lang_files]
        local_dir = os.path.join(tts_dir, 'audiocpp', cfg['repo'].replace('/', '--'))
        for file in files:
            add('audiocpp', f"{cfg['repo']}/{file}", lambda repo=cfg['repo'], file=file, local_dir=local_dir: hf_file(repo, file, local_dir))
acpp_dir = os.path.join(tts_dir, 'audiocpp', audiocpp_repo.replace('/', '--'))
for file in audiocpp_asr['files'] + audiocpp_vc['files']:
    add('audiocpp', f'{audiocpp_repo}/{file}', lambda file=file: hf_file(audiocpp_repo, file, acpp_dir))
gsv = default_engine_settings[TTS_ENGINES['GPTSOVITS']]
if engine_wanted(TTS_ENGINES['GPTSOVITS']):
    gsv_dir = os.path.join(tts_dir, TTS_ENGINES['GPTSOVITS'])
    gsv_weights = list(dict.fromkeys(gsv['weights'] + [w for cfg in load_presets('gptsovits').values() for w in cfg['weights']]))
    gsv_asr_repo = {'large-v3-turbo': 'mobiuslabsgmbh/faster-whisper-large-v3-turbo'}.get(gsv['asr_model'], gsv['asr_model'])
    add('gptsovits', f"{gsv['repo']} pretrained_models", lambda: hf_folder(gsv['repo'], os.path.join(gsv_dir, 'pretrained_models'), gsv_weights))
    add('gptsovits', 'fast_langdetect lid.176.bin', lambda: url_file('https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin', os.path.join(gsv_dir, 'pretrained_models', 'fast_langdetect', 'lid.176.bin')))
    add('gptsovits', 'G2PWModel', lambda: g2pw(os.path.join(gsv_dir, 'G2PWModel')), (os.path.join(gsv_dir, 'G2PWModel_1.1'),))
    add('gptsovits', 'nltk_data', lambda: nltk_data(os.path.join(gsv_dir, 'nltk_data')))
    add('gptsovits', f"faster-whisper-{gsv['asr_model']}", lambda: hf_folder(gsv_asr_repo, os.path.join(tts_dir, f"faster-whisper-{gsv['asr_model']}"), ['config.json', 'preprocessor_config.json', 'model.bin', 'tokenizer.json', 'vocabulary.*']))
f5 = default_engine_settings[TTS_ENGINES['F5TTS']]
f5_checkpoints = [ckpt for cfg in load_presets('f5tts').values() for lang, ckpt in cfg['checkpoints'].items() if wanted(lang)]
for ckpt in f5_checkpoints:
    add('f5tts', f"{ckpt['repo']}/{ckpt['ckpt']}", lambda ckpt=ckpt: hf_folder(ckpt['repo'], os.path.join(tts_dir, 'f5tts', ckpt['repo'].replace('/', '--')), [ckpt['ckpt'], ckpt['vocab']]))
if f5_checkpoints:
    add('f5tts', f5['vocoder'], lambda: hf_folder(f5['vocoder'], os.path.join(tts_dir, 'f5tts', f5['vocoder'].replace('/', '--')), ['config.yaml', 'pytorch_model.bin']))
    add('f5tts', f"whisper {f5['asr_model']}", lambda: hf_folder(f5['asr_model'], os.path.join(tts_dir, f5['asr_model'].replace('/', '--')), None, True))
if any(ckpt.get('tashkeel') for ckpt in f5_checkpoints):
    add('f5tts', 'catt tashkeel', lambda: tashkeel(f5['tashkeel']['url'], os.path.join(tts_dir, 'f5tts', f5['tashkeel']['dir'])), (os.path.join(tts_dir, 'f5tts', f5['tashkeel']['dir']),))
omni = default_engine_settings[TTS_ENGINES['OMNIVOICE']]
if engine_wanted(TTS_ENGINES['OMNIVOICE']):
    add('omnivoice', omni['repo'], lambda: hf_folder(omni['repo'], os.path.join(tts_dir, 'omnivoice', omni['repo'].replace('/', '--'))))
    add('omnivoice', f"whisper {omni['asr_model']}", lambda: hf_folder(omni['asr_model'], os.path.join(tts_dir, omni['asr_model'].replace('/', '--')), None, True))
orp = default_engine_settings[TTS_ENGINES['ORPHEUS']]
orp_repos = list(dict.fromkeys(ckpt['repo'] for lang, ckpt in load_presets('orpheus')['internal']['checkpoints'].items() if wanted(lang)))
for repo in orp_repos:
    add('orpheus', repo, lambda repo=repo: hf_folder(repo, os.path.join(tts_dir, 'orpheus', repo.replace('/', '--')), ['*.json', '*.safetensors', 'tokenizer*'], True))
if orp_repos:
    add('orpheus', f"{orp['repo']} tokenizer", lambda: hf_folder(orp['repo'], os.path.join(tts_dir, 'orpheus', orp['repo'].replace('/', '--')), ['tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json']))
    add('orpheus', orp['snac'], lambda: hf_folder(orp['snac'], os.path.join(tts_dir, 'orpheus', orp['snac'].replace('/', '--')), ['config.json', 'pytorch_model.bin']))
if 'stanza' in selected:
    from iso639 import Lang
    for lang in year_to_decades_languages:
        if wanted(lang):
            add('stanza', f'stanza {lang}', lambda iso1=Lang(lang).pt1: stanza_lang(iso1))
add('pyannote', default_voice_detection_model, pyannote_model)
add('demucs', 'htdemucs', demucs_model)
for repo in [interlude_classifier_repo] + [f'facebook/musicgen-{stereo}{size}' for stereo in ('', 'stereo-') for size in ('small', 'medium')]:
    add('interlude', repo, lambda repo=repo: hf_cache_repo(repo))
add('argos', f"argos-translate packages ({','.join(sorted(languages)) or 'all'})", argos_packages)
add('tessdata', f"tessdata_best ({','.join(sorted(languages)) or 'all'})", tessdata)
if 'jieba' in selected and wanted('zho'):
    add('jieba', 'jieba.cache', jieba_cache)
# voices always come along (only --skip voices leaves them out), beside the models folder
if 'voices' not in skip:
    voices_label = f"voices ({','.join(sorted(languages)) or 'all'})"
    labels.add(voices_label)
    jobs.append(('voices', voices_label, lambda: voices(os.path.dirname(models_dir)), ()))
pending = [job for job in jobs if args.refresh or ledger.get(job[1]) != 'done']
print(f'Target: {models_dir} ({shutil.disk_usage(models_dir).free / 1e9:.1f} GB free), {len(jobs)} jobs: {len(jobs) - len(pending)} already done, {len(pending)} to run', flush=True)
if args.dry_run:
    for category, label, _, _ in jobs:
        print(f"[{category}] [{'done' if ledger.get(label) == 'done' else 'interrupted' if label in interrupted else 'todo'}] {label}")
    sys.exit(0)
failed = []
for i, (category, label, fn, clean) in enumerate(pending, 1):
    print(f'[{i}/{len(pending)}] [{category}] {label}', flush=True)
    if label in interrupted:
        for path in clean:
            shutil.rmtree(path, ignore_errors=True)
    mark(label, 'started')
    try:
        fn()
        mark(label, 'done')
    except Exception as e:
        failed.append(f'[{category}] {label}: {e}')
        print(f'    FAILED: {e}', flush=True)
print(f'Done: {len(pending) - len(failed)} ok, {len(failed)} failed')
for line in failed:
    print(f'  {line}')
sys.exit(1 if failed else 0)
