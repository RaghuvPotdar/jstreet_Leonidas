# Listings (what the chip does today)

Every protocol below is a **program** on the verbs in [isa.md](isa.md). There is no protocol opcode. RX is `IN` / `INW`: `uart_rx_echo.asm`, `eth_10t_rx_echo.asm`.

Clock target 60 MHz. `Rd` is clocks per level (or per Manchester bit for `OUTM`).

## UART TX — `asm/examples/uart.asm`

- Pin `uo_out[1]`, descriptor `0x11`.
- Idle high. `PSET` low = start, eight `OUT`s LSB first, `PSET` high = stop.
- Byte `LDI R0, 0xB1` (not dmem). `R3 = 16` clocks/bit. Change the immediate to change baud.
- After eight `OUT`s `R0` is 0. The loop stops because `DJNZ` hits 0.

Hex: `0211 0310 00B1 1460 0108 2418 3105 1560 4000`.

## SPI mode 0 TX — `asm/examples/spi.asm`

- CS `uo[2]` (`0x22`), SCK `uo[3]` (`0x33`), MOSI `uo[4]` (`0x44`).
- Byte on the wire is `0xB1` MSB first → `LDI R0, 0x8D` because `OUT` is LSB-first on `Rs[0]`.
- **8 means 8/8.** `HALF=8` high. MOSI `OUT` cannot overlap a pin hold, so it stretches SCK low by `MOSI_T+1`. Compiler: `Rd_sck_high = HALF`, `Rd_sck_low = HALF - MOSI_T - 1` → `MOSI_T=1`, `LOW=6`. Period is not `50+50` ns for that reason (the MOSI tax).
- Interior SCK lows are 8 after that accounting. First high/low pair is the same 8/8.

No MISO. Duplex needs `IN` (not silicon).

## I2C master write — inline in `test/test.py`

No `i2c.asm`. After UART+SPI in `test_uart_program`, the test loads a small listing: `PSET`/`REL`/`JL` on **SDA pin 10** (`uio[2]`) and **SCL pin 11** (`uio[3]`). TB pull-ups: `uio_in` looks like `0x0C` after load. That is the bench, not a pin default.

## USB LS ACK — `asm/examples/usb_ls_ack.asm`

- D+ `uo[4]`, D− `uo[5]`, descriptor `0x54`. Bit = 40 clocks, SE0 = 80.
- Listing stores **NRZI D+ levels**, not PID bytes. No NRZI in the shifter. Compiler (or a human) writes line levels. Toggle = USB 0, stay = USB 1.
- LS J is D+ = 0. `OUT` drives pin1 from `Rs[0]` and pin2 from `~Rs[0]`.
- SYNC field is seven 0s then 1 = byte **`0x80`** LSB-first, not `0x01`. ACK PID is **`0xD2`**.
- Level bytes in the listing: `0x00`, `0xD5`, `0xE4`, then SE0 `PSET` both 0, idle J.
- Do not read the analog as `J`/`K` or `DF`/`EF` when the question is pin-4 high/low bits.

## USB FS ACK — `asm/examples/usb_fs_ack.asm`

- Same pins and shape. Bit = 5, SE0 = 10. J is D+ = 1 (LS inverted).
- Inter-byte `LDI` does not fit in a 5-clock hold. Last `OUT` of SYNC uses `R6=4` so the sticky tail restores 5.
- Level bytes: `0x01`, `0x2A`, `0x1B` (= LS levels XOR `0xFF`).
- **`0x2A` is eight D+ levels, LSB first, not a USB PID and not analog.**
- **FS TX is in scope. FS RX is a limitation** (5 clocks/bit will not be software-sampled).

## 10BASE-T TX

- Pin `uo[6]`, descriptor `0x66`. `OUTM`, `R3=6` (IEEE Manchester: 1 = low then high, 0 = high then low). Complement is off-chip.
- Preamble is **7× `0x55` + SFD `0xD5`** (64 bits), not 1500. 1500 is max payload. Min Ethernet frame is 64 bytes.
- `eth_10t.asm` — unrolled. `eth_10t_loop.asm` + `eth_10t_loop.dmem` — 27-byte runt, 216 bits, first `LD` in idle arms the OUTM stream, then `OUTM`+`DJNZ`. Leftover hold 5 hides `DJNZ` and the every-8-bits dmem refill.
- Ethernet is LSB-first on the wire. FCS is in the dmem image (`eth_tx.py` / WIRE).
- **NLP** is the 10BASE-T link pulse (~100 ns every ~16 ms), not the frame. Not listed yet.
- Other 10BASE-T-family PHYs (T1S / T1L) are different. Not this `OUTM`.

## Files that are not silicon

USB listings still `LDI` the shifter. Moving them to dmem+`LD` is later.

## JTAG / SWD / PS/2 / CAN

No TX listing yet. Plan: those TX programs, then RX, then details (NLP, real eth size), then optimize. See [future.md](future.md).
