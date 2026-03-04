import math

capacity = int(input("cache capacity (no. of words cache stores) : "))
block_size = int(input("block size (no. of words per block): "))
associativity = int(input("associativity: "))


class CacheLine:
    def __init__(self, block_size):
        self.valid = 0
        self.tag = None
        self.data = [0] * block_size


class CacheSet:
    def __init__(self, block_size, associativity):
        self.use = None
        self.ways = [CacheLine(block_size)] * associativity


class Cache:
    ADDRESS_SIZE = 32
    WORD_SIZE = 32
    BYTE_OFFSET = 2  # two bits, 1 word = 4 bytes of data
    ADDR_FILE = "addr_file.txt"  # assumes each address is a 32-bit unsigned integer

    def __init__(self, capacity, block_size, associativity):
        total_blocks = capacity // block_size
        total_sets = total_blocks // associativity

        self.set_bits = math.ceil(math.log2(total_sets))
        self.block_offset = math.ceil(math.log2(associativity))
        self.tag_bits = ADDRESS_SIZE - set_bits - block_offset - BYTE_OFFSET

        self.cache = [CacheSet(associativity) for _ in range(total_sets)]

    def get_data(self, addr):
        tag_no = addr >> (self.set_bits + self.block_offset + BYTE_OFFSET)
        set_no = (addr >> (self.block_offset + BYTE_OFFSET)) & (
            (1 << self.set_bits) - 1
        )
        block_no = (addr >> BYTE_OFFSET) & ((1 << self.block_offset) - 1)
        hit, data = comparator(self.cache[set_no], tag_no, block_no)

    def comparator(self, cache_set, tag_no, block_no):

        for way_no, way in enumerate(cache_set.ways):
            if way.valid == 0:
                continue
            if way.tag == tag_no:
                cache_set.use = 1 if way_no >= associativity // 2 else 0
                return (True, way.data[block_no])
        return (False, None)
