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
        found_data = None
        for cache in self.caches:
            if cache.id == id:
                continue
            data = cache.snoop(set_no, tag_no, "write")
            if data:
                self.bus_stats["invalidations"] += 1
                if found_data is None:
                    found_data = data
        if found_data:
            self.bus_stats["cache_2_cache"] += 1
            self.bus_stats["interventions"] += 1
            return found_data, "M"

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
