import os
import subprocess as sp

OS_NAME = os.name
IS_POSIX_OS = os.name == "posix"

def cross_platform_popen_params(popen_params):
    """Wrap with this function a dictionary of ``subprocess.Popen`` kwargs and
    will be ready to work without unexpected behaviours in any platform.
    Currently, the implementation will add to them:

    - ``creationflags=0x08000000``: no extra unwanted window opens on Windows
      when the child process is created. Only added on Windows.
    """
    if OS_NAME == "nt":
        popen_params["creationflags"] = 0x08000000
    return popen_params

def try_cmd(cmd):
    """TODO: add documentation"""
    try:
        popen_params = cross_platform_popen_params(
            {"stdout": sp.PIPE, "stderr": sp.PIPE, "stdin": sp.DEVNULL}
        )
        proc = sp.Popen(cmd, **popen_params)
        proc.communicate()
    except Exception as err:
        return False, err
    else:
        return True, None
    

FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg-imageio")
if FFMPEG_BINARY == "ffmpeg-imageio":
    from imageio.plugins.ffmpeg import get_exe

    FFMPEG_BINARY = get_exe()
elif FFMPEG_BINARY == "auto-detect":
    if try_cmd(["ffmpeg"])[0]:
        FFMPEG_BINARY = "ffmpeg"
    elif not IS_POSIX_OS and try_cmd(["ffmpeg.exe"])[0]:
        FFMPEG_BINARY = "ffmpeg.exe"
    else:  # pragma: no cover
        FFMPEG_BINARY = "unset"
else:
    success, err = try_cmd([FFMPEG_BINARY])
    if not success:
        raise IOError(
            f"{err} - The path specified for the ffmpeg binary might be wrong"
        )