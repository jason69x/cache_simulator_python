# Cache Coherence Simulator

A multi-core L1 cache simulator with MOESI coherence protocol, configurable eviction policies (LRU, PLRU, FIFO, Random), and write strategies (write-back/through, allocate/no-allocate).

## Usage

```bash
python simulator.py --config config.ini --trace trace.txt
```

Results are printed to stdout and saved to `output.txt`.

## Trace Format

```
<core_id> <R|W> <hex_address>
```

```
0 R 0x00000000
1 W 0x000000A4
```

## Configuration

Edit `config.ini` to change cache capacity, block size, associativity, write policy, eviction policy, and DRAM timing.
