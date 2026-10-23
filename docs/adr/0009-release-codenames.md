# ADR 0009: Release codenames

- **Status:** Superseded by [ADR 0011](0011-blackbird-os.md)
- **Date:** 2026-10-22

## Context

OpenDAP OS images are versioned and published as releases (OS-011). OpenDAP OS is built on Debian ([ADR 0002](0002-debian-trixie-with-backports-kernel.md)), whose releases carry codenames (Debian 13 "trixie").

## Decision

Each OpenDAP OS release carries a public codename, as Debian's do. The first release is **Blackbird**: "OpenDAP Blackbird".

The codename appears in the release notes, as `VERSION_CODENAME` in `/etc/os-release`, and in the release's package repository suites. Its brand assets (release lockups and banner) are in [blackbird-ui](https://github.com/opendap-project/blackbird-ui/tree/main/brand/releases/blackbird).
