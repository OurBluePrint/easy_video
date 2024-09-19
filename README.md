## Installation

```
git clone [this repo]
pip install -e .
```

## Usage

### read only video
```
from easy_video import EasyReader, EasyWriter
reader = EasyReader('input.mp4', load_video=True, load_audio=False)

# iterator
for video_array in reader.video_array_chunk_iterator(chunksize=128):
    print(video_array.shape) # (128, 1080, 1920, 3)

# clipping
video_array = reader.get_video_array(start=0, end=128)
print(video_array.shape) # (128, 1080, 1920, 3)

# clipping and random frame
video_array, random_frame = reader.get_video_array_random_frame(start=0, end=128)
print(video_array.shape) # (128, 1080, 1920, 3)
print(random_frame.shape) # (1, 1080, 1920, 3)
```

### read video and audio together
```
from easy_video import EasyReader, EasyWriter
reader = EasyReader('input.mp4', load_video=True, load_audio=True, audio_fps=16000, audio_nchannels=1) # 16kHz & mono

# iterator
for video_array, audio_array in reader.video_array_audio_array_chunk_iterator(chunksize=128):
    print(video_array.shape) # (128, 1080, 1920, 3)
    print(audio_array.shape) # (16000 * 128/video_fps, 1)

# clipping
video_array, audio_array = reader.get_video_array_audio_array(start=0, end=128)

# clipping and random frame
video_array, audio_array, random_frame = reader.get_video_array_audio_array_random_frame(start=0, end=128)
print(video_array.shape) # (128, 1080, 1920, 3)
print(audio_array.shape) # (16000 * 128/video_fps, 1)
print(random_frame.shape) # (1, 1080, 1920, 3)
```

### read only audio
```
from easy_video import EasyReader, EasyWriter
reader = EasyReader('input.mp4', load_video=False, load_audio=True, audio_fps=16000, audio_nchannels=1) # 16kHz & mono
audio_array = reader.get_audio_array()
print(audio_array.shape) # (16000 * audio_duration, 1)
```

### Usful information
```
reader.video_fps
reader.duration
reader.n_frames

reader.audio_fps
reader.audio_duration
reader.audio_n_frames
```

### write video
```
from easy_video import EasyReader, EasyWriter
EasyWriter.writefile(filename, video_array=video_array, video_fps=30)
EasyWriter.writefile(filename, video_array=video_array, get_info_from=any_videofilename)

EasyWriter.writefile(filename, audio_array=audio_array, audio_fps=16000, audio_nchannels=1)
EasyWriter.writefile(filename, audio_array=audio_array, get_info_from=any_video_or_audio_filename)

EasyWriter.writefile(filename, video_array=video_array, audio_array=audio_array, video_fps=30, audio_fps=16000, audio_nchannels=1)
EasyWriter.writefile(filename, video_array=video_array, audio_array=audio_array, get_info_from=any_videofilename)

EasyWriter.combine_video_audio(video_file, audio_file, output_file) # if output_file is None, it will be the same as video_file

EasyWriter.extract_audio(video_file, output_file) # if output_file is None, it will be the same as video_file_name + '.wav'

```