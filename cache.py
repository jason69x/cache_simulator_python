import math
import random
from collections import OrderedDict

CACHE_ACCESS_TIME = 1  # nanoseconds
MAIN_MEMORY_ACCESS_TIME = 90


class CacheLine:
    def __init__(self, block_size):
        self.valid = 0
        self.tag = None
        self.data = [0] * block_size


class CacheSet:
    def __init__(self, block_size, associativity):
        self.use = 0
        self.ways = OrderedDict()


class Cache:
    ADDRESS_SIZE = 32
    WORD_SIZE = 32
    BYTE_OFFSET = 2  # two bits, 1 word = 4 bytes of data

    def __init__(self, capacity, block_size, associativity):
        total_blocks = capacity // block_size
        total_sets = total_blocks // associativity
        self.associativity = associativity
        self.block_size = block_size

        self.set_bits = math.ceil(math.log2(total_sets))
        self.block_offset = math.ceil(math.log2(block_size))
        self.tag_bits = (
            self.ADDRESS_SIZE - self.set_bits - self.block_offset - self.BYTE_OFFSET
        )

        self.cache = [CacheSet(block_size, associativity) for _ in range(total_sets)]

    def get_data(self, addr):
        tag_no = addr >> (self.set_bits + self.block_offset + self.BYTE_OFFSET)
        set_no = (addr >> (self.block_offset + self.BYTE_OFFSET)) & (
            (1 << self.set_bits) - 1
        )
        block_no = (addr >> self.BYTE_OFFSET) & ((1 << self.block_offset) - 1)
        hit, data, hit_set, hit_tag = self.LRU_find(set_no, tag_no, block_no)

        if hit == True:
            return (hit, data, hit_set, hit_tag)
        data, hit_set, hit_tag = self.get_data_memory(set_no, tag_no, block_no)
        return (hit, data, hit_set, hit_tag)

    def LRU_find(self, set_no, tag_no, block_no):
        for tag, line in self.cache[set_no].ways.items():
            if line.valid == 1 and tag == tag_no:
                self.cache[set_no].ways.move_to_end(tag_no, last=False)
                return (True, line.data[block_no], set_no, tag_no)
        return (False, None, None, None)

    def get_data_memory(self, set_no, tag_no, block_no):

        data = [random.randint(0, 100) for r in range(self.block_size)]
        self.LRU_load(set_no, tag_no, block_no, data)
        return data[block_no], set_no, tag_no

    def LRU_load(self, set_no, tag_no, block_no, data):
        if len(self.cache[set_no].ways) == self.associativity:
            self.cache[set_no].ways.popitem(last=True)
        self.cache[set_no].ways[tag_no] = CacheLine(self.block_size)
        self.cache[set_no].ways[tag_no].valid = 1
        self.cache[set_no].ways[tag_no].tag = tag_no
        self.cache[set_no].ways[tag_no].data = data
        self.cache[set_no].ways.move_to_end(tag_no, last=False)


capacity = int(input("cache capacity (no. of words cache stores) : "))
block_size = int(input("block size (no. of words per block): "))
associativity = int(input("associativity: "))
print("--------------------------------")

cache = Cache(capacity, block_size, associativity)

with open("addr_file.txt", "r") as file:
    total_hit = 0
    total_miss = 0
    total_access = 0
    for addr in file:
        addr = int(addr.strip())
        hit, data, hit_set, hit_tag = cache.get_data(addr)
        if hit == True:
            total_hit += 1
            print("HIT ", "addr: ", addr)
            print("set: ", hit_set)
            print("tag: ", hit_tag)
            print("data: ", data)
        else:
            total_miss += 1
            print("MISS", "addr: ", addr)
        total_access += 1
        print()
    print("-------------------------")
    hit_rate = (total_hit / total_access) * 100
    miss_rate = (total_miss / total_access) * 100
    print("HIT RATE:", hit_rate, "%")
    print("MISS RATE:", miss_rate, "%")
    print("AMAT: ", (CACHE_ACCESS_TIME + miss_rate * (MAIN_MEMORY_ACCESS_TIME)), "ns")
