import argparse
import os
import sys
from pydub import AudioSegment, exceptions as pydub_exceptions
from rignak.logging_utils import logger
import glob
import mutagen

# Easily configurable list of supported input audio extensions
SUPPORTED_EXTENSIONS = ['.wav', '.flac', '.ogg', '.aiff', '.mp3']  # MP3 added for re-encoding or tag updates


def convert_audio_file(input_path: str, output_path: str, bitrate_val: str, compression_val: int) -> bool:
    """
    Converts a single audio file to MP3 using the specified parameters,
    preserving relevant metadata using mutagen.
    """
    audio_format = os.path.splitext(input_path)[1][1:].lower()

    try:
        audio_tags_to_export = {}
        try:
            mutagen_file = mutagen.File(input_path)
            if mutagen_file and mutagen_file.tags:
                common_keys = {
                    'artist', 'album', 'title', 'genre', 'date', 'year', 'tracknumber',
                    'tracktotal', 'discnumber', 'disctotal', 'comment', 'composer',
                    'albumartist', 'language'
                }

                for key in common_keys:
                    if key in mutagen_file.tags:
                        value = mutagen_file.tags[key]
                        if isinstance(value, list) and len(value) > 0:
                            audio_tags_to_export[key] = str(value[0])
                        else:
                            audio_tags_to_export[key] = str(value)

                for key, value in mutagen_file.tags.items():
                    if key not in audio_tags_to_export and isinstance(value, str):
                        audio_tags_to_export[key.lower()] = value  # Ensure keys are lowercase for consistency
                    elif key not in audio_tags_to_export and isinstance(value, list) and len(value) > 0 and isinstance(
                            value[0], str):
                        audio_tags_to_export[key.lower()] = value[0]


        except Exception as e:
            logger(f"WARNING: Could not read tags from '{input_path}' using mutagen: {e}. "
                   "Proceeding with conversion without transferring existing tags.")
            audio_tags_to_export = {}
        audio = AudioSegment.from_file(input_path, format=audio_format)

        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        export_params = {
            'format': "mp3",
            'bitrate': bitrate_val,
            'parameters': ['-q:a', str(compression_val)],
            'tags': audio_tags_to_export
        }
        audio.export(output_path, **export_params)
        return True

    except FileNotFoundError:
        logger.error(f"File not found '{input_path}'.")
    except pydub_exceptions.CouldntDecodeError:
        logger.error(
            f"Could not decode audio file '{input_path}'. "
            f"It might be corrupted or an unsupported format variant."
        )
    except Exception as e:
        logger.error(f"Could not convert '{input_path}': {e}")
    return False


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert audio files or directories to MP3 format.")
    parser.add_argument(
        "--source",
        required=True,
        help="Path to the source audio file or directory."
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Path to the target directory where MP3 files will be saved."
    )
    parser.add_argument(
        "-b", "--bitrate",
        default="192k",
        help="Audio bitrate for MP3 conversion (e.g., '128k', '192k', '320k'). Default: '192k'."
    )
    parser.add_argument(
        "-c", "--compression",
        type=int,
        choices=range(10),  # 0-9
        default=4,
        metavar="[0-9]",
        help="MP3 compression level (0=higher quality, 9=smaller size). Default: 4."
    )
    args = parser.parse_args()
    return args


def main(source: str, target: str, bitrate: str, compression: int) -> None:
    if not os.path.exists(source):
        logger.error(f"Source path '{source}' does not exist.")
        sys.exit(1)

    logger(f"Source: {source}")
    logger(f"Target Directory: {target}")
    logger(f"Bitrate: {bitrate}")
    logger(f"Compression: {compression}")
    logger("-" * 30)

    try:
        os.makedirs(target, exist_ok=True)
        if not os.path.isdir(target):
            logger.error(f"Target path '{target}' is not a directory and could not be created as one.")
            sys.exit(1)
    except OSError as e:
        logger.error(f"Could not create target directory '{target}': {e}")
        sys.exit(1)

    logger(f"Processing directory recursively: {source}")
    args = []
    for folder, _, basenames in os.walk(source):
        input_filenames = [
            os.path.join(folder, basename)
            for basename in basenames
            if os.path.splitext(basename)[1].lower() in SUPPORTED_EXTENSIONS
        ]

        for input_filename in sorted(input_filenames):
            output_filename = os.path.join(target, os.path.relpath(input_filename, source))
            output_filename = os.path.splitext(output_filename)[0] + ".mp3"
            args.append((input_filename, output_filename, bitrate, compression))

    logger(f"Found {len(args)} files to convert.")
    logger.set_iterator(len(args))
    for arg in args:
        logger.iterate(f"Process {arg[0]}")
        convert_audio_file(*arg)


if __name__ == "__main__":
    args = get_args()
    main(args.source, args.target, args.bitrate, args.compression)
