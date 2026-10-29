import os, sys, shutil, filecmp, argparse, tempfile, subprocess
from pathlib import Path
root_dir = str(Path(__file__).resolve().parents[1])
python_env_dir = os.path.join(root_dir, 'python_env')
python_env_exec = os.path.join(python_env_dir, 'Scripts', 'python.exe') if sys.platform == 'win32' else os.path.join(python_env_dir, 'bin', 'python')
# runs on e2a's python_env (argostranslate, iso639): started by another interpreter, it starts again with python_env's
if os.path.isfile(python_env_exec) and os.path.normcase(os.path.realpath(sys.prefix)) != os.path.normcase(os.path.realpath(python_env_dir)) and not os.environ.get('E2A_TRANSLATE_EBOOK'):
    try:
        sys.exit(subprocess.run([python_env_exec, os.path.abspath(__file__), *sys.argv[1:]], env={**os.environ, 'E2A_TRANSLATE_EBOOK': '1'}).returncode)
    except KeyboardInterrupt:
        sys.exit(130)
examples = '''examples:
  translate_ebook.py book.epub --to fr
  translate_ebook.py book.azw3 --from en --to deu -o /path/to/book_deu.azw3
  translate_ebook.py /path/to/books -r --to es --output-dir /path/to/books_es
  translate_ebook.py @books.txt --to ita --mode bilingual
  translate_ebook.py --list'''
description = '''Translate EPUB/AZW3 ebooks offline, out of e2a, with the Argos Translate calibre plugin
(tools/argostranslate-calibre-plugin.zip). It runs on e2a's python_env and argos-translate packages
(models/argos-translate): a language pair e2a already uses is not downloaded again, a missing one is
downloaded on first use (direct or through English). The plugin is installed into e2a's own calibre
profile (run/) on first use, your calibre setup is left untouched.
Translated paths are printed on stdout, progress and logs on stderr.'''
parser = argparse.ArgumentParser(prog='translate_ebook.py', fromfile_prefix_chars='@', formatter_class=argparse.RawDescriptionHelpFormatter, epilog=examples, description=description)
parser.add_argument('books', nargs='*', help='EPUB/AZW3 files or folders to translate; @list.txt reads paths from a file, one per line')
parser.add_argument('-t', '--to', dest='dst', metavar='LANG', help='Target language, ISO-639-1 or ISO-639-3 code (fr or fra)')
parser.add_argument('-f', '--from', dest='src', default='', metavar='LANG', help='Source language, ISO-639-1 or ISO-639-3 code (default: read from each book)')
parser.add_argument('-r', '--recursive', action='store_true', help='Also look for books in the subfolders of the given folders')
parser.add_argument('-o', '--output', help='Output file, single input only, same extension as the input (default: <name>.<lang>.<ext> next to the input)')
parser.add_argument('--output-dir', help='Write the translations into this folder (subfolders are mirrored with -r) instead of next to each book')
parser.add_argument('--overwrite', action='store_true', help='Translate again even if the output file already exists (skipped otherwise)')
parser.add_argument('-m', '--mode', choices=['replace', 'bilingual'], default='replace', help='replace: the translation replaces the text. bilingual: each paragraph is followed by its translation, saved as <name>.<lang>.bilingual.<ext> (default: replace)')
parser.add_argument('--device', choices=['cpu', 'cuda', 'auto'], help='Device argostranslate runs on (default: cpu)')
parser.add_argument('--batch-size', type=int, help='Segments sent to the translation worker per request (default: 16)')
parser.add_argument('--no-cache', action='store_true', help='Neither read nor write the translation cache (run/argos_translate/cache.sqlite), the one that makes a second run of the same book near instant')
parser.add_argument('--no-download', action='store_true', help='Never download a missing argos-translate package, fail instead')
parser.add_argument('--allow-changes', action='store_true', help='Only when argostranslate is missing from python_env: install it even if packages already there would change version')
parser.add_argument('--list', action='store_true', help='List the installed and the downloadable language pairs, then exit')
args = parser.parse_args()
if not args.list and (not args.books or not args.dst):
    parser.error('give at least one book or folder and --to')
if args.output and len(args.books) > 1:
    parser.error('--output needs exactly one input book')

def to_iso1(code:str)->str:
    # argos-translate speaks ISO-639-1, e2a ISO-639-3: both are accepted
    if len(code) != 3:
        return code
    try:
        from iso639 import Lang
        return Lang(code).pt1 or code
    except Exception:
        return code

def to_abs(path:str)->str:
    return os.path.abspath(os.path.expanduser(path))

# paths are taken from where the script was started, the plugin then runs from e2a's root
plugin_args = [to_abs(book) for book in args.books]
if args.dst:
    plugin_args += ['--to', to_iso1(args.dst.strip().lower())]
if args.src:
    plugin_args += ['--from', to_iso1(args.src.strip().lower())]
if args.recursive:
    plugin_args.append('--recursive')
if args.output:
    plugin_args += ['--output', to_abs(args.output)]
if args.output_dir:
    plugin_args += ['--output-dir', to_abs(args.output_dir)]
if args.overwrite:
    plugin_args.append('--overwrite')
plugin_args += ['--mode', args.mode]
if args.device:
    plugin_args += ['--device', args.device]
if args.batch_size:
    plugin_args += ['--batch-size', str(args.batch_size)]
if args.no_cache:
    plugin_args.append('--no-cache')
if args.no_download:
    plugin_args.append('--no-download')
if args.allow_changes:
    plugin_args.append('--allow-changes')
if args.list:
    plugin_args.append('--list')
