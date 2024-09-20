from .ffmpeg_reader import FFMPEGReader
import psutil
import numpy as np
import random

class EasyReader(FFMPEGReader):
    """
    # Example Video - 128 frames per chunk
    er = EasyReader("filename.mp4", load_video=True, load_audio=False)
    for video_chunk in er.video_array_chunk_iterator(chunksize=128):
        print(video_chunk.shape)
    
    # Example Audio - 16kHz, 1 channel
    er = EasyReader("filename.mp4", load_video=False, load_audio=True, audio_fps=16000, audio_nchannels=1)
    audio_array = er.get_audio_array()
    """
    def __init__(
            self,
            filename,
            load_video=True,
            load_audio=False,
            decode_file=True,
            print_infos=False,
            bufsize=None,
            pixel_format="rgb24",
            check_duration=True,
            target_resolution=None,
            resize_algo="bicubic",
            fps_source="fps",
            ram_memory_max_usage=0.5,
            audio_fps=None,
            audio_nbytes=2,
            audio_nchannels=2,
        ):
        super().__init__(
            filename,
            decode_file=decode_file,
            print_infos=print_infos,
            bufsize=bufsize,
            pixel_format=pixel_format,
            check_duration=check_duration,
            target_resolution=target_resolution,
            resize_algo=resize_algo,
            fps_source=fps_source,
            audio_fps=audio_fps,
            audio_nbytes=audio_nbytes,
            audio_nchannels=audio_nchannels,
        )
        self.load_video = load_video
        self.load_audio = load_audio
        self.initialize()
    
        # get RAM Memory from the system
        ram_memory_max_system = psutil.virtual_memory().total
        self.ram_memory_max = ram_memory_max_system * ram_memory_max_usage

    def initialize(self):
        if self.load_video:
            assert self.video_found, "Video not found"
            self.video_proc_initialize()
        if self.load_audio:
            assert self.audio_found, "Audio not found"
            self.audio_proc_initialize()
        if self.load_video and self.load_audio:
            video_fps = self.video_fps
            audio_fps = self.audio_fps
            self.per_frame_audio_frames = int(audio_fps // video_fps)
        self.now_frame = 0

    def check_start_end(self, start, end):
        if start >= self.now_frame:
            start = start - self.now_frame
            if end != -1:
                end = end - self.now_frame
            self.now_frame += end - start
        elif start < self.now_frame: # request frame is already passed. Need to reinitialize.
            self.close()
            self.initialize()
        
        if end == -1:
            end = self.n_frames

        return start, end


    def video_array_chunk_iterator(self, chunksize=128, dtype=np.uint8):
        """
        Get video frames from the video process stdout
        return a numpy array of shape (chunksize, h, w, depth), (0~255)
        """
        for i in range(0, self.n_frames, chunksize):
            array = self.get_frames(chunksize)
            array = array.astype(dtype)
            yield array

    def video_array_audio_array_chunk_iterator(self, chunksize=128, dtype=np.uint8):
        """
        Get video frames from the video process stdout
        return a numpy array of shape (chunksize, h, w, depth), (0~255), and audio array (audio_fps/video_fps) * chunksize, n_channels, (-1~1)
        """
        for i in range(0, self.n_frames, chunksize):
            video_array = self.get_frames(chunksize)
            audio_array = self.get_audios(self.audio_n_frames_by_video_n_frames(chunksize))
            yield video_array, audio_array

    def get_video_array_random_frame(self, start=0, end=-1):
        start, end = self.check_start_end(start, end)

        random_index = random.randint(0, self.n_frames-1)
        if random_index < start:
            self.throw_away_video_frames(random_index)
            random_frame = self.get_frames(1)
            self.throw_away_video_frames(start-random_index-1)
            video_array = self.get_frames(end-start)
            return video_array, random_frame
        elif random_index >= start and random_index < end:
            self.throw_away_video_frames(start)
            video_array = self.get_frames(end-start)
            random_frame = video_array[random_index-start:random_index-start+1]
            return video_array, random_frame
        else:
            self.throw_away_video_frames(start)
            video_array = self.get_frames(end-start)
            self.throw_away_video_frames(random_index-end)
            random_frame = self.get_frames(1)
            return video_array, random_frame

    def get_video_array_audio_array_random_frame(self, start=0, end=-1):
        start, end = self.check_start_end(start, end)

        random_index = random.randint(0, self.n_frames-1)
        if random_index < start:
            self.throw_away_video_frames(random_index)
            random_frame = self.get_frames(1)
            self.throw_away_video_frames(start-random_index-1)
            video_array = self.get_frames(end-start)
            
        elif random_index >= start and random_index < end:
            self.throw_away_video_frames(start)
            video_array = self.get_frames(end-start)
            random_frame = video_array[random_index-start:random_index-start+1]

        else:
            self.throw_away_video_frames(start)
            video_array = self.get_frames(end-start)
            self.throw_away_video_frames(random_index-end)
            random_frame = self.get_frames(1)

        audio_n_frames = self.audio_n_frames_by_video_n_frames(end-start)
        audio_array = self.get_audios(audio_n_frames)
        return video_array, audio_array, random_frame

    def get_video_array(self, start=0, end=-1):
        """
        Get all video frames from the video process stdout
        return a numpy array of shape (n_frames, h, w, depth), (0~255)
        """
        start, end = self.check_start_end(start, end)
        
        n_frames = end - start
        self.throw_away_video_frames(start)
        return self.get_frames(n_frames)
        
    def get_video_array_audio_array(self, start=0, end=-1):
        """
        Get all video frames from the video process stdout
        return a numpy array of shape (n_frames, h, w, depth), (0~255)
        """
        start, end = self.check_start_end(start, end)
        
        n_frames = end - start
        self.throw_away_video_frames(start)
        self.throw_away_audio_per_frames(start)
        audio_n_frames = self.audio_n_frames_by_video_n_frames(n_frames)
        return self.get_frames(n_frames), self.get_audios(audio_n_frames)

    def get_audio_array(self, is_raw_audio=False):
        """
        Get all audio frames from the audio process stdout
        return a numpy array of shape (n_frames, n_channels), (-1~1)
        """
        max_audio_n_frames = (round(self.audio_duration) + 1) * self.audio_fps
        return self.get_audios(max_audio_n_frames, is_raw_audio=is_raw_audio)

    def audio_n_frames_by_video_n_frames(self, n_frames):
        """Get audio n_frames by video n_frames"""
        exact_min = int(n_frames // self.video_fps)
        frames_sec = int(n_frames % self.video_fps)
        audio_n_frames = exact_min * self.audio_fps + frames_sec * self.per_frame_audio_frames
        return audio_n_frames

    def throw_away_audio_per_frames(self, n_frames):
        """Throw away n_frames of data from a process stdout"""
        audio_n_frames = self.audio_n_frames_by_video_n_frames(n_frames)
        self.throw_away_chunks(self.audio_proc, audio_n_frames * self.audio_nchannels * self.audio_nbytes)

    def throw_away_video_frames(self, n_frames):
        """Throw away n_frames of data from a process stdout"""
        self.throw_away_chunks(self.video_proc, n_frames * self.frame_bytesize)

    def throw_away_chunks(self, proc, nbytes):
        """Throw away nbytes of data from a process stdout"""
        while True:
            if nbytes == 0:
                break
            if nbytes <= self.ram_memory_max:
                throwaway = proc.stdout.read(nbytes)
                proc.stdout.flush()
                break
            else:
                throwaway = proc.stdout.read(self.ram_memory_max)
                nbytes -= self.ram_memory_max

    def get_frames(self, n_frames):
        """
        Get n_frames from the video process stdout
        return a numpy array of shape (n_frames, h, w, depth), (0~255)
        """
        if self.video_proc is None:
            raise Exception("Video not loaded")
        
        read_nbytes = n_frames * self.w * self.h * self.depth
        s = self.video_proc.stdout.read(read_nbytes)
        result = np.frombuffer(s, dtype="uint8") # need python3
        result.shape = (len(s)//self.frame_bytesize,self.h,self.w,self.depth)
        return result
    
    def get_audios(self, audio_n_frames, is_raw_audio=False):
        """
        Get n_frames from the audio process stdout
        return a numpy array of shape (n_frames, n_channels), (0~255)
        """
        if self.audio_proc is None:
            raise Exception("Audio not loaded")
        
        read_nbytes = audio_n_frames * self.audio_nchannels * self.audio_nbytes

        s = self.audio_proc.stdout.read(read_nbytes)

        result = np.frombuffer(s, dtype=self.audio_data_type) # need python3
        if is_raw_audio:
            return result
        
        result = (1.0 * result / 2 ** (8 * self.audio_nbytes - 1)).reshape(
            (int(len(result) / self.audio_nchannels), self.audio_nchannels)
        )
        return result

if __name__ == '__main__':
    er = EasyReader("/Users/kwonmingi/Codes/macocr/test_vid/vid12_xoobAzitHzs.mp4",
                    load_video=True,
                    load_audio=True,
                    audio_fps=16000,
                    audio_nchannels=1,
                    )
    import pdb; pdb.set_trace()
    er.audio_fps
    tmp = er.get_video_array()
    tmp_audio = er.get_audio_array()
    
    print("done")