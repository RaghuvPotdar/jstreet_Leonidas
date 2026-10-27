# SPI mode 0: 0xB1 MSB first on the wire -> LDI R0 with 0x8D.
# R0 = shifter, R1 = loop. Descriptors in R2/R3/R4, durations in R5/R6/R7.
.equ CS,   0x22
.equ SCK,  0x33
.equ MOSI, 0x44

    LDI  R2, CS
    LDI  R3, SCK
    LDI  R4, MOSI
    LDI  R5, 1
    LDI  R6, 8
    LDI  R7, 4
    LDI  R0, 0x8D
    PSET R3, 0, R5
    PSET R2, 0, R5
    LDI  R1, 8
bit:
    OUT  R4, R0, R7
    PSET R3, 1, R6
    PSET R3, 0, R6
    DJNZ R1, bit
    PSET R2, 1, R5
    HALT
