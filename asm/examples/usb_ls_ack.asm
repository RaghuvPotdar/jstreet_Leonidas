# USB Low-Speed ACK on D+=pin4, D-=pin5 (descriptor 0x54: two pin nibbles).
# At 60 MHz: bit = 40 clocks, SE0 = 80 clocks.
# R0 = line levels (R0[0]=D+), R1 = pins, R3 = bit, R5 = SE0.

.equ PINS, 0x54
.equ BIT,  40
.equ SE0,  80

    LDI   R1, PINS
    LDI   R3, BIT
    LDI   R5, SE0
    LDI   R0, 0x00
    OUT   R1, R0, R3
    LDI   R0, 0xD5
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    LDI   R0, 0xE4
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    PSET  R1, 0, R5
    LDI   R0, 0x00
    OUT   R1, R0, R3
    HALT
