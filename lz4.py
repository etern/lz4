#!/usr/bin/python

import sys
import os
import getopt
import tarfile
import tempfile
import liblz4


def make_archive(dirname):
	f, ar_name = tempfile.mkstemp('.tar')
	f.close()
	with tarfile.open(ar_name, "w") as tar:
		for root, dirs, files in os.walk(dirname, topdown=False):
			for name in files:
				tar.add(os.path.join(root, name))
	return ar_name


def compress_folder(src_dir, filename):
	ar_name = make_archive(src_dir)
	print(ar_name)


def extract_folder(filename, dest_dir='.'):
	ar_name = filename
	tar = tarfile.open(ar_name)
	tar.extractall(dest_dir)
	tar.close()


usage =\
	'''
Usage:
 Compress a folder:
   lz4 -c dir_name.lz4r dir_name

 Extract file:
   lz4 -x dir_name.lz4r
'''


def main():
	try:
		opts, pos_args = getopt.getopt(sys.argv[1:], 'c:x:')
	except getopt.GetoptError as err:
		print(err, usage)
		exit()

	if len(opts) != 1:  # -c and -x are mutually execulsive
		print(usage)
		exit()

	command, filename = opts[0]
	if filename and command == '-c' and len(pos_args) == 1:
		dirname = pos_args[0]
		if not os.path.isdir(dirname):
			print(dirname + ' not exists or not a directory')
			exit()
		if os.path.isfile(filename):
			go_on = 'Y'
			go_on = input(filename + ' already exists, overwrite? Y/n')
			if go_on.upper() != 'Y':
				exit()
		print('compressing ' + dirname + ' to ' + filename)
		compress_folder(dirname, filename)
	elif filename and command == '-x' and len(pos_args) == 0:
		if not os.path.isfile(filename):
			print(filename + ' is not valid file name')
		print('extracting ' + filename)
		extract_folder(filename)
	else:
		print(usage)


if __name__ == '__main__':
	main()
