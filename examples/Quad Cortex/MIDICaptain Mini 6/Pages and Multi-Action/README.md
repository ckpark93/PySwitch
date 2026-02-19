## Quad Cortex Mini 6 Mapping (2026-02)

Key layout:
- Top: `key0 key1 key2`
- Bottom: `key3 key4 key5`

Global:
- Hold time: `600ms`
- `key5` long: Gig View toggle (`CC46`)
- `key2` short: Mode cycle (`CC47`: 0 -> 1 -> 2)

### Gig View mode (`gig_view = ON`)
- `key0` short: current page A, long: opposite page A
- `key1` short: current page B, long: opposite page B
- `key2` long: QC footswitch page swap (`CC64`)
- `key3` short: current page C, long: opposite page C
- `key4` short: current page D, long: opposite page D
- `key5` short: Tap Tempo (`CC44`)

### Chain/Normal mode (`gig_view = OFF`)
- `key0/1/3/4` short: internal MIDI page(1/2) 기준 A/B/C/D 전송
- `key0` long: Tuner toggle (`CC45`)
- `key1` long: QC footswitch page swap (`CC64`)
- `key2` long: internal MIDI page swap (no `CC64`)
- `key3` long: Scene +1 (`CC43` forward wrap)
- `key4` long: Scene -1 (`CC43` backward wrap)
- `key5` short: Tap Tempo (`CC44`)

Display label policy:
- Per-switch label text is kept at `<= 5` chars.

Files to copy to controller root:
- `inputs.py`
- `display.py`
- `communication.py`

## Battery Probe (optional)
- Copy `battery_probe.py` to device root.
- Temporarily replace device `code.py` with contents of `code_probe.py`.
- Open USB serial console and reboot device.
- Plug/unplug USB power and check which pins change:
  - Digital candidates: `GP4`, `GP6`
  - Analog candidates: `GP26`, `GP27`, `GP28`, `GP29`
- Restore normal boot by replacing device `code.py` with `code_pyswitch.py`.
