import math
import random


class CacheLine:
    def __init__(self, block_size):
        self.valid = 0
        self.tag = None
        self.data = [0] * block_size


class CacheSet:
    def __init__(self, block_size, associativity):
        self.use = 0
        self.ways = [CacheLine(block_size) for l in range(associativity)]


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
        hit, data = self.comparator(self.cache[set_no], tag_no, block_no)

        if hit == True:
            return (hit, data)
        data = self.get_data_memory(set_no, tag_no, block_no)
        return (hit, data)

    def comparator(self, cache_set, tag_no, block_no):

        for way_no, way in enumerate(cache_set.ways):
            if way.valid == 0:
                continue
            if way.tag == tag_no:
                if self.associativity > 1:
                    cache_set.use = 1 if way_no >= self.associativity // 2 else 0
                return (True, way.data[block_no])

        return (False, None)

    def get_data_memory(self, set_no, tag_no, block_no):

        data = [random.randint(0, 100) for r in range(self.block_size)]
        if self.associativity == 1:
            evict_way = 0
        elif self.associativity > 2:
            if self.cache[set_no].use == 0:
                evict_way = random.randint(0, self.associativity // 2 - 1)
                self.cache[set_no].use = 1
            else:
                evict_way = random.randint(
                    self.associativity // 2, self.associativity - 1
                )
                self.cache[set_no].use = 0
        else:
            evict_way = self.cache[set_no].use
            self.cache[set_no].use = 0 if self.cache[set_no].use == 1 else 1

        self.cache[set_no].ways[evict_way].valid = 1
        self.cache[set_no].ways[evict_way].tag = tag_no
        self.cache[set_no].ways[evict_way].data = data

        return data[block_no]


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
        hit, data = cache.get_data(addr)
        if hit == True:
            total_hit += 1
            print("HIT ", "addr: ", addr)
            print("data: ", data)
        else:
            total_miss += 1
            print("MISS", "addr: ", addr)
            print("data MM: ", data)
        total_access += 1
        print()
    print("-------------------------")
    print("HIT RATE: ", (total_hit / total_access) * 100, "%")
    print("MISS RATE: ", (total_miss / total_access) * 100, "%")