os.chdir(root_dir)
sys.path.insert(0, root_dir)
# lib.conf pins argostranslate to 1 thread in float32 for e2a: kept only when set by the user, before lib.conf
argos_tuning = {key: os.environ[key] for key in ('ARGOS_INTRA_THREADS', 'ARGOS_COMPUTE_TYPE') if key in os.environ}
# e2a's paths and calibre profile: CALIBRE_CONFIG_DIRECTORY, CALIBRE_CACHE_DIRECTORY and CALIBRE_TEMP_DIR on run/
import lib.conf as conf
plugin_name = 'Argos Translate'
plugin_zip = os.path.join(root_dir, 'tools', 'argostranslate-calibre-plugin.zip')

def calibre_env()->dict:
    # as convert2epub() in lib/core.py: calibre must not run with python_env's interpreter or libraries
    env = dict(os.environ)
    for key in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONEXECUTABLE', 'PYTHONNOUSERSITE', 'LD_LIBRARY_PATH', 'LD_PRELOAD', 'DYLD_LIBRARY_PATH', 'DYLD_INSERT_LIBRARIES'):
        env.pop(key, None)
    # argostranslate's own defaults: CTranslate2 picks the threads and the fastest compute type (int8 on CPU)
    for key in ('ARGOS_INTRA_THREADS', 'ARGOS_COMPUTE_TYPE'):
        env.pop(key, None)
    env.update(argos_tuning)
    prefixes = [os.path.normcase(os.path.normpath(p)) for p in (os.environ.get('CONDA_PREFIX'), os.environ.get('VIRTUAL_ENV'), sys.prefix if sys.prefix != sys.base_prefix else None) if p]
    env['PATH'] = os.pathsep.join([p for p in env.get('PATH', '').split(os.pathsep) if p and not any(os.path.normcase(os.path.normpath(p)) == pre or os.path.normcase(os.path.normpath(p)).startswith(pre + os.sep) for pre in prefixes)])
    env.setdefault('LANG', 'C.UTF-8')
    env.setdefault('LC_ALL', 'C.UTF-8')
    if sys.platform.startswith('linux') and not env.get('DISPLAY') and not env.get('WAYLAND_DISPLAY'):
        env.setdefault('QT_QPA_PLATFORM', 'offscreen')
    # the plugin runs argostranslate with the VIRTUAL_ENV interpreter, else ./python_env (missing in docker): this one
    python = os.path.join(sys.prefix, 'Scripts', 'python.exe') if sys.platform == 'win32' else os.path.join(sys.prefix, 'bin', 'python')
    if os.path.isfile(python):
        env['VIRTUAL_ENV'] = sys.prefix
    return env

def calibre_cmd(prog:str, env:dict)->list[str]|None:
    path = env.get('PATH', '')
    exe = shutil.which(prog, path=path)
    if not exe:
        # calibre reached through an ebook-convert link only: its other tools sit beside the real file
        ebook_convert = shutil.which('ebook-convert', path=path)
        if ebook_convert:
            exe = shutil.which(prog, path=os.path.dirname(os.path.realpath(ebook_convert)))
    if not exe:
        return None
    if sys.platform != 'win32':
        try:
            with open(exe, 'rb') as f:
                head = f.readline(256)
            if head.startswith(b'#!'):
                shebang = head[2:].decode('utf-8', 'replace').strip()
                if shebang.startswith('/usr/bin/env') and 'python' in shebang:
                    interpreter = shutil.which(shebang.split()[-1], path=path)
                    if interpreter:
                        return [interpreter, exe]
        except OSError:
            pass
    return [exe]

def ensure_plugin(env:dict)->str|None:
    if not os.path.isfile(plugin_zip):
        return f'{plugin_zip} not found'
    # calibre-customize copies the zip to <config>/plugins/<plugin name>.zip: same bytes, same plugin
    installed = os.path.join(env.get('CALIBRE_CONFIG_DIRECTORY', ''), 'plugins', f'{plugin_name}.zip')
    if env.get('CALIBRE_CONFIG_DIRECTORY') and os.path.isfile(installed) and filecmp.cmp(plugin_zip, installed, shallow=False):
        return None
    cmd = calibre_cmd('calibre-customize', env)
    if cmd is None:
        return 'calibre-customize not found, install calibre (ebook2audiobook installs it)'
    result = subprocess.run(cmd + ['--add-plugin', plugin_zip], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', env=env)
    if result.returncode != 0:
        return f'calibre-customize could not install {plugin_zip} (exit code {result.returncode}):\n{result.stdout.strip()}'
    return None

env = calibre_env()
error = ensure_plugin(env)
if error is not None:
    print(error, file=sys.stderr)
    sys.exit(1)
cmd = calibre_cmd('calibre-debug', env)
if cmd is None:
    print('calibre-debug not found, install calibre (ebook2audiobook installs it)', file=sys.stderr)
    sys.exit(1)
# a calibre temp folder of its own, removed even when ctrl-c leaves calibre no time to clean it
os.makedirs(env.get('CALIBRE_TEMP_DIR') or conf.run_dir, exist_ok=True)
run_tmp = tempfile.mkdtemp(prefix='e2a_calibre_', dir=env.get('CALIBRE_TEMP_DIR') or conf.run_dir)
try:
    # from the folder holding models/: the plugin takes ./models/argos-translate, e2a's packages folder
    code = subprocess.run(cmd + ['-r', plugin_name, '--'] + plugin_args, cwd=os.path.dirname(conf.models_dir), env={**env, 'CALIBRE_TEMP_DIR': run_tmp}).returncode
except KeyboardInterrupt:
    code = 130
finally:
    shutil.rmtree(run_tmp, ignore_errors=True)
sys.exit(code)
