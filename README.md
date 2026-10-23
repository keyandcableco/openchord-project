# OpenChord

An open hardware and firmware platform for replacing dead chord logic ICs in vintage electronic instruments, built around the Waveshare RP2350-Zero.

**Status: work in progress. Nothing here has been tested on real hardware yet. Treat all GPIO assignments, component values, and wiring details as unverified starting points.**

---

## Background

A lot of instruments from the late 70s and early 80s put all their musical intelligence into one custom IC. When that chip fails, the instrument is usually dead for good — they were never reproduced, and the few that remain are getting harder to find every year.

The Suzuki Omnichord OM-27 is the immediate motivation for this project. Its chord logic lives in an AY-5-1317A that reads the 27-button chord matrix, selects the right top-octave frequencies from an M083A generator, and routes them to a pair of M747 octave dividers that feed the strum plate. None of those chips are obtainable anymore.

The idea here is that a single RP2350-Zero, sitting in the AY-5-1317A socket, can do everything those chips did — and since it's software rather than fixed silicon, it can do more.

---

## What's here

The firmware is split into instrument-agnostic core modules and instrument-specific configuration. The hope is that someone with a different instrument can write a config file and be most of the way there without having to understand everything from scratch.

Currently:
- **OM-27** — the main target, reasonably well mapped out, untested
- **Hammond X-5** — a stub based on Filip Kindt's TOG work, very incomplete

---

## OM-27 specifics

### ICs this is intended to replace

| IC | Role | Approach |
|---|---|---|
| AY-5-1317A | Chord logic brain | RP2350-Zero sits in this socket |
| M083A | Top-octave generator | Frequencies generated in PIO from internal clock |
| 4069 | RC clock oscillator for M083A | No longer needed; its 78L05 power supply gets stolen for VBUS (see Known issues: USB and VBUS) |
| 4001 | NOR gate routing 5th or 7th to bass M747 depending on chord type | Bypassed — firmware outputs the correct note directly |
| M747 ×2 | Octave dividers | Replaced by CD4520 adapter boards (passive pin translation) — **unverified** |

The AY-5-1315 (rhythm chip), 4011 (percussion), and all downstream audio circuitry are left alone.

### Tone generation

`core/freq_gen.py` runs one PIO state machine per tone output at the full
system clock (`machine.freq()`, 150MHz by default on the RP2350, clock
divider 1). Each period is `counter + 12` PIO cycles, so
`counter = round(PIO_CLK / freq) - 12`; rounding costs under 0.06 cent up to
8.4kHz. Counter 0 (`SILENT`) holds the pin at its idle level. `set_freq()`
never blocks: it sends a value only when the value has changed and the state
machine has already taken the previous one, otherwise it returns and the next
call tries again. So call it on every main-loop pass, not only when a chord
changes. This has only been checked on a cycle-level PIO simulator.
On the bench, with A4 = 440 and octave 7, a tone output playing A should
read about 3520Hz at 50% duty: 3519.97Hz at 150MHz, give or take the
crystal's tolerance (typically ±50ppm, about ±0.2Hz; not verified for this
board's crystal).

### Chord types

The original hardware supported major, minor, and dominant 7th. The firmware adds:

- Minor 7th, major 7th (two buttons, same root)
- Diminished (major + minor buttons)
- Augmented (all three buttons)
- Sus2, sus4 (two different roots, interval-aware)
- Slash chords (two different roots, other intervals)
- Barry Harris voicings via solder jumper: maj6, min6, full dim7

### Hardware approach (unverified)

The OM-27 runs on +12V and +5V rails only (no negative rail). The AY-5-1317A is
P-channel MOS, almost certainly wired with VSS=+12V and VDD=GND — the standard
approach for running P-channel ICs on a positive supply. Logic HIGH = +12V,
logic LOW = GND. This is consistent with pin 5 (reset) sitting at +12V at rest
and being triggered by grounding it.

