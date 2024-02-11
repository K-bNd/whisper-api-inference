import os
from urllib.request import urlopen
from shutil import copyfileobj
from pydantic_settings import BaseSettings

ALLOWED_EXTENSIONS = {"mp3", "m4a", "mp4", "mov"}


def allowed_extension(filename: str) -> bool:
    """Check if the extension from the uploaded file is valid."""
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS


def download_file(url: str, filename: str) -> str:
    """Downloads a file from url into a file."""
    r = urlopen(url)
    if r.url != url:
        raise ValueError("Download error, failed to download content")

    with r as in_stream, open(filename, "wb+") as out_file:
        copyfileobj(in_stream, out_file)

    if not os.path.exists(filename):
        raise FileNotFoundError("File could be not created")

    return os.path.abspath(filename)


class Settings(BaseSettings):
    """
    Settings for the FastAPI app. Override with environment variables or .env file.

    Override example:
    `export FASTR_SECRET_KEY=secret`
    """

    secret_key: str = "dev"
    deepl_key: str = os.environ.get("DEEPL_KEY", "")
    upload_folder: str = "./upload_files"
