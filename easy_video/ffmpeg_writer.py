import subprocess as sp
from .ffmpeg_infos import cross_platform_popen_params, FFMPEG_BINARY

from tqdm import tqdm

class FFMPEG_AudioWriter:
    def __init__(
        self,
        filename,
        fps_input,
        nbytes=2,
        nchannels=2,
        codec=None,
        bitrate=None,
        input_video=None,
        logfile=None,
        ffmpeg_params=None,
        chunk_size=4096,
        is_raw_audio=False,
    ):
        if logfile is None:
            logfile = sp.PIPE
        self.logfile = logfile
        self.filename = filename
        self.codec = codec
        self.nbytes = nbytes
        self.nchannels = nchannels
        if codec is None:
            self.codec = "pcm_s%dle" % (8 * nbytes)
            codec = self.codec
        self.ext = self.filename.split(".")[-1]

        # order is important
        cmd = [
            FFMPEG_BINARY,
            "-y",
            "-loglevel",
            "error" if logfile == sp.PIPE else "info",
            "-f",
            "s%dle" % (8 * nbytes),
            "-acodec",
            "pcm_s%dle" % (8 * nbytes),
            "-ar",
            "%d" % fps_input,
            "-ac",
            "%d" % nchannels,
            "-i",
            "-",
        ]
        if input_video is None:
            cmd.extend(["-vn"])
        else:
            cmd.extend(["-i", input_video, "-vcodec", "copy"])

        cmd.extend(["-acodec", codec] + ["-ar", "%d" % fps_input])
        cmd.extend(["-strict", "-2"])  # needed to support codec 'aac'
        if bitrate is not None:
            cmd.extend(["-ab", bitrate])
        if ffmpeg_params is not None:
            cmd.extend(ffmpeg_params)
        cmd.extend([filename])

        popen_params = cross_platform_popen_params(
            {"stdout": sp.DEVNULL, "stderr": logfile, "stdin": sp.PIPE}
        )

        self.proc = sp.Popen(cmd, **popen_params)

        self.chunk_size = chunk_size
        self.is_raw_audio = is_raw_audio

    def audio_array_to_bytes(self, audio_array):
        if self.is_raw_audio:
            return audio_array.tobytes()
        audio_array = (audio_array * 2 ** (8 * self.nbytes - 1)).astype(f"int{8*self.nbytes}")
        return audio_array.tobytes()

    def write_frames_chunk(self, frames_array):
        """TODO: add documentation"""
        try:
            for inx in tqdm(range(0, len(frames_array), self.chunk_size)):
                self.write_frames(frames_array[inx:inx+self.chunk_size])
        except IOError as err:
            self.raise_IOError(err)

    def write_frames(self, frames_array):
        """TODO: add documentation"""
        try:
            self.proc.stdin.write(self.audio_array_to_bytes(frames_array))
        except IOError as err:
            self.raise_IOError(err)

    def raise_IOError(self, err):
        _, ffmpeg_error = self.proc.communicate()
        if ffmpeg_error is not None:
            ffmpeg_error = ffmpeg_error.decode()
        else:
            # The error was redirected to a logfile with `write_logfile=True`,
            # so read the error from that file instead
            self.logfile.seek(0)
            ffmpeg_error = self.logfile.read()

        error = (
            f"{err}\n\nMoviePy error: FFMPEG encountered the following error while "
            f"writing file {self.filename}:\n\n {ffmpeg_error}"
        )

        if "Unknown encoder" in ffmpeg_error:
            error += (
                "\n\nThe audio export failed because FFMPEG didn't find the "
                f"specified codec for audio encoding {self.codec}. "
                "Please install this codec or change the codec when calling "
                "write_videofile or write_audiofile.\nFor instance for mp3:\n"
                "   >>> write_videofile('myvid.mp4', audio_codec='libmp3lame')"
            )

        elif "incorrect codec parameters ?" in ffmpeg_error:
            error += (
                "\n\nThe audio export failed, possibly because the "
                f"codec specified for the video {self.codec} is not compatible"
                f" with the given extension {self.ext}. Please specify a "
                "valid 'codec' argument in write_audiofile or 'audio_codoc'"
                "argument in write_videofile. This would be "
                "'libmp3lame' for mp3, 'libvorbis' for ogg..."
            )

        elif "bitrate not specified" in ffmpeg_error:
            error += (
                "\n\nThe audio export failed, possibly because the "
                "bitrate you specified was too high or too low for "
                "the audio codec."
            )

        elif "Invalid encoder type" in ffmpeg_error:
            error += (
                "\n\nThe audio export failed because the codec "
                "or file extension you provided is not suitable for audio"
            )

        raise IOError(error)

    def close(self):
        """Closes the writer, terminating the subprocess if is still alive."""
        if hasattr(self, "proc") and self.proc:
            self.proc.stdin.close()
            self.proc.stdin = None
            if self.proc.stderr is not None:
                self.proc.stderr.close()
                self.proc.stderr = None
            # If this causes deadlocks, consider terminating instead.
            self.proc.wait()
            self.proc = None

    def __del__(self):
        # If the garbage collector comes, make sure the subprocess is terminated.
        self.close()

    # Support the Context Manager protocol, to ensure that resources are cleaned up.

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

