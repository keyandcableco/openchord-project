# Contributing to OpenChord

OpenChord is designed to be extended. If you have a vintage chord instrument with a dead or unobtainable chord logic IC, you may be able to add support for it here.

## How it works

OpenChord separates firmware into two layers:

**Core** (`firmware/core/`) — instrument-agnostic modules:
- `freq_gen.py` — PIO square wave generator, works on any RP2350/RP2040
- `tuning.py` — frequency table generation from A4 reference
- `chord_logic.py` — key matrix scanning, chord resolution, voicing
- `midi.py` — optional MIDI out

**Instrument** (`firmware/instruments/<name>/`) — instrument-specific files:
- `config.py` — GPIO assignments, matrix layout, power supply details
- `main.py` — entry point, wires core modules together using config

To add a new instrument you only need to write `config.py` and a thin `main.py`. The core modules handle everything else.

---

## Step-by-step: adding a new instrument

### 1. Identify the target IC

What chord logic IC does your instrument use? Common candidates:

| IC | Found in | Notes |
|---|---|---|
| AY-5-1317A | Suzuki Omnichord OM-27 | Supported |
| MM5833 | Hammond X-5, others | Stub exists |
| AY-5-1316 | Omnichord OM-36 | Not yet started |
| MK50240 | Various electronic organs | 13-output TOG only |
| Custom mask ROM | Later Omnichords | Very instrument-specific |

### 2. Get the schematic

You need to know:
- Which pins are power/ground
- Which pins are key matrix rows and columns
- Which pins are frequency/chord outputs
- What downstream circuitry those outputs feed
- What voltage the IC runs at (crucial — see below)

Repair blogs, service manuals, and the Omnichord community are good sources. Even a partial schematic is enough to start.

### 3. Understand the power supply

This is the most important thing to get right. Vintage chord instruments use a variety of supply configurations:

**Positive rail (simplest):**
Logic HIGH = positive supply. Use NPN transistors (MMBT3904) on outputs. Set `CENTER_NEGATIVE = False` in config, `invert=False` in `init_sm()`.

**Center-negative (OM-27 style):**
Batteries wired with center tap as 0V/GND. Logic HIGH = center tap. Logic LOW = negative terminal. Use PNP transistors (MMBT3906) on outputs. Set `CENTER_NEGATIVE = True`.

**Multi-rail negative (Hammond X-5 style):**
Signals swing to negative voltages. Requires AC coupling on inputs and different output transistor arrangement. Read Filip Kindt's notes at https://www.cctv.fm/post/rp2040-tog before attempting.

See `docs/center-negative.md` for a full explanation.

### 4. Create your instrument directory

```
firmware/instruments/<your-instrument-name>/
├── config.py
├── main.py
└── README.md   (optional but appreciated)
```

Copy `firmware/instruments/om-27/config.py` as a starting point. Work through each section:

#### Power supply
```python
CENTER_NEGATIVE = True   # or False
```

#### GPIO assignments
Map each AY/MM/custom IC pin to an RP2350-Zero GPIO. You have 30 GPIOs available. Minimum needed:
- 4 × tone outputs (ROOT/3RD/5TH/BASS)
- N × key matrix rows (usually 2-3)
- M × key matrix columns (usually 6-12)
- Power enable
- Memory switch (if present)
- Modifier button (if desired)

Optional:
- Bass select from rhythm chip
- Tuning ADC
- MIDI TX
- Solder jumpers

#### Key matrix layout
The matrix layout tells the firmware which note corresponds to which button. The OM-27 uses the circle of fifths (Eb Bb F C G D A E B). Your instrument may use chromatic order or some other arrangement.

```python
COL_TO_ROOT_NORMAL = [C, D, E, F, G, A, B, Cs, Ds]  # example
```

You also need to define what the flat and sharp modifier modes should do — typically just shift each root by ±1 semitone.

#### Row to chord type
```python
ROW_TO_TYPE = ['maj', 'min', 'dom7']  # most instruments
```

### 5. Write main.py

Copy `firmware/instruments/om-27/main.py`. The only changes needed are:
- Update the import to use your config
- Adjust any instrument-specific startup behaviour

### 6. Test

Minimum bench test: power + 4 tone outputs + key matrix. Everything else (memory, modifier, MIDI, tuning pot) can be left unconnected initially.

### 7. Document hardware

Add a README.md in your instrument directory covering:
- Which IC you're replacing and which socket the board sits in
- Power supply details and transistor types
- Any level shifting required
- Bench test wiring table (minimum viable wiring)
- Any gotchas specific to this instrument

Add a hardware directory entry under `hardware/instruments/<name>/` with at minimum a wiring diagram or pin map table.

### 8. Open a pull request

Even a partial, unverified stub is welcome — it gives the next person with that instrument a starting point. Mark unverified sections clearly with `# TODO: verify` comments.

---

## Downstream divider chips

Most instruments use binary divider chains downstream of the chord IC to generate multiple octaves. The OM-27 uses M747s, replaced here by CD4520 adapter boards.

If your instrument uses a different divider chip, check whether a still-available replacement exists with compatible function. Common dividers:

| Original | Replacement | Notes |
|---|---|---|
| M747 (DIP-14) | CD4520 (DIP-16) | Adapter board needed, passive |
| MM5837 | CD4024 | 7-stage ripple counter |
| Various | CD4040 | 12-stage, more octaves than needed but works |

Document the pin translation in `hardware/instruments/<name>/`.

---

## Code style

- MicroPython compatible (no CPython-only features)
- Functions over classes where possible — easier to read on small screens
- Comment the *why*, not the *what*
- GPIO numbers as named constants in config.py, never magic numbers in core
- All instrument-specific values in config.py, never in core modules

---

## Questions

Open an issue. If you're not sure whether your instrument is a good candidate, describe it in an issue and someone will help you figure it out.
