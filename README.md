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
| 4069 | RC clock oscillator for M083A | No longer needed; its 78L05 power supply gets stolen for VBUS |
| 4001 | NOR gate for bass routing | Logic moved into firmware |
| M747 ×2 | Octave dividers | Replaced by CD4520 adapter boards (passive pin translation) — **unverified** |

The AY-5-1315 (rhythm chip), 4011 (percussion), and all downstream audio circuitry are left alone.

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

**RP2350 Errata 9:** PULL_DOWN is unreliable on floating GPIO pins. The key
matrix uses PULL_UP with rows driven LOW instead — already handled in firmware.

### GPIO map (proposed, unverified)

| GPIO | Function | AY-5-1317A pin |
|---|---|---|
| 0 | ROOT output → CD4520 #1 clock A | 31 |
| 1 | 3RD output  → CD4520 #1 clock B | 29 |
| 2 | 5TH output  → CD4520 #2 clock A | 28 |
| 3 | 7TH output  → CD4520 #2 clock B | 32 (silent on non-7th chords) |
| 4 | MO output (auto-bass) | 34 |
| 5 | 7th Select drive (LOW = 7th active) | 33 |
| 6 | Row drive: Major | 11 + 12 (tie both pads together) |
| 7 | Row drive: Minor | 9 + 10 |
| 8 | Row drive: Seventh | 7 + 8 |
| 9 | Col sense: C  | 24 |
| 10 | Col sense: C# | 23 |
| 11 | Col sense: D  | 22 |
| 12 | Col sense: D# | 21 |
| 13 | Col sense: E  | 20 |
| 14 | Col sense: F  | 19 |
| 15 | Col sense: F# | 18 (NC — no button in OM-27) |
| 16 | Col sense: G  | 17 |
| 17 | Col sense: G# | 16 (NC — no button in OM-27) |
| 18 | Col sense: A  | 15 |
| 19 | Col sense: A# | 14 (NC — no button in OM-27) |
| 20 | Col sense: B / MIDI TX | 13 / UART1 alt TX |
| 21 | Power enable | — |
| 22 | Any Key Down drive | 30 |
| 23 | Memory switch input | 35 |
| 24 | Modifier button input (was reset) | 5 |
| 25 | Bass select B3 from AY-5-1315 | 25 (needs 68k+33k level shift) |
| 26 | Bass select B2 from AY-5-1315 | 26 (needs 68k+33k level shift) |
| 27 | Bass select B1 from AY-5-1315 | 27 (needs 68k+33k level shift) |
| 28 | JP1: flat/sharp select | — |
| 29 | JP2: Barry Harris mode | — |

AY-5-1317A pins 1 (VSS), 2 (VDD), 3 (C1), 4 (OSC), 6 (m Sel), 36–40
are not connected to the RP2350 — VSS and VDD go to the supply rails,
OSC is unused (no external clock needed), and the others need PCB trace
investigation to determine if they connect to anything downstream.

### CD4520 adapter boards

The M747 is a 14-pin dual 7-stage divider. The CD4520 is a 16-pin dual
4-stage binary counter that should be functionally equivalent for the OM-27's
purposes (only the first three divide stages are used). The plan is a passive
adapter board in each M747 socket — just pin translation, no active components.

This is theoretically straightforward but hasn't been built or tested.

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
│       ├── om-27/
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
