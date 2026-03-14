import math
import random
from collections import OrderedDict
import configparser
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--config", type=str, required=True, help="Path to config file")
parser.add_argument("--trace", type=str, required=True, help="Path to Trace file")
# parser.add_argument("--levels", type=int, help="no. of cache levels")
args = parser.parse_args()

# load config
config = configparser.ConfigParser()
config.read(args.config)

MAIN_MEMORY_ACCESS_TIME = config.getint("DRAM", "access_time")


# main memory structure (Lazy structure only stores what is accessed)
# stores blocks of data, block addressable
class MainMemory:

    def __init__(self):
        self.blocks = {}
        self.TOTAL_ACCESS = 0

    def read_mm(self, block_addr, block_size):
        self.TOTAL_ACCESS += 1
        if block_addr in self.blocks:
            return self.blocks[block_addr]
        # create a block with block_size number of random words
        self.blocks[block_addr] = [random.randint(0, 100) for i in range(block_size)]
        return self.blocks[block_addr]

    def write_mm(self, block_addr, block_no, block_size, dataword, flag):
        self.TOTAL_ACCESS += 1
        # flag == 1 is used to write a entire block to the memory
        if flag == 1:
            self.blocks[block_addr] = dataword
            return
        # else write only a word into a block (in case of write-around)
        if block_addr in self.blocks:
            self.blocks[block_addr][block_no] = dataword
            return
        # self.blocks[block_addr] = [random.randint(0, 100) for i in range(block_size)]
        # self.blocks[block_addr][block_no] = dataword


# cache line structure
class CacheLine:
    def __init__(self, block_size):
        self.valid = 0
        self.dirty = 0
        self.tag = None
        self.data = [0] * block_size


# cache set structure
class CacheSet:
    def __init__(self, associativity):
        self.ways = OrderedDict()
        self.plru_set = [None] * associativity
        self.plru_bits = [0] * (associativity - 1)


