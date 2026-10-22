# ADR 0005: Trust model for now

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

Signing and verification are part of the lifecycle (OS-011, HCS-010), but the trust policy had to be chosen. Research: [`../research/2026-10-os-lifecycle.md`](../research/2026-10-os-lifecycle.md).

## Decision

- Devices stay **unlocked**: the maintainers controls the keys, and nothing is burned into the SoC's one-time-programmable memory.
- **Every third-party HAT is trusted** for now, including device tree overlays that are not part of the signed image.

Both will be revisited.
