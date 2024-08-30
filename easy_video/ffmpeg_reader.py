import subprocess as sp
from .ffmpeg_infos import ffmpeg_parse_infos, cross_platform_popen_params, FFMPEG_BINARY

class FFMPEGReader:

    def __init__(
            self,
            filename,
            decode_file=True,
            print_infos=False,
            bufsize=None,
            pixel_format="rgb24",
            check_duration=True,
            target_resolution=None,
            resize_algo="bicubic",
            fps_source="fps",
            audio_fps=None,
            audio_nbytes=2,
            audio_nchannels=2,
        ):
        self.filename = filename

        infos = ffmpeg_parse_infos(
            filename,
            check_duration=check_duration,
            fps_source=fps_source,
            decode_file=decode_file,
            print_infos=print_infos,
        )
        self.infos = infos # ['video_found', 'audio_found', 'metadata', 'inputs', 'duration', 'bitrate', 'start', 'default_video_input_number', 'default_video_stream_number', 'video_size', 'video_bitrate', 'video_fps', 'default_audio_input_number', 'default_audio_stream_number', 'audio_fps', 'audio_bitrate', 'video_n_frames', 'video_duration']
        self.ffmpeg_duration = infos["duration"]

        self.video_proc = None
        self.video_found = infos["video_found"]
        if self.video_found:
            self.video_fps = infos["video_fps"]
            self.origin_size = infos["video_size"]
            self.origin_w, self.origin_h = self.origin_size
            
            self.size = self.origin_size
            # ffmpeg automatically rotates videos if rotation information is
            # available, so exchange width and height
            self.rotation = abs(infos.get("video_rotation", 0))
            if self.rotation in [90, 270]:
                self.size = [self.size[1], self.size[0]]
            # if target_resolution is specified, to resize the video, set the size
            if target_resolution:
                if None in target_resolution:
                    ratio = 1
                    for idx, target in enumerate(target_resolution):
                        if target:
                            ratio = target / self.size[idx]
                    self.size = (int(self.size[0] * ratio), int(self.size[1] * ratio))
                else:
                    self.size = target_resolution
            self.w, self.h = self.size

            self.resize_algo = resize_algo

            self.duration = infos["video_duration"]
            self.n_frames = infos["video_n_frames"]
            self.bitrate = infos["video_bitrate"]

            self.pixel_format = pixel_format
            self.depth = 4 if pixel_format[-1] == "a" else 3
            # 'a' represents 'alpha' which means that each pixel has 4 values instead of 3.
            # See https://github.com/Zulko/moviepy/issues/1070#issuecomment-644457274

            self.frame_bytesize = self.w * self.h * self.depth

            if bufsize is None:
                bufsize = self.frame_bytesize + 100

            self.bufsize = bufsize

            self.frame_pos = 0

        self.audio_proc = None
        self.audio_found = infos["audio_found"]

        if self.audio_found:
            self.audio_fps = infos["audio_fps"]
            if audio_fps is not None:
                self.audio_fps = audio_fps # set sample rate
            self.audio_duration = self.ffmpeg_duration # for convenience
            self.audio_nchannels = audio_nchannels
            self.audio_nbytes = audio_nbytes
            self.audio_format = "s%dle" % (8 * self.audio_nbytes)
            self.audio_codec = "pcm_s%dle" % (8 * self.audio_nbytes)

            self.audio_n_frames = int(self.audio_duration * self.audio_fps)
            self.audio_buffersize = self.audio_n_frames+1

            self.audio_data_type = {1: "int8", 2: "int16", 4: "int32"}[self.audio_nbytes]


    def video_proc_initialize(self):
        if self.video_proc is None:
            cmd = (
                [FFMPEG_BINARY]
                + ["-i", self.filename]
                + [
                    "-loglevel",
                    "error",
                    "-f",
                    "image2pipe",
                    "-vf",
                    "scale=%d:%d" % tuple(self.size),
                    "-sws_flags",
                    self.resize_algo,
                    "-pix_fmt",
                    self.pixel_format,
                    "-vcodec",
                    "rawvideo",
                    "-",
                ]
            )

            popen_params = cross_platform_popen_params(
                {
                    "bufsize": self.bufsize,
                    "stdout": sp.PIPE,
                    "stderr": sp.PIPE,
                    "stdin": sp.DEVNULL,
                }
            )

            self.video_proc = sp.Popen(cmd, **popen_params)

    def audio_proc_initialize(self):
        if self.audio_proc is None:
            cmd = (
                [FFMPEG_BINARY]
                + ["-i", self.filename, "-vn"]
                + [
                    "-loglevel",
                    "error",
                    "-f",
                    self.audio_format,
                    "-acodec",
                    self.audio_codec,
                    "-ar",
                    "%d" % self.audio_fps,
                    "-ac",
                    "%d" % self.audio_nchannels,
                    "-",
                ]
            )

            popen_params = cross_platform_popen_params(
                {
                    "bufsize": self.audio_buffersize,
                    "stdout": sp.PIPE,
                    "stderr": sp.PIPE,
                    "stdin": sp.DEVNULL,
                }
            )

            self.audio_proc = sp.Popen(cmd, **popen_params)

    def close(self):
        """Closes the reader terminating the process, if is still open."""
        if self.video_proc:
            if self.video_proc.poll() is None:
                self.video_proc.terminate()
                self.video_proc.stdout.close()
                self.video_proc.stderr.close()
                self.video_proc.wait()
            self.video_proc = None

        if self.audio_proc:
            if self.audio_proc.poll() is None:
                self.audio_proc.terminate()
                self.audio_proc.stdout.close()
                self.audio_proc.stderr.close()
                self.audio_proc.wait()
            self.audio_proc = None

    def __del__(self):
        self.close()



if __name__ == "__main__":
    test_video = "/Users/kwonmingi/Codes/macocr/test_vid/vid12_xoobAzitHzs.mp4"
    # test_video = "/Users/kwonmingi/Codes/macocr/test_vid/vid12_xoobAzitHzs.wav"
    reader = FFMPEGReader(test_video, decode_file=False)
    import pdb; pdb.set_trace()
    reader.close()