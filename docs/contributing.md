# Contributing to OpenChord

OpenChord is designed to be extended. If you have a vintage chord instrument
with a dead or unobtainable chord logic IC, you may be able to add support
for it here.

## How it works

OpenChord separates firmware into two layers:

**Core** (`firmware/core/`) — instrument-agnostic modules:
- `freq_gen.py` — PIO square wave generator, works on any RP2350/RP2040
- `tuning.py` — frequency table generation from A4 reference
- `chord_logic.py` — key matrix scanning, chord resolution, voicing, auto-bass
- `midi.py` — optional MIDI out

**Instrument** (`firmware/instruments/<name>/`) — instrument-specific files:
- `config.py` — GPIO assignments, matrix layout, supply details
- `main.py` — entry point, wires core modules together using config

To add a new instrument you only need to write `config.py` and a thin
`main.py`. The core modules handle everything else.

---

## Step-by-step: adding a new instrument

### 1. Identify the target IC

What chord logic IC does your instrument use? Common candidates:

| IC | Found in | Notes |
|---|---|---|
| AY-5-1317A | Suzuki Omnichord OM-27 | Supported |
| MM5833 | Hammond X-5, others | Stub exists |
| AY-5-1316 | Omnichord OM-36 | Not yet started |
| MK50240 | Various electronic organs | TOG only, no chord logic |

### 2. Get the schematic

You need to know:
- Which pins are power and ground (and their orientation — see below)
- Which pins are key matrix rows and columns
- Which pins are chord tone outputs and what they connect to
- What downstream circuitry those outputs feed
- What voltage the IC operates at

### 3. Understand the power supply

**This is the most important thing to get right.** Read
`docs/center-negative.md` before doing anything else.

The short version:
- Many vintage chord ICs are P-channel MOS running on a negative supply
  relative to their VSS pin — but when installed in a positive-supply
  instrument, VSS is wired to the positive rail and VDD to GND
- Logic HIGH = toward VSS (positive rail), Logic LOW = toward VDD (GND)
- Output transistors should be NPN open-collector pulling up to the positive rail
- The RP2350 GPIO drives the transistor base: LOW = transistor off =
  output pulled high = logic HIGH to downstream IC

Instruments with genuine multi-rail negative supplies (Hammond X-5 style)
are a more complex case — see Filip Kindt's write-up linked in the README.

### 4. Watch out for RP2350 Errata 9

GPIO pins with PULL_DOWN can latch at ~2.1V when floating on the RP2350.
Use PULL_UP and invert your scan logic instead. The core `chord_logic.py`
already does this for the key matrix — rows driven LOW, columns sense LOW
on press. If your instrument's matrix works differently, make sure you are
not relying on PULL_DOWN for floating pins.

### 5. Check downstream IC voltage levels

If the instrument has a rhythm chip or other IC driving control inputs to
your target chord IC, check its output voltage swing. The AY-5-1315 in
the OM-27 swings to +12V — far above the 3.3V RP2350 GPIO maximum.
A simple 68kΩ + 33kΩ voltage divider brings 12V down to ~3V safely.
Don't skip level shifting on any input that could exceed 3.3V.

### 6. Create your instrument directory

```
firmware/instruments/<your-instrument-name>/
├── config.py
├── main.py
└── README.md   (optional but appreciated)
```

Copy `firmware/instruments/om-27/config.py` as a starting point and work
through each section. Most of the work is filling in GPIO numbers.

Key things to define in config.py:
- All GPIO assignments with AY/IC pin cross-references
- `MATRIX_ROW_PINS` and `MATRIX_COL_PINS`
- `ROW_TO_TYPE` (usually `['maj', 'min', 'dom7']`)
- `COL_TO_ROOT_NORMAL` — which note each column maps to
- `COL_TO_ROOT_FLAT` and `COL_TO_ROOT_SHARP` — modifier mappings
- `TUNING_A4_HZ` — set to 440.0 unless the instrument has a different pitch
- `BASS_SELECT_TABLE` — if the instrument has a rhythm chip with bass select
- `GPIO_MIDI_TX` — set to None if not implementing MIDI

### 7. Write main.py

Copy `firmware/instruments/om-27/main.py`. Changes needed:
- Update the import to use your config
- Adjust the number of tone output SMs to match your IC's output pins
- Update `startup_jingle()` if you want different encoding
- Remove any OM-27-specific pin handling (AK pin, 7SEL pin) if not relevant

### 8. MIDI TX pin assignment

UART1 TX on the RP2350 is available on GPIO 4 by default, with alternates
at GPIO 8, 12, 20, and 24 (via pin multiplexing). GPIO 20 is used by the
OM-27 implementation because it maps to an unwired matrix column. Check
which GPIO is free in your instrument's pin assignment and confirm it
supports UART1 TX before assigning `GPIO_MIDI_TX`.

### 9. Test on the bench

Minimum wiring for initial testing: power + tone outputs + key matrix.
Everything else (memory switch, modifier, bass select, MIDI) can be left
unconnected — the firmware handles floating inputs gracefully provided
you are using PULL_UP (not PULL_DOWN) on sense pins.

### 10. Document the hardware

Add a README.md in your instrument directory covering:
- Which IC you are replacing and which socket the board sits in
- Power supply details and transistor types required
- Any level shifting required
- Bench test wiring (minimum viable connections)
- Any gotchas specific to this instrument

Add an entry under `hardware/instruments/<name>/` with at minimum a
wiring/pin map table.

### 11. Open a pull request

Unverified stubs are welcome — mark them clearly and they give the next
person with that instrument a starting point. Tested and working
implementations are even better. Either way, document what you know and
what you don't.

---

## Downstream divider chips

Most instruments use binary divider chains downstream of the chord IC.
The OM-27 uses M747s, replaced here by CD4520 adapter boards.

| Original | Replacement | Notes |
|---|---|---|
| M747 (DIP-14, 7-stage) | CD4520 (DIP-16, 4-stage dual) | Passive adapter board, pin translation only |
| MM5837 | CD4024 | 7-stage ripple counter |
| Various | CD4040 | 12-stage, more than needed but works |

The CD4520 clocks on the positive-going edge (ENABLE tied HIGH), matching
M747 behaviour. RESET tied LOW to run freely. Q4 outputs unused (NC).

---

## Code style

- MicroPython compatible — no CPython-only features
- All instrument-specific values in `config.py`, never in core modules
- GPIO numbers as named constants, never magic numbers
- Comment the *why*, not the *what*
- Mark unverified sections with `# UNVERIFIED — confirm with scope`

---

## Questions

Open an issue. If you are not sure whether your instrument is a good
candidate, describe it and someone will help you figure it out.
