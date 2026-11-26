# SPI mode 0 controller, full duplex, one byte each way, MSB first.
# CS=uo2, SCK=uo3, MOSI=uo4, MISO=uio2 (pin 10).
# Per bit: OUT MOSI (SCK low), PSET SCK high, IN MISO (sample while SCK
# is high), PSET SCK low. CAP after 8 bits puts the MISO byte in rxp.
# OUT and IN shift LSB first: MOSI loads 0xB1 bit-reversed (0x8D), and
# rxp holds the MISO wire byte bit-reversed. The host reverses it.
#
# Host pins (HCFG): data uo0, uo1, uo5, uo6, n=4. Strobe uo7. Request uio7.
.equ CS,   0x22
.equ SCK,  0x33
.equ MOSI, 0x44
.equ MISO, 0xAA
.equ T,    4

    LDI  R0, 0x63
    LDI  R1, 0x00
    LDI  R7, 0x77
    HCFG R0, R1, R7
    LDI  R2, CS
    LDI  R3, SCK
    LDI  R4, MOSI
    LDI  R5, MISO
    LDI  R6, T
    LDI  R0, 0x8D
    LDI  R1, 8
    PSET R3, 0, R6
    PSET R2, 0, R6
bit:
    OUT  R4, R0, R6
    PSET R3, 1, R6
    IN   R5, R7, R6
    PSET R3, 0, R6
    DJNZ R1, bit
    CAP  R7
    PSET R2, 1, R6
    HALT
