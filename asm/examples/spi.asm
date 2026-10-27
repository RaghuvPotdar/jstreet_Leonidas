# SPI mode 0: 0xB1 MSB first on the wire -> LDI R0 with 0x8D.
# R0 = shifter, R1 = loop count.
.equ CS, 2
.equ SCK, 3
.equ MOSI, 4

    LDI  R0, 0x8D
    PSET SCK, 0, 1
    PSET CS, 0, 1
    LDI  R1, 8
bit:
    OUT  MOSI, 4
    PSET SCK, 1, 8
    PSET SCK, 0, 8
    DJNZ R1, bit
    PSET CS, 1, 1
    HALT
