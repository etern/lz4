'''
Pack folder to into a file / Unpack archive file

Archive Format:
 Files are packed into archive sequencially with a "file header"
 followed by file content, the file header layout as follows:

   |-- length of file name  --|  -> 4 bytes little endian int
   |--length of file content--|  -> 4 bytes little endian int
   |--       file name      --|  -> bytes encoded in utf-8
   |--   header checksum    --|  -> md5

'''
import os
import pdb
import hashlib


class UnpackError(Exception):
    pass


class ArchiveFile:

    BUFFER_SIZE = 4 * (2**20)

    def __init__(self):
        pass

    def open_for_write(self, filename):
        self.ar_file_size = os.path.getsize(filename)
        self.file = open(filename, 'w+b')

    def open_for_read(self, filename):
        self.ar_file_size = os.path.getsize(filename)
        self.file = open(filename, 'rb')

    def close(self):
        self.file.close()

    def packfolder(self, dirname):
        names = []
        for root, dirs, files in os.walk(dirname, topdown=False):
            for name in files:
                names.append(os.path.join(root, name))
        self.packfiles(names)

    def packfiles(self, filenames):
        for name in filenames:
            self.append(name)

    def _append_header(self, filename):
        name_bytes = filename.encode('utf-8')
        name_len = len(name_bytes).to_bytes(4, 'little')
        file_size = os.path.getsize(filename).to_bytes(4, 'little')
        self.file.write(name_len)
        self.file.write(file_size)
        self.file.write(name_bytes)
        # header checksum
        md5 = hashlib.md5()
        md5.update(name_len + file_size + name_bytes)
        self.file.write(md5.digest())

    def append(self, filename):
        if not os.path.isfile(filename):
            return
        with open(filename, 'rb') as f:
            self._append_header(filename)
            while True:
                buf = f.read(self.BUFFER_SIZE)
                self.file.write(buf)
                if not buf:
                    break

    def _read_header(self):
        header_len = 0
        md5 = hashlib.md5()
        buf = self.file.read(4)
        header_len += 4
        md5.update(buf)
        name_len = int.from_bytes(buf, 'little')
        buf = self.file.read(4)
        header_len += 4
        md5.update(buf)
        file_len = int.from_bytes(buf, 'little')
        buf = self.file.read(name_len)
        header_len += name_len
        md5.update(buf)
        filename = buf.decode('utf-8')
        buf = self.file.read(md5.digest_size)
        header_len += md5.digest_size
        if buf == md5.digest():
            return header_len, filename, file_len
        else:
            raise UnpackError('checksum error')

    def _unpack_file(self, filename, file_size):
        with open(filename, 'w+b') as f:
            while file_size > self.BUFFER_SIZE:
                buf = self.file.read(self.BUFFER_SIZE)
                if len(buf) != self.BUFFER_SIZE:
                    raise UnpackError('file corrupted')
                f.write(buf)
                file_size -= self.BUFFER_SIZE
            buf = self.file.read(file_size)
            if len(buf) != file_size:
                raise UnpackError('file corrupted')
            f.write(buf)

    def unpack(self, dst_dirname):
        remained_size = self.ar_file_size
        while remained_size > 0:
            header_len, filename, file_size = self._read_header()
            remained_size -= header_len
            filename = os.path.join(dst_dirname, filename)
            file_dir, _ = os.path.split(filename)
            if not os.path.isdir(file_dir):
                os.makedirs(file_dir)
            self._unpack_file(filename, file_size)
            remained_size -= file_size


def test_pack_folder():
    # pdb.set_trace()
    ar = ArchiveFile()
    ar.open_for_write('testpack.mytar')
    ar.packfolder('testfolder')
    ar.close()


def test_unpack_folder():
    # pdb.set_trace()
    ar = ArchiveFile()
    ar.open_for_read('testpack.mytar')
    ar.unpack('testout')
    ar.close()

if __name__ == '__main__':
    test_unpack_folder()