The current plan uses NPN MMBT3904 transistors on the five tone outputs,
open-collector pulling up to +12V. Worth trying direct GPIO connection first on
the bench — 3.3V may register as a valid HIGH on a 12V CMOS input. See
`docs/center-negative.md` for full details.

The AY-5-1315 bass-select outputs swing to +12V and require voltage dividers
(68kΩ + 33kΩ) before connecting to RP2350 GPIOs.

### RP2350 erratum E9 (not handled yet)

On the first RP2350 stepping (A2), a GPIO input that is floating or only
weakly pulled low can leak about 120µA and hold itself near 2.2V. The
internal pull-down is too weak to pull it back down; only a pull-down or
driver of 8.2kΩ or less overcomes it. Steppings A3 and A4 fix it.
(Figures from the RP2350 datasheet, erratum RP2350-E9; not verified on a
bench.)

The OM-27 firmware still depends on weak pull-downs, so on an A2 chip these
inputs can read 1 when they should read 0:

- Memory switch (GPIO 18): internal PULL_DOWN (`main.py`).
- Bass select B1–B3 (GPIO 20–22): internal PULL_DOWN behind the 68kΩ/33kΩ
  dividers (`chord_logic.py`). The 33kΩ leg is above the 8.2kΩ limit.
- Key matrix columns (GPIO 9–14): no internal pull, only the PCB's 33kΩ
  pull-downs, also above the limit. (The firmware drives the rows HIGH to
  scan, not LOW with PULL_UP as this README used to say.)

What to do:

- Check the stepping first. In the MicroPython REPL,
  `import machine; print(machine.mem32[0x40000000] >> 28)` prints 2 on an
  A2 chip (affected) and 3 on A3 or A4 (fixed). It reads CHIP_ID.REVISION
  (address from the datasheet; not yet run on a board).
- On an A2 chip, add an external pull-down of 8.2kΩ or less on the memory
  switch and on each key matrix column. The memory switch may also need a
  divider: see "Two inputs may see +12V" under Known issues.
- On B1–B3, re-size the whole divider. The lower leg is the pull-down E9
  cares about, so it has to be 8.2kΩ or less, and the top leg has to shrink
  with it so a 12V high still reads as 1. For example 22kΩ over 8.2kΩ gives
  about 3.3V from 12V; keep the high between about 2.5V and 3.3V (values not
  verified on the instrument). That loads each AY-5-1315 output with about
  30kΩ, roughly 0.4mA at 12V, three times the old divider's load: check on
  the bench that the high still reads at least 2.5V. Adding 8.2kΩ across the 33kΩ, or swapping
  only the 33kΩ for 8.2kΩ under the 68kΩ, leaves the high at about 1.1V or
  1.3V, which is below the 2.0V minimum for a high (RP2350 datasheet; not
  verified), so it won't reliably read as 1.
- A firmware workaround (keep each pad's input enable off except while
  reading it, per the datasheet) is possible but not written.

### GPIO map (proposed, unverified)

The key matrix is 3 rows × 6 column pins. Three of those column pins are
shared between two roots each (tritone pairs), giving 9 accessible roots
from 6 pins. The frequency input pins (13–24) are dedicated M083A
connections and are not used as matrix columns — they are left unconnected
on the daughterboard.

