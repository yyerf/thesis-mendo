# Vendor DIP-switch sheets (external evidence)

Downloaded 2026-08-03 while reverse-engineering the TB74-PH6 pulse interface.
These are **manufacturer documents for sibling currency builds**, not the
missing Philippine sheet for our exact unit. They are strong structural
evidence and they agree with each other, but the Phase-0 bench trial is still
what promotes any value here to "measured".

| File | Source URL | What it establishes |
| --- | --- | --- |
| `TB74-DipSetting-Mexico-MXP6-20-1K-RS232-104U.pdf` | `topvme.com/index.php/files/330/Currencies-accepted-and-DipSetting/417/` | **Primary.** Genuine TOPVME **TB74** sheet. MXP6 = 20/50/100/200/500/1000 — the same six-bill structure as PHP6 — on the same **10-way + 4-way** bank layout as our unit. |
| `ICT-V7P-PHP6-Pulse-MDB-ICT104V-ICT104U.pdf` | `icteurope.de/en/files/V7P/` | Genuine **PHP6** currency set: confirms ₱20/50/100/200/500/1000 and the `1 pulse / PHP 10` base scaling. 8+4 bank variant. |
| `ICT-TAO-A.V-PHP6-Pulse-ICT-MDB.pdf` | `ictgroup.net.cn/files/tao/` | Second independent **PHP6** sheet; same denominations and same ₱10 pulse base. |
| `ICT-TP70-P5-MYR7-Pulse.pdf` | `ictgroup.net.cn/files/TP70/` | Independent **10-way + 4-way** layout confirming the SW1-3 / SW4 / SW5 / SW6-10 role split. |

## Bank-layout families

Two families exist in this device class. Do not mix their polarities.

- **10 + 4 banks** (TB74, TP70/P5, L70/P5) — SW1-3 pulse scaling, SW4 speed,
  SW5 inhibit level, SW6-10 denominations, **ON = ACCEPT**.
- **8 + 4 banks** (ICT TAO-A.V, V7P) — SW1-5 denominations with
  **ON = REJECT**, SW7 harness, SW8 inhibit level; scaling/timing live on the
  4-way bank.

Our unit has CTS195-10 (10-way) + CTS208-4 (4-way), so it is the **10 + 4**
family and **ON = ACCEPT**.

## Rejected source

`industrialmonitordirect.com/blogs/knowledgebase/tb74-bill-acceptor-arduino-wiring-and-pulse-output-configuration`
claims the TB74 has a single 8-position bank with switch 7 = pulse width and
switch 8 = output polarity. That contradicts both the physical hardware
(10-way + 4-way) and the manufacturer sheet above. Treat that page as
unreliable; do not cite it.
