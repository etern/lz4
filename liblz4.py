#!/usr/bin/python

import pdb
import base64

class FrameParam:
	BLOCK_SIZE_ID = 7  # 4:max64KB, 5:max256KB, 6:max1MB, 7:max4MB
	BLOCK_SIZE = 4 * (2**20)  # 4MB matches BLOCK_SIZE_ID
	# when decompressing, independent blocks can be random accessed, otherwise
	# must be accessed sequentially
	BLOCK_INDEPENDENT = True
	FRAME_CHECKSUM = True  # does frame need checksum


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



MAX_OFFSET = 65535
MIN_MATCH = 4
MFLIMIT = 12 # remained buffer less than MFLIMIT will not be compressed

def read_uint32(buf, pos):
	return (buf[pos+3]<<24) + (buf[pos+2]<<16) + (buf[pos+1]<<8) + buf[pos]

def find_match(table, val, src_buf, src_ptr):
	pos = table.get_position(val)
	if pos is not None and val == read_uint32(src_buf, pos):
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

def write_uint16(buf, i, val):
	buf[i] = val & 0x0FF
	buf[i+1] = (val >> 8) & 0x0FF

def copy_sequence(dst_buf, dst_head, literal, match):
	lit_len = len(literal)
	dst_ptr = dst_head

	#pdb.set_trace()
	# write literal length
	token = memoryview(dst_buf)[dst_ptr:dst_ptr+1]
	dst_ptr += 1
	if lit_len > 15:
		token[0] = (15 << 4)
		lit_len -= 15
		while lit_len >= 255:
			dst_buf[dst_ptr] = 255
			dst_ptr += 1
			lit_len -= 255
		dst_buf[dst_ptr] = lit_len
		dst_ptr += 1
	else:
		token[0] = (lit_len << 4)

	# write literal
	dst_buf[dst_ptr : dst_ptr+lit_len] = literal
	dst_ptr += lit_len

	offset, match_len = match
	if match_len > 0:
		#write match offset
		write_uint16(dst_buf, dst_ptr, offset)
		dst_ptr += 2

		#write match length
		if match_len > 15:
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

	print(lit_len, '+', match_len, '->', dst_ptr-dst_head)
	print(base64.b16encode(dst_buf[dst_head:dst_ptr]))
	return dst_ptr - dst_head

def lz4_compress_sequences(dest_buffer, src_buffer):
	'''
	Scan src_buffer, split it into sequences, store sequences to dest_buffer.
	A sequence is a pair of literal and match
	'''

	pos_table = PositionTable()
	src_len = len(src_buffer)
	src_ptr = 0
	literal_head = 0 #store the literal head postition
	dst_ptr = 0 # number of bytes writen to dest buffer
	MAX_INDEX = src_len - MFLIMIT
	#pdb.set_trace()
	while src_ptr < MAX_INDEX:
		match_value = read_uint32(src_buffer, src_ptr)
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

def worst_case_block_length(src_len):
	return src_len + (src_len//255) + 16 # LZ4_COMPRESSBOUND(isize)

def test():
	src_buf = b'00000000000001111111111111000000000000011111111111110000000000000111111111111100000000000001111111111111'
	print('src len: ', len(src_buf))
	dst_len = worst_case_block_length(len(src_buf))
	dest_buf = bytearray(b'\0') * dst_len
	compressed_len = lz4_compress_sequences(dest_buf, src_buf)
	dest_buf = dest_buf[0:compressed_len]
	print(base64.b16encode(dest_buf))


if __name__ == '__main__':
	test()