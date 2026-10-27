# USB Full-Speed ACK. Same shape as LS; J bit is 1, durations 5 / 10.
# Inter-byte LDI does not fit in a 5-clock hold; last OUT of SYNC uses
# R6=4 so the sticky tail restores 5.

.equ PINS, 0x54
.equ BIT,  5
.equ GAP,  4
.equ SE0,  10

    LDI   R1, PINS
    LDI   R3, BIT
    LDI   R5, SE0
    LDI   R6, GAP
    LDI   R0, 0x01
    OUT   R1, R0, R6
    LDI   R0, 0x2A
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R6
    LDI   R0, 0x1B
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    OUT   R1, R0, R3
    PSET  R1, 0, R5
    LDI   R0, 0x01
    OUT   R1, R0, R3
    HALT
