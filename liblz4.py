#!/usr/bin/python

import pdb
import base64
import xxhash


MAX_OFFSET = 65535
MIN_MATCH = 4
MFLIMIT = 12 # remained buffer less than MFLIMIT will not be compressed
MAX_BLOCK_INPUT_SIZE = 0x7E000000 # LZ4_MAX_INPUT_SIZE


class PositionTable:
	'''
	stores occurance position of a 4 bytes value
	'''
	TABLE_SIZE = 4096

	def __init__(self):
		self.table = [None] * self.TABLE_SIZE

	@staticmethod
	def _hash(val):
		val = val & 0x0FFFFFFFF  # prune to 32 bit
		return (val * 2654435761) & 0x0FFF  # max = 4095

	def get_position(self, val):
		index = self._hash(val)
		return self.table[index]

	def set_position(self, val, pos):
		index = self._hash(val)
		self.table[index] = pos

def print_hex(b):
	print(base64.b16encode(b))

'''
little endian byte conversions
'''
def read_le_uint32(buf, pos):
	return int.from_bytes(buf[pos:pos+4], 'little')

def write_le_uint16(buf, i, val):
	buf[i] = val & 0x00FF
	buf[i+1] = (val >> 8) & 0x00FF

def write_le_uint32(buf, i, val):
	buf[i] = val & 0x000000FF
	buf[i+1] = (val >> 8) & 0x000000FF
	buf[i+2] = (val >> 16) & 0x000000FF
	buf[i+3] = (val >> 24) & 0x000000FF

def find_match(table, val, src_buf, src_ptr):
	pos = table.get_position(val)
	if pos is not None and val == read_le_uint32(src_buf, pos):
		if src_ptr - pos > MAX_OFFSET: # if the found match is too far away
			return None
		else:
			return pos
	else:
		return None

def count_match(buf, front_idx, back_idx, max_idx):
	cnt = 0
	while back_idx <= max_idx:
		if buf[front_idx] == buf[back_idx]:
			cnt += 1
		else:
			break
		front_idx += 1
		back_idx += 1
	return cnt

def copy_sequence(dst_buf, dst_head, literal, match):
	lit_len = len(literal)
	dst_ptr = dst_head

	#pdb.set_trace()
	# write literal length
	token = memoryview(dst_buf)[dst_ptr:dst_ptr+1]
	dst_ptr += 1
	if lit_len >= 15:
		token[0] = (15 << 4)
		remain_len = lit_len - 15
		while remain_len >= 255:
			dst_buf[dst_ptr] = 255
			dst_ptr += 1
			remain_len -= 255
		dst_buf[dst_ptr] = remain_len
		dst_ptr += 1
	else:
		token[0] = (lit_len << 4)

	# write literal
	dst_buf[dst_ptr : dst_ptr+lit_len] = literal
	dst_ptr += lit_len

	offset, match_len = match
	if match_len > 0:
		# write match offset
		write_le_uint16(dst_buf, dst_ptr, offset)
		dst_ptr += 2

		# write match length
		match_len -= MIN_MATCH
		if match_len >= 15:
			token[0] = token[0] | 15
			match_len -= 15
			while match_len >= 255:
				dst_buf[dst_ptr] = 255
				dst_ptr += 1
				match_len -= 255
			dst_buf[dst_ptr] = match_len
			dst_ptr += 1
		else:
			token[0] = token[0] | match_len

	print('lit len ',len(literal), '|match ', match, '|seq len', dst_ptr-dst_head)
	print_hex(dst_buf[dst_head:dst_ptr])
	return dst_ptr - dst_head

def lz4_compress_sequences(dest_buffer, src_buffer):
	'''
	Scan src_buffer, split it into sequences, store sequences to dest_buffer.
	A sequence is a pair of literal and match
	'''
	src_len = len(src_buffer)
	if src_len > MAX_BLOCK_INPUT_SIZE:
		return 0
	pos_table = PositionTable()
	src_ptr = 0
	literal_head = 0 #store the literal head postition
	dst_ptr = 0 # number of bytes writen to dest buffer
	MAX_INDEX = src_len - MFLIMIT
	#pdb.set_trace()
	while src_ptr < MAX_INDEX:
		match_value = read_le_uint32(src_buffer, src_ptr)
		match_pos = find_match(pos_table, match_value, src_buffer, src_ptr)
		if match_pos is not None:
			length = count_match(src_buffer, match_pos, src_ptr, MAX_INDEX)
			dst_ptr += copy_sequence(dest_buffer,
									 dst_ptr,
									 memoryview(src_buffer)[literal_head:src_ptr],
									 (src_ptr-match_pos, length) )
			src_ptr += length
			literal_head = src_ptr
		else:
			pos_table.set_position(match_value, src_ptr)
			src_ptr += 1
	# last literal
	dst_ptr += copy_sequence(dest_buffer, dst_ptr,
		memoryview(src_buffer)[literal_head:src_len], (0, 0))

	return dst_ptr

