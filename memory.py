from random import randint


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
        self.blocks[block_addr] = [randint(0, 100) for i in range(block_size)]
        return self.blocks[block_addr]

    def write_block(self, block_addr, data_block):
        self.TOTAL_ACCESS += 1
        self.blocks[block_addr] = data_block

    def write_word(self, block_addr, block_no, block_size, dataword):
        self.TOTAL_ACCESS += 1
        if block_addr in self.blocks:
            self.blocks[block_addr][block_no] = dataword
            return
        self.blocks[block_addr] = [randint(0, 100) for i in range(block_size)]
        self.blocks[block_addr][block_no] = dataword
