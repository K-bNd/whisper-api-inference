import os
import time
import concurrent.futures
from urllib.error import URLError

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import webvtt
from app_utils import Settings, allowed_extension, download_file
from transcript import Transcript

app = FastAPI()


SERVER_URL = os.getenv("SERVER_URL", "")

settings = Settings()
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.mount("/upload_files", StaticFiles(directory="./upload_files"), name="upload_files")
app.mount("/static", StaticFiles(directory="./static"), name="static")

obj = Transcript(settings.deepl_key)


class Param(BaseModel):
    """Define param class"""

    file: str


class TranslateParam(Param):
    """Define translate param class"""

    in_lang: str
    out_langs: list[str]


def remove_files_parallel(paths: list[str]):
    """Remove files from disk with multithreading"""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(remove_file, paths)


def remove_file(path: str) -> None:
    """Remove file from disk"""
    try:
        time.sleep(5 * 60)
        os.remove(path)
        print(f"File {path} removed successfully.")
    except Exception as e:
        print(f"Error removing file {path}: {e}")


def get_file(file: str) -> str:
    """Get path from file after downloading"""

    filename = os.path.join(settings.upload_folder, file.rsplit("/", maxsplit=1)[-1])

    try:
        path = download_file(file, filename)
    except (URLError, ValueError) as err:
        raise HTTPException(
            status_code=403,
            detail="Server does not have access to the content",
        ) from err
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=502, detail="Server could not write file to disk"
        ) from err

    return path


@app.get("/")
def root() -> FileResponse:
    """Show home page."""
    return FileResponse(path="./static/index.html", media_type="text/html")


@app.get("/transcript")
def get_transcript(param: Param, background_tasks: BackgroundTasks):
    """Get transcript"""
    if not allowed_extension(param.file):
        raise HTTPException(
            status_code=422, detail="Unallowed extension for audio file"
        )

    path = get_file(param.file)
    background_tasks.add_task(remove_file, path)
    transcript = obj.get_transcript(path)
    return {"data": transcript["text"], "language": obj.spoken_lang}


@app.get("/subtitles")
def write_subtitles(param: Param, background_tasks: BackgroundTasks):
    """Write subtitles for file"""
    if not allowed_extension(param.file):
        raise HTTPException(
            status_code=422, detail="Unallowed extension for audio file"
        )

    path = get_file(param.file)

    subtitles_src = ".".join(path.split(".")[0:-1]) + "-subtitles.vtt"
    obj.write_subtitles(path, subtitles_src)
    background_tasks.add_task(remove_files_parallel, [path, subtitles_src])
    return {
        "data": f"{SERVER_URL}/upload_files/{subtitles_src.rsplit('/', maxsplit=1)[-1]}",
        "language": obj.spoken_lang,
    }


@app.get("/translate_subtitles")
def translate_subtitles(param: TranslateParam, background_tasks: BackgroundTasks):
    """Translate subtitles"""

    if not "." in param.file or not param.file.rsplit(".", 1)[-1] == "vtt":
        raise HTTPException(
            status_code=422, detail="Unallowed extension for subtitle format"
        )

    path = get_file(param.file)
    subtitles_src = webvtt.read(path)

    subtitles_url_dst, subtitles_path_dst = obj.translate_subtitles(
        subtitles_src, param.out_langs
    )

    background_tasks.add_task(remove_file, path)
    background_tasks.add_task(remove_files_parallel, list(subtitles_path_dst.values()))
    return subtitles_url_dst
