'''
lz4 program to compress a folder into *.lz4r format
'''
import sys
import os
import getopt
import tarfile
import tempfile
import liblz4
import lz4archiver


def make_archive(dirname):
    f, ar_name = tempfile.mkstemp('.tar')
    os.close(f)
    ar_file = lz4archiver.ArchiveFile()
    ar_file.open_for_write(ar_name)
    ar_file.packfolder(dirname)
    ar_file.close()
    return ar_name


def compress_folder(src_dir, filename):
    ar_name = make_archive(src_dir)
    compresser = liblz4.Compresser()
    compresser.compress_file(ar_name, filename)
    print('Successfully compressed ', src_dir, ' to ', filename)


def extract_folder(filename, dest_dir='.'):
    extractor = liblz4.Extractor()
    f, ar_name = tempfile.mkstemp('.tar')
    os.close(f)
    try:
        extractor.extract_file(filename, ar_name)
        ar_file = lz4archiver.ArchiveFile()
        ar_file.open_for_read(ar_name)
        ar_file.unpack(dest_dir)
        ar_file.close()
        print('Successfully extracted ', filename, ' to current directory')
    except liblz4.BadFileError:
        print('Error: Unrecognized file format')
    except lz4archiver.UnpackError:
    	print('Error: Unrecognized archive format')


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
            print('Error: ', dirname + ' not exists or not a directory')
            exit()
        if os.path.isfile(filename):
            answer = input('Warning: ' + filename +
                           ' already exists\nOverwrite? Y/n : ')
            if answer and answer.upper() not in ('Y', 'YES'):
                exit()
        print('Compressing ', dirname, ' to ', filename, ', please wait...')
        compress_folder(dirname, filename)
    elif filename and command == '-x' and len(pos_args) == 0:
        if not os.path.isfile(filename):
            print('Error: ', filename, ' is not valid file name')
            exit()
        print('Extracting ', filename, ', please wait...')
        extract_folder(filename)
    else:
        print(usage)


if __name__ == '__main__':
    main()
