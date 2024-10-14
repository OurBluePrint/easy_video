from .ffmpeg_writer import FFMPEG_VideoWriter, FFMPEG_AudioWriter
from .ffmpeg_infos import ffmpeg_parse_infos
from .video_reader import EasyReader
import os
import subprocess
import numpy as np

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
            start_time=None,
            end_time=None,
    ):
        if get_info_from is not None:
            infos = ffmpeg_parse_infos(get_info_from)
            if infos['video_found']:
                if video_fps is None:
                    video_fps = infos['video_fps']
                if video_size is None:
                    video_size = infos['video_size']

            if infos['audio_found']:
                if audio_fps is None:
                    audio_fps = infos['audio_fps']

        if type(video_array) != type(None):
            assert video_fps is not None

        if type(audio_array) != type(None):
            assert audio_fps is not None

        # Determine if start_time and end_time are provided
        if start_time is None and end_time is None:
            # Process the entire video/audio
            multiple_segments = False
        elif isinstance(start_time, list) and isinstance(end_time, list):
            if len(start_time) != len(end_time):
                raise ValueError("start_time and end_time lists must have the same length.")
            multiple_segments = True
        elif isinstance(start_time, (int, float)) and isinstance(end_time, (int, float)):
            if end_time <= start_time:
                raise ValueError(f"Error: end_time ({end_time}) must be later than start_time ({start_time}).")
            # Convert a single value to a list
            start_time = [start_time]
            end_time = [end_time]
            multiple_segments = True
        else:
            raise ValueError("start_time and end_time should both be lists of the same length, both None, or both numbers.")

        # Check segment timing validity
        if multiple_segments:
            for idx, (start, end) in enumerate(zip(start_time, end_time)):
                if end <= start:
                    raise ValueError(f"Error at index {idx}: end_time ({end}) must be later than start_time ({start}).")
                if type(video_array) != type(None):
                    video_length = video_array.shape[0] / video_fps
                    if end > video_length:
                        raise ValueError(f"Error at index {idx}: end_time ({end}) exceeds video duration ({video_length}).")
                    if start > video_length:
                        raise ValueError(f"Error at index {idx}: start_time ({start}) exceeds video duration ({video_length}).")
                if type(audio_array) != type(None):
                    audio_length = len(audio_array) / audio_fps
                    if end > audio_length:
                        raise ValueError(f"Error at index {idx}: end_time ({end}) exceeds audio duration ({audio_length}).")
                    if start > audio_length:
                        raise ValueError(f"Error at index {idx}: start_time ({start}) exceeds audio duration ({audio_length}).")

        # Handle video and audio processing based on whether multiple segments(multiple start, stop) are present or not
        if type(video_array) == type(None):  # Audio only
            assert type(audio_array) != type(None)
            if multiple_segments:
                EasyWriter._process_multiple_audio_segments(
                    filename, audio_array, audio_fps, audio_nbytes, audio_nchannels,
                    is_raw_audio, start_time, end_time
                )
            else:
                audio_clip = FFMPEG_AudioWriter(
                    filename,
                    fps_input=audio_fps,
                    nbytes=audio_nbytes,
                    nchannels=audio_nchannels,
                    is_raw_audio=is_raw_audio,
                )
                print("\033[92m Writing audio... \033[0m")
                audio_clip.write_frames_chunk(audio_array)
                print(f"\033[92m Done...!! Saved at {filename}\033[0m")
                audio_clip.close()

        elif type(audio_array) == type(None):  # Video only
            if multiple_segments:
                EasyWriter._process_multiple_video_segments(
                    filename, video_array, video_fps, video_size,
                    start_time, end_time
                )
            else:
                video_clip = FFMPEG_VideoWriter(
                    filename,
                    size=video_size,
                    fps=video_fps,
                )
                print("\033[92m Writing video... \033[0m")
                video_clip.write_frames_chunk(video_array)
                print(f"\033[92m Done...!! Saved at {filename}\033[0m")
                video_clip.close()

        else:  # Video and audio
            file_dir = os.path.dirname(filename)
            file_name = os.path.basename(filename).split(".")[0]

            del_audio_tmp = True
            # When audio_array is a **file path**
            if isinstance(audio_array, str):   
                if audio_array.split(".")[-1] == "mp4":
                    audio_tmp = os.path.join(file_dir, f"{TEMP_PREFIX_RANDOMCHARS}{file_name}.wav")
                    EasyWriter.extract_audio(audio_array, audio_tmp)
                elif audio_array.split(".")[-1] == "wav":
                    audio_tmp = audio_array
                    del_audio_tmp = False
                else:
                    raise Exception("Only mp4 or wav file is allowed for audio_array as string.")

                # Extract audio segments corresponding to the video segments
                if multiple_segments:
                    temp_audio_files = EasyWriter._extract_audio_segments(
                        audio_tmp, audio_fps, start_time, end_time
                    )
                    # Process video segments with corresponding audio segments
                    EasyWriter._process_multiple_video_segments_with_audio(
                        filename, video_array, video_fps, video_size, temp_audio_files,
                        start_time, end_time
                    )
                    # Clean up temporary audio files
                    if del_audio_tmp:
                        os.remove(audio_tmp)

                else:   # process entire video
                    video_clip = FFMPEG_VideoWriter(
                        filename,
                        size=video_size,
                        fps=video_fps,
                        audiofile=audio_tmp,
                    )
                    print("\033[92m Writing video with audio... \033[0m")
                    video_clip.write_frames_chunk(video_array)
                    print(f"\033[92m Done! Saved at {filename}\033[0m")
                    video_clip.close()

                    if del_audio_tmp:
                        os.remove(audio_tmp)

             # When audio_array is an **array**
            else:       
                if multiple_segments:
                    # Process audio segments individually
                    temp_audio_files = EasyWriter._process_multiple_audio_segments_individual(
                        audio_array, audio_fps, audio_nbytes, audio_nchannels,
                        is_raw_audio, start_time, end_time
                    )
                    # Process video segments with corresponding audio segments
                    EasyWriter._process_multiple_video_segments_with_audio(
                        filename, video_array, video_fps, video_size, temp_audio_files,
                        start_time, end_time
                    )
                else: # process entire video
                    audio_tmp = os.path.join(file_dir, f"{TEMP_PREFIX_RANDOMCHARS}{file_name}.wav")
                    audio_clip = FFMPEG_AudioWriter(
                        audio_tmp,
                        fps_input=audio_fps,
                        nbytes=audio_nbytes,
                        nchannels=audio_nchannels,
                        is_raw_audio=is_raw_audio,
                    )
                    print("\033[92m Writing audio... \033[0m")
                    audio_clip.write_frames_chunk(audio_array)
                    audio_clip.close()

                    video_clip = FFMPEG_VideoWriter(
                        filename,
                        size=video_size,
                        fps=video_fps,
                        audiofile=audio_tmp,
                    )
                    print("\033[92m Writing video with audio... \033[0m")
                    video_clip.write_frames_chunk(video_array)
                    print(f"\033[92m Done! Saved at {filename}\033[0m")
                    video_clip.close()

                    os.remove(audio_tmp)

    # Helper methods to handle audio and video segments
    @staticmethod
    def _process_multiple_audio_segments(filename, audio_array, audio_fps,
                                         audio_nbytes, audio_nchannels, is_raw_audio,
                                         start_times, end_times):
        temp_audio_files = []
        for idx, (start, end) in enumerate(zip(start_times, end_times)):
            temp_filename = f"temp_audio_{idx}.wav"
            start_idx = int(start * audio_fps)
            end_idx = int(end * audio_fps)
            audio_segment = audio_array[start_idx:end_idx]

            audio_clip = FFMPEG_AudioWriter(
                temp_filename,
                fps_input=audio_fps,
                nbytes=audio_nbytes,
                nchannels=audio_nchannels,
                is_raw_audio=is_raw_audio,
            )
            print(f"\033[92m Writing audio segment {idx} from {start}s to {end}s... \033[0m")
            audio_clip.write_frames_chunk(audio_segment)
            audio_clip.close()
            temp_audio_files.append(temp_filename)

        # Combine audio segments
        combined_audio_array = []
        for temp_file in temp_audio_files:
            temp_reader = EasyReader(temp_file, load_audio=True)
            temp_audio_array = temp_reader.get_audio_array()
            combined_audio_array.append(temp_audio_array)
            temp_reader.close()
            os.remove(temp_file)

        combined_audio_array = np.concatenate(combined_audio_array, axis=0)

        # Write combined audio to final file
        audio_clip = FFMPEG_AudioWriter(
            filename,
            fps_input=audio_fps,
            nbytes=audio_nbytes,
            nchannels=audio_nchannels,
            is_raw_audio=is_raw_audio,
        )
        print("\033[92m Writing combined audio... \033[0m")
        audio_clip.write_frames_chunk(combined_audio_array)
        print(f"\033[92m Done! Saved at {filename}\033[0m")
        audio_clip.close()

    @staticmethod
    def _process_multiple_video_segments(filename, video_array, video_fps, video_size,
                                         start_times, end_times):
        temp_video_files = []
        for idx, (start, end) in enumerate(zip(start_times, end_times)):
            temp_filename = f"temp_video_{idx}.mp4"
            start_frame = int(start * video_fps)
            end_frame = int(end * video_fps)
            video_segment = video_array[start_frame:end_frame]

            video_clip = FFMPEG_VideoWriter(
                temp_filename,
                size=video_size,
                fps=video_fps,
            )
            print(f"\033[92m Writing video segment {idx} from {start}s to {end}s... \033[0m")
            video_clip.write_frames_chunk(video_segment)
            video_clip.close()
            temp_video_files.append(temp_filename)

        # Combine video segments
        combined_video_array = []
        for temp_file in temp_video_files:
            temp_reader = EasyReader(temp_file, load_video=True)
            temp_video_array = temp_reader.get_video_array()
            combined_video_array.append(temp_video_array)
            temp_reader.close()
            os.remove(temp_file)

        combined_video_array = np.concatenate(combined_video_array, axis=0)

        # Write combined video to final file
        video_clip = FFMPEG_VideoWriter(
            filename,
            size=video_size,
            fps=video_fps,
        )
        print("\033[92m Writing combined video... \033[0m")
        video_clip.write_frames_chunk(combined_video_array)
        print(f"\033[92m Done! Saved at {filename}\033[0m")
        video_clip.close()

    @staticmethod
    def _process_multiple_audio_segments_individual(audio_array, audio_fps,
                                                    audio_nbytes, audio_nchannels, is_raw_audio,
                                                    start_times, end_times):
        temp_audio_files = []
        for idx, (start, end) in enumerate(zip(start_times, end_times)):
            temp_filename = f"temp_audio_{idx}.wav"
            start_idx = int(start * audio_fps)
            end_idx = int(end * audio_fps)
            audio_segment = audio_array[start_idx:end_idx]

            audio_clip = FFMPEG_AudioWriter(
                temp_filename,
                fps_input=audio_fps,
                nbytes=audio_nbytes,
                nchannels=audio_nchannels,
                is_raw_audio=is_raw_audio,
            )
            print(f"\033[92m Writing audio segment {idx} from {start}s to {end}s... \033[0m")
            audio_clip.write_frames_chunk(audio_segment)
            audio_clip.close()
            temp_audio_files.append(temp_filename)
        return temp_audio_files

    @staticmethod
    def _extract_audio_segments(audio_file, start_times, end_times):
        temp_audio_files = []
        for idx, (start, end) in enumerate(zip(start_times, end_times)):
            temp_audio_file = f"temp_audio_{idx}.wav"
            duration = end - start
            command = [
                'ffmpeg', '-y',
                '-i', audio_file,
                '-ss', str(start),
                '-t', str(duration),
                '-acodec', 'copy',
                temp_audio_file
            ]
            subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            temp_audio_files.append(temp_audio_file)
        return temp_audio_files

    @staticmethod
    def _process_multiple_video_segments_with_audio(filename, video_array, video_fps, video_size,
                                                    audio_files, start_times, end_times):
        temp_video_files = []
        for idx, (start, end, audio_file) in enumerate(zip(start_times, end_times, audio_files)):
            temp_filename = f"temp_video_{idx}.mp4"
            start_frame = int(start * video_fps)
            end_frame = int(end * video_fps)
            video_segment = video_array[start_frame:end_frame]

            video_clip = FFMPEG_VideoWriter(
                temp_filename,
                size=video_size,
                fps=video_fps,
                audiofile=audio_file,
            )
            print(f"\033[92m Writing video segment {idx} with audio from {start}s to {end}s... \033[0m")
            video_clip.write_frames_chunk(video_segment)
            video_clip.close()
            temp_video_files.append(temp_filename)
            os.remove(audio_file)

        # Combine video segments
        combined_video_array = []
        for temp_file in temp_video_files:
            temp_reader = EasyReader(temp_file, load_video=True)
            temp_video_array = temp_reader.get_video_array()
            combined_video_array.append(temp_video_array)
            temp_reader.close()
            os.remove(temp_file)

        combined_video_array = np.concatenate(combined_video_array, axis=0)

        # Write combined video to final file
        video_clip = FFMPEG_VideoWriter(
            filename,
            size=video_size,
            fps=video_fps,
        )
        print("\033[92m Writing combined video... \033[0m")
        video_clip.write_frames_chunk(combined_video_array)
        print(f"\033[92m Done! Saved at {filename}\033[0m")
        video_clip.close()

    @staticmethod
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

    @staticmethod
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
    from video_reader import EasyReader

    er = EasyReader(test_video, load_video=True, load_audio=True)

    video_array = er.get_video_array()
    audio_array = er.get_audio_array()

    EasyWriter.writefile("test_1.mp4", video_array=video_array, get_info_from=test_video)
    EasyWriter.writefile("test.wav", audio_array=audio_array, get_info_from=test_video)
    EasyWriter.writefile("test.mp4", video_array=video_array, audio_array=audio_array, get_info_from=test_video)

    EasyWriter.combine_video_audio("test_1.mp4", "test.wav", "test_2.mp4")
    EasyWriter.extract_audio("test.mp4", "test_1.wav")


    # Another Examples (Cutting video or audio files based on start, end time)
    start_times = [2.5, 20.75, 120.1]  # start time (sec)
    end_times = [5.0, 40.5, 130.4]    # End time (sec)
    # start_times = 5  end_times= 8 is possible (Only one time doesn’t need to be in a list)
    er.close()


    # Test 1: Process video and audio together (multiple segments)
    print("=== Test 1: Process video and audio together (multiple segments) ===")
    EasyWriter.writefile(
        filename="output_video_audio_segments.mp4",
        video_array=video_array,
        audio_array=audio_array,
        get_info_from=test_video,
        start_time=start_times,
        end_time=end_times
    )

    # Test 2: Process video only (multiple segments)
    print("=== Test 2: Process video only (multiple segments) ===")
    EasyWriter.writefile(
        filename="output_video_segments_video.mp4",
        video_array=video_array,
        get_info_from=test_video,
        start_time=start_times,
        end_time=end_times
    )

    # Test 3: Process audio only (multiple segments)
    print("=== Test 3: Process audio only (multiple segments) ===")
    EasyWriter.writefile(
        filename="output_audio_segments.wav",
        audio_array=audio_array,
        get_info_from=test_video,
        start_time=start_times,
        end_time=end_times
    )

    # Test 4: Process video and audio together (full video)
    print("=== Test 4: Process video and audio together (full video) ===")
    EasyWriter.writefile(
        filename="output_full_video_audio.mp4",
        video_array=video_array,
        audio_array=audio_array,
        get_info_from=test_video
    )

    # Test 5: Process video only (full video)
    print("=== Test 5: Process video only (full video) ===")
    EasyWriter.writefile(
        filename="output_full_video.mp4",
        video_array=video_array,
        get_info_from=test_video
    )

    # Test 6: Process audio only (full audio)
    print("=== Test 6: Process audio only (full audio) ===")
    EasyWriter.writefile(
        filename="output_full_audio.wav",
        audio_array=audio_array,
        get_info_from=test_video
    )