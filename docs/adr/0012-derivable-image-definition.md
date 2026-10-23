# ADR 0012: A derivable image definition

- **Status:** Accepted
- **Date:** 2026-10-23
- **Decided by:** Claude, under the maintainers' delegation (OS-028)

## Context

Distributions based on Blackbird OS should be possible the way Blackbird OS is based on Debian: kept apart, changing it without patching it (OS-028, SYS-035). Building a test derivative with mkosi 25.3 showed three traps: the system's identity was written by a script with fixed values; mkosi reads an included directory's default-named files (`mkosi.env`, `mkosi.extra/`) before the including directory's settings, so a derivative's identically named files lost; and both builds wrote to the same outputs.

## Decision

- The system's identity lives in `image/mkosi.env` as `OS_*` variables (name, pretty name, ID, ID_LIKE, version, URLs). `image/mkosi.postinst.chroot` writes `/usr/lib/os-release`, `/etc/issue`, `/etc/issue.net` and `/etc/motd` from them, and nothing else in the image definition names the system.
- A derivative includes `image/` with `Include=` and, after it, sets its own `EnvironmentFiles=` (identity), `ExtraTrees=` (files), `ImageId`, `Hostname`, output and cache directories, and per-profile `Output`. Its files are not named after mkosi's defaults, so they are read last and win.
- `examples/derivative/` is the reference and is built when the image definition changes; `docs/derivatives.md` is the guide.
