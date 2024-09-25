from easy_video import EasyReader, EasyWriter

## read only video
# iterator
reader = EasyReader('test_video.mp4', load_video=True, load_audio=False)
for video_array in reader.video_array_chunk_iterator(chunksize=17):
    print(video_array.shape) # (17, 1080, 1920, 3)
del reader

# clipping
reader = EasyReader('test_video.mp4', load_video=True, load_audio=False)
video_array = reader.get_video_array(start=0, end=128)
print(video_array.shape) # (75, 1080, 1920, 3)
del reader

# clipping and random frame
reader = EasyReader('test_video.mp4', load_video=True, load_audio=False)
video_array, random_frame = reader.get_video_array_random_frame(start=0, end=128)
print(video_array.shape) # (75, 1080, 1920, 3)
print(random_frame.shape) # (1, 1080, 1920, 3)
del reader


## read video and audio together
# iterator
reader = EasyReader('test_video.mp4', load_video=True, load_audio=True, audio_fps=16000, audio_nchannels=1) # 16kHz & mono
for video_array, audio_array in reader.video_array_audio_array_chunk_iterator(chunksize=15):
    print(video_array.shape) # (15, 1080, 1920, 3)
    print(audio_array.shape) # (7995,1)
del reader

# clipping
reader = EasyReader('test_video.mp4', load_video=True, load_audio=True, audio_fps=16000, audio_nchannels=1) # 16kHz & mono
video_array, audio_array = reader.get_video_array_audio_array(start=0, end=70)
print(video_array.shape) # (70, 1080, 1920, 3)
print(audio_array.shape) # (37361,1)
del reader

# clipping and random frame
reader = EasyReader('test_video.mp4', load_video=True, load_audio=True, audio_fps=16000, audio_nchannels=1) # 16kHz & mono
video_array, audio_array, random_frame = reader.get_video_array_audio_array_random_frame(start=0, end=128)
print(video_array.shape) # (75, 1080, 1920, 3)
print(audio_array.shape) # (40867, 1)
print(random_frame.shape) # (1, 1080, 1920, 3)
del reader

## read only audio
reader = EasyReader('test_video.mp4', load_video=False, load_audio=True, audio_fps=16000, audio_nchannels=1) # 16kHz & mono
audio_array = reader.get_audio_array()
print(audio_array.shape) # (40867, 1)
del reader

## write video
reader = EasyReader('test_video.mp4', load_video=True, load_audio=True, audio_fps=16000, audio_nchannels=1) # 16kHz & mono
video_array, audio_array = reader.get_video_array_audio_array(start=0, end=-1)
del reader
EasyWriter.writefile("test_only_video.mp4", video_array=video_array, get_info_from='test_video.mp4')
EasyWriter.writefile("test_only_audio.wav", audio_array=audio_array, get_info_from='test_video.mp4', audio_fps=16000, audio_nchannels=1)

EasyWriter.combine_video_audio("test_only_video.mp4", "test_only_audio.wav", "test_video_combine.mp4")
EasyWriter.extract_audio("test_video_combine.mp4", "test_audio_extract.wav")
