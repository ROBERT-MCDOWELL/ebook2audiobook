# 📚 ebook2audiobook (E2A)
<a href="https://trendshift.io/repositories/12252?utm_source=repository-badge&amp;utm_medium=badge&amp;utm_campaign=badge-repository-12252" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/repositories/12252" alt="DrewThomasson%2Febook2audiobook | Trendshift" width="250" height="55"/></a>

Conversor CPU/GPU de libro electrónico a audiolibro con capítulos y metadatos<br/>
usando motores TTS avanzados y mucho más.<br/>
¡Admite la clonación de voz y 1696 idiomas!
> [!IMPORTANT]
**Esta herramienta está destinada a usarse únicamente con libros electrónicos sin DRM y adquiridos legalmente.** <br>
Los autores no se hacen responsables de ningún uso indebido de este software ni de las consecuencias legales que de ello se deriven. <br>
Utiliza esta herramienta de forma responsable y conforme a todas las leyes aplicables.

[![Discord](https://dcbadge.limes.pink/api/server/https://discord.gg/63Tv3F65k6)](https://discord.gg/63Tv3F65k6)

### ¡Gracias por apoyar a los desarrolladores de ebook2audiobook!
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/athomasson2) 

### Ejecución local

[![Quick Start](https://img.shields.io/badge/Quick%20Start-blue?style=for-the-badge)](#instructions)

[![Docker Build](https://github.com/DrewThomasson/ebook2audiobook/actions/workflows/Docker-Build.yml/badge.svg)](https://github.com/DrewThomasson/ebook2audiobook/actions/workflows/Docker-Build.yml)  [![Download](https://img.shields.io/badge/Download-Now-blue.svg)](https://github.com/DrewThomasson/ebook2audiobook/releases/latest)   


<a href="https://github.com/DrewThomasson/ebook2audiobook">
  <img src="https://img.shields.io/badge/Platform-mac%20|%20linux%20|%20windows-lightgrey" alt="Platform">
</a><a href="https://hub.docker.com/r/athomasson2/ebook2audiobook">
<img alt="Docker Pull Count" src="https://img.shields.io/docker/pulls/athomasson2/ebook2audiobook.svg"/>
</a>

### Ejecución remota
[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Spaces-yellow?style=flat&logo=huggingface)](https://huggingface.co/spaces/drewThomasson/ebook2audiobook)
[![Free Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DrewThomasson/ebook2audiobook/blob/main/Notebooks/colab_ebook2audiobook.ipynb) [![Kaggle](https://img.shields.io/badge/Kaggle-035a7d?style=flat&logo=kaggle&logoColor=white)](https://github.com/Rihcus/ebook2audiobookXTTS/blob/main/Notebooks/kaggle-ebook2audiobook.ipynb)

#### Interfaz gráfica (GUI)
![demo_web_gui](assets/demo_web_gui.gif)

<details>
  <summary>Haz clic para ver imágenes de la GUI web</summary>
  <img width="1728" alt="GUI Screen 1" src="assets/gui_1.png">
  <img width="1728" alt="GUI Screen 2" src="assets/gui_2.png">
  <img width="1728" alt="GUI Screen 3" src="assets/gui_3.png">
</details>

## Demos

**Demo de la nueva voz por defecto**  

https://github.com/user-attachments/assets/750035dc-e355-46f1-9286-05c1d9e88cea  

<details>
  <summary>Más demos</summary>

**Voz ASMR** 

https://github.com/user-attachments/assets/68eee9a1-6f71-4903-aacd-47397e47e422

**Voz de día lluvioso**  

https://github.com/user-attachments/assets/d25034d9-c77f-43a9-8f14-0d167172b080  

**Voz Scarlett**

https://github.com/user-attachments/assets/b12009ee-ec0d-45ce-a1ef-b3a52b9f8693

**Voz David Attenborough** 

https://github.com/user-attachments/assets/81c4baad-117e-4db5-ac86-efc2b7fea921

**Ejemplo**

![Example](https://github.com/DrewThomasson/VoxNovel/blob/dc5197dff97252fa44c391dc0596902d71278a88/readme_files/example_in_app.jpeg)
</details>

## README.md

## Tabla de contenidos
- [ebook2audiobook](#-ebook2audiobook)
- [Características](#features)
- [Interfaz gráfica](#gui-interface)
- [Demos](#demos)
- [Idiomas admitidos](#supported-languages)
- [Requisitos mínimos](#hardware-requirements)
- [Uso](#instructions)
  - [Ejecución local](#instructions)
    - [Lanzar la interfaz web de Gradio](#instructions)
    - [Uso básico sin interfaz (headless)](#basic-usage)
    - [Uso de modelo XTTS personalizado sin interfaz](#example-of-custom-model-zip-upload)
    - [Salida del comando de ayuda](#help-command-output)
  - [Ejecución remota](#run-remotely)
  - [Docker](#docker)
    - [Pasos para ejecutar](#docker)
- [Tools](#tools)
  - [Preload models for offline installs](#preload-models)
  - [Traducir libros electrónicos de e2a](#translate-ebooks)
  
- [Cloned Voices](#cloned-voices)
- [Fine Tuned TTS models](#fine-tuned-tts-models) 
  - [Colección de modelos TTS ajustados](#fine-tuned-tts-collection)
  - [Tren TTS Modelo](#fine-tune-your-own-tts-model)
- [Formatos de libro electrónico admitidos](#supported-ebook-formats)
- [Formatos de salida](#output-and-process-formats)
- [Volver a una versión anterior](#reverting-to-older-versions)
- [Problemas habituales](#common-issues)
- [Agradecimientos especiales](#special-thanks)
- [Tabla de contenidos](#table-of-contents)


## Características
- 🔧 ** Motores TTS compatibles**: `XTTSv2, Bark, Fairseq, VITS, Tacotron2, Tortoise, GlowTTS, YourTTS, Piper, Zonos, GPT-SoVITS, OmniVoice, Breeze TTS, Chatterbox, Confucius4 TTS, CosyVoice3, Dots TTS, DramaBox, FireRed Audio, FireRedTTS3, Fish Audio, Higgs Audio TTS, Index TTS2, Irodori TTS, Kokoro TTS, KugelAudio, Magpie TTS, Maya1, MioTTS, Moss TTS Local, Moss TTS Nano, NeuTTS, Pocket TTS, Qwen3 TTS, Supertonic, VibeVoice, VoxCPM2, Voxtral TTS, F5-TTS, Orpheus-TTS, ChatTTS, Spark-TTS, OpenVoice, MeloTTS`
- 📚 **Convertir múltiples formatos de archivo**: `.epub`, `.mobi`, `.azw3`, `.fb2`, `.lrf`, `.rb`, `.snb`, `.tcr`, `.pdf`, `.txt`, `.rtf`, `.doc`, `.docx`, `.html`, `.odt`, `.azw`, `.tiff`, `.tif`, `.png`, `.jpg`, `.jpeg`, `.bmp`, `.zip`
- 💻 **Área de texto** para convertir directamente un texto corto en audio
- 🔍 **Escaneo OCR** para archivos con páginas de texto en forma de imágenes
- 🔊 **Texto a voz de alta calidad**, desde casi en tiempo real hasta una voz casi real
- 🗣️ **Clonación de voz opcional** usando tu propio archivo de voz
- 🌐 **Supports 1696 languages** ([supported languages list](https://dl.fbaipublicfiles.com/mms/tts/all-tts-languages.html))
- 💻 **Apto para recursos limitados** — funciona con **2 GB de RAM / 1 GB de VRAM (mínimo)**
- 🎵 **Formatos de salida del audiolibro**: mono or stereo `aac`, `flac`, `mp3`, `m4b`, `m4a`, `mp4`, `mov`, `ogg`, `wav`, `webm`
- 🧠 **Etiquetas SML admitidas** — control preciso de cortes, pausas, cambio de voz y mucho más ([see below](#sml-tags-available))
- 🧩 **Modelo personalizado opcional** usando tu propio modelo entrenado (XTTSv2, VITS, FAIRSEQ, PIPER, others on request)
- 🎛️ **Modelos preajustados y ajustados** entrenados por el equipo de E2A<br/>
     <i>(Contáctanos si necesitas modelos ajustados adicionales, o si quieres compartir los tuyos en la lista oficial de preajustes)</i>


##  Requisitos de hardware
- 2 GB de RAM mín., 8 GB recomendados.
- 1 GB de VRAM mín., 4 GB recomendados.
- Virtualización habilitada si se ejecuta en Windows (solo Docker).
- CPU, XPU (Intel, AMD, ARM)*.
- CUDA, ROCm, JETSON
- MPS (CPU Apple Silicon)

*<i> Los motores TTS modernos son muy lentos en CPU, así que usa TTS de menor calidad como YourTTS, Tacotron2, etc.</i>

## Idiomas admitidos
| **Árabe (ar)**    | **Chino (zh)**    | **Inglés (en)**   | **Español (es)**   |
|:------------------:|:------------------:|:------------------:|:------------------:|
| **Francés (fr)**    | **Alemán (de)**     | **Italiano (it)**   | **Portugués (pt)** |
| **Polaco (pl)**    | **Turco (tr)**    | **Ruso (ru)**   | **Holandés (nl)**     |
| **Checo (cs)**     | **Japonés (ja)**   | **Hindi (hi)**     | **Bengalí (bn)**   |
| **Húngaro (hu)** | **Coreano (ko)**     | **Vietnamita (vi)**| **Sueco (sv)**   |
| **Persa (fa)**   | **Yoruba (yo)**     | **Swahili (sw)**   | **Indonesio (id)**|
| **Eslovaco (sk)**    | **Croata (hr)**   | **Tamil (ta)**     | **Danés (da)**    |
- [**+1130 idiomas y dialectos aquí**](https://dl.fbaipublicfiles.com/mms/tts/all-tts-languages.html)


## Formatos de libro electrónico admitidos
- `.epub`, `.pdf`, `.mobi`, `.txt`, `.html`, `.rtf`, `.chm`, `.lit`,
  `.pdb`, `.fb2`, `.odt`, `.cbr`, `.cbz`, `.prc`, `.lrf`, `.pml`,
  `.snb`, `.cbc`, `.rb`, `.tcr`
- **Mejores resultados**: `.epub` o `.mobi` para la detección automática de capítulos

## Formatos de salida y de proceso
- `.m4b`, `.m4a`, `.mp4`, `.webm`, `.mov`, `.mp3`, `.flac`, `.wav`, `.ogg`, `.aac`
- El formato de proceso se puede cambiar en lib/conf.py

## Etiquetas SML disponibles
- `[break]` — silencio (rango aleatorio **0.3–0.6 sec.**)
- `[pause]` — silencio (rango aleatorio **1.0–1.6 sec.**)
- `[pause:N]` — pausa fija (**N sec.**)
- `[voice:/path/to/voice/file]...[/voice]` — cambiar de voz respecto a la voz por defecto o seleccionada desde la GUI/CLI
- `[emotion:sadness]...[/emotion]` — Solo zonos: emoción por un pasaje (felicidad, tristeza, disgusto, miedo, sorpresa, enojo, otro, neutro) o una mezcla como `[emotion:sadness=0.7,neutral=0.3]`; otros motores lo ignoran

**Consulta nuestro otro repositorio dedicado a añadir SML automáticamente en tu libro electrónico -> [E2A-SML](https://github.com/DrewThomasson/E2A-SML)**

> [!IMPORTANT]
**Antes de publicar un problema de instalación o un error, busca cuidadosamente en la pestaña de problemas abiertos y cerrados<br>
para asegurarte de que tu problema no exista ya.**

Nota
**El formato EPUB carece de cualquier estructura estándar que defina qué es un capítulo, un párrafo, un prefacio, etc.<br>
Por tanto, primero deberías eliminar manualmente cualquier texto que no quieras convertir en audio.**


### Instructions 
1. **Clone repo**
	```bash
	git clone https://github.com/DrewThomasson/ebook2audiobook.git
	cd ebook2audiobook
	```

2. **Instalar / Ejecutar ebook2audiobook**:

   - **Linux/MacOS**  
     ```bash
     ./ebook2audiobook.command
     ```
     <i>Note for MacOS users: homebrew is installed to install missing programs.</i>
     
   - **Lanzador de Mac**  
     Haz doble clic en `Mac Ebook2Audiobook Launcher.command`


   - **Windows**  
     ```bash
     ebook2audiobook.cmd
     ```
     or
     Double click `ebook2audiobook.cmd`

     <i>Nota para usuarios de Windows: se instala scoop para instalar los programas que falten sin privilegios de administrador.</i>
   
1. **Abrir la aplicación web**: Haz clic en la URL proporcionada en el terminal para acceder a la aplicación web y convertir libros electrónicos. `http://localhost:7860/`
2. **Para un enlace público**:
   `./ebook2audiobook.command --share` (Linux/MacOS)
   `ebook2audiobook.cmd --share` (Windows)
   `python app.py --share` (all OS)

> [!IMPORTANT]
**Si el script se detiene y se vuelve a ejecutar, debes actualizar tu interfaz gráfica de Gradio<br>
para que la página web vuelva a conectarse al nuevo socket de conexión.**

### Basic  Usage
   - **Linux/MacOS**:
     ```bash
     ./ebook2audiobook.command --headless --ebook <path_to_ebook_file> --voice <path_to_voice_file> --language <language_code>
     ```
   - **Windows**
     ```bash
     ebook2audiobook.cmd --headless --ebook <path_to_ebook_file> --voice <path_to_voice_file> --language <language_code>
     ```
     
  - **[--ebook]**: Ruta a tu archivo de libro electrónico
  - **[--voice]**: Ruta del archivo de clonación de voz (opcional)
  - **[--language]**: Código de idioma en ISO-639-3 (p. ej.: ita para italiano, eng para inglés, deu para alemán...).<br>
    El idioma por defecto es eng y --language es opcional para el idioma por defecto definido en ./lib/lang.py.<br>
    También se admiten los códigos ISO-639-1 de 2 letras.


###  Example of Custom Model Zip Upload
  (must be a .zip file containing the mandatory model files. Example for XTTSv2: config.json, model.pth, vocab.json and ref.wav)
   - **Linux/MacOS**
     ```bash
     ./ebook2audiobook.command --headless --ebook <ebook_file_path> --language <language> --custom_model <custom_model_path>
     ```
   - **Windows**
     ```bash
     ebook2audiobook.cmd --headless --ebook <ebook_file_path> --language <language> --custom_model <custom_model_path>
     ```
     <i>Note: the ref.wav of your custom model is always the voice selected for the conversion</i>
     
- **<custom_model_path>**: Ruta al archivo `model_name.zip`,
      que debe contener (según el motor TTS) todos los archivos obligatorios<br>
      (consulta ./lib/models.py).

### For Detailed Guide with list of all Parameters to use
   - **Linux/MacOS**
     ```bash
     ./ebook2audiobook.command --help
     ```
   - **Windows**
     ```bash
     ebook2audiobook.cmd --help
     ```
   - **Or for all OS**
    ```python
     app.py --help
    ```

<a id="help-command-output"></a>
```bash
usage: app.py [-h] [--session SESSION] [--share] [--headless] [--ebook EBOOK] [--ebooks_dir EBOOKS_DIR]
              [--language LANGUAGE] [--voice VOICE] [--voice_map VOICE_MAP] [--device {CPU,CUDA,MPS,ROCM,XPU,JETSON}]
              [--tts_engine {XTTS,BARK,VITS,FAIRSEQ,TACOTRON,YOURTTS,xtts,bark,vits,fairseq,tacotron,yourtts}]
              [--custom_model CUSTOM_MODEL] [--fine_tuned FINE_TUNED] [--output_format OUTPUT_FORMAT]
              [--output_channel OUTPUT_CHANNEL] [--temperature TEMPERATURE] [--length_penalty LENGTH_PENALTY]
              [--num_beams NUM_BEAMS] [--repetition_penalty REPETITION_PENALTY] [--top_k TOP_K] [--top_p TOP_P]
              [--speed SPEED] [--enable_text_splitting] [--text_temp TEXT_TEMP] [--waveform_temp WAVEFORM_TEMP]
              [--output_dir OUTPUT_DIR] [--version]

Convert eBooks to Audiobooks using a Text-to-Speech model. You can either launch the Gradio interface or run the script in headless mode for direct conversion.

options:
  -h, --help            show this help message and exit
  --session SESSION     Session to resume the conversion in case of interruption, crash,
                            or reuse of custom models and custom cloning voices.

**** The following option is for gradio/gui mode only:
  --share               (Optional) Enable a public shareable Gradio link.

**** The following options are for --headless mode only:
  --headless            Run the script in headless mode
  --ebook EBOOK         Path to the ebook file for conversion. Cannot be used when --ebooks_dir is present.
  --ebooks_dir EBOOKS_DIR
                        Relative or absolute path of the directory containing the files to convert.
                            Cannot be used when --ebook is present.
  --text TEXT           Raw text for conversion. Cannot be used when --ebook or --ebooks_dir is present.
  --language LANGUAGE   Language of the e-book. Default language is set
                            in ./lib/lang.py sed as default if not present. All compatible language codes are in ./lib/lang.py

optional parameters:
  --translate ISO3      (Optional) Translate ebook to a target language (ISO 639-3 code, e.g. eng, fra, deu) before TTS synthesis.
                            Uses argostranslate. The target language becomes the effective TTS language for the run.
                            A copy of the source ebook is made with the _<iso3> suffix so translated and non-translated
                            outputs stay isolated (independent process folder, audio chunks, and final file).
  --voice VOICE         (Optional) Path to the voice cloning file for TTS engine.
                            Uses the default voice if not present.
  --voice_map VOICE_MAP
                        (Optional, --ebooks_dir only) Path to a JSON file mapping ebook path -> voice path.
                            Each entry overrides --voice for that specific ebook. Missing/null entries fall back to --voice.
                            Keys may be absolute paths or basenames. Example:
                            {"book1.epub": "/voices/eng/adult/female/alice.wav", "/abs/path/book2.epub": null}
  --device {CPU,CUDA,MPS,ROCM,XPU,JETSON}
                        (Optional) Processor unit type for the conversion.
                            Default is set in ./lib/conf.py if not present. Fall back to CPU if CUDA or MPS is not available.
  --tts_engine {XTTS,BARK,VITS,FAIRSEQ,TACOTRON,YOURTTS,xtts,bark,vits,fairseq,tacotron,yourtts}
                        (Optional) Preferred TTS engine (available are: ['XTTS', 'BARK', 'VITS', 'FAIRSEQ', 'TACOTRON', 'YOURTTS', 'xtts', 'bark', 'vits', 'fairseq', 'tacotron', 'yourtts'].
                            Default depends on the selected language. The tts engine should be compatible with the chosen language
  --custom_model CUSTOM_MODEL
                        (Optional) Path to the custom model zip file cntaining mandatory model files.
                            Please refer to ./lib/models.py
  --fine_tuned FINE_TUNED
                        (Optional) Fine tuned model path. Default is builtin model.
  --output_format OUTPUT_FORMAT
                        (Optional) Output audio format. Default is m4b set in ./lib/conf.py
  --output_channel OUTPUT_CHANNEL
                        (Optional) Output audio channel. Default is mono set in ./lib/conf.py
  --temperature TEMPERATURE
                        (xtts only, optional) Temperature for the model.
                            Default to config.json model. Higher temperatures lead to more creative outputs.
  --length_penalty LENGTH_PENALTY
                        (xtts only, optional) A length penalty applied to the autoregressive decoder.
                            Default to config.json model. Not applied to custom models.
  --num_beams NUM_BEAMS
                        (xtts only, optional) Controls how many alternative sequences the model explores. Must be equal or greater than length penalty.
                            Default to config.json model.
  --repetition_penalty REPETITION_PENALTY
                        (xtts only, optional) A penalty that prevents the autoregressive decoder from repeating itself.
                            Default to config.json model.
  --top_k TOP_K         (xtts only, optional) Top-k sampling.
                            Lower values mean more likely outputs and increased audio generation speed.
                            Default to config.json model.
  --top_p TOP_P         (xtts only, optional) Top-p sampling.
                            Lower values mean more likely outputs and increased audio generation speed. Default to config.json model.
  --speed SPEED         (xtts only, optional) Speed factor for the speech generation.
                            Default to config.json model.
  --enable_text_splitting
                        (xtts only, optional) Enable TTS text splitting. This option is known to not be very efficient.
                            Default to config.json model.
  --text_temp TEXT_TEMP
                        (bark only, optional) Text Temperature for the model.
                            Default to config.json model.
  --waveform_temp WAVEFORM_TEMP
                        (bark only, optional) Waveform Temperature for the model.
                            Default to config.json model.
  --output_dir OUTPUT_DIR
                        (Optional) Path to the output directory. Default is set in ./lib/conf.py
  --abs_url ABS_URL     Audiobookshelf server URL (e.g. http://localhost:13378).
  --abs_api_token ABS_API_TOKEN
                        Audiobookshelf API token.
  --abs_library ABS_LIBRARY
                        Audiobookshelf library ID.
  --enable_interlude    Add MusicGen music before the first chapter, between chapters, and at the end of the audiobook. Settings are in ./lib/conf_interlude.py
  --version             Show the version of the script and exit

Example usage:
Windows:
    Gradio/GUI:
    ebook2audiobook.cmd
    Headless mode:
    ebook2audiobook.cmd --headless --ebook '/path/to/file' --language eng
Linux/Mac:
    Gradio/GUI:
    ./ebook2audiobook.command
    Headless mode:
    ./ebook2audiobook.command --headless --ebook '/path/to/file' --language eng

SML tags available:
	[break] — silence (random range **0.3–0.6 sec.**)
	[pause] — silence (random range **1.0–1.6 sec.**)
	[pause:N] — fixed pause (**N sec.**)
	[voice:/path/to/voice/file]...[/voice] — switch voice from default or selected voice from GUI/CLI
	[emotion:sadness]...[/emotion] — Zonos only: emotion for a passage (happiness, sadness, disgust, fear, surprise, anger, other, neutral) or a mix like [emotion:sadness=0.7,neutral=0.3]; other engines ignore it

```

NOTA: en modo gradio/gui, para cancelar una conversión en curso, simplemente haz clic en la [X] del componente de subida del libro electrónico.
CONSEJO: si necesita algo más de pausa, añade '[pause:3]' para 3 seg., etc.

### Docker
1. **Clone the Repository**:
```bash
   git clone https://github.com/DrewThomasson/ebook2audiobook.git
   cd ebook2audiobook
```
2. **Build the container**
```bash
    Windows:
        Docker:
            ebook2audiobook.cmd --script_mode build_docker
        Docker Compose:
            ebook2audiobook.cmd --script_mode build_docker --docker_mode compose
        Podman Compose:
            ebook2audiobook.cmd --script_mode build_docker --docker_mode podman
    Linux/Mac
        Docker:
            ./ebook2audiobook.command --script_mode build_docker
        Docker Compose
            ./ebook2audiobook.command --script_mode build_docker --docker_mode compose
        Podman Compose:
            ./ebook2audiobook.command --script_mode build_docker --docker_mode podman
```
4. **Run the Container:**
```bash
Docker run image:
    Gradio/GUI:
        CPU:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "e2a_venvs:/app/lib/classes/tts_engines/venvs" --rm -it -p 7860:7860 athomasson2/ebook2audiobook:cpu
        CUDA:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "e2a_venvs:/app/lib/classes/tts_engines/venvs" --gpus all --rm -it -p 7860:7860 athomasson2/ebook2audiobook:cu[118/122/124/126 etc..]
        ROCM:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "e2a_venvs:/app/lib/classes/tts_engines/venvs" --device=/dev/kfd --device=/dev/dri --rm -it -p 7860:7860 athomasson2/ebook2audiobook:rocm[6.0/6.1/6.4 etc..]
        XPU:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "e2a_venvs:/app/lib/classes/tts_engines/venvs" --device=/dev/dri --rm -it -p 7860:7860 athomasson2/ebook2audiobook:xpu
        JETSON:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "e2a_venvs:/app/lib/classes/tts_engines/venvs" --runtime nvidia --rm -it -p 7860:7860 athomasson2/ebook2audiobook:jetson[5/6/7 etc...]
    Headless mode:
        CPU:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "e2a_venvs:/app/lib/classes/tts_engines/venvs" -v "/my/real/ebooks/folder/absolute/path:/app/another_ebook_folder" --rm -it -p 7860:7860 athomasson2/ebook2audiobook:cpu --headless --ebook "/app/another_ebook_folder/myfile.pdf" [--voice /app/my/voicepath/voice.mp3 etc..]
        CUDA:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "e2a_venvs:/app/lib/classes/tts_engines/venvs" -v "/my/real/ebooks/folder/absolute/path:/app/another_ebook_folder" --gpus all --rm -it -p 7860:7860 athomasson2/ebook2audiobook:cu[118/122/124/126 etc..] --headless --ebook "/app/another_ebook_folder/myfile.pdf" [--voice /app/my/voicepath/voice.mp3 etc..]
        ROCM:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "e2a_venvs:/app/lib/classes/tts_engines/venvs" -v "/my/real/ebooks/folder/absolute/path:/app/another_ebook_folder" --device=/dev/kfd --device=/dev/dri --rm -it -p 7860:7860 athomasson2/ebook2audiobook:rocm[6.0/6.1/6.4 etc.] --headless --ebook "/app/another_ebook_folder/myfile.pdf" [--voice /app/my/voicepath/voice.mp3 etc..]
        XPU:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "e2a_venvs:/app/lib/classes/tts_engines/venvs" -v "/my/real/ebooks/folder/absolute/path:/app/another_ebook_folder" --device=/dev/dri --rm -it -p 7860:7860 athomasson2/ebook2audiobook:xpu --headless --ebook "/app/another_ebook_folder/myfile.pdf" [--voice /app/my/voicepath/voice.mp3 etc..]
        JETSON:
          docker run -v "./ebooks:/app/ebooks" -v "./audiobooks:/app/audiobooks" -v "./models:/app/models" -v "./voices:/app/voices" -v "./tmp:/app/tmp" -v "e2a_venvs:/app/lib/classes/tts_engines/venvs" -v "/my/real/ebooks/folder/absolute/path:/app/another_ebook_folder" --runtime nvidia --rm -it -p 7860:7860 athomasson2/ebook2audiobook:jetson[5/6/7 etc.] --headless --ebook "/app/another_ebook_folder/myfile.pdf" [--voice /app/my/voicepath/voice.mp3 etc..]
Docker Compose (i.e. cuda 12.8:
        Run Gradio GUI:
               DEVICE_TAG=cu128 docker compose --profile cuda up --no-log-prefix
        Run Headless mode:
               DEVICE_TAG=cu128 docker compose --profile cuda run --rm ebook2audiobook-cuda --headless --ebook "/app/ebooks/myfile.pdf" --voice /app/voices/eng/adult/female/some_voice.wav etc..
Podman Compose (i.e. cuda 12.8:
        Run Gradio GUI:
               DEVICE_TAG=cu128 podman-compose -f podman-compose.yml --profile cuda up
        Run Headless mode:
               DEVICE_TAG=cu128 podman-compose -f podman-compose.yml --profile cuda run --rm ebook2audiobook-cuda --headless --ebook "/app/ebooks/myfile.pdf" --voice /app/voices/eng/adult/female/some_voice.wav etc..
```
- NOTE: MPS is not exposed in docker so CPU must be used
- NOTE: the named volume `e2a_venvs` keeps the TTS engines installed in their own venv (GPT-SoVITS, Zonos, OmniVoice, F5-TTS, Orpheus, Spark-TTS, ChatTTS, OpenVoice, MeloTTS, CSM etc.)
  across container runs, so they are not reinstalled each time. To reset them: `docker volume rm e2a_venvs`

## Herramientas
Herramientas independientes, ejecutadas con el propio Python de e2a (`python_env`, creado por el primer lanzamiento de e2a).

<a id="preload-models"></a>
### Preload models for offline installs: `tools/preload_models.py`
Downloads every model e2a uses (TTS engines and their fine-tunes, voice conversion, stanza, pyannote, demucs,
music interludes, argos-translate packages, tesseract data, jieba, and the voices) into one folder laid out
exactly like `./models`, i.e. a USB key. On the offline machine, copy that folder into e2a's `./models`
and the `voices` folder written beside it into e2a's `./voices`.
Every finished job is recorded in `<models_dir>/.e2a_downloads.json`: a rerun skips what is done and starts
again what was cut (ctrl-c, crash, unplugged key) after removing its partial files.
   - **Linux/MacOS**
     ```bash
     ./python_env/bin/python tools/preload_models.py /media/user/KEY/models --languages eng,fra
     ```
   - **Windows**
     ```bash
     python_env\Scripts\python.exe tools\preload_models.py E:\models --languages eng,fra
     ```
   - `--dry_run` lists the jobs and their state (done, interrupted, todo) without downloading anything.

```bash
usage: preload_models.py [-h] [--only ONLY] [--skip SKIP] [--languages LANGUAGES]
                         [--audiocpp_packages AUDIOCPP_PACKAGES] [--refresh] [--dry_run]
                         models_dir

Download every model e2a uses into one folder laid out exactly like ./models (i.e. a USB key for offline
installs).

positional arguments:
  models_dir            Target folder, i.e. /media/user/KEY/models or E:\models

options:
  -h, --help            show this help message and exit
  --only ONLY           Comma list of categories: common,xtts,bark,tortoise,vits,fairseq,glowtts,tacotron,yo
                        urtts,piper,zonos,audiocpp,audiocpp_server,gptsovits,f5tts,omnivoice,orpheus,sparktt
                        s,chattts,csm,openvoice,melotts,phonon,stanza,pyannote,demucs,interlude,argos,tessda
                        ta,jieba,voices
  --skip SKIP           Comma list of categories to leave out
  --languages LANGUAGES
                        Comma list of e2a ISO-639-3 codes (eng,fra,ita...): single-language models and fine-
                        tunes for these only, multilingual models only for engines speaking one of them
  --audiocpp_packages AUDIOCPP_PACKAGES
                        audiocpp_server category: auto (the packages this machine runs, GPU and CPU), all
                        (every platform, for a key used elsewhere), or a comma list of audiocpp_packages
                        keys from lib/conf_models.py
  --refresh             Run every job again, even those already marked done (files already there are still
                        not downloaded twice)
  --dry_run             List every download job with its state (done, interrupted, todo) and exit
```

<a id="translate-ebooks"></a>
### Translate ebooks out of e2a: `translate_ebook.sh` / `translate_ebook.cmd`
Translates EPUB/AZW3 files, a whole folder (`-r` for its subfolders) or a list of paths (`@list.txt`)
into translated ebooks, offline, with the Argos Translate calibre plugin shipped in
`tools/argostranslate-calibre-plugin.zip`. Independent of the audiobook conversion: it only writes ebooks.
It needs calibre (already required by e2a) and runs on e2a's `python_env` and argos-translate packages:
a language pair e2a already uses is not downloaded again, a missing one is downloaded on first use.
The plugin is installed on first use into e2a's own calibre profile (`./run`), your calibre is left untouched.
`--to fra,ara,spa` translates into several languages at once, one ebook per language, and `--to all` into every
language the source reaches (`--from`, else each book's own language; installed ones only with `--no-download`).
`--list --from eng` lists the languages English translates into (installed, downloadable, or through English for
another source).
Without `-o` or `--output-dir`, each translation is saved beside its book as `<name>.<lang>.<ext>`,
and a book whose translation already exists is skipped (`--overwrite` to translate it again).
The launchers in e2a's folder run `tools/translate_ebook.py` with `python_env`, nothing to activate,
from any folder (relative paths are taken from where it is started):
   - **Linux/MacOS**
     ```bash
     ./translate_ebook.sh /path/to/books -r --to fra,spa --output-dir /path/to/books_translated
     ```
   - **Windows**
     ```bash
     translate_ebook.cmd C:\books -r --to fra,spa --output-dir C:\books_translated
     ```
   - Or directly with `python_env`'s Python: `./python_env/bin/python tools/translate_ebook.py ...`
     (Windows: `python_env\Scripts\python.exe tools\translate_ebook.py ...`). Started with any other Python,
     the script starts itself again with `python_env`'s.
   - **Docker**: run it inside the e2a container, e.g. `docker exec -it <container> python3 tools/translate_ebook.py ...`
     with paths seen from the container.
   - **Speed**: argostranslate runs on its own defaults (CTranslate2 picks the threads and the fastest compute type,
     int8 on CPU), not on e2a's 1 thread in float32. Set `ARGOS_INTRA_THREADS` or `ARGOS_COMPUTE_TYPE` to override them.

```bash
usage: translate_ebook.py [-h] [-t LANG[,LANG...]] [-f LANG] [-r] [-o OUTPUT] [--output-dir OUTPUT_DIR]
                          [--overwrite] [-m {replace,bilingual}] [--device {cpu,cuda,auto}]
                          [--batch-size BATCH_SIZE] [--no-cache] [--no-download] [--allow-changes] [--list]
                          [books ...]

Translate EPUB/AZW3 ebooks offline, out of e2a, with the Argos Translate calibre plugin
(tools/argostranslate-calibre-plugin.zip). It runs on e2a's python_env and argos-translate packages
(models/argos-translate): a language pair e2a already uses is not downloaded again, a missing one is
downloaded on first use (direct or through English). The plugin is installed into e2a's own calibre
profile (run/) on first use, your calibre setup is left untouched.
Translated paths are printed on stdout, progress and logs on stderr.

positional arguments:
  books                 EPUB/AZW3 files or folders to translate; @list.txt reads paths from a file, one per
                        line

options:
  -h, --help            show this help message and exit
  -t, --to LANG[,LANG...]
                        Target language(s), ISO-639-1 or ISO-639-3 codes, comma separated for several (fr,
                        fra or fra,ara,spa): one translated ebook per language. all: every language the
                        source reaches (see --list --from), installed ones only with --no-download
  -f, --from LANG       Source language, ISO-639-1 or ISO-639-3 code (default: read from each book)
  -r, --recursive       Also look for books in the subfolders of the given folders
  -o, --output OUTPUT   Output file, single input only, same extension as the input (default:
                        <name>.<lang>.<ext> next to the input)
  --output-dir OUTPUT_DIR
                        Write the translations into this folder (subfolders are mirrored with -r) instead of
                        next to each book
  --overwrite           Translate again even if the output file already exists (skipped otherwise)
  -m, --mode {replace,bilingual}
                        replace: the translation replaces the text. bilingual: each paragraph is followed by
                        its translation, saved as <name>.<lang>.bilingual.<ext> (default: replace)
  --device {cpu,cuda,auto}
                        Device argostranslate runs on (default: cpu)
  --batch-size BATCH_SIZE
                        Segments sent to the translation worker per request (default: 16)
  --no-cache            Neither read nor write the translation cache (run/argos_translate/cache.sqlite), the
                        one that makes a second run of the same book near instant
  --no-download         Never download a missing argos-translate package, fail instead
  --allow-changes       Only when argostranslate is missing from python_env: install it even if packages
                        already there would change version
  --list                List the installed and the downloadable language pairs, then exit. With --from
                        and/or --to: only their pairs, plus the targets a source reaches through English

examples:
  translate_ebook.py book.epub --to fr
  translate_ebook.py book.epub --to fra,ara,spa
  translate_ebook.py book.azw3 --from en --to deu -o /path/to/book_deu.azw3
  translate_ebook.py /path/to/books -r --to es,it --output-dir /path/to/books_translated
  translate_ebook.py book.epub --from eng --to all
  translate_ebook.py @books.txt --to ita --mode bilingual
  translate_ebook.py --list
  translate_ebook.py --list --from eng
```

## Voces clonadas
Puedes subir cualquier audio de voz en cualquiera de los formatos de audio admitidos, la duración ideal es de alrededor de 1 a 5 minutos.
No importa si la grabación tiene un fondo ruidoso o si se reproduce música sobre ella: E2A limpiará la voz por ti.

La lista de voces clonadas incorporada está principalmente en inglés. Si necesitas voces en otros idiomas para ser oficialmente
añadidos a la lista, ponte en contacto con nosotros y los añadiremos después de revisarlos.

## Modelos TTS ajustados (fine-tuned)
#### Ajusta tu propio modelo TTS

[Universal_TTS_Finetune](https://github.com/DrewThomasson/Universal_TTS_Finetune)

#### Eliminar ruido de los datos de entrenamiento

[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Spaces-yellow?style=flat&logo=huggingface)](https://huggingface.co/spaces/drewThomasson/DeepFilterNet2_no_limit) [![GitHub Repo](https://img.shields.io/badge/DeepFilterNet-181717?logo=github)](https://github.com/Rikorose/DeepFilterNet)


### Colección de modelos TTS ajustados

[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Models-yellow?style=flat&logo=huggingface)](https://huggingface.co/drewThomasson/fineTunedTTSModels/tree/main)

Para un modelo personalizado XTTSv2 es obligatorio un clip de audio de referencia de la voz:

## Tu propia personalización de Ebook2Audiobook
Eres libre de modificar libs/conf.py para añadir o eliminar los ajustes que desees. Si piensas hacerlo, simplemente haz
una copia del conf.py original para que en cada actualización de ebook2audiobook puedas respaldar tu conf.py modificado y volver a poner
el original. Debes planificar el mismo proceso para models.py. Si deseas convertir tu propio modelo personalizado
en un modelo ajustado oficial de ebook2audiobook, contáctanos y lo añadiremos a la lista de preajustes.

## Reverting to older Versions
Releases can be found -> [here](https://github.com/DrewThomasson/ebook2audiobook/releases)
```bash
git checkout tags/VERSION_NUM # Locally/Compose -> Example: git checkout tags/v25.7.7
```

## Problemas habituales:
- ¿Mi GPU NVIDIA/ROCm/XPU/MPS no se detecta?? -> [GPU ISSUES Wiki Page](https://github.com/DrewThomasson/ebook2audiobook/wiki/GPU-ISSUES)
-  La CPU es lenta (mejor en una CPU SMP de servidor) mientras que la GPU puede lograr una conversión casi en tiempo real.
   [Discusión sobre esto](https://github.com/DrewThomasson/ebook2audiobook/discussions/19#discussioncomment-10879846)
   (Sin embargo, no tiene clonación de voz zero-shot, y las voces son de calidad Siri, pero es mucho más rápido en CPU).
- «Tengo problemas de dependencias» - Simplemente usa Docker, es totalmente autónomo y tiene un modo headless,
   añade el parámetro `--help` al final del comando docker run para más información.
- «¡Tengo un problema de audio truncado!» - POR FAVOR, ABRE UN ISSUE SOBRE ESTO,
   no hablamos todos los idiomas y necesitamos el consejo de los usuarios para ajustar la lógica de división de frases.😊

## ***** HOJA DE RUTA *****
- Todas las características abiertas a contribuciones públicas ⭐
- Cualquier ayuda de personas que hablen alguno de los idiomas admitidos para ayudarnos a mejorar los modelos ⭐
- [x] Previsualizar bloques/capítulos antes de iniciar la conversión
- [x] Edición por frase convertida para un cambio quirúrgico del texto
- [x] Generar introducciones, interludios y finales de música; editar interludios y finales
- [x] Integración de etiquetas SML para voz, pausa, corte y más cambios 
- [x] Información de los parámetros -h -help en distintos idiomas
- [x] Escaneo OCR para PDF / JPG / BMP / PNG / TIFF
- [x] Carpeta de notebooks [Talked about here](https://github.com/DrewThomasson/ebook2audiobookXTTS/issues/5#issuecomment-2408773254)
- [x] Hacer que la división de texto en chino no parta las palabras y mejorar la sincronización de las pausas [Talked about here](https://github.com/DrewThomasson/ebook2audiobookXTTS/issues/18#issuecomment-2401154894)
- [x] Dockerfile
- [x] Docker- Compose
- [x] Podman componer
- [x] Notebook de Kaggle
- [x] Notebook de Google Colab
- [x] Integración con Audiobookshelf
- [x] Opción de traducción del libro electrónico
- [x] Opciones de formato de salida
- [x] Conversión con multiprocesamiento
- [x] Conversión por lotes de una carpeta de libros electrónicos
- [x] Detección del dispositivo GPU
- [x] Denoise cualquier audio de referencia de fondo para la carga de clonación de voz
- [x] Carga de modelo personalizada y ajustada
- [ ] [Crear una app para iOS](https://github.com/DrewThomasson/ebook2audiobook/pull/35#issuecomment-2496495212)
- [ ] [Crear una app para Android](https://github.com/DrewThomasson/ebook2audiobook/pull/35#issuecomment-2496495212)

#### Peticiones de usuario
- [ ] Añadir un modelo de idioma portugués europeo para xttsv2, fairseq, vits, piper como mínimo (ayuda bienvenida)
- [ ] Añadir un modelo de idioma sindhi para xttsv2, fairseq, vits, piper como mínimo (ayuda bienvenida)

#### Motores TTS
- [x] DramaBox (https://github.com/dramabox-ai/dramabox)[cite: 1]
- [x] FireRed Audio / FireRedTTS3 (https://github.com/FireRedTeam/FireRedTTS)[cite: 1]
- [x] Discurso de pez/Audio de pez (https://github.com/fishaudio/fish-speech)[cite: 1]
- [x] Higgs Audio TTS (https://github.com/higgs-audio/higgs-audio)[cite: 1]
- [x] Maya1 (https://github.com/maya-ai/maya1)[cite: 1]
- [x] OmniVoice (https://github.com/k2-fsa/OmniVoice)[cite: 1]
- [x] F5-TTS (https://github.com/swivid/f5-tts)[cite: 1]
- [x] Qwen3-TTS (https://huggingface.co/spaces/Qwen/Qwen3-TTS)[cite: 1]
- [x] VibeVoice (https://github.com/vibevoice-community/VibeVoice)[cite: 1]
- [x] VoxCPM2 (https://github.com/voxcpm/voxcpm)[cite: 1]
- [x] Voxtral TTS (https://github.com/voxtral/voxtral-tts)[cite: 1]
- [x] Chatterbox (https://github.com/resemble-ai/chatterbox)[cite: 1]
- [x] CosyVoice / CosyVoice3 (https://github.com/FunAudioLLM/CosyVoice)[cite: 1]
- [x] Index-tts / Index TTS2 (https://github.com/index-tts/index-tts)[cite: 1]
- [x] XTTSv2 (https://github.com/coqui-ai/XTTS)[cite: 1]
- [x] Breeze TTS (https://github.com/FreedomIntelligence/Breeze-TTS)[cite: 1]
- [x] Confucio4 TTS (https://github.com/confucius-tts/confucius4)[cite: 1]
- [x] Puntos TTS (https://github.com/dot-audio/dots-tts)[cite: 1]
- [x] GPT-SoVITS (https://github.com/RVC-Boss/GPT-SoVITS)[cite: 1]
- [x] Kokoro-TTS (https://github.com/hexgrad/kokoro)[cite: 1]
- [x] KugelAudio (https://github.com/kugel-audio/kugelaudio)[cite: 1]
- [x] Magpie TTS (https://github.com/magpie-tts/magpie-tts)[cite: 1]
- [x] MioTTS (https://github.com/mio-tts/miotts)[cite: 1]
- [x] Moss TTS Local / Nano (https://github.com/OpenBMB/MossTTS)[cite: 1]
- [x] NewTTS / NeuTTS (https://github.com/neuphonic/neutts)[cite: 1]
- [x] Bolsillo TTS (https://github.com/pocket-tts/pocket-tts)[cite: 1]
- [x] Gradio Fonón (https://github.com/gradium-ai/xn-ptts)[cite: 1]
- [x] Supertónica (https://github.com/supertone-inc/supertonic)[cite: 1]
- [x] Irodori TTS (https://github.com/irodori-tts/irodori-tts)[cite: 1]
- [x] Piper (https://github.com/rhasspy/piper)[cite: 1]
- [x] VITS (https://github.com/jaywalnut330/vits)[cite: 1]
- [x] Fairseq (https://github.com/facebookresearch/fairseq)[cite: 1]
- [x] GlowTTS (https://github.com/jaywalnut330/glow-tts)[cite: 1]
- [x] Tacotron2 (https://github.com/NVIDIA/Tacotron2)[cite: 1)
- [x] Tortuga (https://github.com/neonbjb/tortoise-tts)[cite: 1]
- [x] Zonos (https://github.com/Zyphra/Zonos)[cite: 1]
- [x] Corteza (https://github.com/suno-ai/bark)[cite: 1)
- [x] YourTTS (https://github.com/Edresson/YourTTS)[cite: 1)
- [x] Orpheus-TTS (https://github.com/canopyai/Orpheus-TTS)
- [x] OpenVoice (https://github.com/myshell-ai/OpenVoice)
- [x] ChatTTS (https://github.com/2noise/ChatTTS)
- [x] Spark-TTS (https://github.com/sparkaudio/spark-tts)
- [x] MeloTTS (https://github.com/myshell-ai/MeloTTS)
- [x] CSM (https://github.com/SesameAILabs/csm)

#### Traducción del Readme
- [x] Árabe (ara)
- [x] Chino (zho)
- [x] English (ENG)
- [x] Español IV (Esp)
- [x] Francés (fra)
- [x] Alemán (deu)
- [x] Italiano I (ita)
- [x] Portugués (por)
- [x] Polaco (pol)
- [x] Turco (tur)
- [x] Russian (rus)
- [x] Holandés (nld)
- [x] Czech (ces)
- [x] Japonés (jpn)
- [x] Hindi (hin)
- [x] Bengalí (ben)
- [x] Húngaro (HUN)
- [x] Coreano (kor)
- [x] Vietnamita (vie)
- [x] Swedish (swe)
- [x] Persa (fas)
- [x] Yoruba (yor)
- [x] Swahili (swa)
- [x] Indonesio (ind)
- [x] Eslovaco (slk)
- [x] Croata (hrv)

#### Compatibilidad con sistemas operativos
- [x] 🪟 Windows x86
- [x] 🪟 ARM WINDOWS
- [x] 🍎 Mac Intel x86
- [x] 🍎 Apple Silicon Mac
- [x] 🐧 Linux x86
- [x] 🐧 ARM LINUX

**********

## Extra exagerado para entrenar modelos y demás (todos los modelos Coqui-tts admitidos y piper-tts en un solo comando fácil) 
- Para obtener información sobre este @ DrewThomasson, actualmente está trabajando en el desarrollo de este, [Universal TTS Finetune](https://github.com/DrewThomasson/Universal_TTS_Finetune)
- [x] Haga una guía de entrenamiento fácil de usar para todos los modelos de coqui-tts en el [ljspeech format training recipes](https://github.com/coqui-ai/TTS/tree/dev/recipes/ljspeech) Completado en [Universal TTS Finetune](https://github.com/DrewThomasson/Universal_TTS_Finetune)


## Información de normalización del código Python para colaboradores
- sin línea en blanco entre el código, salvo entre funciones y clases.
- comilla simple usada para todas las claves salvo para dict() y json. dict['key'] siempre se llama con comilla simple
- indentación de 4 espacios, nada de tabulaciones
- tipado estricto para todas las funciones y la declaración de sus argumentos y valores de retorno
- sin espacio entre el argumento y su tipado, sin espacio entre la función, el «->» y el valor de retorno

Ejemplo:

```python
import json
from typing import Optional

def get_user(user_id:int, users:list[dict])->Optional[dict]:
    for user in users:
        if user['id'] == user_id:
            return user
    return None

def summarize(user:dict)->str:
    return f"User {user['name']} is {'active' if user['is_active'] else 'inactive'}."

def to_json(user:dict)->str:
    return json.dumps({"id": user['id'], "name": user['name'], "email": user['email']})

users:list = [
    dict(id=1, name="alice", email="alice@example.com", role="admin", is_active=True),
    dict(id=2, name="bob", email="bob@example.com", role="editor", is_active=False),
    dict(id=3, name="carol", email="carol@example.com", role="viewer", is_active=True),
]
config = {
    "max_users": 100,
    "default_role": "viewer",
    "allow_signup": True,
}
roles = ['admin', 'editor', 'viewer']
found = get_user(1, users)
if found:
    print(summarize(found))
    print(found['email'])
    print(to_json(found))
if config['default_role'] in roles:
    print(config['default_role'])
```

## Se busca donación de hardware para pruebas beta
Aceptamos cualquier tipo de hardware para probar nuestro desarrollo, como:
- Nvidia soportando cuda >= 11.8
- Tarjetas XPU Intel
- Tarjetas ROCm AMD compatibles con ROCm >=5,7

¡@DrewThomasson si quieres ayudar en lo que sea! 😃
<!--
## ¿Necesitas alquilar una GPU para potenciar nuestro servicio?
- Hay una encuesta abierta aquí https://github.com/DrewThomasson/ebook2audiobook/discussions/889
-->

## Créditos
- [Coqui-tts](https://github.com/idiap/coqui-ai-TTS) -- A deep learning toolkit for Text-to-Speech, battle-test in research and production.
- [Piper-tts](https://github.com/OHF-Voice/piper1-gpl) -- Fast and local neural text-to-speech engine.
- [Zonos2.cpp](https://github.com/Zyphra/zonos2.cpp) -- código de inferencia ggml para Zonos2.
- [Audio.cpp](https://github.com/0xShug0/audio.cpp) -- Un motor de inferencia todo en uno, puro C++ para modelos de audio, alimentado por ggml.

## Agradecimientos especiales
Para todos los contribuyentes financieros y de código, cada contribución y sugerencia ayuda a mejorar la calidad de E2A.