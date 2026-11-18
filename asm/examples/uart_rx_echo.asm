# UART RX echo. Receive a byte on uio[2] (pin 10), send it back on
# uo[1] (pin 1). 16 clocks/bit, LSB first, 3 bytes then HALT.
# INW waits for the start edge, then holds one bit. Each IN then samples
# mid-bit (Rd>>1 = 8) of the next 16-clock bit.

.equ RX,  0xAA
.equ TX,  0x11
.equ BIT, 16

    LDI  R1, RX
    LDI  R5, TX
    LDI  R3, BIT
    LDI  R6, 3
byte:
    LDI  R2, 8
    INW  R1, R7, R3
bits:
    IN   R1, R0, R3
    DJNZ R2, bits
    LDI  R2, 8
    PSET R5, 0, R3
echo:
    OUT  R5, R0, R3
    DJNZ R2, echo
    PSET R5, 1, R3
    DJNZ R6, byte
    HALT
