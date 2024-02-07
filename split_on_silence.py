import eyed3
import datetime
import time
import fnmatch
import os
import re
import sys
import ffmpeg
import logging
import subprocess
from pydub import AudioSegment
import argparse
from string import Template

#adapted from https://github.com/kkroening/ffmpeg-python/blob/master/examples/split_silence.py and others

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)

DEFAULT_DURATION = 3
DEFAULT_THRESHOLD = -40

silence_start_re = re.compile(r' silence_start: (?P<start>[0-9]+(\.?[0-9]*))$')
silence_end_re = re.compile(r' silence_end: (?P<end>[0-9]+(\.?[0-9]*)) ')
total_duration_re = re.compile(
    r'size=[^ ]+ time=(?P<hours>[0-9]{2}):(?P<minutes>[0-9]{2}):(?P<seconds>[0-9\.]{5}) bitrate=')

def _logged_popen(cmd_line, *args, **kwargs):
    logger.debug('Running command: {}'.format(subprocess.list2cmdline(cmd_line)))
    return subprocess.Popen(cmd_line, *args, **kwargs)

def get_modified_chunk_times(in_filename, silence_threshold, silence_duration): 
	start_time = 0
	input_kwargs = {}
	p = _logged_popen(
		(ffmpeg
			.input(in_filename, **input_kwargs)
			.filter('silencedetect', n='{}dB'.format(silence_threshold), d=silence_duration)
			.output('-', format='null')
			.compile()
		) + ['-nostats'],  # FIXME: use .nostats() once it's implemented in ffmpeg-python.
		stderr=subprocess.PIPE
	)
	output = p.communicate()[1].decode('utf-8')
	if p.returncode != 0:
		sys.stderr.write(output)
		sys.exit(1)
	logger.debug(output)
	lines = output.splitlines()

	# Chunks start when silence ends, and chunks end when silence starts.
	chunk_starts = []
	chunk_ends = []
	for line in lines:
		silence_start_match = silence_start_re.search(line)
		silence_end_match = silence_end_re.search(line)
		total_duration_match = total_duration_re.search(line)

		if silence_start_match:
			chunk_ends.append(float(silence_start_match.group('start')))
			if len(chunk_starts) == 0:
				# Started with non-silence.
				chunk_starts.append(start_time or 0.)
		elif silence_end_match:
			chunk_starts.append(float(silence_end_match.group('end')))
		elif total_duration_match:
			hours = int(total_duration_match.group('hours'))
			minutes = int(total_duration_match.group('minutes'))
			seconds = float(total_duration_match.group('seconds'))
			end_time = hours * 3600 + minutes * 60 + seconds

	if len(chunk_starts) == 0:
		# No silence found.
		chunk_starts.append(start_time)

	if len(chunk_starts) > len(chunk_ends):
		# Finished with non-silence.
		chunk_ends.append(end_time or 10000000.)

	chunk_times = list(zip(chunk_starts, chunk_ends))

	prev_end_time = 0
	modified_start_times = []
	for i, (start_time, end_time) in enumerate(chunk_times):
		modified_start_time = start_time
		start_offset = 0
		if prev_end_time > 0:
			start_offset = ((start_time - prev_end_time)/2)
			modified_start_time = start_time - start_offset
		modified_start_times.append(modified_start_time)
		prev_end_time = end_time
	return modified_start_times

def process_file(p_file_name, p_start_num, p_create_dir, p_args,silence_threshold=DEFAULT_THRESHOLD):
	audiofile = eyed3.load(p_file_name)
	album_name = ""
	artist_name = ""
	if audiofile.tag:
		album_name =  audiofile.tag.album 
		artist_name = audiofile.tag.artist
	prev_name = p_file_name
	file_name = p_file_name.replace(".mp3", "")
	out_dir = ""
	if p_create_dir and p_args.s:
		out_dir = f"{file_name}_out"
		if not os.path.exists(out_dir):
			os.mkdir(out_dir)
		out_dir = f"{out_dir}/"
	if p_args.s:
		audio_bytes = AudioSegment.from_mp3(p_file_name)
	i = 0
	prev_seconds = 0
	prev_name = ""
	markers = get_modified_chunk_times(p_file_name, silence_threshold, p_args.m)
	for marker in markers:
		curr_name = f"{p_start_num}_{file_name}"
		if p_args.n:
			new = Template(p_args.n)
			curr_name = new.substitute(number= p_start_num)
		curr_seconds = float(marker)
		start_ms = (1000 * prev_seconds)
		end_ms = (1000 * curr_seconds) 
		if i > 0:
			out_file_path = f"{out_dir}{prev_name}.mp3" 
			if p_args.s:
				split_audio_bytes = audio_bytes[start_ms:end_ms]
				split_audio_bytes.export(out_file_path, format="mp3",parameters=["-q:a","8"], bitrate="64k",tags={'artist': artist_name, 'album': album_name, 'track': prev_name, 'title': prev_name})
				print(f"Exported {out_file_path}")
			else:
				print(f"{round((start_ms/1000),3)}\t{round((end_ms/1000),3)}\t{prev_name}")
		prev_name = curr_name
		prev_seconds = curr_seconds
		i+=1
		p_start_num += 1
	#last one
	duration = audiofile.info.time_secs
	out_file_path = f"{out_dir}{prev_name}.mp3" 
	start_ms = (1000 * prev_seconds)
	end_ms = (1000 * duration) 
	if p_args.s:
		split_audio_bytes = audio_bytes[start_ms:end_ms]
		split_audio_bytes.export(out_file_path, format="mp3",parameters=["-q:a","8"], bitrate="64k",tags={'artist': artist_name, 'album': album_name, 'track': prev_name, 'title': prev_name})
		print(f"Exported {out_file_path}")
	else:
		print(f"{round((start_ms/1000),3)}\t{round((end_ms/1000),3)}\t{prev_name}")
	return p_start_num

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('-m', help="Min silence duration between chapters, in seconds. Default 3.", type= float, default = 3)
	parser.add_argument('-c', help="Starting chapter number if not starting at 1- for use when skipping files. Default 1", type= int, default = 1)
	parser.add_argument('-n', help="Naming scheme for numbered files, enclosed in singled quotes using $number as replacement. Default ($number)_FileName")
	parser.add_argument('-s', help="Perform split. If not present, will print markers only. Default False.", action='store_true')
	parser.add_argument('-f', nargs='+', help='<Optional> List of files to process. Default all mp3 files in current dir')

	args = parser.parse_args()
	print(f"start chapter: {args.c}") 
	print(f"min silence seconds: {args.m}")
	print(f"perform split: {args.s}")
	print(f"naming scheme: {args.n}")

	dir_path = os.getcwd()
	curr_path = os.path.basename(os.getcwd())
	is_specific_files = args.f and len(args.f) > 0
	if is_specific_files:
		list_files = args.f
	else:
		list_files = os.listdir(dir_path)

	num_files = len(fnmatch.filter(list_files,"*.mp3")) 
	print(f"file list: {args.f} - {num_files} file(s)")

	sorted_files = sorted(list_files)

	create_subdirs = (num_files > 1 and args.s)
	
	n = args.c

	for iter_file in sorted_files:
		if iter_file.endswith('.mp3'):
			n = process_file(iter_file, n, create_subdirs, args)		

if __name__ == "__main__":
	main()
	print('done')
