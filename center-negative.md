# Center-negative power supplies in vintage chord instruments

This is the single most dangerous gotcha when adapting OpenChord to a new instrument. Read this before wiring anything.

## What is a center-negative supply?

Many vintage portable electronic instruments (Omnichords, early Casios, some Yamaha organs) run on batteries wired in a split configuration:

```
(+) terminal  ─────────────────  +6V rail
                                      │
                                 instrument
                                   circuits
                                      │
Center tap   ─────────────────   0V / GND
                                      │
                                 instrument
                                   circuits
                                      │
(−) terminal  ─────────────────  −6V rail
```

The center tap between two battery packs becomes the ground reference (0V). The positive terminal sits above it and the negative terminal sits below.

## Why does this matter?

In a conventional positive-supply digital circuit:
- Logic HIGH = positive supply voltage (+5V, +3.3V, etc.)
- Logic LOW  = GND (0V)

In a center-negative circuit:
- Logic HIGH = center tap (0V in battery terms)
- Logic LOW  = negative rail (−6V in battery terms)

**The RP2350's GND and the instrument's center tap are the same node.** A GPIO driven HIGH (+3.3V) is actually ABOVE the center tap, which the instrument's ICs may interpret as an over-voltage condition, not a logic level.

A GPIO driven LOW (0V, same as center tap) is the instrument's logic HIGH.

This is completely backwards from what you'd expect.

## What the original ICs did

The AY-5-1317A's output pins pulled toward the center tap (logic HIGH) when active, and floated or were pulled toward the negative rail (logic LOW) when inactive. The pulldown resistors visible on the output pins in the schematic pull toward the negative rail, providing the LOW state.

## How OpenChord handles this

OpenChord uses **PNP transistors (MMBT3906)** on all tone outputs in center-negative mode:

```
RP2350 GPIO ──── 1kΩ ──── MMBT3906 base
                           MMBT3906 emitter ──── GND (center tap)
                           MMBT3906 collector ──── output ──── instrument circuit
                                                       │
                                                     10kΩ
                                                       │
                                                  negative rail
```

- GPIO LOW  → PNP base pulled toward emitter (GND) → transistor ON  → collector pulled to GND (center tap) → **instrument sees logic HIGH** ✓
- GPIO HIGH → PNP reverse biased → transistor OFF → collector pulled to negative rail via 10kΩ → **instrument sees logic LOW** ✓

The PIO program is also inverted to match:
- `set(pins, 0)` (GPIO LOW)  = active half of square wave (logic HIGH to instrument)
- `set(pins, 1)` (GPIO HIGH) = inactive half (logic LOW to instrument)
- Idle state: `set_init=OUT_HIGH` = GPIO HIGH = transistor OFF = outputs silent

Set `CENTER_NEGATIVE = True` in your instrument config and pass `invert=True` to `init_sm()`.

## The Hammond X-5: a harder case

The Hammond X-5 is more complex. It uses a **multi-rail negative supply** (GND, −18V, −25V, −33V) where signals swing down to negative voltages rather than floating around a center tap. The clock input in particular swings to −18V, which requires:

- AC coupling (series capacitor) before the GPIO
- A bias resistor network to hold the signal near 0V at rest
- Protection diodes to clamp any over-voltage

Filip Kindt's write-up at https://www.cctv.fm/post/rp2040-tog covers this in detail with a working schematic for the X-5.

## How to determine your instrument's supply configuration

1. Measure voltage between the negative battery terminal and the center tap (if there is one). If it reads roughly half the total battery voltage, you have a center-negative supply.

2. With the instrument powered on, measure the logic HIGH voltage on an output pin of the chord IC relative to the circuit board's ground plane. If it's near 0V, the circuit's "ground" is not the same as logic LOW.

3. Check whether the IC's VDD pin connects to a positive rail or to a center tap. The datasheet (if you can find it) will clarify the intended supply configuration.

When in doubt, post your measurements in an issue before wiring anything to a GPIO.