def lz4_compress_block(dst_buffer, src_buffer):
	seq_len = lz4_compress_sequences(memoryview(dst_buffer)[4:], src_buffer)
	write_le_uint32(dst_buffer, 0, seq_len)
	if seq_len == 0: # if failed, copy src to dst directly
		write_le_uint32(0x80000000)
		dst_buffer[4:len(src_buffer)] = src_buffer
	# TODO: no block checksum
	return seq_len + 4


def worst_case_block_length(src_len):
	return src_len + (src_len//255) + 16 # LZ4_COMPRESSBOUND(isize)


class FrameParam:
	BLOCK_SIZE_ID = 7  # 4:max64KB, 5:max256KB, 6:max1MB, 7:max4MB
	BLOCK_SIZE = 4 * (2**20)  # 4MB matches BLOCK_SIZE_ID
	# when decompressing, independent blocks can be random accessed, otherwise
	# must be accessed sequentially
	BLOCK_INDEPENDENT = True
	BLOCK_CHECKSUM = False
	CONTENT_CHECKSUM = True  # does frame need checksum


class Compresser:
	def __init__(self):
		pass

	def compress_file(self, src_name, dst_name):
		self.src_file = open(src_name, mode='rb')
		self.dst_file = open(dst_name, mode='wb')
		self.compress_frame()

	def _frame_header(self):
		header = bytearray()
		MAGIC_NUMBER = 0x184D2204
		header += MAGIC_NUMBER.to_bytes(4, 'little')
		# default frame descriptor FLG, Version Number 01
		# Block Independenc 1, Block Checksum 0
		# Content Size 0, Content Checksum 1
		FD_FLG = int('01100100', 2)
		# frame descriptor BD
		# Block Max Size 7 -> 4M
		FD_BD = int('01110000', 2)
		# frame descriptor header checksum
		checksum = xxhash.xxh32(bytes([FD_FLG, FD_BD]), seed=0).digest()
		FD_HC = checksum[2]
		header.append(FD_FLG)
		header.append(FD_BD)
		header.append(FD_HC)
		return header


	def compress_frame(self):
		'''
		frame contains all the blocks, plus frame header and checksum
		'''
		self.dst_file.write(self._frame_header())
		def read_src(buf):
			return self.src_file.readinto(buf)

		self.src_buffer = bytearray(b'\0') * FrameParam.BLOCK_SIZE
		self.dst_buffer = bytearray(b'\0') * worst_case_block_length(FrameParam.BLOCK_SIZE)

		xxh = xxhash.xxh32(seed=0)

		nbytes = read_src(self.src_buffer)
		while nbytes != 0:
			block_len = lz4_compress_block(self.dst_buffer, memoryview(self.src_buffer)[0:nbytes])
			self.dst_file.write(memoryview(self.dst_buffer)[0:block_len])
			xxh.update(bytes(self.src_buffer[0:nbytes])) # only pinned buffer, not appropriate here
			nbytes = read_src(self.src_buffer)

		self.dst_file.write((0).to_bytes(4, 'little')) #EndMark
		self.dst_file.write(xxh.intdigest().to_bytes(4, 'little')) #EndMark


def test_comp_sequences():
	src_buf = b'00000000000001111111111111000000000000011111111111110000000000000111111111111100000000000001111111111111'
	print('src len: ', len(src_buf))
	dst_len = worst_case_block_length(len(src_buf))
	dest_buf = bytearray(b'\0') * dst_len
	compressed_len = lz4_compress_sequences(dest_buf, src_buf)
	dest_buf = dest_buf[0:compressed_len]
	print_hex(dest_buf)

def test_compresser():
	comp = Compresser()
	comp.compress_file('testfolder/testfile.txt', 'testout.bin')

if __name__ == '__main__':
	test_compresser()