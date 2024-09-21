from .ffmpeg_writer import FFMPEG_VideoWriter, FFMPEG_AudioWriter
from .ffmpeg_infos import ffmpeg_parse_infos

from .video_reader import EasyReader
import os
import subprocess

TEMP_PREFIX_RANDOMCHARS = "EZVQB_NNIEHVPQD_"

class EasyWriter:
    def writefile(
            filename,
            video_array=None,
            audio_array=None,
            get_info_from=None,
            video_fps=None,
            video_size=None,
            audio_fps=None,
            audio_nbytes=2,
            audio_nchannels=2,
            is_raw_audio=False,
    ):

        if get_info_from != None:
            infos = ffmpeg_parse_infos(get_info_from)
            if infos['video_found']:
                if video_fps == None:
                    video_fps = infos['video_fps']
                if video_size == None:
                    video_size = infos['video_size']

            if infos['audio_found']:
                if audio_fps == None:
                    audio_fps = infos['audio_fps']
        
        if type(video_array) != type(None):
            assert video_fps != None

        if type(audio_array) != type(None):
            assert audio_fps != None

        if type(video_array) == type(None): # audio only
            assert type(audio_array) != type(None)

            audio_clip = FFMPEG_AudioWriter(
                filename,
                fps_input=audio_fps,
                nbytes=audio_nbytes,
                nchannels=audio_nchannels,
                is_raw_audio=is_raw_audio,
            )
            print("\033[92m Writing... \033[0m")
            audio_clip.write_frames_chunk(audio_array)
            print(f"\033[92m Done...!! Saved at {filename}\033[0m")
            audio_clip.close()

        elif type(audio_array) == type(None): # video only
            video_clip = FFMPEG_VideoWriter(
                filename,
                size=video_size,
                fps=video_fps,
            )
            print("\033[92m Writing... \033[0m")
            video_clip.write_frames_chunk(video_array)
            print(f"\033[92m Done...!! Saved at {filename}\033[0m")
            video_clip.close()

        else: # video and audio
            # save audio as tmp file and merge it with video.
            # need to remove tmp audio file after merge
            file_dir = os.path.dirname(filename)
            file_name = os.path.basename(filename).split(".")[0]
            
            if type(audio_array) == str:
                audio_tmp = audio_array
            else:
                audio_tmp = os.path.join(file_dir, f"{TEMP_PREFIX_RANDOMCHARS}{file_name}.wav")
                audio_clip = FFMPEG_AudioWriter(
                    audio_tmp,
                    fps_input=audio_fps,
                    nbytes=audio_nbytes,
                    nchannels=audio_nchannels,
                    is_raw_audio=is_raw_audio,
                )
                print("\033[92m Audio Writing... \033[0m")
                audio_clip.write_frames_chunk(audio_array)
                audio_clip.close()

            video_clip = FFMPEG_VideoWriter(
                filename,
                size=video_size,
                fps=video_fps,
                audiofile=audio_tmp,
            )
            print("\033[92m Writing... \033[0m")
            video_clip.write_frames_chunk(video_array)
            print(f"\033[92m Done...!! Saved at {filename}\033[0m")
            video_clip.close()
            
            os.remove(audio_tmp)
 
    def combine_video_audio(video_file, audio_file, output_file=""):
        if output_file == "":
            output_file = video_file
        
        print("\033[92m Writing... \033[0m")
        # ffmpeg 명령어 동작
        command = [
            'ffmpeg', '-y',  # -y는 기존 파일을 덮어쓰기 위한 옵션
            '-i', video_file,  # 비디오 파일 입력
            '-i', audio_file,  # 오디오 파일 입력
            '-c:v', 'copy',  # 비디오 코덱 복사 (재인코딩 없음)
            '-c:a', 'copy',  # 오디오를 aac 코덱으로 인코딩
            output_file  # 출력 파일 경로
        ]

        # 명령어 실행
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            stdout, stderr = process.communicate()
        print(f"\033[92m Done...!! Saved at {output_file}\033[0m")
        
    def extract_audio(video_file, output_file=""):
        if output_file == "":
            output_file = video_file.split(".")[0] + ".wav"

        print("\033[92m Writing... \033[0m")
        # ffmpeg 명령어 동작
        command = [
            'ffmpeg', '-y',  # -y는 기존 파일을 덮어쓰기 위한 옵션
            '-i', video_file,  # 비디오 파일 입력
            '-vn',  # 비디오 스트림 무시
            '-ac', '2',  # 스테레오 오디오
            '-f', 'wav',  # wav 포맷
            output_file  # 출력 파일 경로
        ]

        # 명령어 실행
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            stdout, stderr = process.communicate()
        print(f"\033[92m Done...!! Saved at {output_file}\033[0m")

if __name__ == "__main__":
    test_video = "/Users/kwonmingi/Codes/macocr/test_vid/vid12_xoobAzitHzs.mp4"
    from easy_video import EasyReader

    er = EasyReader(test_video, load_audio=True)

    video_array = er.get_video_array()
    audio_array = er.get_audio_array()

    del er

    EasyWriter.writefile("test_1.mp4", video_array=video_array, get_info_from=test_video)
    EasyWriter.writefile("test.wav", audio_array=audio_array, get_info_from=test_video)
    EasyWriter.writefile("test.mp4", video_array=video_array, audio_array=audio_array, get_info_from=test_video)

    EasyWriter.combine_video_audio("test_1.mp4", "test.wav", "test_2.mp4")
    EasyWriter.extract_audio("test.mp4", "test_1.wav")
