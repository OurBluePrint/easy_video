from utils import convert_to_seconds
import re
import warnings

import subprocess as sp
import os

from os_dependency import FFMPEG_BINARY, cross_platform_popen_params

class FFmpegInfosParser:
    """Finite state ffmpeg `-i` command option file information parser.
    Is designed to parse the output fast, in one loop. Iterates line by
    line of the `ffmpeg -i <filename> [-f null -]` command output changing
    the internal state of the parser.

    Parameters
    ----------

    filename
      Name of the file parsed, only used to raise accurate error messages.

    infos
      Information returned by FFmpeg.

    fps_source
      Indicates what source data will be preferably used to retrieve fps data.

    check_duration
      Enable or disable the parsing of the duration of the file. Useful to
      skip the duration check, for example, for images.

    decode_file
      Indicates if the whole file has been decoded. The duration parsing strategy
      will differ depending on this argument.
    """

    def __init__(
        self,
        infos,
        filename,
        fps_source="fps",
        check_duration=True,
        decode_file=False,
    ):
        self.infos = infos
        self.filename = filename
        self.check_duration = check_duration
        self.fps_source = fps_source
        self.duration_tag_separator = "time=" if decode_file else "Duration: "

        self._reset_state()

    def _reset_state(self):
        """Reinitializes the state of the parser. Used internally at
        initialization and at the end of the parsing process.
        """
        # could be 2 possible types of metadata:
        #   - file_metadata: Metadata of the container. Here are the tags set
        #     by the user using `-metadata` ffmpeg option
        #   - stream_metadata: Metadata for each stream of the container.
        self._inside_file_metadata = False

        # this state is needed if `duration_tag_separator == "time="` because
        # execution of ffmpeg decoding the whole file using `-f null -` appends
        # to the output the blocks "Stream mapping:" and "Output:", which
        # should be ignored
        self._inside_output = False

        # flag which indicates that a default stream has not been found yet
        self._default_stream_found = False

        # current input file, stream and chapter, which will be built at runtime
        self._current_input_file = {"streams": []}
        self._current_stream = None
        self._current_chapter = None

        # resulting data of the parsing process
        self.result = {
            "video_found": False,
            "audio_found": False,
            "metadata": {},
            "inputs": [],
        }

        # keep the value of latest metadata value parsed so we can build
        # at next lines a multiline metadata value
        self._last_metadata_field_added = None

    def parse(self):
        """Parses the information returned by FFmpeg in stderr executing their binary
        for a file with ``-i`` option and returns a dictionary with all data needed
        by MoviePy.
        """
        # chapters by input file
        input_chapters = []

        for line in self.infos.splitlines()[1:]:
            if (
                self.duration_tag_separator == "time="
                and self.check_duration
                and "time=" in line
            ):
                # parse duration using file decodification
                self.result["duration"] = self.parse_duration(line)
            elif self._inside_output or line[0] != " ":
                if self.duration_tag_separator == "time=" and not self._inside_output:
                    self._inside_output = True
                # skip lines like "At least one output file must be specified"
            elif not self._inside_file_metadata and line.startswith("  Metadata:"):
                # enter "  Metadata:" group
                self._inside_file_metadata = True
            elif line.startswith("  Duration:"):
                # exit "  Metadata:" group
                self._inside_file_metadata = False
                if self.check_duration and self.duration_tag_separator == "Duration: ":
                    self.result["duration"] = self.parse_duration(line)

                # parse global bitrate (in kb/s)
                bitrate_match = re.search(r"bitrate: (\d+) kb/s", line)
                self.result["bitrate"] = (
                    int(bitrate_match.group(1)) if bitrate_match else None
                )

                # parse start time (in seconds)
                start_match = re.search(r"start: (\d+\.?\d+)", line)
                self.result["start"] = (
                    float(start_match.group(1)) if start_match else None
                )
            elif self._inside_file_metadata:
                # file metadata line
                field, value = self.parse_metadata_field_value(line)

                # multiline metadata value parsing
                if field == "":
                    field = self._last_metadata_field_added
                    value = self.result["metadata"][field] + "\n" + value
                else:
                    self._last_metadata_field_added = field
                self.result["metadata"][field] = value
            elif line.lstrip().startswith("Stream "):
                # exit stream "    Metadata:"
                if self._current_stream:
                    self._current_input_file["streams"].append(self._current_stream)

                # get input number, stream number, language and type
                main_info_match = re.search(
                    r"^Stream\s#(\d+):(\d+)(?:\[\w+\])?\(?(\w+)?\)?:\s(\w+):",
                    line.lstrip(),
                )
                (
                    input_number,
                    stream_number,
                    language,
                    stream_type,
                ) = main_info_match.groups()
                input_number = int(input_number)
                stream_number = int(stream_number)
                stream_type_lower = stream_type.lower()

                if language == "und":
                    language = None

                # start builiding the current stream
                self._current_stream = {
                    "input_number": input_number,
                    "stream_number": stream_number,
                    "stream_type": stream_type_lower,
                    "language": language,
                    "default": not self._default_stream_found
                    or line.endswith("(default)"),
                }
                self._default_stream_found = True

                # for default streams, set their numbers globally, so it's
                # easy to get without iterating all
                if self._current_stream["default"]:
                    self.result[
                        f"default_{stream_type_lower}_input_number"
                    ] = input_number
                    self.result[
                        f"default_{stream_type_lower}_stream_number"
                    ] = stream_number

                # exit chapter
                if self._current_chapter:
                    input_chapters[input_number].append(self._current_chapter)
                    self._current_chapter = None

                if "input_number" not in self._current_input_file:
                    # first input file
                    self._current_input_file["input_number"] = input_number
                elif self._current_input_file["input_number"] != input_number:
                    # new input file

                    # include their chapters if there are for this input file
                    if len(input_chapters) >= input_number + 1:
                        self._current_input_file["chapters"] = input_chapters[
                            input_number
                        ]

                    # add new input file to self.result
                    self.result["inputs"].append(self._current_input_file)
                    self._current_input_file = {"input_number": input_number}

                # parse relevant data by stream type
                try:
                    global_data, stream_data = self.parse_data_by_stream_type(
                        stream_type, line
                    )
                except NotImplementedError as exc:
                    warnings.warn(
                        f"{str(exc)}\nffmpeg output:\n\n{self.infos}", UserWarning
                    )
                else:
                    self.result.update(global_data)
                    self._current_stream.update(stream_data)
            elif line.startswith("    Metadata:"):
                # enter group "    Metadata:"
                continue
            elif self._current_stream:
                # stream metadata line
                if "metadata" not in self._current_stream:
                    self._current_stream["metadata"] = {}

                field, value = self.parse_metadata_field_value(line)

                if self._current_stream["stream_type"] == "video":
                    field, value = self.video_metadata_type_casting(field, value)
                    if field == "rotate":
                        self.result["video_rotation"] = value

                # multiline metadata value parsing
                if field == "":
                    field = self._last_metadata_field_added
                    value = self._current_stream["metadata"][field] + "\n" + value
                else:
                    self._last_metadata_field_added = field
                self._current_stream["metadata"][field] = value
            elif line.startswith("    Chapter"):
                # Chapter data line
                if self._current_chapter:
                    # there is a previews chapter?
                    if len(input_chapters) < self._current_chapter["input_number"] + 1:
                        input_chapters.append([])
                    # include in the chapters by input matrix
                    input_chapters[self._current_chapter["input_number"]].append(
                        self._current_chapter
                    )

                # extract chapter data
                chapter_data_match = re.search(
                    r"^    Chapter #(\d+):(\d+): start (\d+\.?\d+?), end (\d+\.?\d+?)",
                    line,
                )
                input_number, chapter_number, start, end = chapter_data_match.groups()

                # start building the chapter
                self._current_chapter = {
                    "input_number": int(input_number),
                    "chapter_number": int(chapter_number),
                    "start": float(start),
                    "end": float(end),
                }
            elif self._current_chapter:
                # inside chapter metadata
                if "metadata" not in self._current_chapter:
                    self._current_chapter["metadata"] = {}
                field, value = self.parse_metadata_field_value(line)

                # multiline metadata value parsing
                if field == "":
                    field = self._last_metadata_field_added
                    value = self._current_chapter["metadata"][field] + "\n" + value
                else:
                    self._last_metadata_field_added = field
                self._current_chapter["metadata"][field] = value

        # last input file, must be included in self.result
        if self._current_input_file:
            self._current_input_file["streams"].append(self._current_stream)
            # include their chapters, if there are
            if len(input_chapters) == self._current_input_file["input_number"] + 1:
                self._current_input_file["chapters"] = input_chapters[
                    self._current_input_file["input_number"]
                ]
            self.result["inputs"].append(self._current_input_file)

        # some video duration utilities
        if self.result["video_found"] and self.check_duration:
            self.result["video_n_frames"] = int(
                self.result["duration"] * self.result["video_fps"]
            )
            self.result["video_duration"] = self.result["duration"]
        else:
            self.result["video_n_frames"] = 1
            self.result["video_duration"] = None
        # We could have also recomputed duration from the number of frames, as follows:
        # >>> result['video_duration'] = result['video_n_frames'] / result['video_fps']

        # not default audio found, assume first audio stream is the default
        if self.result["audio_found"] and not self.result.get("audio_bitrate"):
            self.result["audio_bitrate"] = None
            for streams_input in self.result["inputs"]:
                for stream in streams_input["streams"]:
                    if stream["stream_type"] == "audio" and stream.get("bitrate"):
                        self.result["audio_bitrate"] = stream["bitrate"]
                        break

                if self.result["audio_bitrate"] is not None:
                    break

        result = self.result

        # reset state of the parser
        self._reset_state()

        return result

    def parse_data_by_stream_type(self, stream_type, line):
        """Parses data from "Stream ... {stream_type}" line."""
        try:
            return {
                "Audio": self.parse_audio_stream_data,
                "Video": self.parse_video_stream_data,
                "Data": lambda _line: ({}, {}),
            }[stream_type](line)
        except KeyError:
            raise NotImplementedError(
                f"{stream_type} stream parsing is not supported by moviepy and"
                " will be ignored"
            )

    def parse_audio_stream_data(self, line):
        """Parses data from "Stream ... Audio" line."""
        global_data, stream_data = ({"audio_found": True}, {})
        try:
            stream_data["fps"] = int(re.search(r" (\d+) Hz", line).group(1))
        except (AttributeError, ValueError):
            # AttributeError: 'NoneType' object has no attribute 'group'
            # ValueError: invalid literal for int() with base 10: '<string>'
            stream_data["fps"] = "unknown"
        match_audio_bitrate = re.search(r"(\d+) kb/s", line)
        stream_data["bitrate"] = (
            int(match_audio_bitrate.group(1)) if match_audio_bitrate else None
        )
        if self._current_stream["default"]:
            global_data["audio_fps"] = stream_data["fps"]
            global_data["audio_bitrate"] = stream_data["bitrate"]
        return (global_data, stream_data)

    def parse_video_stream_data(self, line):
        """Parses data from "Stream ... Video" line."""
        global_data, stream_data = ({"video_found": True}, {})

        try:
            match_video_size = re.search(r" (\d+)x(\d+)[,\s]", line)
            if match_video_size:
                # size, of the form 460x320 (w x h)
                stream_data["size"] = [int(num) for num in match_video_size.groups()]
        except Exception:
            raise IOError(
                (
                    "MoviePy error: failed to read video dimensions in"
                    " file '%s'.\nHere are the file infos returned by"
                    "ffmpeg:\n\n%s"
                )
                % (self.filename, self.infos)
            )

        match_bitrate = re.search(r"(\d+) kb/s", line)
        stream_data["bitrate"] = int(match_bitrate.group(1)) if match_bitrate else None

        # Get the frame rate. Sometimes it's 'tbr', sometimes 'fps', sometimes
        # tbc, and sometimes tbc/2...
        # Current policy: Trust fps first, then tbr unless fps_source is
        # specified as 'tbr' in which case try tbr then fps

        # If result is near from x*1000/1001 where x is 23,24,25,50,
        # replace by x*1000/1001 (very common case for the fps).

        if self.fps_source == "fps":
            try:
                fps = self.parse_fps(line)
            except (AttributeError, ValueError):
                fps = self.parse_tbr(line)
        elif self.fps_source == "tbr":
            try:
                fps = self.parse_tbr(line)
            except (AttributeError, ValueError):
                fps = self.parse_fps(line)
        else:
            raise ValueError(
                ("fps source '%s' not supported parsing the video '%s'")
                % (self.fps_source, self.filename)
            )

        # It is known that a fps of 24 is often written as 24000/1001
        # but then ffmpeg nicely rounds it to 23.98, which we hate.
        coef = 1000.0 / 1001.0
        for x in [23, 24, 25, 30, 50]:
            if (fps != x) and abs(fps - x * coef) < 0.01:
                fps = x * coef
        stream_data["fps"] = fps

        if self._current_stream["default"] or "video_size" not in self.result:
            global_data["video_size"] = stream_data.get("size", None)
        if self._current_stream["default"] or "video_bitrate" not in self.result:
            global_data["video_bitrate"] = stream_data.get("bitrate", None)
        if self._current_stream["default"] or "video_fps" not in self.result:
            global_data["video_fps"] = stream_data["fps"]

        return (global_data, stream_data)

    def parse_fps(self, line):
        """Parses number of FPS from a line of the ``ffmpeg -i`` command output."""
        return float(re.search(r" (\d+.?\d*) fps", line).group(1))

    def parse_tbr(self, line):
        """Parses number of TBS from a line of the ``ffmpeg -i`` command output."""
        s_tbr = re.search(r" (\d+.?\d*k?) tbr", line).group(1)

        # Sometimes comes as e.g. 12k. We need to replace that with 12000.
        if s_tbr[-1] == "k":
            tbr = float(s_tbr[:-1]) * 1000
        else:
            tbr = float(s_tbr)
        return tbr

    def parse_duration(self, line):
        """Parse the duration from the line that outputs the duration of
        the container.
        """
        try:
            time_raw_string = line.split(self.duration_tag_separator)[-1]
            match_duration = re.search(
                r"([0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9])",
                time_raw_string,
            )
            return convert_to_seconds(match_duration.group(1))
        except Exception:
            raise IOError(
                (
                    "MoviePy error: failed to read the duration of file '%s'.\n"
                    "Here are the file infos returned by ffmpeg:\n\n%s"
                )
                % (self.filename, self.infos)
            )

    def parse_metadata_field_value(
        self,
        line,
    ):
        """Returns a tuple with a metadata field-value pair given a ffmpeg `-i`
        command output line.
        """
        raw_field, raw_value = line.split(":", 1)
        return (raw_field.strip(" "), raw_value.strip(" "))

    def video_metadata_type_casting(self, field, value):
        """Cast needed video metadata fields to other types than the default str."""
        if field == "rotate":
            return (field, float(value))
        return (field, value)
    



