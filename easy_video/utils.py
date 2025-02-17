import os
import numpy as np
from natsort import natsorted

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

def convert_to_seconds(time):
    """Will convert any time into seconds.

    If the type of `time` is not valid,
    it's returned as is.

    Here are the accepted formats:

    >>> convert_to_seconds(15.4)   # seconds
    15.4
    >>> convert_to_seconds((1, 21.5))   # (min,sec)
    81.5
    >>> convert_to_seconds((1, 1, 2))   # (hr, min, sec)
    3662
    >>> convert_to_seconds('01:01:33.045')
    3693.045
    >>> convert_to_seconds('01:01:33,5')    # coma works too
    3693.5
    >>> convert_to_seconds('1:33,5')    # only minutes and secs
    99.5
    >>> convert_to_seconds('33.5')      # only secs
    33.5
    """
    factors = (1, 60, 3600)

    if isinstance(time, str):
        time = [float(part.replace(",", ".")) for part in time.split(":")]

    if not isinstance(time, (tuple, list)):
        return time

    return sum(mult * part for mult, part in zip(factors, reversed(time)))


def mp4list(path, pass_hidden_folders=True, sort=False):
    """
    Get all mp4 files in the given path. but not in the .subfolders (hidden folders)
    """
    if path.endswith(".mp4"):
        return [path]
    mp4_files = []
    for root, dirs, files in os.walk(path):
        if pass_hidden_folders and any(part.startswith('.') for part in root.split(os.sep)):
            continue
        for file in files:
            if file.endswith(".mp4"):
                mp4_files.append(os.path.join(root, file))
    if sort:
        mp4_files = natsorted(mp4_files)
    return mp4_files

def wavlist(path, pass_hidden_folders=True):
    """
    Get all mp4 files in the given path. but not in the .subfolders (hidden folders)
    """
    if path.endswith(".wav"):
        return [path]
    mp4_files = []
    for root, dirs, files in os.walk(path):
        if pass_hidden_folders and any(part.startswith('.') for part in root.split(os.sep)):
            continue
        for file in files:
            if file.endswith(".wav"):
                mp4_files.append(os.path.join(root, file))
    return mp4_files


def array_video_to_tensor(video_array, _min=0, _max=1):
    """
    Convert a numpy array to a torch tensor.
    (Frames, Height, Width, Channels) -> (Frames, Channels, Height, Width)
    (0~255) -> (_min~_max)

    input: numpy array
    output: torch tensor
    """

    if not TORCH_AVAILABLE:
        raise ImportError("Torch is not installed. Please install it to use this function: pip install torch")

    if type(video_array) == torch.Tensor:
        return video_array
    video_array = video_array.astype(np.float32)
    video_tensor = torch.from_numpy(video_array)
    video_tensor = video_tensor.permute(0, 3, 1, 2)
    video_tensor = video_tensor / 255.
    video_tensor = video_tensor * (_max - _min) + _min
    video_tensor = video_tensor.clamp(_min, _max)
    return video_tensor

def tensor_video_to_array(video_tensor, _min=0, _max=1):
    """
    Convert a torch tensor to a numpy array.
    (Frames, Channels, Height, Width) -> (Frames, Height, Width, Channels)
    (_min~_max) -> (0~255)

    input: torch tensor
    output: numpy array
    """
    if not TORCH_AVAILABLE:
        raise ImportError("Torch is not installed. Please install it to use this function: pip install torch")

    if type(video_tensor) == np.ndarray:
        return video_tensor
    video_tensor = video_tensor.clamp(_min, _max)
    video_tensor = (video_tensor + _min) / (_max - _min)
    video_tensor = video_tensor.clamp(0, 1)
    video_tensor = video_tensor.cpu()
    video_tensor = video_tensor * 255.
    video_tensor = video_tensor.permute(0, 2, 3, 1)
    video_array = video_tensor.numpy().astype(np.uint8)
    return video_array

def resize_video_tensor(video_tensor, size=(512,512), mode='bilinear', align_corners=False):
    """
    Resize a video tensor.
    (Frames, Channels, Height, Width) -> (Frames, Channels, new_Height, new_Width)

    input: torch tensor, size=(new_Height, new_Width), mode='bilinear', align_corners=False
    output: torch tensor
    """
    if not TORCH_AVAILABLE:
        raise ImportError("Torch is not installed. Please install it to use this function: pip install torch")

    if type(size) == int:
        size = (size, size) # (new_Height, new_Width)

    video_tensor = torch.nn.functional.interpolate(video_tensor, size=size, mode=mode, align_corners=align_corners)
    return video_tensor

def centercrop_resize_video_tensor(video_tensor, size=(512,512), mode='bilinear', align_corners=False):
    """
    Center crop and resize a video tensor.
    (Frames, Channels, Height, Width) -> (Frames, Channels, new_Height, new_Width)

    input: torch tensor, size=(new_Height, new_Width)
    output: torch tensor
    """
    if not TORCH_AVAILABLE:
        raise ImportError("Torch is not installed. Please install it to use this function: pip install torch")

    if type(size) == int:
        size = (size, size) # (new_Height, new_Width)

    h, w = video_tensor.shape[2], video_tensor.shape[3]
    min_shape = min(h, w)
    width_start = (video_tensor.shape[3] - min_shape) // 2
    height_start = (video_tensor.shape[2] - min_shape) // 2
    video_tensor = video_tensor[:, :, height_start:height_start+min_shape, width_start:width_start+min_shape]
    video_tensor = torch.nn.functional.interpolate(video_tensor, size=size, mode=mode, align_corners=align_corners)
    return video_tensor

def resize_video_array(video_array, size=(512,512), mode='bilinear', align_corners=False):
    """
    Resize a video array.
    (Frames, Height, Width, Channels) -> (Frames, new_Height, new_Width, Channels)

    input: numpy array, size=(new_Height, new_Width), mode='bilinear', align_corners=False
    output: numpy array
    """
    if not TORCH_AVAILABLE:
        raise ImportError("Torch is not installed. Please install it to use this function: pip install torch")

    if type(size) == int:
        size = (size, size) # (new_Height, new_Width)

    video_tensor = array_video_to_tensor(video_array)
    video_tensor = resize_video_tensor(video_tensor, size=size, mode=mode, align_corners=align_corners)
    video_array = tensor_video_to_array(video_tensor)
    return video_array

def centercrop_resize_video_array(video_array, size=(512,512), mode='bilinear', align_corners=False):
    """
    Center crop and resize a video array.
    (Frames, Height, Width, Channels) -> (Frames, new_Height, new_Width, Channels)

    input: numpy array, size=(new_Height, new_Width)
    output: numpy array
    """
    if not TORCH_AVAILABLE:
        raise ImportError("Torch is not installed. Please install it to use this function: pip install torch")

    if type(size) == int:
        size = (size, size) # (new_Height, new_Width)

    video_tensor = array_video_to_tensor(video_array)
    video_tensor = centercrop_resize_video_tensor(video_tensor, size=size, mode=mode, align_corners=align_corners)
    video_array = tensor_video_to_array(video_tensor)
    return video_array