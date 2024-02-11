import concurrent.futures
import deepl
import torch
from faster_whisper import WhisperModel
import logging
import os
from subtitle_utils import WriteVTT
from webvtt import WebVTT


class Transcript:
    """
    Init Object that creates transcript and summaries from audio files.
    """

    SERVER_URL = os.getenv("SERVER_URL", "")

    def __init__(self, deepl_key, debug=False) -> None:
        """Init function.

        :param deepl_key : DeepL API key
        :type deepl_key: str
        """
        self.deepl_key = deepl_key
        self.transcript = None

        self.spoken_lang = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        if debug:
            logging.basicConfig()
            logging.getLogger("faster-whisper").setLevel(logging.DEBUG)

    def get_transcript(self, audio_file, debug=False) -> dict:
        """Get transcript from audio file.

        :param audio_file: Audio file to transcribe
        :type audio_file: str
        """

        model = WhisperModel("base", device=self.device, compute_type="int8")
        segments, info = model.transcribe(audio_file, vad_filter=True)
        segments = list(segments)

        self.spoken_lang = info.language

        transcript = ""

        for segment in segments:
            transcript += segment.text

        if debug:
            print(segments)

        self.transcript = dict({"segments": segments, "text": transcript, "info": info})
        return self.transcript

    def write_subtitles(
        self,
        audio_file: str,
        filename: str,
        transcript: dict = None,
        css_options: dict = None,
    ) -> None:
        """Write subtitles to file in any standard format.

        :param audio_file: The path to the audio file for which subtitles are generated.
        :type audio_file: str

        :param filename: The name of the file to write subtitles to.
        :type filename: str

        :param transcript: The subtitles text. If None, it will be generated from the audio_file.
        :type transcript: str

        :param css_options: Options like max_line_width, max_line_count, and highlight_words.
        :type css_options: dict
        """
        if transcript is None:
            transcript = self.get_transcript(audio_file)

        vtt_writer = WriteVTT(transcript)
        default_options = {
            "max_line_width": 28,
            "max_line_count": 2,
            "highlight_words": False,
        }
        options = css_options if css_options is not None else default_options
        with open(filename, "w", encoding="utf-8") as subs_file:
            vtt_writer.write_result(transcript, subs_file, options)

    def _translate_text(self, text: str, translator, out_lang: str) -> str:
        """
        Translate text to another language.

        :param text: The text to translate
        :type text: str

        :param translator: DeepL translator object
        :type translator: deepl.translator.Translator

        :param out_lang: The requested language
        :type out_lang: str

        :return: The translated text
        :rtype: str
        """
        return translator.translate_text(text, target_lang=out_lang.capitalize()).text

    def _translate_subtitle(
        self, source: WebVTT, translator: deepl.translator.Translator, lang: str
    ) -> (str, str):
        """
        Translate subtitles into a single language.

        :param source: Input subtitles in WebVTT format.
        :type source: WebVTT

        :param translator: DeepL translator object.
        :type translator: deepl.translator.Translator

        :param lang: Output language in ISO 639-1 standard.
        :type lang: str

        :return: URL to access filename of the translated WebVTT file and its path.
        :rtype: (str, str)
        """

        for caption in source.captions:
            caption.text = self._translate_text(caption.text, translator, lang)

        dst_filename = f"{source.file.rsplit('.', maxsplit=1)[0]}_{lang}.vtt"

        WebVTT(dst_filename, captions=source.captions, styles=source.styles).save(
            dst_filename
        )

        return (
            f"{Transcript.SERVER_URL}/upload_files/{dst_filename.rsplit('/')[-1]}",
            dst_filename,
        )

    def translate_subtitles(
        self, source: WebVTT, out_langs: list[str]
    ) -> (dict[str, str], dict[str, str]):
        """
        Translate the subtitles from the segment part of the transcript.

        :param source: The source subtitle
        :type source: WebVTT

        :param out_langs: The list of languages wanted in ISO 639-1 standard
        :type out_langs: list[str]

        :return: A dictionary mapping language codes (ISO 639-1) to translated subtitle URLs and a second one with their path.
        :rtype: dict[str, str]
        """

        with concurrent.futures.ProcessPoolExecutor() as executor:
            transcript_url_dict = {}
            transcript_path_dict = {}
            translator = deepl.Translator(auth_key=self.deepl_key)
            translate_batch = {
                executor.submit(
                    self._translate_subtitle, source, translator, lang
                ): lang
                for lang in out_langs
            }
            for future in concurrent.futures.as_completed(translate_batch):
                lang = translate_batch[future]
                try:
                    subtitles_url, subtitles_path = future.result()
                except Exception as exc:
                    print(f"{lang} generated an exception: {exc}")
                else:
                    transcript_url_dict[lang] = subtitles_url
                    transcript_path_dict[lang] = subtitles_path

            return transcript_url_dict, transcript_path_dict
