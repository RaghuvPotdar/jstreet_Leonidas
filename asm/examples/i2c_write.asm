# I2C controller write to 7-bit address 0x50, data 0xB1, MSB first.
# SDA=uio[2], SCL=uio[3]. Use external pull-ups on both lines.
# PSET only drives low. REL lets the pull-ups drive high.
# After each byte, wait for SCL to rise and branch on the target's ACK.
# A NACK ends the transaction with STOP. A target holding SCL low
# indefinitely keeps the controller waiting.
#
# Short pulse lengths match the cocotb simulation fixture.

.equ SDA, 0xAA
.equ SCL, 0xBB
.equ SETUP, 4
.equ PHASE, 8
.equ POLL, 1

    LDI  R1, SDA
    LDI  R2, SCL
    LDI  R3, SETUP
    LDI  R4, PHASE
    LDI  R5, POLL
    PSET R1, 0, R4
    PSET R2, 0, R4

    # Address byte 0xA0 (address and write bit).
    REL  R1, R3
    REL  R2, R4
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    PSET R2, 0, R4
    REL  R1, R3
    REL  R2, R4
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    PSET R2, 0, R4

    REL  R1, R3
stretch_data:
    REL  R2, R5
    JL   R2, stretch_data
    JL   R1, data
    PSET R2, 0, R3
    PSET R1, 0, R3
    REL  R2, R4
    REL  R1, R3
    HALT

data:
    PSET R2, 0, R4

    # Data byte 0xB1.
    REL  R1, R3
    REL  R2, R4
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    PSET R2, 0, R4
    REL  R1, R3
    REL  R2, R4
    PSET R2, 0, R4
    REL  R1, R3
    REL  R2, R4
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    PSET R2, 0, R4
    REL  R1, R3
    REL  R2, R4
    PSET R2, 0, R4

    REL  R1, R3
stretch_stop:
    REL  R2, R5
    JL   R2, stretch_stop
    JL   R1, stop
    PSET R2, 0, R3
    PSET R1, 0, R3
    REL  R2, R4
    REL  R1, R3
    HALT

stop:
    PSET R2, 0, R4
    PSET R1, 0, R3
    REL  R2, R4
    REL  R1, R3
    HALT
