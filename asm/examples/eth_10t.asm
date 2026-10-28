# 10BASE-T TX. IEEE Manchester, OUTM, 6 clocks/bit at 60 MHz.
# TD+=pin6, TD-=pin7 (descriptor 0x76). R0 shifter, R1 pins, R3 duration.
# Preamble 7*0x55, SFD 0xD5, then runt frame (no 64-byte pad):
#   dest ff:ff:ff:ff:ff:ff  src 02:00:00:00:00:01  type 88b5  data 42
#   FCS little-endian (IEEE CRC32).
# Unrolled LDI+OUTM so halves stay on the 3-clock grid. RX is not in silicon.

.equ PINS, 0x76
.equ BIT,  6

    LDI   R1, PINS
    LDI   R3, BIT
    LDI   R0, 0x55
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x55
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x55
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x55
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x55
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x55
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x55
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0xD5
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0xFF
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0xFF
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0xFF
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0xFF
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0xFF
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0xFF
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x02
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x00
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x00
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x00
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x00
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x01
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x88
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0xB5
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x42
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0xDB
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0xC4
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x8F
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    LDI   R0, 0x7C
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    OUTM  R1, R0, R3
    HALT
