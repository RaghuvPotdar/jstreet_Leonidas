# I2C controller read from 7-bit address 0x50 (0xA1 on the wire).
# START, address, read byte 1 (ACK), read byte 2 (NACK), repeated START,
# address again, read byte 3 (NACK), STOP. Each byte goes to rxp by CAP
# and the host reads it with the pull handshake.
# SDA=uio2, SCL=uio3, external pull-ups. PSET only drives low; REL and
# ODO release. After each SCL release the program polls SCL (stretch).
# The host holds 0xA1 on ui_in from the start; LDH loads it for ODO.
# IN shifts LSB first: rxp holds each wire byte bit-reversed.
#
# Host pins (HCFG): data uo0..uo7, n=8. Strobe pin 15. Request uio6.
.equ SDA, 0xAA
.equ SCL, 0xBB
.equ SETUP, 4
.equ PHASE, 8
.equ POLL, 1

    LDI  R1, 0xFF
    LDI  R2, 0x00
    LDI  R3, 0xF6
    HCFG R1, R2, R3
    LDI  R1, SDA
    LDI  R2, SCL
    LDI  R3, SETUP
    LDI  R4, PHASE
    LDI  R5, POLL
    LDH
    PSET R1, 0, R4          # START
    PSET R2, 0, R4

    LDI  R6, 8
abit:
    ODO  R1, R3
    REL  R2, R5
apoll:
    JL   R2, apoll
    REL  R2, R4
    PSET R2, 0, R4
    DJNZ R6, abit
    REL  R1, R3             # target ACK?
    REL  R2, R5
akp:
    JL   R2, akp
    JL   R1, acked
    PSET R2, 0, R4          # NACK: STOP
    PSET R1, 0, R3
    REL  R2, R4
    REL  R1, R3
    HALT

acked:
    PSET R2, 0, R4
    LDI  R6, 8
r1:
    REL  R2, R5
r1p:
    JL   R2, r1p
    IN   R1, R0, R4
    PSET R2, 0, R4
    DJNZ R6, r1
    CAP  R0
    PSET R1, 0, R3          # ACK byte 1
    REL  R2, R5
k1p:
    JL   R2, k1p
    REL  R2, R4
    PSET R2, 0, R4
    REL  R1, R3

    LDI  R6, 8
r2:
    REL  R2, R5
r2p:
    JL   R2, r2p
    IN   R1, R0, R4
    PSET R2, 0, R4
    DJNZ R6, r2
    CAP  R0
    REL  R2, R5             # NACK byte 2 (SDA stays released)
k2p:
    JL   R2, k2p
    REL  R2, R4
    PSET R2, 0, R4

    REL  R1, R3             # repeated START
    REL  R2, R5
srp:
    JL   R2, srp
    REL  R2, R4
    PSET R1, 0, R4
    PSET R2, 0, R4
    LDH
    LDI  R6, 8
a2bit:
    ODO  R1, R3
    REL  R2, R5
a2p:
    JL   R2, a2p
    REL  R2, R4
    PSET R2, 0, R4
    DJNZ R6, a2bit
    REL  R1, R3
    REL  R2, R5
a2k:
    JL   R2, a2k
    JL   R1, acked2
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    REL  R1, R3
    HALT

acked2:
    PSET R2, 0, R4
    LDI  R6, 8
r3:
    REL  R2, R5
r3p:
    JL   R2, r3p
    IN   R1, R0, R4
    PSET R2, 0, R4
    DJNZ R6, r3
    CAP  R0
    REL  R2, R5             # NACK byte 3
k3p:
    JL   R2, k3p
    REL  R2, R4
    PSET R2, 0, R4

    PSET R1, 0, R3          # STOP
    REL  R2, R5
stp:
    JL   R2, stp
    REL  R2, R4
    REL  R1, R3
    HALT
