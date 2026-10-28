# 10BASE-T TX, looped. IEEE Manchester OUTM, 6 clocks/bit, pin 6.
# Payload is in dmem (host strobe 11 before start). One OUTM per bit.
# Inner DJNZ shifts one byte; outer DJNZ walks dmem. Same 27-byte runt as
# eth_10t.asm (preamble/SFD/frame/FCS). Byte-boundary LD may stretch 1 clock.
# R0 shifter, R1 pins, R2 bit count, R3 duration, R4 nbytes, R5 dmem ptr.

.equ PINS, 0x66
.equ BIT,  6
.equ N,    27

    LDI   R1, PINS
    LDI   R3, BIT
    LDI   R5, 0
    LDI   R4, N
byte:
    LD    R0, [R5]
    LDI   R2, 8
bits:
    OUTM  R1, R0, R3
    DJNZ  R2, bits
    DJNZ  R4, byte
    HALT
