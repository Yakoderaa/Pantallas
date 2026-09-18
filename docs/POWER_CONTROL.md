# Monitor power control

External monitor power control is not uniform on Windows. Different panels,
GPU drivers, docks and adapters expose different behavior.

Pantallas therefore treats power as a **per-monitor capability**, not a global
assumption.

## Methods

### DDC/CI

Pantallas can use MCCS VCP code `0xD6` when the monitor exposes it. A command
being acknowledged is not enough: Pantallas verifies that the panel actually
changed power state.

### Windows display path

When DDC/CI is unsupported or unreliable, Pantallas can disable the monitor's
Windows display output instead.

## Automatic mode

Each monitor starts in **Automatic** mode. Pantallas records outcomes
separately per monitor.

- DDC command acknowledged but monitor stays on → DDC is treated as failed.
- DDC turns the monitor off but software cannot wake it → future Automatic
  attempts prefer Windows.
- DDC off + DDC wake both work → Automatic can keep using DDC.
- The user can override Automatic with **Windows** or **DDC/CI** in the monitor
  card.

This avoids forcing the same power strategy onto monitors with different
firmware behavior.

## Last-monitor protection

By default Pantallas refuses to turn off the final usable display. The user may
explicitly disable this protection in Settings after acknowledging the risk.
