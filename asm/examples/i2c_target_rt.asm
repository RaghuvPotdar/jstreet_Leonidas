# I2C target at 7-bit address 0x50 with a live host reply.
# Write 0xA0, D: the target ACKs, receives D with IN, and CAPs it.
# Then repeated START, read 0xA1: the target ACKs and stretches SCL. The
# host reads D through the pull handshake, puts the reply on ui_in, and
# pulls READY (uio5) low. LDH loads the reply. ODO drives bit 7 while SCL
# is still low, then SCL is released. Bits 6..0: wait for SCL high (JL
# poll, so a rise right at the release is not missed), then low, then ODO.
# After 8 bits SDA is released for the controller ACK/NACK.
# If READY does not come before the DJNZ timeout, the reply is 0xFF.
# Address mismatch: no ACK, back to idle. The target never drives high.
#
# SDA=uio2, SCL=uio3, READY=uio5. IN shifts LSB first: rxp holds D
# bit-reversed. Host pins (HCFG): data uo0..uo7, n=8. Strobe pin 15.
# Request uio6. Program rules: host holds ui_in stable >= 2 clocks
# before READY falls; the controller changes SDA only while SCL is low.
.equ SDA, 0xAA
.equ SCL, 0xBB
.equ RDY, 0xDD
.equ Z, 0x88

    LDI  R1, 0xFF
    LDI  R2, 0x00
    LDI  R3, 0xF6
    HCFG R1, R2, R3
    LDI  R1, SDA
    LDI  R2, SCL
    LDI  R3, 1
    LDI  R5, RDY
    LDI  R7, Z

idle:                       # START: SDA falls while SCL is high
    JL   R1, idle
    JL   R2, idle
sw:
    JL   R2, idle
    JL   R1, start
    JL   R7, sw

start:
    INW  R2, R6, R3         # SCL falls after START
    INW  R2, R6, R3         # bit 7 = 1
    JL   R1, idle
    INW  R2, R6, R3
    INW  R2, R6, R3         # bit 6 = 0
    JL   R1, b6
    JL   R7, idle
b6:
    INW  R2, R6, R3
    INW  R2, R6, R3         # bit 5 = 1
    JL   R1, idle
    INW  R2, R6, R3
    INW  R2, R6, R3         # bit 4 = 0
    JL   R1, b4
    JL   R7, idle
b4:
    INW  R2, R6, R3
    INW  R2, R6, R3         # bit 3 = 0
    JL   R1, b3
    JL   R7, idle
b3:
    INW  R2, R6, R3
    INW  R2, R6, R3         # bit 2 = 0
    JL   R1, b2
    JL   R7, idle
b2:
    INW  R2, R6, R3
    INW  R2, R6, R3         # bit 1 = 0
    JL   R1, b1
    JL   R7, idle
b1:
    INW  R2, R6, R3
    INW  R2, R6, R3         # R/W
    JL   R1, write
                            # read: ACK, stretch, wait for the host reply
    INW  R2, R6, R3
    PSET R1, 0, R3
    INW  R2, R6, R3
    INW  R2, R6, R3
    PSET R2, 0, R3          # hold SCL low
    REL  R1, R3
    LDI  R6, 0
rdy:
    JL   R5, reply
    DJNZ R6, rdy
    REL  R2, R3             # timeout: SDA stays released, reply 0xFF
    LDI  R4, 8
tmo:
    JL   R2, tmo            # SCL high (the controller may wait on our release)
    INW  R2, R6, R3         # SCL falls
    DJNZ R4, tmo
    JL   R7, ackc
reply:
    LDH
    ODO  R1, R3             # bit 7 while SCL is still low
    REL  R2, R3
    LDI  R4, 7
tb:
    JL   R2, tb             # wait for SCL high, then for the fall
    INW  R2, R6, R3
    ODO  R1, R3             # bits 6..0 while SCL is low
    DJNZ R4, tb
tb0:
    JL   R2, tb0
    INW  R2, R6, R3
    REL  R1, R3
ackc:
    INW  R2, R6, R3         # controller ACK/NACK clock
    INW  R2, R6, R3
    JL   R7, idle

write:
    INW  R2, R6, R3
    PSET R1, 0, R3          # ACK address
    INW  R2, R6, R3
    INW  R2, R6, R3
    REL  R1, R3
    LDI  R4, 8
d:
    INW  R2, R6, R3
    IN   R1, R0, R3
    INW  R2, R6, R3
    DJNZ R4, d
    CAP  R0
    PSET R1, 0, R3          # ACK data
    INW  R2, R6, R3
    INW  R2, R6, R3
    REL  R1, R3
    JL   R7, idle
