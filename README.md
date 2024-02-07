# split-on-silence
Divide long audio tracks into chapters based on a specified silence duration, performing the split halfway through each silence segment.

Adapted from: https://github.com/kkroening/ffmpeg-python/blob/master/examples/split_silence.py

## Dependencies:
- python3
- ffmpeg
- pydub
- eyeD3

## Notes:
- Call split_on_silence.py -h for the help menu.
- If there are multiple files to process and the -s flag is present (see next point), an output folder will be created for each file (filename_out).
- The **-s** (do split) flag must be present to actually output files. Without it, the script simply outputs what it _would_ do. I recommend running first without the -s to ensure the files and naming are as expected.
- Script will run on all .mp3 files in cwd unless files are specified with the **-f** flag.
- Starting chapter number will be 1 unless otherwise specified with the **-c** flag. Helpful if running one file at a time and continuing where the last one left off.
- Minimum silence duration is 3 seconds unless specified with the **-m** flag. This is sufficient for most audiobooks but there may be some variation, another reason to do a preview run without the -s before executing.
- Default naming scheme is ($number)_FileName unless otherwise specified with the **-n** flag. Example: _-n 'Chapter $number'_
