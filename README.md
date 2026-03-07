Here is a **short, clean README** suitable for GitHub.

---

# Cache Simulator

A configurable **CPU cache simulator** implemented in Python. The simulator models a set-associative cache with configurable parameters including block size, associativity, write policies, and eviction policies. It supports both **True LRU** and **Tree-based Pseudo-LRU (PLRU)** replacement strategies.

## Features

* Configurable cache parameters:

  * Cache capacity (in words)
  * Block size
  * Associativity
* Write policies:

  * **Write-through**
  * **Write-back**
* Write miss policies:

  * **Write-allocate**
  * **Write-around**
* Replacement policies:

  * **True LRU** (using `OrderedDict`)
  * **Tree-based Pseudo-LRU**
* Lazy main memory implementation
* Tracks:

  * Hit rate
  * Miss rate
  * Effective Memory Access Time (EMAT)

## Cache Design

The simulator models a **32-bit byte-addressable architecture**.

Address fields:

```
| tag | set index | block offset | byte offset |
```

* Word size: **4 bytes**
* Byte offset: **2 bits**

Each cache line contains:

* valid bit
* dirty bit
* tag
* block data

## Replacement Policies

### True LRU

Implemented using Python's `OrderedDict`. Cache lines are reordered on every access to track recency.

### Pseudo-LRU (Tree PLRU)

Uses a **binary tree of (N−1) bits** for an N-way set to approximate LRU with lower metadata overhead.

Each set contains:

* `plru_set` → cache lines
* `plru_bits` → tree bits used for victim selection

## Main Memory Model

Main memory is implemented as a **lazy dictionary of blocks**.
Blocks are only created when accessed, and their data is initialized with random values.

## Input Trace Format

Memory access traces are read from `addr_file.txt`.

Format:

```
R <address>
W <address>
```

Example:

```
R 0
R 4
W 8
R 16
```

Addresses are **byte addresses**.

## Running the Simulator

Run the program and provide configuration parameters when prompted:

```
cache capacity (no. of words cache stores) =
block size (no. of words per block) =
associativity =
write hit policy (0->write-through 1->write-back) =
write miss policy (0->write-allocate 1->write-around) =
eviction policy (0->True-LRU 1->Pseudo-LRU) =
```

Example configuration:

```
capacity = 64
block size = 4
associativity = 2
write hit policy = 1
write miss policy = 0
eviction policy = 1
```

## Output

For each access the simulator prints:

* HIT / MISS
* accessed address
* set index
* tag

At the end it reports:

* Hit rate
* Miss rate
* Effective Memory Access Time (EMAT)
* 
Default latencies used:
```
Cache access time = 1 ns
Main memory access time = 90 ns
```
