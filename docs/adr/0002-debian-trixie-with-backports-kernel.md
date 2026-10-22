# ADR 0002: Debian trixie with the backports kernel

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

DAP OS starts from prebuilt images and packages (OS-005, OS-006) and needs a mainline kernel 7 or later (OS-001) updatable as a package (OS-007). The SoC is the Rockchip RK3566 (board ADR 0003). Research: [`../research/2026-10-base-distribution.md`](../research/2026-10-base-distribution.md).

## Decision

DAP OS is based on **Debian trixie**, with the kernel from **trixie-backports**. Components are trimmed or added from there as needed; the image composition is analysed separately.
