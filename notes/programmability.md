# Programmability notes

Written after the fixed UART transmitter passed RTL, gate-level, and GDS.
Nothing in this file is a commitment to build it now. The current design
stays a one-byte transmitter: 8 data bits, no parity, 16 clocks per bit,
no queue.

## What is built

`ff_uart` copies `ui_in` into a shift register on the edge where `uio_in[0]`
(`send`) is high and the machine is idle. `uo_out[0]` then sends start,
eight data bits least-significant-bit first, and stop. Each of those bits
is 16 `clk` cycles. `uo_out[1]` (`busy`) is high for the whole frame.
`send` during a frame is ignored. The next `send` overwrites the register.

Gate-level `test_uart_tx` passed at 1620002 ns (seed 1791841903). There is
no `<failure>` in `test_results/gatelevel_test_results.zip`.

GDS for this same transmitter (`test_results/GDS_logs.zip`, which contains
`src/uart.sv`):

| Check | Worst case | Slack | Violations |
|---|---|---|---|
| Setup | slow, 1.08 V, 125 °C | 13.72 ns | 0 |
| Hold | fast, 1.32 V, −40 °C | 0.137 ns | 0 |

19 flip-flops, which are exactly `state`, `timer`, `bit_idx`, `shifter`,
`tx_q`, and `stop_done`. 188 standard cells, 28 of them hold buffers.
Clock constraint is still 20 ns. Do not change it because of these numbers.

## Frame format, which is in scope

These change the shape of one frame. They are the first programmability
worth having, because a fixed UART and a later SPI/I2C engine differ here,
and a program can carry them without a memory.

The hardware behind each one already exists in the transmitter. A program
would load them before `send`, and the state machine would read those
registers instead of the constants baked in today.

### Clocks per bit

Today `CLKS_PER_BIT` is 16, and `timer` is 4 bits because 15 fits in 4 bits.
Eight clocks per bit needs a terminal count of 7. Four clocks per bit needs
a terminal count of 3. The sample point of a future receiver is the middle
of that window (clock 8 when the width is 16, clock 4 when the width is 8).

This has to be chosen before the frame starts. Changing it in the middle of
a bit makes the other end's sample land on an edge. The register is a
terminal count, or a width, loaded while idle. The counter width on silicon
is the maximum we are willing to pay for. A program can pick any value up
to that maximum. It cannot ask for 1000 clocks per bit if the counter is
4 bits wide.

Worth keeping: 16 as the default, because the middle clock is unambiguous
and a one-clock mistake does not land on the edge. 8 is the interesting
smaller case. Anything below 4 makes a mid-bit sample and the bit edges
share a clock.

### Parity

One extra bit between the last data bit and the stop bit. Even parity means
the parity bit makes the number of 1s in the data bits plus the parity bit
even. Odd parity makes that number odd. "No parity" is the machine we have
now: data, then stop.

"Parity bits" plural is a different feature. Standard UART parity is a
single bit. Two or more check bits are a checksum or extra data bits, and
they belong with a later protocol, not with this frame.

The transmitter already walks a counted number of data bits and then stop.
Parity is one more state, or one more counted bit, whose value is the XOR
of the byte (inverted for odd). The receiver, when it exists, recomputes
that XOR and drops the byte on a mismatch. Until a receiver exists, parity
on the transmitter is a bit the test can see on the wire and nothing more.

Load even / odd / none while idle, with the clocks-per-bit value.

### Data width and stop length

Same family, not requested yet, written down so they are not invented
separately later.

- Data bits: 7 and 8 are the ones a UART actually uses. The shift count
  becomes a register instead of `bit_idx == 7`.
- Stop bits: one or two. Two stop bits means the stop state runs twice.
  The line is high either way. The difference is how long `busy` stays high
  before the next byte may start.

## Buffer depth, which is out of scope

How big the queue is cannot be programmed after the chip is built, except
as "use k of the N slots that were actually placed." N is flops or a memory,
chosen at design time. A program that says "give me a 12-byte buffer" does
not create 96 flops.

The transmitter does not need a queue to be a correct UART. The test is the
other end of the wire: it holds the next byte on `ui_in` and waits until
`busy` falls. Bytes are not lost, because the only writer is the test and
it can see `busy`.

A buffer becomes necessary when the writer cannot wait. That is a host that
dumps bytes on its own clock, or a receiver that accepts a second byte
before the first has been read. Neither of those exists in this design.
Building a FIFO now would add read and write pointers, a full flag, and a
depth we would be guessing.

When a workload forces it, the decision to record is:

- Depth N is still fixed in silicon. A flip-flop queue is the small version
  (2 or 16 bytes). An IHP SRAM macro is the large version: Jane Street
  allows one or more, if they fit the tile and pass precheck. A program
  still cannot grow the macro. It can only use the bytes that were built.
  Do not add a macro until a workload needs more storage than flops.
- Candidates to discuss then, not now: 2 (one byte loading while one
  shifts) or 16. Twelve was an example in conversation, not a measured need.
- A program may use 1..N of those slots. The unused ones stay empty.
- Overwrite versus drop-when-full has to be chosen with the workload.
  Dropping loses a byte and can be detected. Overwriting loses an older
  byte silently.

Do not add this to `ff_uart` while the frame is still fixed and there is
no receiver.

## Order to build later

1. Receiver for the frame we have now: start detected on a falling `ui`
   line, sample in the middle of each 16-clock bit, one byte out on
   `uo_out`. Same rule as the transmitter: the test consumes the byte
   before the next frame.
2. Only then replace the constants with registers: clocks per bit, parity
   mode, data width, stop length. The existing pin tests must still pass
   when those registers hold today's values (16, no parity, 8 data, 1 stop).
3. A second fixed protocol (SPI, or I2C so that `uio_oe` is real) before
   any instruction set. The instruction list is the operations those
   machines repeat: drive, wait N, shift, sample, connect the driver,
   disconnect the driver.
4. A buffer only if one of those workloads loses a byte that the test
   was ready to present on time.

## What the chip is for

Jane Street wants a chip that can be loaded with a new protocol after
fabrication, without a new tapeout. A fixed UART cannot become SPI. A
program can, if the program is allowed to drive, wait, shift, sample, and
connect or disconnect a pin. Flexibility is what they said they will judge.
UART, SPI, and I2C are the protocols to demonstrate. Standard rates are the
target: common UART bauds, SPI modes 0–3, I2C at 100 kHz and 400 kHz.
USB and 10 Mbit Ethernet are stretch goals. An assembler and example
programs are part of the submission, not an extra.

The demo-board microcontroller is the host. It loads the program over the
pins. When the project is deselected the tile powers down and the program
is gone, so every selection starts with reset and a reload. `rst_n` is
mandatory because the flops do not wake up as 0.

Stay on 6x4 until they mail the 8x4 template. There is no required clock
frequency. The 20 ns constraint stays until a protocol or a timing report
forces a change. I2C needs external pull-ups; those go on a Pmod, not in
the pad. There are no analog pads. 3.3 V I/O on the demo board.

## How pins get their values

`uo_out` is driven directly. `assign uo_out = {6'b0, busy, tx}` is the chip
setting those pads. `uio_out` reaches its pad only while that bit of
`uio_oe` is 1. `ui_in` is driven by the host, never by this design.

A later program does not get a new way to touch the metal. It writes the
registers that feed those same assigns. Pin choice is a mux in front of
each pad: the program picks which internal signal is connected to
`uo_out[0]`, or whether `uio_oe[0]` is forced on, forced off, or controlled
by the protocol. One pin stays a load strobe so the host can still feed a
new program after reset.
