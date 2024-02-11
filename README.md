# Whisper API for inference

This codebase provides code to generate transcript and subtitles from audio input from a FastAPI API

> WARNING: This codebase assumes that you have access to an NVIDIA GPU (CUDA 12.1) as well a [DeepL API key](https://www.deepl.com/en/docs-api)

## Requirements

This project requires [Python 3.11](https://www.python.org/downloads/) to run as well as [Docker](https://www.docker.com/get-started/).

You will also need to the python packages in requirements.txt using pip.

```bash
pip install -r requirements.txt
```

You will need to have the following as environnment variables:

- DEEPL_KEY: DeepL API key for translation
- SERVER_URL: URL where the API is accesible

You can set them in the compose.yaml file.

## Usage

```bash
docker-compose -f compose.yaml up
```