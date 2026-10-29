# SPI mode 0: 0xB1 MSB first on the wire -> LDI R0 with 0x8D.
# R0 = shifter, R1 = loop. Descriptors in R2/R3/R4, durations in R5/R6/R7.
#
# HALF=8 means 8 high and 8 low (16 clocks/bit at 60 MHz). MOSI OUT cannot
# overlap a pin hold, so it sticks SCK low after the low PSET, plus one
# clock for the MOSI pin flop. Compiler:
#   Rd_sck_high = HALF
#   Rd_sck_low  = HALF - MOSI_T - 1
.equ CS,   0x22
.equ SCK,  0x33
.equ MOSI, 0x44
.equ HALF, 8
.equ MOSI_T, 1
.equ LOW,  6

    LDI  R2, CS
    LDI  R3, SCK
    LDI  R4, MOSI
    LDI  R5, 1
    LDI  R6, HALF
    LDI  R7, MOSI_T
    LDI  R0, 0x8D
    PSET R3, 0, R5
    PSET R2, 0, R5
    LDI  R5, LOW
    LDI  R1, 8
bit:
    OUT  R4, R0, R7
    PSET R3, 1, R6
    PSET R3, 0, R5
    DJNZ R1, bit
    PSET R2, 1, R5
    HALT