| GPIO | Function | AY-5-1317A pin |
|---|---|---|
| 0 | ROOT output → CD4520 #1 clock A | 31 |
| 1 | 3RD output  → CD4520 #1 clock B | 29 |
| 2 | 5TH output  → CD4520 #2 clock A | 28 |
| 3 | 7TH output  → CD4520 #2 clock B | 32 (silent on non-7th chords) |
| 4 | MO output (auto-bass) | 34 |
| 5 | 7th Select drive (LOW = 7th active) | 33 |
| 6 | Row drive: Major | 11 + 12 (tie both pads) |
| 7 | Row drive: Minor | 9 + 10 (tie both pads) |
| 8 | Row drive: Seventh | 7 + 8 (tie both pads) |
| 9 | Col sense: Eb / A | 39 |
| 10 | Col sense: Bb / E | 40 |
| 11 | Col sense: F  / B | 3  |
| 12 | Col sense: C      | 36 |
| 13 | Col sense: G      | 37 |
| 14 | Col sense: D      | 38 |
| 15 | MIDI TX (optional) | — (UART1, verify pin capability) |
| 16 | Power enable (see Known issues) | — |
| 17 | Any Key Down drive | 30 |
| 18 | Memory switch input (may see +12V: see Known issues) | 35 |
| 19 | Modifier button input, was reset (may see +12V: see Known issues) | 5 |
| 20 | Bass select B3 from AY-5-1315 | 25 (needs a divider: see the E9 section) |
| 21 | Bass select B2 from AY-5-1315 | 26 (needs a divider: see the E9 section) |
| 22 | Bass select B1 from AY-5-1315 | 27 (needs a divider: see the E9 section) |
| 23 | JP1: flat/sharp select | — |
| 24 | JP2: Barry Harris mode | — |
| 25–29 | Free for future use | — |

AY-5-1317A pins 1 (VSS) and 2 (VDD) go to the supply rails (+12V and GND
respectively). Pin 4 (OSC) is left unconnected — no external clock needed.
Pins 13–24 (frequency inputs from M083A) are left unconnected — we generate
frequencies internally. Pins 6 (m Sel) and 36–40 (column pins) connect to
the key matrix as shown above. Pin 30 (AK) is driven by the RP2350.

### CD4520 adapter boards

The M747 is a 14-pin dual 7-stage divider. The CD4520 is a 16-pin dual
4-stage binary counter that should be functionally equivalent for the OM-27's
purposes (only the first three divide stages are used). The plan is a passive
adapter board in each M747 socket — just pin translation, no active components.

This is theoretically straightforward but hasn't been built or tested.

---

## Known issues (not fixed yet)

The pin map above is unchanged. These need deciding before a board is laid
out.

- **MicroPython 1.26.0 or newer.** Releases before 1.26.0 never load programs
  into the RP2350's third PIO block (MicroPython issue #17509), so anything on
  state machines 8-11 silently does nothing: here, the WS2812 status LED on
  state machine 11 in the OM-27 firmware. Use 1.26.0 or newer.

- **Two inputs may see +12V.** `config.py` says AY pin 5 (GPIO 19, the
  modifier button) sits at +12V at rest, and AY pin 35 (GPIO 18, the memory
  switch) is active HIGH, which on this chip means +12V. Only B1–B3 have a
  divider in the pin map. GPIO 0–25 take 5.5V at most, and only while the
  RP2350 is powered (RP2350 datasheet; not verified). With the AY-5-1317A
  out of its socket and the instrument on, measure both pins before
  connecting them. Anything above 3.3V needs a divider like B1–B3, and on an
  A2 chip its lower leg must be 8.2kΩ or less (see the B1–B3 example in the
  E9 section). Check AY pins 30 and 33 (GPIO 17 and 5, outputs) for pull-ups
  to +12V too.
- **GPIO 16 is used twice.** `GPIO_POWER = 16` in
  `instruments/om-27_omnichord/config.py`, but on the RP2350-Zero GPIO 16
  only goes to the onboard WS2812 LED, not to a header pin or pad (Waveshare
  schematic; not verified on a board). `main.py` drives it as the power
  enable at boot, then `_led_init()` claims the same pin for the LED state
  machine.
- **Pull-down inputs and erratum E9.** The OM-27 config still relies on
  PULL_DOWN inputs (memory switch, B1–B3) and on 33kΩ pull-downs (key matrix
  columns). See the E9 section above.
