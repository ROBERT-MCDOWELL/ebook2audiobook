import subprocess
from setuptools import setup, find_packages, Command

class InstallPackages(Command):
    description = 'Install dependencies and download additional resources'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        subprocess.check_call(['pip', 'install', '-r', 'requirements.txt'])
        subprocess.check_call(['python', '-m', 'unidic', 'download'])
        subprocess.check_call(['python', '-m', 'nltk.downloader', 'punkt'])

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()

# Read requirements.txt
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="ebook2audiobookXTTS",
    version="1.2",
    author="Drew Thomasson",
    description="Convert eBooks to audiobooks with chapters and metadata.",
    url="https://github.com/DrewThomasson/ebook2audiobookXTTS",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'ebook2audiobook=ebook2audiobook:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    cmdclass={
        'install': InstallPackages,
    }
    python_requires='>=3.10',
    install_requires=requirements,
    keywords='ebook, audiobook, '
             'TTS-engine, python'
)
