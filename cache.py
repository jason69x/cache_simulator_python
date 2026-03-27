import math
import random
from collections import OrderedDict, deque
import configparser
import argparse


# main memory structure (Lazy structure only stores what is accessed)
# stores blocks of data, block addressable
class MainMemory:

    def __init__(self):
        self.blocks = {}
        self.TOTAL_ACCESS = 0

    def read(self, block_addr, block_size):
        self.TOTAL_ACCESS += 1
        if block_addr in self.blocks:
            return self.blocks[block_addr]
        # create a block with block_size number of random words
        self.blocks[block_addr] = [random.randint(0, 100) for i in range(block_size)]
        return self.blocks[block_addr]

    def write_block(self, block_addr, data_block):
        self.TOTAL_ACCESS += 1
        self.blocks[block_addr] = data_block

    def write_word(self, block_addr, block_no, block_size, dataword):
        self.TOTAL_ACCESS += 1
        if block_addr in self.blocks:
            self.blocks[block_addr][block_no] = dataword
            return
        self.blocks[block_addr] = [random.randint(0, 100) for i in range(block_size)]
        self.blocks[block_addr][block_no] = dataword


class Bus:
    def __init__(self, main_memory):
        self.main_memory = main_memory
        self.caches = []
        self.bus_stats = {
            "reads": 0,
            "writes": 0,
            "upgrades": 0,
            "write_backs": 0,
            "write_through": 0,
            "cache_2_cache": 0,
            "interventions": 0,
            "invalidations": 0,
        }

    def attach_cache(self, cache):
        self.caches.append(cache)

    def RdX(self, id, set_no, tag_no, block_addr, block_size):
        self.bus_stats["reads"] += 1
        for cache in self.caches:
            if cache.id == id:
                continue
            data = cache.snoop(set_no, tag_no, "read")
            if data:
                self.bus_stats["cache_2_cache"] += 1
                self.bus_stats["interventions"] += 1
                return data, "S"
        data = self.main_memory.read(block_addr, block_size)
        return data, "E"

    def WrX(self, id, set_no, tag_no, block_addr, block_size):
        self.bus_stats["writes"] += 1
        for cache in self.caches:
            if cache.id == id:
                continue
            data = cache.snoop(set_no, tag_no, "write")
            if data:
                self.bus_stats["invalidations"] += 1
        if data:
            self.bus_stats["cache_2_cache"] += 1
            self.bus_stats["interventions"] += 1
            return data, "M"

        data = self.main_memory.read(block_addr, block_size)
        return data, "M"

    def WrX_u(self, id, set_no, tag_no):
        self.bus_stats["upgrades"] += 1
        for cache in self.caches:
            if cache.id == id:
                continue
            data = cache.snoop(set_no, tag_no, "write_upgrade")
            if data:
                self.bus_stats["invalidations"] += 1

    def Wb(self, block_addr, line_data):
        self.main_memory.write_block(block_addr, line_data)
        self.bus_stats["write_backs"] += 1

    def Wt(self, block_addr, block_no, block_size, data_word):
        self.main_memory.write_word(block_addr, block_no, block_size, data_word)
        self.bus_stats["write_through"] += 1


# cache line structure
class CacheLine:
    def __init__(self, block_size):
        self.state = "I"
        self.tag = None
        self.data = [0] * block_size


# cache set structure
class CacheSet:
    def __init__(self, associativity):
        self.ways = OrderedDict()  # LRU set
        self.plru_set = [None] * associativity  # PLRU set, stores actual lines
        self.plru_bits = [0] * (
            associativity - 1
        )  # PLRU data structure to find least recently used line
        self.fifo = deque()