- **USB and VBUS.** On the RP2350-Zero, the VBUS pin connects straight to
  the USB-C connector with no diode (Waveshare schematic; not verified on a
  board). Don't plug USB in while the board is installed with VBUS wired to
  the 78L05, even with the instrument off: the PC's 5V would back-feed the
  OM-27's 5V rail, or the 78L05 the PC's port. Flash it out of the
  instrument, or add a Schottky diode from the 78L05 to VBUS. AY pin 1 is
  +12V and must never reach VBUS, which takes 5V only.
- **Which octave C belongs in.** The M083 has two C outputs: ÷239 (F1, its
  highest) and ÷478 (F13, an octave lower), per the M083 datasheet (not
  verified on an instrument). Which one the OM-27 sends to the AY-5-1317A
  is not known yet. `build_note_counters(octave=7)` makes C7 to B7, with C
  at the bottom, which matches F13 but not F1. Check against a stock OM-27:
  with A major held and A4 = 440, this firmware's ROOT output should read
  A7, about 3520Hz, and the stock ROOT line (AY pin 31) close to that (the
  stock RC clock is only roughly in tune). If the stock reads about 7040Hz
  or 1760Hz instead, change `TUNING_OCTAVE` in config.py to 8 or 6 to
  match. Then hold C major and B major on the stock instrument: if C reads
  higher than B, the OM-27 uses F1, so generate C at `TUNING_OCTAVE + 1`
  for TOG-replacement instruments.
- **Docs and comments out of date.** `docs/center-negative.md` (its E9
  section) and `docs/contributing.md` (sections 4 and 9) still say E9 is
  handled by PULL_UP columns with rows driven LOW. So do the comments in
  `config.py` (rows "driven LOW", columns "PULL_UP") and `chord_logic.py`
  (the 33kΩ pull-downs "dominate over any internal pull"). The E9 section
  above is the current one. Both docs also give about 3V for the
  68kΩ/33kΩ divider; from 12V it is about 3.9V. `docs/contributing.md` and
  the docstring headers of `config.py` and `main.py` still point to
  `instruments/om-27/`, now `om-27_omnichord/`. `docs/center-negative.md`
  says RP2350 GPIOs are not 5V tolerant; GPIO 0–25 are, up to 5.5V while
  the chip is powered (datasheet; not verified). 12V is still too much.

---

## Repository structure

```
openchord/
├── firmware/
│   ├── core/               # instrument-agnostic modules
│   │   ├── freq_gen.py     # PIO square wave generator
│   │   ├── tuning.py       # frequency tables, ADC tuning
│   │   ├── chord_logic.py  # matrix scanning, chord resolution
│   │   └── midi.py         # optional MIDI out
│   └── instruments/
│       ├── om-27_omnichord/
│       │   ├── config.py   # GPIO map, matrix layout
│       │   └── main.py     # entry point
│       └── hammond-x5/
│           └── config.py   # stub, very incomplete
├── hardware/
│   ├── common/
│   │   └── cd4520-adapter/ # M747 replacement adapter (design not started)
│   └── instruments/
│       └── om-27/          # schematic refs, BOM (unverified)
└── docs/
    ├── contributing.md
    └── center-negative.md  # important: read before wiring outputs
```

---

## If you want to help

The most useful thing right now would be someone with an OM-27, a scope, and some patience verifying the output stage behaviour — specifically whether the existing PCB pulldown resistors on the AY output pins will fight a 3.3V GPIO signal, or whether direct connection might actually work without transistors. That determines a lot of the hardware design.

If you have a different instrument with a dead chord IC and want to add support for it, see `docs/contributing.md`.

---

## Acknowledgements

Filip Kindt's RP2040 TOG replacement for the Hammond X-5 at [cctv.fm](https://www.cctv.fm/post/rp2040-tog) is where the PIO frequency generation idea came from. Erich Izdepski's OM-27 repair blog at [erichizdepski.wordpress.com](https://erichizdepski.wordpress.com) was an invaluable schematic reference.

---

## License

Firmware: MIT  
Hardware designs: CERN-OHL-S-2.0
