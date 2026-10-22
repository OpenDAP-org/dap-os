# ADR 0006: Native DSD through upstream driver work

- **Status:** Accepted
- **Date:** 2026-10-22

## Context

Playback must be bit-perfect including DSD, native and DoP (OS-020). The mainline Rockchip I2S drivers have no DSD formats, so on-board native DSD is not possible with the mainline kernel today; the CS43198 driver caps DSD at DSD128 ([system architecture research](https://github.com/opendap-project/system/blob/main/docs/research/2026-10-system-architecture.md)). DAP OS builds no custom kernel (OS-002), but OpenDAP may add a driver when mainline lacks one (FPT-018, for display panels, sets the precedent).

## Decision

- DoP works from the start on the on-board outputs.
- OpenDAP adds native DSD support to the Rockchip I2S driver (and extends the CS43198 limits where the hardware allows), and upstreams it to mainline Linux.
