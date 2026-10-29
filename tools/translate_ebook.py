import os, re, sys, glob, shutil, filecmp, argparse, tempfile, subprocess
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
  translate_ebook.py book.epub --to fra,ara,spa
  translate_ebook.py book.azw3 --from en --to deu -o /path/to/book_deu.azw3
  translate_ebook.py /path/to/books -r --to es,it --output-dir /path/to/books_translated
  translate_ebook.py @books.txt --to ita --mode bilingual
  translate_ebook.py --list
  translate_ebook.py --list --from eng'''
description = '''Translate EPUB/AZW3 ebooks offline, out of e2a, with the Argos Translate calibre plugin
(tools/argostranslate-calibre-plugin.zip). It runs on e2a's python_env and argos-translate packages
(models/argos-translate): a language pair e2a already uses is not downloaded again, a missing one is
downloaded on first use (direct or through English). The plugin is installed into e2a's own calibre
profile (run/) on first use, your calibre setup is left untouched.
Translated paths are printed on stdout, progress and logs on stderr.'''
parser = argparse.ArgumentParser(prog='translate_ebook.py', fromfile_prefix_chars='@', formatter_class=argparse.RawDescriptionHelpFormatter, epilog=examples, description=description)
parser.add_argument('books', nargs='*', help='EPUB/AZW3 files or folders to translate; @list.txt reads paths from a file, one per line')
parser.add_argument('-t', '--to', dest='dst', metavar='LANG[,LANG...]', help='Target language(s), ISO-639-1 or ISO-639-3 codes, comma separated for several (fr, fra or fra,ara,spa): one translated ebook per language')
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
parser.add_argument('--list', action='store_true', help='List the installed and the downloadable language pairs, then exit. With --from and/or --to: only their pairs, plus the targets a source reaches through English')
args = parser.parse_args()

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

def is_translation(path:str)->bool:
    # named after one of the target languages, or <name>.<lang>[.bilingual].<ext> beside its <name>.epub/.azw3 (an earlier run)
    folder, name = os.path.split(path)
    stem = os.path.splitext(name)[0]
    if any(stem.endswith(f'.{dst}') or stem.endswith(f'.{dst}.bilingual') for dst in targets):
        return True
    base, dot, code = stem.removesuffix('.bilingual').rpartition('.')
    return bool(dot) and 2 <= len(code) <= 3 and code.isalpha() and code.islower() and any(os.path.isfile(os.path.join(folder, base + ext)) for ext in book_formats)

def list_books(items:list[str], output_dir:str)->dict[str, list[str]]:
    # folders are listed once, before the first language: the plugin then gets files only, so the translations
    # of a language never become books to translate for the next one. books are grouped by output folder,
    # mirrored from their folder with -r, as the plugin's own --output-dir does
    groups:dict[str, list[str]] = {}
    seen:set = set()
    for item in (entry.strip() for entry in items):
        if not item:
            continue
        path = to_abs(item)
        if os.path.isdir(path):
            pattern = os.path.join(glob.escape(path), '**', '*') if args.recursive else os.path.join(glob.escape(path), '*')
            # nothing under the output folder is a book, even when it sits inside a scanned folder
            found = [(book, os.path.join(output_dir, os.path.dirname(os.path.relpath(book, path))) if output_dir else '') for book in sorted(glob.glob(pattern, recursive=args.recursive)) if os.path.isfile(book) and os.path.splitext(book)[1].lower() in book_formats and not is_translation(book) and not (output_dir and book.startswith(output_dir + os.sep))]
        else:
            found = [(path, output_dir)]
        for book, out_dir in found:
            if book not in seen:
                seen.add(book)
                groups.setdefault(out_dir, []).append(book)
    return groups

book_formats = ('.epub', '.azw3')
targets = list(dict.fromkeys(to_iso1(code.strip().lower()) for code in (args.dst or '').split(',') if code.strip()))
if not args.list and (not args.books or not targets):
    parser.error('give at least one book or folder and --to')
if args.output and (len(args.books) > 1 or len(targets) > 1):
    parser.error('--output needs exactly one input book and one --to language')
# paths are taken from where the script was started, the plugin then runs from e2a's root
groups = list_books(args.books, to_abs(args.output_dir) if args.output_dir else '') if not args.list else {}
if not args.list and not groups:
    parser.error('no EPUB/AZW3 books found in the given paths')
common_args = []
if args.src:
    common_args += ['--from', to_iso1(args.src.strip().lower())]
if args.output:
    common_args += ['--output', to_abs(args.output)]
if args.overwrite:
    common_args.append('--overwrite')
common_args += ['--mode', args.mode]
if args.device:
    common_args += ['--device', args.device]
if args.batch_size:
    common_args += ['--batch-size', str(args.batch_size)]
if args.no_cache:
    common_args.append('--no-cache')
if args.no_download:
    common_args.append('--no-download')
if args.allow_changes:
    common_args.append('--allow-changes')
# one plugin run per language (and output folder): it translates into one language at a time
runs = [(None, ['--list'] + common_args)] if args.list else [(dst, books + ['--to', dst] + (['--output-dir', out_dir] if out_dir else []) + common_args) for dst in targets for out_dir, books in groups.items()]
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

def show_pairs(listing:str)->None:
    # the plugin lists every pair: --from and --to keep theirs, and a source other than English gets the targets
    # it reaches through English, fetched on first use like the direct ones
    source = to_iso1(args.src.strip().lower()) if args.src else ''
    if not source and not targets:
        print(listing, end='')
        return
    sections:list = []
    names:dict = {}
    for line in listing.splitlines():
        match = re.match(r'^\s+(\S+) -> (\S+)\t(.*) -> (.*)$', line)
        if match and sections:
            names[match.group(1)], names[match.group(2)] = match.group(3), match.group(4)
            sections[-1][1].append((match.group(1), match.group(2)))
        elif line.strip() and line.strip() != '(none)':
            sections.append((line.rstrip(), []))
    known = [pair for _, pairs in sections for pair in pairs]
    if source and source != 'en' and (source, 'en') in known:
        sections.append((f'Reachable through English ({source} -> en -> ...), fetched automatically on first use:', sorted({(source, dst) for src, dst in known if src == 'en' and dst != source}, key=lambda pair: pair[1])))
    shown:set = set()
    for title, pairs in sections:
        kept = [pair for pair in pairs if (not source or pair[0] == source) and (not targets or pair[1] in targets) and pair not in shown]
        shown.update(kept)
        print(title)
        for src, dst in kept:
            print(f'  {src} -> {dst}\t{names.get(src, src)} -> {names.get(dst, dst)}')
        if not kept:
            print('  (none)')

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
failed:list = []
code = 0
try:
    for dst, plugin_args in runs:
        if dst is not None and len(targets) > 1:
            print(f'=== {dst} ({targets.index(dst) + 1}/{len(targets)})', file=sys.stderr, flush=True)
        # from the folder holding models/: the plugin takes ./models/argos-translate, e2a's packages folder
        result = subprocess.run(cmd + ['-r', plugin_name, '--'] + plugin_args, cwd=os.path.dirname(conf.models_dir), env={**env, 'CALIBRE_TEMP_DIR': run_tmp}, stdout=subprocess.PIPE if args.list else None, text=True, encoding='utf-8', errors='replace')
        if args.list:
            if result.returncode == 0:
                show_pairs(result.stdout)
            else:
                print(result.stdout, end='')
        if result.returncode != 0:
            code = 1
            if dst not in failed:
                failed.append(dst)
except KeyboardInterrupt:
    code = 130
finally:
    shutil.rmtree(run_tmp, ignore_errors=True)
if not args.list and len(targets) > 1 and code != 130:
    print(f"Languages done: {', '.join(f'{dst} failed' if dst in failed else f'{dst} ok' for dst in targets)}", file=sys.stderr)
sys.exit(code)
