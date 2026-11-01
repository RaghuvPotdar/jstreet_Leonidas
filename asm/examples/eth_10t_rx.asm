# 10BASE-T RX, IEEE Manchester INM, 6 clocks/bit, uio[6] (pin 14).
# REL 32 lets the testbench start the wire 2 clocks before first INM
# (2-flop sample). 8 bits LSB first into R0.

.equ RX,   0xEE
.equ BIT,  6
.equ WAIT, 32

    LDI   R1, RX
    LDI   R3, BIT
    LDI   R0, 0
    LDI   R4, 8
    LDI   R5, WAIT
    REL   R1, R5
loop:
    INM   R1, R0, R3
    DJNZ  R4, loop
    HALT
