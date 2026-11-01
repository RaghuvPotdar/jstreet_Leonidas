# UART RX: byte 0xB1 on uio[2] (pin 10), 16 clocks/bit, LSB first.
# JL waits for start (low). REL waits; does not drive the RX pad.
# IN samples pin1 (2-flop), shifts into R0, holds BIT.

.equ RX,   0xAA
.equ BIT,  16
.equ HALF, 8

    LDI  R1, RX
    LDI  R3, BIT
    LDI  R4, HALF
    LDI  R0, 0
wait:
    JL   R1, start
    LDI  R6, 2
    DJNZ R6, wait
start:
    REL  R1, R4
    REL  R1, R3
    LDI  R2, 8
loop:
    IN   R1, R0, R3
    DJNZ R2, loop
    HALT
