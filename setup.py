import os, shutil
from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

here = os.path.abspath(os.path.dirname(__file__))

# The pip package is the bootstrap in tools/pip_bootstrap plus these app files, shipped as data in app_tree:
# the bootstrap copies them to the user's ebook2audiobook folder and starts its launcher there.
# Everything the launchers need to install and run e2a natively or build its docker image.
# Dev only files (readme translations, notebooks, i18n and workflow tools, README media) stay out.
app_tree_items = [
    'app.py', 'VERSION.txt', 'requirements.txt', 'LICENSE', 'README.md', 'SUPPORTED_LANGUAGES.md', 'favicon.ico', '.bh.ps1',
    'ebook2audiobook.command', 'ebook2audiobook.cmd', 'ebook2audiobook.sh', 'e2a.sh', 'e2a.cmd',
    'uninstall.command', 'uninstall.sh', 'uninstall.cmd',
    'Dockerfile', '.dockerignore', 'docker-compose.yml', 'podman-compose.yml',
    'lib', 'components', 'ext', 'voices', 'models', 'ebooks', 'audiobooks', 'tmp', 'run',
    'tools/icons', 'tools/preload_models.py', 'tools/translate_ebook.py', 'tools/translate_ebook.sh', 'tools/translate_ebook.cmd',
    'tools/argostranslate-calibre-plugin.zip',
]
# folders e2a fills at runtime: only their .gitkeep ships, never what a local run left in them
runtime_dirs = ['voices', 'models', 'ebooks', 'audiobooks', 'tmp', 'run']
skip_dirs = ['__pycache__']
skip_paths = ['lib/classes/tts_engines/venvs']

def list_app_tree(root:str)->list:
    files = []
    for item in app_tree_items:
        path = os.path.join(root, item)
        if not os.path.exists(path):
            raise FileNotFoundError(f"app tree item missing: {item}")
        if os.path.isfile(path):
            files.append(item)
            continue
        for dir_path, dir_names, file_names in os.walk(path):
            rel_dir = os.path.relpath(dir_path, root).replace(os.sep, '/')
            dir_names[:] = sorted(d for d in dir_names if d not in skip_dirs and f"{rel_dir}/{d}" not in skip_paths)
            for name in sorted(file_names):
                if name.endswith('.pyc') or (item in runtime_dirs and name != '.gitkeep'):
                    continue
                files.append(f"{rel_dir}/{name}")
    return files

class build_app_tree(build_py):
    def run(self)->None:
        super().run()
        # an editable install (pip install -e .) has no app_tree: its bootstrap runs the checkout in place
        if getattr(self, 'editable_mode', False):
            return
        target = os.path.join(self.build_lib, 'ebook2audiobook', 'app_tree')
        shutil.rmtree(target, ignore_errors=True)
        for rel in list_app_tree(here):
            dst = os.path.join(target, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            # copy2 follows symlinks: e2a.sh, ebook2audiobook.sh and uninstall.sh ship as copies of their target
            shutil.copy2(os.path.join(here, rel), dst)

class sdist_app_tree(sdist):
    def make_distribution(self)->None:
        # the wheel is often built from the sdist (uv build, pip from an sdist): the app tree must be in it too
        self.filelist.extend(list_app_tree(here))
        self.filelist.sort()
        self.filelist.remove_duplicates()
        super().make_distribution()

setup(
    cmdclass={'build_py': build_app_tree, 'sdist': sdist_app_tree}
)