# main cache structure
class Cache:

    def __init__(
        self,
        id,
        bus,
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
        self.id = id
        self.TOTAL_ACCESS = 0
        self.ADDRESS_SIZE = ADDRESS_SIZE
        self.WORD_SIZE = WORD_SIZE
        self.BYTE_OFFSET = BYTE_OFFSET
        self.bus = bus
        self.write_policy = write_hit_policy
        self.write_allocate = write_miss_policy
        self.eviction_policy = eviction_policy
        self.total_blocks = capacity // block_size
        total_sets = self.total_blocks // associativity
        self.associativity = associativity
        self.block_size = block_size
        self.capacity = capacity
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
        self.misses_count = {
            "conflict": 0,
            "capacity": 0,
            "compulsory": 0,
        }
        self._find = {
            "LRU": self.LRU_find,
            "FIFO": self.FIFO_find,
            "Random": self.Random_find,
            "PLRU": self.PLRU_find,
        }
        self._load = {
            "LRU": self.LRU_load,
            "FIFO": self.FIFO_load,
            "Random": self.Random_load,
            "PLRU": self.PLRU_load,
        }
        self._search = {
            "LRU": self.LRU_search,
            "FIFO": self.FIFO_search,
            "Random": self.Random_search,
            "PLRU": self.PLRU_search,
        }

    def snoop(self, set_no, tag_no, type):
        return self._search[self.eviction_policy](set_no, tag_no, type)

    def LRU_search(self, set_no, tag_no, type):
        if tag_no in self.cache[set_no].ways:
            state = self.cache[set_no].ways[tag_no].state
            if type == "read":
                if line.state in ("M", "E", "O"):
                    self.cache[set_no].ways[tag_no].state = "O"
                    return self.cache[set_no].ways[tag_no].data

            if type in ("write", "write_upgrade"):
                self.cache[set_no].ways[tag_no].state = "I"
                del self.cache[set_no].ways[tag_no]
                return self.cache[set_no].ways[tag_no].data
        return None

    def PLRU_search(self, set_no, tag_no, type):
        for line_no, line in enumerate(self.cache[set_no].plru_set):
            if line != None and line.tag == tag_no:
                if type == "read":
                    if line.state in ("M", "E", "O"):
                        line.state = "O"
                        return line.data

                if type in ("write", "write_upgrade"):
                    line.state = "I"
                    self.cache[set_no].plru_set[line_no] = None
                    return line.data
        return None

    def Random_search(self, set_no, tag_no, type):
        if tag_no in self.cache[set_no].ways:
            state = self.cache[set_no].ways[tag_no].state
            if type == "read":
                if line.state in ("M", "E", "O"):
                    self.cache[set_no].ways[tag_no].state = "O"
                    return self.cache[set_no].ways[tag_no].data

            if type in ("write", "write_upgrade"):
                self.cache[set_no].ways[tag_no].state = "I"
                del self.cache[set_no].ways[tag_no]
                return self.cache[set_no].ways[tag_no].data
        return None

    def FIFO_search(self, set_no, tag_no, type):
        for line in self.cache[set_no].fifo:
            if line.tag == tag_no:
                if type == "read":
                    if line.state in ("M", "E", "O"):
                        line.state = "O"
                        return line.data

                if type in ("write", "write_upgrade"):
                    line.state = "I"
                    self.cache[set_no].fifo.remove(line)
                    return line.data
        return None

    def read_cache(self, addr):
        self.TOTAL_ACCESS += 1
        set_no, tag_no, block_no, miss_type = self.decode_addr(addr)
        hit, data = self._find[self.eviction_policy](
            set_no, tag_no, block_no, write_data=None, write=False
        )
        if hit:
            return (hit, data, set_no, tag_no, None)

        self.misses_count[miss_type] += 1
        block_addr = addr >> (self.BYTE_OFFSET + self.block_offset)
        data, state = self.bus.RdX(self.id, set_no, tag_no, block_addr, self.block_size)
        self._load[self.eviction_policy](
            set_no, tag_no, block_no, data, state, write_data=None, write=False
        )
        return (hit, data, set_no, tag_no, miss_type)

    def write_cache(self, addr, new_data):
        self.TOTAL_ACCESS += 1
        set_no, tag_no, block_no, miss_type = self.decode_addr(addr)
        hit, data = self._find[self.eviction_policy](
            set_no, tag_no, block_no, new_data, write=True
        )

        block_addr = addr >> (self.BYTE_OFFSET + self.block_offset)
        if hit:
            # if write-through policy is used, on cache hit write data to main memory too
            if self.write_policy == "write_through":
                self.bus.Wt(block_addr, block_no, self.block_size, new_data)
            return hit, set_no, tag_no, None
        self.misses_count[miss_type] += 1
        # in case of write-allocate
        if self.write_allocate == "yes":
            data, state = self.bus.WrX(
                self.id, set_no, tag_no, block_addr, self.block_size
            )
            self._load[self.eviction_policy](
                set_no, tag_no, block_no, data, state, write_data=new_data, write=True
            )
            return hit, set_no, tag_no, miss_type
        # in case of write-not-allocate directly write to main memory
        self.bus.Wt(block_addr, block_no, self.block_size, new_data)
        return hit, set_no, tag_no, miss_type

    def LRU_find(self, set_no, tag_no, block_no, write_data, write):
        if tag_no in self.cache[set_no].ways:
            self.cache[set_no].ways.move_to_end(tag_no, last=False)
            if write:
                if self.cache[set_no].ways[tag_no].state in ("O", "S"):
                    self.bus.WrX_u(self.id, set_no, tag_no)
                self.cache[set_no].ways[tag_no].state = "M"
                self.cache[set_no].ways[tag_no].data[block_no] = write_data
            return (True, self.cache[set_no].ways[tag_no].data[block_no])
        return (False, None)

    def PLRU_find(self, set_no, tag_no, block_no, write_data, write):
        for line_no, line in enumerate(self.cache[set_no].plru_set):
            if line != None and line.tag == tag_no:
                if write:
                    if self.cache[set_no].plru_set[line_no].state in ("O", "S"):
                        self.bus.WrX_u(self.id, set_no, tag_no)
                    self.cache[set_no].plru_set[line_no].state = "M"
                    self.cache[set_no].plru_set[line_no].data[block_no] = write_data
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

    def Random_find(self, set_no, tag_no, block_no, write_data, write):
        if tag_no in self.cache[set_no].ways:
            if write:
                if self.cache[set_no].ways[tag_no].state in ("O", "S"):
                    self.bus.WrX_u(self.id, set_no, tag_no)
                self.cache[set_no].ways[tag_no].state = "M"
                self.cache[set_no].ways[tag_no].data[block_no] = write_data
            return (True, self.cache[set_no].ways[tag_no].data[block_no])
        return (False, None)

    def FIFO_find(self, set_no, tag_no, block_no, write_data, write):
        for line in self.cache[set_no].fifo:
            if line.tag == tag_no:
                if write:
                    if line.state in ("O", "S"):
                        self.bus.WrX_u(self.id, set_no, tag_no)
                    line.state = "M"
                    line.data[block_no] = write_data
                return (True, line.data[block_no])
        return (False, None)

    def LRU_load(self, set_no, tag_no, block_no, data, state, write_data, write):
        if len(self.cache[set_no].ways) == self.associativity:
            evicted_tag, evicted_line = self.cache[set_no].ways.popitem(last=True)
            # if cache line is dirty and write_back policy is used then write evicted data to memory
            if (
                evicted_line.state == "M" or evicted_line.state == "O"
            ) and self.write_policy == "write_back":
                self.dirty_evictions += 1
                block_addr = (evicted_tag << self.set_bits) | set_no
                self.bus.Wb(block_addr, evicted_line.data)
        new_line = self.new_cacheline(state, tag_no, data.copy())
        if write:
            new_line.data[block_no] = write_data
        self.cache[set_no].ways[tag_no] = new_line
        self.cache[set_no].ways.move_to_end(tag_no, last=False)

    def PLRU_load(self, set_no, tag_no, block_no, data, state, write_data, write):
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
            if (
                evicted_line.state == "M" or evicted_line.state == "O"
            ) and self.write_policy == "write_back":
                self.dirty_evictions += 1
                block_addr = (evicted_line.tag << self.set_bits) | set_no
                self.bus.Wb(block_addr, evicted_line.data)

        new_line = self.new_cacheline(state, tag_no, data.copy())
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

    # Load from Main Memory to Random cache
    def Random_load(self, set_no, tag_no, block_no, data, state, write_data, write):
        if len(self.cache[set_no].ways) == self.associativity:
            evicted_tag = random.choice(list(self.cache[set_no].ways))
            evicted_line = self.cache[set_no].ways.pop(evicted_tag)
            # if cache line is dirty and write_back policy is used then write evicted data to memory
            if (
                evicted_line.state == "M" or evicted_line.state == "O"
            ) and self.write_policy == "write_back":
                self.dirty_evictions += 1
                block_addr = (evicted_tag << self.set_bits) | set_no
                self.bus.Wb(block_addr, evicted_line.data)
        new_line = self.new_cacheline(state, tag_no, data.copy())
        if write:
            new_line.data[block_no] = write_data
        self.cache[set_no].ways[tag_no] = new_line

    # Load from Main Memory to FIFO cache
    def FIFO_load(self, set_no, tag_no, block_no, data, state, write_data, write):
        if len(self.cache[set_no].fifo) == self.associativity:
            evicted_line = self.cache[set_no].fifo.popleft()
            evicted_tag = evicted_line.tag
            # if cache line is dirty and write_back policy is used then write evicted data to memory
            if (
                evicted_line.state == "M" or evicted_line.state == "O"
            ) and self.write_policy == "write_back":
                self.dirty_evictions += 1
                block_addr = (evicted_tag << self.set_bits) | set_no
                self.bus.Wb(block_addr, evicted_line.data)
        new_line = self.new_cacheline(state, tag_no, data.copy())
        if write:
            new_line.data[block_no] = write_data
        self.cache[set_no].fifo.append(new_line)

    def new_cacheline(self, state, tag_no, data):
        new_line = CacheLine(self.block_size)
        new_line.state = state
        new_line.tag = tag_no
        new_line.data = data
        return new_line

    # decode the given address to find tag no, set no, block no
    def decode_addr(self, addr):
        tag_no = addr >> (self.set_bits + self.block_offset + self.BYTE_OFFSET)
        set_no = (addr >> (self.block_offset + self.BYTE_OFFSET)) & (
            (1 << self.set_bits) - 1
        )
        block_no = (addr >> self.BYTE_OFFSET) & ((1 << self.block_offset) - 1)

        block_addr = addr >> (self.block_offset + self.BYTE_OFFSET)
        if block_addr not in self.cold_start:
            miss_type = "compulsory"
        elif block_addr not in self.fully:
            miss_type = "capacity"
        else:
            miss_type = "conflict"  # add real checking
        self.cold_start.add(block_addr)
        if len(self.fully) == self.total_blocks:
            self.fully.popitem(last=True)
        self.fully[block_addr] = 1
        self.fully.move_to_end(block_addr, last=False)
        return (set_no, tag_no, block_no, miss_type)

    def print_cache(self):
        if self.eviction_policy in ("LRU", "Random"):
            for set_no, cset in enumerate(self.cache):
                if len(cset.ways):
                    print(f"set {set_no}:")
                    print(cset.ways)
        elif self.eviction_policy == "PLRU":
            for set_no, cset in enumerate(self.cache):
                for line in cset.plru_set:
                    if line:
                        print(f"set: {set_no} tag: {line.tag} -> {line.state}")
        elif self.eviction_policy == "FIFO":
            for set_no, cset in enumerate(self.cache):
                for line in cset.fifo:
                    print(f"set: {set_no} tag: {line.tag} -> {line.state}")


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True, help="Path to config file")
    parser.add_argument("--trace", type=str, required=True, help="Path to Trace file")
    # parser.add_argument("--levels", type=int, help="no. of cache levels")
    args = parser.parse_args()

    # load config
    config = configparser.ConfigParser()
    config.read(args.config)

    MAIN_MEMORY_ACCESS_TIME = config.getint("DRAM", "access_time")
    total_cores = config.getint("CORE", "total_cores")
    coherence_protocol = config.get("CORE", "coherence_protocol")
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

    main_memory = MainMemory()
    bus = Bus(main_memory)
    cores = []

    for i in range(total_cores):

        cache = Cache(
            i,
            bus,
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
        bus.attach_cache(cache)
        cores.append(cache)

    with open(args.trace, "r") as file:
        total_hit = 0
        total_miss = 0
        total_access = 0
        total_read = 0
        total_write = 0
        for addr in file:
            core_id, op, addr = addr.strip().split()
            addr = int(addr, 16)
            core_id = int(core_id)
            if op == "R":
                total_read += 1
                hit, data, hit_set, hit_tag, miss_type = cores[core_id].read_cache(addr)
            else:
                total_write += 1
                hit, hit_set, hit_tag, miss_type = cores[core_id].write_cache(
                    addr, random.randint(0, 100)
                )
            if hit:
                total_hit += 1
                print("HIT ", "addr: ", addr)
                print("set: ", hit_set)
                print("tag: ", hit_tag)
            else:
                total_miss += 1
                print("MISS", "addr: ", addr)
                print("MISS TYPE:", miss_type)
            total_access += 1
            print()
        print("-------------------------")
        hit_rate = total_hit / total_access
        miss_rate = total_miss / total_access
        with open("output.txt", "w") as output:
            output.write("Cache Configuration -> \n\n")
            output.write(f"Number of Cores: {total_cores}\n")
            output.write(f"Cache Size: {cache.capacity//1024} KB\n")
            output.write(f"Block Size: {cache.block_size} B\n")
            output.write(f"Associativity: {cache.associativity}-way\n")
            output.write(f"Replacement: {cache.eviction_policy}\n")
            output.write(f"Write Policy: {cache.write_policy}\n")
            output.write(f"Write Allocate: {cache.write_allocate}\n")
            output.write(f"Coherence Protocol: {coherence_protocol}")
            output.write("\n-----------------------------\n")
            output.write("Statistics -> \n\n")
            output.write(f"Total Accesses: {total_access}\n")
            output.write(f"Reads: {total_read}\n")
            output.write(f"Writes: {total_write}\n\n")
            output.write(f"Hits: {total_hit}\n")
            output.write(f"Misses: {total_miss}\n")
            output.write(f"Dirty Evictions: {cache.dirty_evictions}\n\n")
            output.write(f"Compulsory Misses: {cache.misses_count["compulsory"]}\n")
            output.write(f"Conflict Misses: {cache.misses_count["conflict"]}\n")
            output.write(f"Capacity Misses: {cache.misses_count["capacity"]}\n\n")
            output.write(f"Hit Rate: {hit_rate * 100:.2f}%\n")
            output.write(f"Miss Rate: {miss_rate * 100:.2f}%\n\n")
            output.write(
                f"AMAT: {cache_hit_time + miss_rate * cache_miss_time:.2f} ns\n"
            )
            output.write(f"Coherence Results:\n\n")
            output.write(f"BusRdX: {bus.bus_stats["reads"]}\n")
            output.write(f"BusWrX: {bus.bus_stats["writes"]}\n")
            output.write(f"BusWrXu: {bus.bus_stats["upgrades"]}\n\n")
            output.write(f"Invalidations: {bus.bus_stats["invalidations"]}\n")
            output.write(f"Interventions: {bus.bus_stats["interventions"]}\n")
            output.write(
                f"Cache-to-Cache Transfers: {bus.bus_stats["cache_2_cache"]}\n"
            )

            for core_id, cache in enumerate(cores):
                print(f"Core {core_id}:")
                cache.print_cache()


if __name__ == "__main__":
    main()
