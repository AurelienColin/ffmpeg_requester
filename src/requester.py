import glob
import os

os.environ['DISABLE_RIGNAK_BACKUP'] = "True"

import subprocess
from datetime import datetime

import fire
import pytubefix as pytube
import typing

import ffmpeg_requester.local_config as config
from rignak.src.init import ExistingFilename, assert_argument_types, logger
from rignak.src.textfile_utils import get_lines


class Requester():
    @assert_argument_types
    def __init__(
            self: 'Requester',
            input_filename: str,
            output_filename: str,
            start_datestring: str,
            end_datestring: str
    ) -> None:
        self.input_filename: (None, ExistingFilename) = None
        self.line: (None, str) = None
        self.output_filename: (None, str) = output_filename
        self.duration: str = ""
        self.start: str = ""
        self.command: (None, str) = None
        self.ready: bool = False

        self.video_options: list = [
            '-c:v libsvtav1',
            '-c:s copy',
            '-c:a copy',
            "-map 0:a",
            "-map 0:v:0",
            "-map 0:s?",
            "-force_key_frames 0",
            "-crf 32",
            "-threads 3",
            "-pix_fmt yuv420p10le",
        ]
        self.audio_options: list = [
            '-codec:a libmp3lame',
            '-qscale:a 3'
        ]
        self.options: list = [
            "-v quiet"
        ]
        try:
            self.set_input_file(input_filename)
            self.set_output_file(output_filename)
            self.set_start(start_datestring)
            self.set_duration(start_datestring, end_datestring)
        except AssertionError as e:
            return
        self.ready = True
        if output_filename.startswith('-'):
            self.ready = False

    @assert_argument_types
    def get_input_from_youtube(
            self: 'Requester',
            url: str,
            output_path: str = config.INPUT_FOLDER
    ) -> ExistingFilename:
        logger(f'Download from {url}')
        yt = pytube.YouTube(url)
        input_filename = yt.streams.get_highest_resolution().download(output_path=output_path)
        input_filename = ExistingFilename(input_filename)
        logger('Download OK')
        return input_filename

    @assert_argument_types
    def set_input_file(
            self: 'Requester',
            input_filename: str,
            input_folder: str = config.INPUT_FOLDER
    ) -> None:
        ok = False
        if 'youtube.com' in input_filename:
            try:
                input_filename = self.get_input_from_youtube(input_filename)
                ok = True
            except pytube.exceptions.BotDetection as e:
                print(e)
        if not ok:
            input_filename = os.path.join(input_folder, input_filename)
            message = f"{os.path.basename(input_filename)}: Source not found."
            input_filename = ExistingFilename(input_filename, message=message)

        self.input_filename = input_filename

    @assert_argument_types
    def set_output_file(
            self: 'Requester',
            output_filename: str,
            output_folder: str = config.OUTPUT_FOLDER
    ) -> None:
        self.output_filename = os.path.join(output_folder, output_filename)

            
        if self.output_filename.endswith('.mp3'):
            self.options += self.audio_options

            title = os.path.basename(os.path.splitext(self.output_filename)[0])
            self.options.append(f'-metadata title="{title}"')

        elif self.output_filename.endswith('.mkv'):
            self.add_resize_option()
            self.options += self.video_options

    @assert_argument_types
    def set_duration(
            self: 'Requester',
            start_timestring: str,
            end_timestring: str
    ) -> None:
        if end_timestring == '00:00:00':
            return

        timestrings = {}
        for key, timestring in (('start', start_timestring), ('end', end_timestring)):
            hour = int(timestring[:2])
            minute = int(timestring[3:5])
            second = int(timestring[6:8])
            timestrings[key] = hour * 3600 + minute * 60 + second

        duration = timestrings['end'] - timestrings['start']
        message = f"{os.path.basename(self.output_filename)}: Check duration."
        assert duration > 0, message
        self.duration = f"-t {duration // 3600:02d}:{duration % 3600 // 60:02d}:{duration % 60:02d}"

    @assert_argument_types
    def set_start(
            self: 'Requester',
            start_timestring: str
    ) -> None:
        if start_timestring == '00:00:00':
            return

        self.start = f"-ss {start_timestring}"

    @assert_argument_types
    def add_resize_option(self: 'Requester'):
        command = 'ffprobe -v error -select_streams v:0 -show_entries stream=width,height ' \
                  f'-of csv=s=x:p=0 "{self.input_filename}"'
        if '1080' in subprocess.run(command, stdout=subprocess.PIPE).stdout.decode('utf-8'):
            self.video_options.append("-vf \"scale=trunc(iw/2)*2:720\"")
        else:
            self.video_options.append("-vf \"scale=trunc(iw/2)*2:trunc(ih/2)*2\"")
            

    @assert_argument_types
    def run(self: 'Requester', only_generate_command: bool = False) -> str:
        self.command = f'ffmpeg {self.start} -i "{self.input_filename}" ' \
                       f'{self.duration} {" ".join(self.options)} "{self.output_filename}"'

        if not only_generate_command:
            print(self.command)
            os.system(self.command)

            if not os.path.exists(self.output_filename):
                logger.error(f'No file created: {self.output_filename}')
            elif os.path.getsize(self.output_filename) < 1024:
                logger.error(f'Very small file created: {self.output_filename}')
        return self.command


