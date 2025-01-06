# Easy Video
Why do we need to use this repo?
- Existing video and audio libraries are not easy to use for deep learning research
    - For example, moviepy **drops frames or duplicates frames** when reading video. It is same for audio.
    - The reason is they are not designed for deep learning research. They are designed for video utility. (One frame dropping/duplicating is not important for video utility, but **it is important for deep learning research**)
- Usually, we need to convert video to png or jpg files and audio to wav files. It is not efficient if the dataset is large.

What this repo can do?
- Read and write video and audio
- Memory efficient reading and writing
- Provide easy conversion between numpy array and torch tensor

## Notice
- We only tested on mp4 format.
- We only tested on Linux and MacOS.
- We only tested on Python 3.11

## Installation

```
git clone [this repo]
pip install -e .
```

- ffmpeg is required to read and write video and audio. We don't provide ffmpeg installation guide here. Please refer to [ffmpeg](https://ffmpeg.org/download.html) for installation.
- python >= 3.6 is required
- numpy, psutil, tqdm are required
- torch is required if you want to use utils.py

## Usage

### Update
- 2025.01.06: target video fps, target resolution.

```python
reader = EasyReader(...,
                     target_video_fps=30, # target video fps. If it is None, it will be the same as the original video fps.
                     target_resolution=(256, 256), # target resolution. If it is None, it will be the same as the original resolution.
                     )
```

- 2024.11.10: EasyWriter silent mode.

```python
EasyWriter.writefile(..., silent=True)
```


### read only video
```python
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

- video array is numpy array with shape (n_frames, height, width, n_channels), and 0~255 values.

### read video and audio together
```python
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

- video array is numpy array with shape (n_frames, height, width, n_channels), and 0~255 values.
- audio array is numpy array with shape (audio_n_frames, audio_n_channels), and 0~1 values (normalized).
- Of course, **video and audio are synchronized.** You can change audio sampling rate and number of channels by `audio_fps` and `audio_nchannels` options.

### read only audio
```python
from easy_video import EasyReader, EasyWriter
reader = EasyReader('input.mp4', load_video=False, load_audio=True, audio_fps=16000, audio_nchannels=1) # 16kHz & mono
audio_array = reader.get_audio_array()
print(audio_array.shape) # (16000 * audio_duration, 1)
```
- audio array is numpy array with shape (audio_n_frames, audio_n_channels), and 0~1 values (normalized).
- if you want to get raw audio array, use `is_raw_audio=True` in `get_audio_array` method. (Not normalized)

### Usful information
```
reader.video_fps
reader.duration
reader.n_frames # this is (fps * duration)+1. It is not exact number of frames. Just for reference. Don't believe this value.

reader.audio_fps
reader.audio_duration
reader.audio_n_frames
```

### write video
```python
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

### utils
```python
from easy_video import mp4list, array_video_to_tensor, tensor_video_to_array, resize_video_tensor, centercrop_resize_video_tensor, resize_video_array, centercrop_resize_video_array

mp4_file_list = mp4list('video_folder') # return list of mp4 files in the folder including subfolders

from easy_video import EasyReader, EasyWriter
reader = EasyReader(mp4_file_list[0], load_video=True, load_audio=False)
video_array = reader.get_video_array(start=0, end=-1) # read all frames as numpy array

# convert numpy array to torch tensor (0~1)
video_tensor = array_video_to_tensor(video_array) # (n_frames, n_channels, height, width)

# if you want to convert torch tensor (-1~1), use this
video_tensor = array_video_to_tensor(video_array, _min=-1, _max=1) # (n_frames, n_channels, height, width)

# convert torch tensor to numpy array
video_array = tensor_video_to_array(video_tensor) # (n_frames, height, width, n_channels)

# if the torch tensor is not (0~1), need to specify _min and _max
video_array = tensor_video_to_array(video_tensor, _min=-1, _max=1) # (n_frames, height, width, n_channels)

# resize video tensor
video_tensor = resize_video_tensor(video_tensor, (256, 256)) # (n_frames, n_channels, 256, 256)

# centercrop and resize video tensor: it crops the center of the video with shorter side and resize it to given size
video_tensor = centercrop_resize_video_tensor(video_tensor, (256, 256)) # (n_frames, n_channels, 256, 256) 

# resize video array
video_array = resize_video_array(video_array, (256, 256)) # (n_frames, 256, 256, n_channels)

# centercrop and resize video array: it crops the center of the video with shorter side and resize it to given size
video_array = centercrop_resize_video_array(video_array, (256, 256)) # (n_frames, 256, 256, n_channels)

```

## Acknowledgement
- Some codes are from [moviepy](https://zulko.github.io/moviepy/), but I modified a lot.
