# USB Full-Speed ACK handshake on uo_out[5]=D+, uo_out[6]=D-.
# At 60 MHz: bit = 5 clocks, SE0 = 10 clocks (two bit times).
#
# FS idle J: D+=1 D-=0. K: D+=0 D-=1. SE0: both 0.
# Same NRZI line-state stream as LS, flipped J/K polarity:
#   establish J, SYNC KJKJKJKK, PID ACK -> JJKJJKKK, EOP SE0 SE0 J.

.equ DP, 5
.equ DM, 6

    LDI   R4, 5
    LDI   R5, 10

    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 0, 0, R5
    PSETH DP, DM, 1, 0, R4
    HALT