def ffmpeg_parse_infos(
    filename,
    check_duration=True,
    fps_source="fps",
    decode_file=False,
    print_infos=False,
):
    """Get the information of a file using ffmpeg.

    Returns a dictionary with next fields:

    - ``"duration"``
    - ``"metadata"``
    - ``"inputs"``
    - ``"video_found"``
    - ``"video_fps"``
    - ``"video_n_frames"``
    - ``"video_duration"``
    - ``"video_bitrate"``
    - ``"video_metadata"``
    - ``"audio_found"``
    - ``"audio_fps"``
    - ``"audio_bitrate"``
    - ``"audio_metadata"``

    Note that "video_duration" is slightly smaller than "duration" to avoid
    fetching the incomplete frames at the end, which raises an error.

    Parameters
    ----------

    filename
      Name of the file parsed, only used to raise accurate error messages.

    infos
      Information returned by FFmpeg.

    fps_source
      Indicates what source data will be preferably used to retrieve fps data.

    check_duration
      Enable or disable the parsing of the duration of the file. Useful to
      skip the duration check, for example, for images.

    decode_file
      Indicates if the whole file must be read to retrieve their duration.
      This is needed for some files in order to get the correct duration (see
      https://github.com/Zulko/moviepy/pull/1222).
    """
    # Open the file in a pipe, read output
    cmd = [FFMPEG_BINARY, "-hide_banner", "-i", filename]
    if decode_file:
        cmd.extend(["-f", "null", "-"])

    popen_params = cross_platform_popen_params(
        {
            "bufsize": 10**5,
            "stdout": sp.PIPE,
            "stderr": sp.PIPE,
            "stdin": sp.DEVNULL,
        }
    )

    proc = sp.Popen(cmd, **popen_params)
    (output, error) = proc.communicate()
    infos = error.decode("utf8", errors="ignore")

    proc.terminate()
    del proc

    if print_infos:
        # print the whole info text returned by FFMPEG
        print(infos)

    try:
        return FFmpegInfosParser(
            infos,
            filename,
            fps_source=fps_source,
            check_duration=check_duration,
            decode_file=decode_file,
        ).parse()
    except Exception as exc:
        if os.path.isdir(filename):
            raise IsADirectoryError(f"'{filename}' is a directory")
        elif not os.path.exists(filename):
            raise FileNotFoundError(f"'{filename}' not found")
        else:
            try: # try decode_file=False for wav files
                cmd_new = [FFMPEG_BINARY, "-hide_banner", "-i", filename]
                proc = sp.Popen(cmd_new, **popen_params)
                (output, error) = proc.communicate()
                infos = error.decode("utf8", errors="ignore")

                proc.terminate()
                del proc
                if print_infos:
                    # print the whole info text returned by FFMPEG
                    print(infos)
                
                return FFmpegInfosParser(
                    infos,
                    filename,
                    fps_source=fps_source,
                    check_duration=check_duration,
                    decode_file=False,
                ).parse()
            except:
                raise IOError(f"Error passing `ffmpeg -i` command output:\n\n{infos}") from exc


if __name__ == "__main__":
    test_video = "/Users/kwonmingi/Codes/macocr/test_vid/vid12_xoobAzitHzs.wav"
    info = ffmpeg_parse_infos(test_video, print_infos=False)
    print(info)
