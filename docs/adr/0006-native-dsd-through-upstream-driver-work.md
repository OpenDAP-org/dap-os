# ADR 0006: Native DSD through upstream driver work

- **Status:** Accepted
- **Date:** 2026-10-22

## Context

Playback must be bit-perfect including DSD, native and DoP (OS-020). The mainline Rockchip I2S drivers have no DSD formats, so on-board native DSD is not possible with the mainline kernel today; the CS43198 driver caps DSD at DSD128 ([system architecture research](https://github.com/opendap-project/system/blob/main/docs/research/2026-10-system-architecture.md)). OpenDAP OS builds no custom kernel (OS-002), but OpenDAP may add a driver when mainline lacks one (FPT-018, for display panels, sets the precedent).

## Decision

- DoP works from the start on the on-board outputs, up to DSD64: the SoC's I2S block is specified up to 192 kHz, so DoP DSD128 (352.8 kHz) and PCM above 192 kHz are not available on-board (revised 2026-10-22, [DSD research §5](../research/2026-10-dsd512.md)). PCM is bit-perfect on-board up to 192 kHz; higher PCM rates are resampled and labelled, or go bit-perfect to a USB DAC.
- OpenDAP adds native DSD support to the Rockchip I2S-TDM driver (modelled on NXP `fsl_sai`), fixes the `cs43130` DSD speed mask so the existing native DSD DAI reaches DSD256, and upstreams both to mainline Linux.
- **DSD rates (amended 2026-10-22, [DSD512 research](../research/2026-10-dsd512.md)):** native and bit-perfect on the on-board outputs up to **DSD256**, the CS43198's hardware limit (DSDCLK ≤ fMCLK_INT / 2). **DSD512** files play on-board through a visible, labelled conversion in the playback engine (PCM 176.4 kHz / 32-bit by default). Native DSD512 and above go bit-perfect to external USB DACs that support them.
