# ADR 0011: The system is Blackbird OS, versioned by number

- **Status:** Accepted
- **Date:** 2026-10-23
- **Supersedes:** [ADR 0009](0009-release-codenames.md), [ADR 0010](0010-release-codename-theme.md)
- **RFC:** [0003](https://github.com/opendap-project/rfcs/blob/main/text/0003-blackbird-os.md)

## Context

The system was named OpenDAP OS, and each release carried a codename, the first being Blackbird (ADR 0009), with later ones named after experimental and reconnaissance aircraft (ADR 0010).

## Decision

The system is named **Blackbird OS**. "Blackbird" is the product's name, no longer a release codename, and releases are identified by their version number only (OS-011): "Blackbird OS 1.0". There are no release codenames, and `VERSION_CODENAME` is not set in `/etc/os-release`.

This repository is renamed `blackbird-os`, and its build identifiers follow: the mkosi image ID, outputs and hostname, and the Lima build VM.
