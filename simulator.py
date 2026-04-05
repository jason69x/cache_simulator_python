import random
import configparser
import argparse
from memory import MainMemory
from bus import Bus
from cache import Cache


def main():

    # parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True, help="Path to config file")
    parser.add_argument("--trace", type=str, required=True, help="Path to Trace file")
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
                print("HIT ", "addr: ", addr, " set: ", hit_set, " tag: ", hit_tag)
            else:
                total_miss += 1
                print("MISS", "addr: ", addr, " type:", miss_type)
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
            total_dirty = sum(c.dirty_evictions for c in cores)
            output.write(f"Dirty Evictions: {total_dirty}\n\n")
            total_misses = {}
            for k in ("compulsory", "conflict", "capacity"):
                total_misses[k] = sum(c.misses_count[k] for c in cores)
            output.write(f"Compulsory Misses: {total_misses["compulsory"]}\n")
            output.write(f"Conflict Misses: {total_misses["conflict"]}\n")
            output.write(f"Capacity Misses: {total_misses["capacity"]}\n\n")
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
                f"Cache-to-Cache Transfers: {bus.bus_stats["cache_2_cache"]}\n\n"
            )

            for core_id, cache in enumerate(cores):
                output.write(f"--- Core {core_id} --- \n\n")
                output.write(cache.__str__())
                output.write("\n\n")


if __name__ == "__main__":
    main()
