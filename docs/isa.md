# ISA

A program is a list of 16-bit words in a 256-word memory. The address of a word is 8 bits. The opcode is bits 15 through 12. The other bits mean whatever that opcode says.

The first byte stored for a word is bits 7 through 0. The second byte is bits 15 through 8. How those bytes are strobed in is in [info.md](info.md).

```
15        12 11        8 7         0
+-----------+-----------+-----------+
| opcode    | payload, per opcode   |
+-----------+-----------+-----------+
```

| Opcode | Name | Bits 11–8 | Bits 7–0 |
|---|---|---|---|
| `0000` | `LDI` | ignored | byte loaded into the shifter |
| `0001` | `LOW` | pin | duration |
| `0010` | `HIGH` | pin | duration |
| `0011` | `SETX` | ignored | value loaded into X |
| `0100` | `OUT_L` | pin | duration |
| `0101` | `DJNZ` | ignored | jump target |
| `0110` | `HALT` | ignored | ignored |
| `0111` | `OUT_M` | pin | duration |
| `1000` | `REL` | pin | duration |
| `1001` | `JL` | pin | jump target |
| `1010`–`1111` | unused | ignored | ignored |

## Pins and duration

A pin number is 4 bits. Pins 0 through 7 are `uo_out[0]` through `uo_out[7]`. Pins 8 through 15 are `uio[0]` through `uio[7]`. `ui_in` cannot be driven. `uo_out` resets high. `uio` resets to inputs.

`LOW`, `HIGH`, `OUT_L`, `OUT_M`, and `REL` use the numbered pin and wait for the duration. The duration is that many chip clocks, and the clock that starts the level is one of them. A duration of 0 waits 256 clocks. When the wait ends, the pin keeps its level until a later instruction writes that same pin.

Driving a `uio` pin with `LOW`, `HIGH`, `OUT_L`, or `OUT_M` turns that bit of `uio_oe` on. `REL` turns it off.

## LDI — `0000`

Loads bits 7 through 0 into the shifter. The shifter is 8 bits. This does not drive a pin. The next instruction is the next word.

`OUT_L` will emit bit 0 of this byte first. `OUT_M` will emit bit 7 first.

## LOW — `0001`

Drives the pin to 0 and waits for the duration.

## HIGH — `0010`

Drives the pin to 1 and waits for the duration.

## SETX — `0011`

Loads bits 7 through 0 into X. X is an 8-bit counter used by `DJNZ`. This does not drive a pin. The next instruction is the next word.

## OUT_L — `0100`

Drives the pin from bit 0 of the shifter, then shifts the shifter right by one, filling bit 7 with 0. Waits for the duration.

Eight `OUT_L` instructions emit the loaded byte low bit first. The shifter is 0 afterwards.

## DJNZ — `0101`

Subtracts 1 from X. The subtraction wraps, so 0 becomes 255. If the result is not 0, the next instruction is the word at the address in bits 7 through 0. If the result is 0, the next instruction is the next word.

## HALT — `0110`

Stops fetching. A level already in progress runs for its full duration. After that, the pins stay where they are.

## OUT_M — `0111`

Drives the pin from bit 7 of the shifter, then shifts the shifter left by one, filling bit 0 with 0. Waits for the duration.

Eight `OUT_M` instructions emit the loaded byte high bit first. The shifter is 0 afterwards.

## REL — `1000`

Turns the driver off for a `uio` pin, leaves the driven bit at 0, and waits for the duration. The external pull-up decides the line. On a `uo_out` pin, which cannot be released, this drives 0.

## JL — `1001`

Reads a `uio` pin. If it is 0, the next instruction is the word at the address in bits 7 through 0. If it is 1, the next instruction is the next word. A `uo_out` pin has no input and reads as 1, so `JL` falls through.

## Unused opcodes — `1010` through `1111`

The instruction does nothing and the next instruction is the next word.
