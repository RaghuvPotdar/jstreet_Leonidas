# UART TX: byte 0xB1 on pin 1, 16 clocks per level, LSB first.
# R0 = shift register, R1 = loop count.
.equ TX, 1
.equ BIT, 16

    LDI  R0, 0xB1
    PSET TX, 0, BIT
    LDI  R1, 8
loop:
    OUT  TX, BIT
    DJNZ R1, loop
    PSET TX, 1, BIT
    HALT