@assert_argument_types
def backup(commands: list, backup_folder: str = config.BACKUP_FOLDER):
    backup_filename = os.path.join(
        backup_folder,
        datetime.now().strftime('%Y-%m-%d.txt')
    )
    os.makedirs(os.path.dirname(backup_filename), exist_ok=True)
    with open(backup_filename, 'w', encoding='utf-8') as file:
        file.writelines(commands)


def get_exists():  # /!\ This use the basename, so all basename should be different.
    roots = (config.OUTPUT_FOLDER, "D:\\OneDrive/Videos")
    available_filenames = [
        os.path.basename(filename)
        for root in roots
        for filename in glob.glob(root + "/**/*.mkv", recursive=True)
    ]
    logger(f"Found {len(available_filenames)} existing .mkv.")

    def exists(filename):
        short_filename = os.path.basename(filename)
        return short_filename in available_filenames

    return exists

def get_requesters(lines:typing.Sequence[str], return_args:bool=False) -> typing.Union[typing.List[typing.Sequence[str]], typing.List[Requester]]:
    args = []
    exists = get_exists()
    requesters = []

    logger('Initialize the requesters.')
    commands = []
    for line in lines:
        # Example line:
        # $targetfilename	$start	$end	$source_filename
        # A/Aria/Aria S3 09 "Athena & Alice" (2008).mkv	00:16:41	00:22:35	Aria S03E09 Surrounded by That Orange Wind....mkv
        original_line = line
        if line.startswith('#'):
            continue
        elif line.startswith('STOP'):
            break
        
            
        while '\t\t' in line:
            line = line.replace('\t\t', '\t')
        split_line = line.split('\t')
        if len(split_line) != 4:
            if len(split_line) >3:
                logger.warning(f'Check delimiters: {split_line}')
        else:
            output_filename, start_timestring, end_timestring, input_filename = split_line
            output_filename = output_filename.replace("?", "").replace("'", "").replace('"', "'")

            args.append((input_filename, output_filename, start_timestring, end_timestring))
            if exists(output_filename) or return_args:
                continue

            requester = Requester(*args[-1])  
            if not requester.ready:
                continue
            elif os.path.exists(requester.output_filename):
                logger(f'Already processed: {requester.output_filename}')
                if os.path.getsize(requester.output_filename) < 1024:
                    logger.warning(f'Please check: {requester.output_filename}')
                    commands.append(original_line + '\n')
            elif requester.ready:
                requesters.append(requester)
    return args if return_args else requesters
    


def main(instruction_filename: ExistingFilename = config.INSTRUCTION_FILENAME, prerun: bool = False) -> None:

    lines = get_lines(instruction_filename)
    requesters = get_requesters(lines)

    if prerun:
        used_filenames = [
            os.path.basename(requester.input_filename)
            for requester in requesters
        ]
        unused_filename = [filename for filename in os.listdir(config.INPUT_FOLDER) if filename not in used_filenames]
        logger("Won't use some files. Can use these commands:")
        for filename in unused_filename:
            print(f'del "{filename}"')
        
        return

    logger.set_iterator(len(requesters))
    commands = []
    for requester in requesters:
        os.makedirs(os.path.dirname(requester.output_filename), exist_ok=True)

        command = requester.run()
        logger.iterate(message=command)
        commands.append(command + '\n')

    backup(commands)
    os.system("../output/remove_black.bat")


if __name__ == '__main__':
    fire.Fire(main)