class FFMPEG_VideoWriter:

    def __init__(
        self,
        filename,
        size,
        fps,
        codec="libx264",
        audiofile=None,
        preset="slow",
        bitrate=None,
        with_mask=False,
        logfile=None,
        threads=None,
        ffmpeg_params=None,
        pixel_format=None,
    ):
        if logfile is None:
            logfile = sp.PIPE
        self.logfile = logfile
        self.filename = filename
        self.codec = codec
        self.ext = self.filename.split(".")[-1]
        if not pixel_format:  # pragma: no cover
            pixel_format = "rgba" if with_mask else "rgb24"

        # order is important
        cmd = [
            FFMPEG_BINARY,
            "-y",
            "-loglevel",
            "error" if logfile == sp.PIPE else "info",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-s",
            "%dx%d" % (size[0], size[1]),
            "-pix_fmt",
            pixel_format,
            "-r",
            "%.02f" % fps,
            "-an",
            "-i",
            "-",
        ]
        if audiofile is not None:
            cmd.extend(["-i", audiofile, "-acodec", "aac"])
        cmd.extend(["-vcodec", codec, "-preset", preset])
        if ffmpeg_params is not None:
            cmd.extend(ffmpeg_params)
        if bitrate is not None:
            cmd.extend(["-b", bitrate])

        if threads is not None:
            cmd.extend(["-threads", str(threads)])

        if (codec == "libx264"):
            # cmd.extend(["-crf", "0",])
            if (size[0] % 2 == 0) and (size[1] % 2 == 0):
                cmd.extend(["-pix_fmt", "yuv420p"])

        cmd.extend([filename])

        popen_params = cross_platform_popen_params(
            {"stdout": sp.DEVNULL, "stderr": logfile, "stdin": sp.PIPE}
        )
        self.proc = sp.Popen(cmd, **popen_params)

    def write_frames(self, frames_array):
        try:
            self.proc.stdin.write(frames_array.tobytes())
        except IOError as err:
            self.raise_IOError(err)

    def write_frames_chunk(self, frames_array):
        try:
            for frame in tqdm(frames_array):
                self.write_frame(frame)
        except IOError as err:
            self.raise_IOError(err)

    def write_frame(self, img_array):
        """Writes one frame in the file."""
        try:
            self.proc.stdin.write(img_array.tobytes())
        except IOError as err:
            self.raise_IOError(err)

    def raise_IOError(self, err):
        _, ffmpeg_error = self.proc.communicate()
        if ffmpeg_error is not None:
            ffmpeg_error = ffmpeg_error.decode()
        else:
            # The error was redirected to a logfile with `write_logfile=True`,
            # so read the error from that file instead
            self.logfile.seek(0)
            ffmpeg_error = self.logfile.read()

        error = (
            f"{err}\n\nMoviePy error: FFMPEG encountered the following error while "
            f"writing file {self.filename}:\n\n {ffmpeg_error}"
        )

        if "Unknown encoder" in ffmpeg_error:
            error += (
                "\n\nThe video export failed because FFMPEG didn't find the "
                f"specified codec for video encoding {self.codec}. "
                "Please install this codec or change the codec when calling "
                "write_videofile.\nFor instance:\n"
                "  >>> clip.write_videofile('myvid.webm', codec='libvpx')"
            )

        elif "incorrect codec parameters ?" in ffmpeg_error:
            error += (
                "\n\nThe video export failed, possibly because the codec "
                f"specified for the video {self.codec} is not compatible with "
                f"the given extension {self.ext}.\n"
                "Please specify a valid 'codec' argument in write_videofile.\n"
                "This would be 'libx264' or 'mpeg4' for mp4, "
                "'libtheora' for ogv, 'libvpx for webm.\n"
                "Another possible reason is that the audio codec was not "
                "compatible with the video codec. For instance, the video "
                "extensions 'ogv' and 'webm' only allow 'libvorbis' (default) as a"
                "video codec."
            )

        elif "bitrate not specified" in ffmpeg_error:
            error += (
                "\n\nThe video export failed, possibly because the bitrate "
                "specified was too high or too low for the video codec."
            )

        elif "Invalid encoder type" in ffmpeg_error:
            error += (
                "\n\nThe video export failed because the codec "
                "or file extension you provided is not suitable for video"
            )

        raise IOError(error)

    def close(self):
        """Closes the writer, terminating the subprocess if is still alive."""
        if self.proc:
            self.proc.stdin.close()
            if self.proc.stderr is not None:
                self.proc.stderr.close()
            self.proc.wait()

            self.proc = None

    # Support the Context Manager protocol, to ensure that resources are cleaned up.

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

if __name__ == "__main__":
    test_video = "/Users/kwonmingi/Codes/macocr/test_vid/vid12_xoobAzitHzs.mp4"
    from easy_video import EasyReader

    er = EasyReader(test_video, load_audio=True)
    vw = FFMPEG_VideoWriter("test.mp4", er.size, er.video_fps)
    vw.write_frames(er.get_frames(100))

    aw = FFMPEG_AudioWriter("test.wav", er.audio_fps, er.audio_nbytes, er.audio_nchannels)
    aw.write_frames(er.get_audio_array())