# main cache structure
class Cache:

    def __init__(
        self,
        main_memory,
        capacity,
        block_size,
        associativity,
        write_hit_policy,
        write_miss_policy,
        eviction_policy,
        ADDRESS_SIZE,
        WORD_SIZE,
        BYTE_OFFSET,
    ):
        self.TOTAL_ACCESS = 0
        self.ADDRESS_SIZE = ADDRESS_SIZE
        self.WORD_SIZE = WORD_SIZE
        self.BYTE_OFFSET = BYTE_OFFSET
        self.main_memory = main_memory
        self.write_policy = write_hit_policy
        self.write_allocate = write_miss_policy
        self.eviction_policy = eviction_policy
        self.total_blocks = capacity // block_size
        total_sets = self.total_blocks // associativity
        self.associativity = associativity
        self.block_size = block_size

        self.set_bits = math.ceil(math.log2(total_sets))
        self.block_offset = math.ceil(math.log2(block_size // (WORD_SIZE // 8)))
        self.tag_bits = (
            self.ADDRESS_SIZE - self.set_bits - self.block_offset - self.BYTE_OFFSET
        )

        self.cache = [CacheSet(associativity) for _ in range(total_sets)]
        self.cold_start = set()
        self.fully = OrderedDict()
        self.miss_type = ""
        self.dirty_evictions = 0
        self.compulsory_misses = 0
        self.conflict_misses = 0
        self.capacity_misses = 0

    def read_cache(self, addr):
        self.TOTAL_ACCESS += 1
        set_no, tag_no, block_no, miss_type = self.decode_addr(addr)
        if self.eviction_policy == "LRU":
            hit, data = self.LRU_find(
                set_no, tag_no, block_no, write_data=None, write=None
            )
        if self.eviction_policy == "PLRU":
            hit, data = self.PLRU_find(
                set_no, tag_no, block_no, write_data=None, write=None
            )

        if hit == True:
            return (hit, data, set_no, tag_no, None)
        data = self.get_data_memory(
            addr, set_no, tag_no, block_no, write_data=None, write=False
        )
        return (hit, data, set_no, tag_no, miss_type)

    def write_cache(self, addr, new_data):
        self.TOTAL_ACCESS += 1
        set_no, tag_no, block_no, miss_type = self.decode_addr(addr)
        if self.eviction_policy == "LRU":
            hit, data = self.LRU_find(set_no, tag_no, block_no, new_data, write=True)
        if self.eviction_policy == "PLRU":
            hit, data = self.PLRU_find(set_no, tag_no, block_no, new_data, write=True)

        block_addr = addr >> (self.BYTE_OFFSET + self.block_offset)
        if hit == True:
            # if write-through policy is used, on cache hit write data to main memory too
            if self.write_policy == "write_through":
                self.main_memory.write_mm(
                    block_addr, block_no, self.block_size, new_data, 0
                )
            return hit, set_no, tag_no, None
        # in case of write-allocate
        if self.write_allocate == "yes":
            self.get_data_memory(addr, set_no, tag_no, block_no, new_data, write=True)
            return hit, set_no, tag_no, miss_type
        # in case of write-not-allocate directly write to main memory
        self.main_memory.write_mm(block_addr, block_no, self.block_size, new_data, 0)
        return hit, set_no, tag_no, miss_type

    def LRU_find(self, set_no, tag_no, block_no, write_data, write):
        if tag_no in self.cache[set_no].ways:
            self.cache[set_no].ways.move_to_end(tag_no, last=False)
            if write:
                self.cache[set_no].ways[tag_no].data[block_no] = write_data
                self.cache[set_no].ways[tag_no].dirty = 1
            return (True, self.cache[set_no].ways[tag_no].data[block_no])
        return (False, None)

    def PLRU_find(self, set_no, tag_no, block_no, write_data, write):
        for line_no, line in enumerate(self.cache[set_no].plru_set):
            if line != None and line.tag == tag_no:
                if write:
                    self.cache[set_no].plru_set[line_no].data[block_no] = write_data
                    self.cache[set_no].plru_set[line_no].dirty = 1
                # update plru_bits
                line_no = line_no + self.associativity - 1
                parent = (line_no - 1) // 2
                while parent >= 0:
                    if line_no % 2 == 0:
                        self.cache[set_no].plru_bits[parent] = 1
                    else:
                        self.cache[set_no].plru_bits[parent] = 0
                    line_no = parent
                    parent = (parent - 1) // 2
                return (True, line.data[block_no])
        return (False, None)

    def get_data_memory(self, addr, set_no, tag_no, block_no, write_data, write):

        block_addr = addr >> (self.BYTE_OFFSET + self.block_offset)
        # get a block of data from memory
        data = self.main_memory.read_mm(block_addr, self.block_size)
        # update this data as most recently used in eviction_policy
        if self.eviction_policy == "LRU":
            self.LRU_load(set_no, tag_no, block_no, data, write_data, write)
        if self.eviction_policy == "PLRU":
            self.PLRU_load(set_no, tag_no, block_no, data, write_data, write)

        return data[block_no]

    def LRU_load(self, set_no, tag_no, block_no, data, write_data, write):
        if len(self.cache[set_no].ways) == self.associativity:
            self.dirty_evictions += 1
            evicted_tag, evicted_line = self.cache[set_no].ways.popitem(last=True)
            # if cache line is dirty and write_back policy is used then write evicted data to memory
            if evicted_line.dirty == 1 and self.write_policy == "write_back":
                block_addr = (evicted_tag << self.set_bits) | set_no
                self.main_memory.write_mm(
                    block_addr, block_no, self.block_size, evicted_line.data, 1
                )
        new_line = CacheLine(self.block_size)
        new_line.valid = 1
        new_line.tag = tag_no
        new_line.data = data.copy()
        if write:
            new_line.data[block_no] = write_data
        self.cache[set_no].ways[tag_no] = new_line
        self.cache[set_no].ways.move_to_end(tag_no, last=False)

    def PLRU_load(self, set_no, tag_no, block_no, data, write_data, write):
        load_at = None
        for line_no, line in enumerate(self.cache[set_no].plru_set):
            if line is None:
                load_at = line_no
                break
        if load_at is None:
            i = 0
            while i < (self.associativity - 1):
                if self.cache[set_no].plru_bits[i] == 0:
                    i = 2 * i + 2
                else:
                    i = 2 * i + 1
            load_at = i - (self.associativity - 1)
            evicted_line = self.cache[set_no].plru_set[load_at]
            self.dirty_evictions += 1
            if evicted_line.dirty == 1 and self.write_policy == "write_back":
                block_addr = (evicted_line.tag << self.set_bits) | set_no
                self.main_memory.write_mm(
                    block_addr, block_no, self.block_size, evicted_line.data, 1
                )

        new_line = CacheLine(self.block_size)
        new_line.valid = 1
        new_line.tag = tag_no
        new_line.data = data.copy()
        if write:
            new_line.data[block_no] = write_data
        self.cache[set_no].plru_set[load_at] = new_line
        load_at = load_at + self.associativity - 1
        parent = (load_at - 1) // 2
        while parent >= 0:
            if load_at % 2 == 0:
                self.cache[set_no].plru_bits[parent] = 1
            else:
                self.cache[set_no].plru_bits[parent] = 0
            load_at = parent
            parent = (parent - 1) // 2

    def decode_addr(self, addr):
        tag_no = addr >> (self.set_bits + self.block_offset + self.BYTE_OFFSET)
        set_no = (addr >> (self.block_offset + self.BYTE_OFFSET)) & (
            (1 << self.set_bits) - 1
        )
        block_no = (addr >> self.BYTE_OFFSET) & ((1 << self.block_offset) - 1)
        block_addr = addr >> (self.block_offset + self.BYTE_OFFSET)
        if block_addr not in self.cold_start:
            miss_type = "compulsory"
            self.compulsory_misses += 1
        elif block_addr not in self.fully:
            self.capacity_misses += 1
            miss_type = "capacity"
        else:
            self.conflict_misses += 1
            miss_type = "conflict"  # add real checking
        self.cold_start.add(block_addr)
        if len(self.fully) == self.total_blocks:
            self.fully.popitem(last=True)
        self.fully[block_addr] = 1
        self.fully.move_to_end(block_addr, last=False)
        return (set_no, tag_no, block_no, miss_type)


""" print cache state ->

    def print_cache(self):
        if eviction_policy == "LRU":
            for i, set in enumerate(self.cache):
                print("set", i)
                for i, (tag, line) in enumerate(set.ways.items()):
                    print("->way", i)
                    print("tag:", tag, "valid:", line.valid, "dirty:", line.dirty)
                    print("data:", line.data)
        if eviction_policy == "PLRU":
            for i, set in enumerate(self.cache):
                print("set", i)
                for i, line in enumerate(set.plru_set):
                    if line == None:
                        print("empty", "\n")
                        continue
                    print("->way", i)
                    print("tag:", line.tag, "valid:", line.valid, "dirty:", line.dirty)
                    print("data:", line.data, "\n")
"""


capacity = int(config["CACHE_L1"]["capacity"])
block_size = int(config["CACHE_L1"]["block_size"])
associativity = int(config["CACHE_L1"]["associativity"])
write_policy = config["CACHE_L1"]["write_policy"]
write_allocate = config["CACHE_L1"]["write_allocate"]
eviction_policy = config["CACHE_L1"]["eviction_policy"]
address_size = int(config["DRAM"]["address_size"])
word_size = config.getint("DRAM", "word_size")
byte_offset = config.getint("CACHE_L1", "byte_offset")
cache_hit_time = config.getint("CACHE_L1", "hit_time")
cache_miss_time = config.getint("CACHE_L1", "miss_time")
print("--------------------------------")

main_memory = MainMemory()
cache = Cache(
    main_memory,
    capacity,
    block_size,
    associativity,
    write_policy,
    write_allocate,
    eviction_policy,
    address_size,
    word_size,
    byte_offset,
)

with open(args.trace, "r") as file:
    total_hit = 0
    total_miss = 0
    total_access = 0
    total_read = 0
    total_write = 0
    for addr in file:
        op, addr = addr.strip().split()
        addr = int(addr, 16)
        if op == "R":
            total_read += 1
            hit, data, hit_set, hit_tag, miss_type = cache.read_cache(addr)
        else:
            total_write += 1
            hit, hit_set, hit_tag, miss_type = cache.write_cache(
                addr, random.randint(0, 100)
            )
        if hit == True:
            total_hit += 1
            print("HIT ", "addr: ", addr)
            print("set: ", hit_set)
            print("tag: ", hit_tag)
        else:
            total_miss += 1
            print("MISS", "addr: ", addr)
            print("MISS TYPE:", miss_type)
            if op == "W":
                print(f"block fetched from MM to set: {hit_set} tag: {hit_tag}")
        total_access += 1
        print()
    print("-------------------------")
    # cache.print_cache()
    # print("-------------------------")
    hit_rate = total_hit / total_access
    miss_rate = total_miss / total_access
    print("total access:", total_access)
    print("total_read:", total_read)
    print("total_write:", total_write)
    print("total_hit:", total_hit)
    print("total_miss:", total_miss)
    print("dirty_evictions:", cache.dirty_evictions)
    # print("total memory access:", main_memory.TOTAL_ACCESS)
    # print("total cache access:", cache.TOTAL_ACCESS)
    print("compulsory_misses:", cache.compulsory_misses)
    print("conflict_misses:", cache.conflict_misses)
    print("capacity_misses:", cache.capacity_misses)
    print(f"HIT RATE: {hit_rate * 100:.2f}%")
    print(f"MISS RATE: {miss_rate * 100:.2f}%")
    print(f"AMAT: {cache_hit_time + miss_rate * (cache_miss_time):.2f} ns")
