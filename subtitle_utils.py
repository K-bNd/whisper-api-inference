import os
import re
from typing import Optional, TextIO
from faster_whisper.utils import format_timestamp


class ResultWriter:
    """ResultWriter interface to write transcripts."""

    extension: str

    def __init__(self, output_dir: str):
        """Init function."""
        self.output_dir = output_dir

    def __call__(self, result: dict, audio_path: str, options: dict):
        """Call function."""
        audio_basename = os.path.basename(audio_path)
        audio_basename = os.path.splitext(audio_basename)[0]
        output_path = os.path.join(
            self.output_dir, audio_basename + "." + self.extension
        )

        with open(output_path, "w", encoding="utf-8") as f:
            self.write_result(result, file=f, options=options)

    def write_result(self, result: dict, file: TextIO, options: dict):
        """Write this function."""
        raise NotImplementedError


class SubtitlesWriter(ResultWriter):
    """SubtitlesWriter interface to write subtitles."""

    always_include_hours: bool
    decimal_marker: str

    def iterate_result(self, result: dict, options: dict):
        """Iterate on transcript."""
        raw_max_line_width: Optional[int] = options["max_line_width"]
        max_line_count: Optional[int] = options["max_line_count"]
        highlight_words: bool = options["highlight_words"]
        max_line_width = 1000 if raw_max_line_width is None else raw_max_line_width
        preserve_segments = max_line_count is None or raw_max_line_width is None

        def iterate_subtitles():
            line_len = 0
            line_count = 1
            # the next subtitle to yield (a list of word timings with whitespace)
            subtitle: list[dict] = []
            last = result["segments"][0].words[0].start
            for segment in result["segments"]:
                for i, original_timing in enumerate(segment.words):
                    timing = original_timing.copy()
                    long_pause = not preserve_segments and timing.start - last > 3.0
                    has_room = line_len + len(timing.word) <= max_line_width
                    seg_break = i == 0 and len(subtitle) > 0 and preserve_segments
                    if line_len > 0 and has_room and not long_pause and not seg_break:
                        # line continuation
                        line_len += len(timing.word)
                    else:
                        # new line
                        timing.word = timing.word.strip()
                        if (
                            len(subtitle) > 0
                            and max_line_count is not None
                            and (long_pause or line_count >= max_line_count)
                            or seg_break
                        ):
                            # subtitle break
                            yield subtitle
                            subtitle = []
                            line_count = 1
                        elif line_len > 0:
                            # line break
                            line_count += 1
                            timing.word = "\n" + timing.word
                        line_len = len(timing.word.strip())
                    subtitle.append(timing)
                    last = timing.start
            if len(subtitle) > 0:
                yield subtitle

        if result["segments"][0].words:
            for subtitle in iterate_subtitles():
                subtitle_start = format_timestamp(subtitle[0].start)
                subtitle_end = format_timestamp(subtitle[-1].end)
                subtitle_text = "".join([word.word for word in subtitle])
                if highlight_words:
                    last = subtitle_start
                    all_words = [timing.word for timing in subtitle]
                    for i, this_word in enumerate(subtitle):
                        start = format_timestamp(this_word.start)
                        end = format_timestamp(this_word.end)
                        if last != start:
                            yield last, start, subtitle_text

                        yield start, end, "".join(
                            [
                                re.sub(r"^(\s*)(.*)$", r"\1<u>\2</u>", word)
                                if j == i
                                else word
                                for j, word in enumerate(all_words)
                            ]
                        )
                        last = end
                else:
                    yield subtitle_start, subtitle_end, subtitle_text
        else:
            for segment in result["segments"]:
                segment_start = format_timestamp(segment.start)
                segment_end = format_timestamp(segment.end)
                segment_text = segment.text.strip().replace("-->", "->")
                yield segment_start, segment_end, segment_text


class WriteVTT(SubtitlesWriter):
    """Reimplementation of WriteVTT to add align:middle."""

    extension: str = "vtt"
    always_include_hours: bool = False
    decimal_marker: str = "."

    def write_result(self, result: dict, file: TextIO, options: dict):
        """Add new write_result."""
        print("WEBVTT\n", file=file)
        for start, end, text in self.iterate_result(result, options):
            print(f"{start} --> {end} align:middle\n{text}\n", file=file, flush=True)
