import math
import random
from collections import OrderedDict

CACHE_ACCESS_TIME = 1  # nanoseconds
MAIN_MEMORY_ACCESS_TIME = 90  # nanoseconds


# main memory structure (Lazy structure only stores what is accessed)
# stores blocks of data, block addressable
class MainMemory:
    def __init__(self):
        self.blocks = {}

    def read_mm(self, block_addr, block_size):
        if block_addr in self.blocks:
            return self.blocks[block_addr]
        self.blocks[block_addr] = [random.randint(0, 100) for i in range(block_size)]
        return self.blocks[block_addr]

    def write_mm(self, block_addr, block_no, block_size, dataword, flag):
        if flag == 1:
            self.blocks[block_addr] = dataword
            return
        if block_addr in self.blocks:
            self.blocks[block_addr][block_no] = dataword
            return
        self.blocks[block_addr] = [random.randint(0, 100) for i in range(block_size)]
        self.blocks[block_addr][block_no] = dataword


# cache line structure
class CacheLine:
    def __init__(self, block_size):
        self.valid = 0
        self.dirty = 0
        self.tag = None
        self.data = [0] * block_size


# cache set structure
class CacheSet:
    def __init__(self):
        self.ways = OrderedDict()


# main cache structure
class Cache:
    ADDRESS_SIZE = 32
    WORD_SIZE = 32
    BYTE_OFFSET = 2  # two bits, 1 word = 4 bytes of data

    def __init__(
        self,
        main_memory,
        capacity,
        block_size,
        associativity,
        write_hit_policy,
        write_miss_policy,
    ):
        self.main_memory = main_memory
        self.write_hit_policy = write_hit_policy
        self.write_miss_policy = write_miss_policy
        total_blocks = capacity // block_size
        total_sets = total_blocks // associativity
        self.associativity = associativity
        self.block_size = block_size

        self.set_bits = math.ceil(math.log2(total_sets))
        self.block_offset = math.ceil(math.log2(block_size))
        self.tag_bits = (
            self.ADDRESS_SIZE - self.set_bits - self.block_offset - self.BYTE_OFFSET
        )

        self.cache = [CacheSet() for _ in range(total_sets)]

    def read_cache(self, addr):
        set_no, tag_no, block_no = self.decode_addr(addr)
        hit, data, hit_set, hit_tag = self.LRU_find(set_no, tag_no, block_no)

        if hit == True:
            return (hit, data, hit_set, hit_tag)
        data, hit_set, hit_tag = self.get_data_memory(addr, set_no, tag_no, block_no)
        return (hit, data, hit_set, hit_tag)

    def write_cache(self, addr, new_data):
        set_no, tag_no, block_no = self.decode_addr(addr)
        hit, data, hit_set, hit_tag = self.LRU_find(set_no, tag_no, block_no)

        block_addr = addr >> (self.BYTE_OFFSET + self.block_offset)
        if hit == True:
            self.cache[hit_set].ways[hit_tag].data[block_no] = new_data
            if self.write_hit_policy == 0:
                self.main_memory.write_mm(
                    block_addr, block_no, self.block_size, new_data, 0
                )
                return hit, hit_set, hit_tag
            self.cache[hit_set].ways[hit_tag].dirty = 1
            return hit, hit_set, hit_tag

        if self.write_miss_policy == 0:
            data, hit_set, hit_tag = self.get_data_memory(
                addr, set_no, tag_no, block_no
            )
            self.cache[hit_set].ways[hit_tag].data[block_no] = new_data
            if self.write_hit_policy == 0:
                self.main_memory.write_mm(
                    block_addr, block_no, self.block_size, new_data, 0
                )
                return hit, hit_set, hit_tag
            self.cache[hit_set].ways[hit_tag].dirty = 1
            return hit, hit_set, hit_tag
        self.main_memory.write_mm(block_addr, block_no, self.block_size, new_data, 0)
        return hit, hit_set, hit_tag

    def LRU_find(self, set_no, tag_no, block_no):
        for tag, line in self.cache[set_no].ways.items():
            if tag == tag_no:
                self.cache[set_no].ways.move_to_end(tag_no, last=False)
                return (True, line.data[block_no], set_no, tag_no)
        return (False, None, None, None)

    def get_data_memory(self, addr, set_no, tag_no, block_no):

        block_addr = addr >> (self.BYTE_OFFSET + self.block_offset)

        data = self.main_memory.read_mm(block_addr, self.block_size)
        self.LRU_load(addr, set_no, tag_no, block_no, data)
        return data[block_no], set_no, tag_no

    def LRU_load(self, addr, set_no, tag_no, block_no, data):
        if len(self.cache[set_no].ways) == self.associativity:
            evicted_tag, evicted_line = self.cache[set_no].ways.popitem(last=True)
            if evicted_line.dirty == 1 and self.write_hit_policy == 1:
                block_addr = (evicted_tag << self.set_bits) | set_no
                self.main_memory.write_mm(
                    block_addr, block_no, self.block_size, evicted_line.data, 1
                )
        self.cache[set_no].ways[tag_no] = CacheLine(self.block_size)
        self.cache[set_no].ways[tag_no].valid = 1
        self.cache[set_no].ways[tag_no].tag = tag_no
        self.cache[set_no].ways[tag_no].data = data.copy()
        self.cache[set_no].ways.move_to_end(tag_no, last=False)

    def decode_addr(self, addr):
        tag_no = addr >> (self.set_bits + self.block_offset + self.BYTE_OFFSET)
        set_no = (addr >> (self.block_offset + self.BYTE_OFFSET)) & (
            (1 << self.set_bits) - 1
        )
        block_no = (addr >> self.BYTE_OFFSET) & ((1 << self.block_offset) - 1)
        return (tag_no, set_no, block_no)


capacity = int(input("cache capacity (no. of words cache stores) = "))
block_size = int(input("block size (no. of words per block) = "))
associativity = int(input("associativity = "))
write_hit_policy = int(
    input("write hit policy: \n(0->write-through 1-> write-back) = ")
)
write_miss_policy = int(
    input("write miss policy: \n(0->write-allocate 1-> write-around) = ")
)
print("--------------------------------")

main_memory = MainMemory()
cache = Cache(
    main_memory,
    capacity,
    block_size,
    associativity,
    write_hit_policy,
    write_miss_policy,
)

with open("addr_file.txt", "r") as file:
    total_hit = 0
    total_miss = 0
    total_access = 0
    for addr in file:
        op, addr = addr.strip().split()
        addr = int(addr)
        if op == "R":
            hit, data, hit_set, hit_tag = cache.read_cache(addr)
        else:
            hit, hit_set, hit_tag = cache.write_cache(addr, random.randint(0, 100))
        if hit == True:
            total_hit += 1
            print("HIT ", "addr: ", addr)
            print("set: ", hit_set)
            print("tag: ", hit_tag)
        else:
            total_miss += 1
            print("MISS", "addr: ", addr)
        total_access += 1
        print()
    print("-------------------------")
    hit_rate = total_hit / total_access
    miss_rate = total_miss / total_access
    print("HIT RATE:", hit_rate * 100, "%")
    print("MISS RATE:", miss_rate * 100, "%")
    print("EMAT: ", (CACHE_ACCESS_TIME + miss_rate * (MAIN_MEMORY_ACCESS_TIME)), "ns")
