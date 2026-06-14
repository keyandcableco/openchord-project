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
| M747 ×2 | Octave dividers | Intended to be replaced by CD4520 adapter boards — **unverified** |

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

The OM-27 uses a center-negative battery supply — the center tap is 0V/GND, and logic HIGH in the original circuit means pulling toward ground, not toward the positive rail. This has significant implications for output transistor selection. See `docs/center-negative.md`.

The current plan uses MMBT3906 PNP transistors on the four tone outputs. Whether this actually works, and whether direct GPIO connection might work instead, is something that needs to be verified with a scope before committing to a PCB layout.

### GPIO map (proposed, unverified)

| GPIO | Function | AY-5-1317A pin |
|---|---|---|
| 0 | ROOT → CD4520 #1 | 31 |
| 1 | 3RD  → CD4520 #1 | 29 |
| 2 | 5TH  → CD4520 #2 | 32 |
| 3 | BASS → CD4520 #2 | 34 |
| 4–6 | Row drive: Maj/Min/7th | 12, 9, 7 |
| 7–15 | Col sense: Eb Bb F C G D A E B | 2,3,4,6,8,10,11,38,39 |
| 16 | Power enable | — |
| 17 | Memory switch | 35 |
| 18 | Modifier button (was reset) | 5 |
| 19–21 | Bass select from AY-5-1315 | 25, 26, 27 |
| 22 | JP1: flat/sharp select | — |
| 23 | JP2: Barry Harris | — |
| 26 | Tuning ADC | — |
| 27 | MIDI TX (optional) | — |

### CD4520 adapter boards

The M747 is a 14-pin dual 7-stage divider. The CD4520 is a 16-pin dual 4-stage binary counter that should be functionally equivalent for the OM-27's purposes (only the first three divide stages are used). The plan is a passive adapter board in each M747 socket — just pin translation, no active components.

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

If you have a different instrument with a dead chord IC and want to add support for it, see `docs/contributing.md`.

---

## Acknowledgements

Filip Kindt's RP2040 TOG replacement for the Hammond X-5 at [cctv.fm](https://www.cctv.fm/post/rp2040-tog) is where the PIO frequency generation idea came from. Erich Izdepski's OM-27 repair blog at [erichizdepski.wordpress.com](https://erichizdepski.wordpress.com) was an invaluable schematic reference.

---

## License

Firmware: MIT  
Hardware designs: CERN-OHL-S-2.0
