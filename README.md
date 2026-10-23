# Blackbird OS

Blackbird OS, the operating system of OpenDAP devices: the image definition, its profiles and releases. The T1 is its first device; a device's specifics come from its board support package, never from this definition.

To build your own custom ROM based on Blackbird OS, see [docs/derivatives.md](docs/derivatives.md).

## Layout

- `image/` — the image definition (built with toolkit-image `odap-image`; outputs in `image/mkosi.output/`)
- `examples/` — `derivative/`, a minimal distribution based on Blackbird OS ([guide](docs/derivatives.md))
- `docs/`

## License

This repository follows the [REUSE](https://reuse.software) layout: license texts live in `LICENSES/` and `REUSE.toml` maps each path to its license.

- Default: **GNU GPL v3.0 or later** (`GPL-3.0-or-later`)
- Markdown files: **Creative Commons Attribution-ShareAlike 4.0** (`CC-BY-SA-4.0`)
- `docs/`: **Creative Commons Attribution-ShareAlike 4.0** (`CC-BY-SA-4.0`)

Copyright © 2026 The OpenDAP Project.
