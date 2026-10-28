# secomat-ha

Home Assistant integration for the **Krüger Secomat** — a Swiss room-air laundry dryer
("Raumluftwäschetrockner") — reverse-engineered from the official **secomat** Android
app's cloud API. No local network protocol, no extra hardware: this talks to the same
cloud API the app does.

> **Unofficial project.** Not affiliated with, endorsed by, or supported by Krüger + Co.
> AG. Built by observing the official app's own network behavior for personal use with
> hardware I own. Use at your own risk — see [Disclaimer](#disclaimer).

## What this gives you

A Home Assistant device with 14 entities per configured Secomat:

| Entity | Purpose |
| --- | --- |
| `sensor.secomat_temperature` | Live room temperature (°C) |
| `sensor.secomat_humidity` | Live room humidity (%) |
| `sensor.secomat_drying_state` | Physical Drying State: Idle / Fan only / Drying / Unknown |
| `sensor.secomat_drying_state_raw` | Diagnostic raw integer Drying State, without averaged measurement statistics |
| `binary_sensor.secomat_drying` | On whenever the fan or compressor is physically running |
| `binary_sensor.secomat_laundry_detected` | The optical Eye Sensor detects hung laundry |
| `binary_sensor.secomat_problem` | Diagnostic warnings/errors, with the active list in the `errors` attribute |
| `binary_sensor.secomat_connectivity` | Diagnostic live cloud connection, with `source` and `age` attributes |
| `select.secomat_power_mode` | Power Mode: Off / Auto / Manual on |
| `select.secomat_target_humidity_level` | Target Humidity Level: Very dry / Dry / Medium / Humid |
| `switch.secomat_auto_dry` | One-tap Auto drying control |
| `switch.secomat_room_drying` | 24-hour Room Drying |
| `switch.secomat_target_humidity_level_lock` | Configuration: persist the Target Humidity Level across drying cycles |
| `switch.secomat_control_light` | Configuration: the status light on the physical panel |

All entities belong to a single Secomat device in **Settings → Devices & services**,
showing its Secomat ID and live firmware version. The entity IDs above use the default
name, **Secomat**; custom names change the default entity ID prefix.

Power Mode and Room Drying describe the program state; Drying State shows what
the fan and compressor are actually doing. Raw values `0` and `15` mean Idle,
`2` means Fan only, and `6` and `12` mean Drying. State `15` is a completed cycle
waiting for laundry removal, or Room Drying standby, with the fan and compressor
off. Unseen integers remain visible unchanged in the raw diagnostic sensor;
the enum and Drying binary sensor report unknown for unrecognized or missing readings.

The existing **Manual on** label is retained for Power Mode `2`, but this state can
also be entered automatically when Auto detects laundry. It can persist after a
cycle finishes, so it does not by itself mean that the fan or compressor is running.

When the Secomat disconnects from the cloud, Connectivity stays available and shows
**off**. All other 13 entities become **unavailable** so cached readings are not
recorded as live measurements. A failed cloud poll makes Connectivity unavailable
too. Live readings recover automatically when the connection returns.

## Requirements

- A Krüger Secomat, already set up and working with the official **secomat** app
- Home Assistant (any host with outbound internet — this is a cloud-polling
  integration, no Bluetooth/local network requirement at runtime)
- Your **Claim Token** — read it directly over BLE as described below. Home Assistant
  discovers the **Secomat ID** automatically; you do not need to look it up.

## Getting your Claim Token over BLE

Use a standard Bluetooth Low Energy GATT tool such as **nRF Connect for Mobile on
Android**, near your Secomat. The official app can remain installed and paired; no
root access, app modification, or re-pairing is needed.

1. Enable Bluetooth, open nRF Connect, grant its requested Bluetooth/nearby-device
   permissions, then scan for and connect to your Secomat.
2. **Before reading the Claim Token**, use the connection menu's **Request MTU**
   action. Request **247**, for example, and confirm that the negotiated **MTU is at
   least 35** (`MTU >= 35`).
3. Open GATT service `bbbbbbbb-1234-5678-abcd-06050403ff00`.
4. Read characteristic `bbbbbbbb-1234-5678-abcd-06050403ff01` within that service.
   Display/decode its value as **ASCII text** and copy all **32 ASCII characters** of
   the Claim Token, not the hexadecimal representation. Then disconnect.
5. Enter the Claim Token in Home Assistant's setup form. Home Assistant retrieves
   the Secomat ID from the cloud response.

**Why the MTU matters:** the Secomat's BLE server has a bug in its
`ATT_READ_BLOB_REQ` offset handling. At the default **23-byte ATT MTU**, a long read
repeats the first **22 characters** of the Claim Token instead of correctly fetching
the remainder. Negotiating `MTU >= 35` before reading retrieves all 32 ASCII
characters in one `ATT_READ_REQ`. If the value repeats or is incomplete, negotiate
the larger MTU and read it again; do not use the broken default-MTU result.

**Keep your Claim Token secret** — it grants access to monitor and control your Secomat.
Enter it directly in Home Assistant's setup form below. No separate configuration file
is needed. Home Assistant stores it in the config entry; protect your Home Assistant
configuration and backups, and never publish your Claim Token.

## Installing the Home Assistant integration

### Via HACS (recommended)

1. Install [HACS](https://hacs.xyz/docs/use/download/download/) if you haven't already.
2. Add this repository as a custom repository: **HACS → Integrations → ⋮ → Custom
   repositories**, then enter `https://github.com/evoL/secomat-ha` with category
   **Integration**.

   [![Open your Home Assistant instance and open a repository inside the HACS custom repositories dialog.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=evoL&repository=secomat-ha&category=integration)

3. Search for **Krüger Secomat** in HACS, install it, and restart Home Assistant when
   prompted.

HACS installs from the `main` branch; there are no tagged releases yet.

### Manually

Copy `custom_components/secomat/` into your HA config's `custom_components/`
directory, then restart Home Assistant to discover the integration.

### Configuration (either route)

1. Open **Settings → Devices & services → Add Integration**.
2. Search for **Krüger Secomat**.
3. Enter your **Claim Token**. Optionally enter a **Name**; the default is
   **Secomat**. The Claim Token input is masked.
4. Submit. Home Assistant validates the Claim Token against the Krüger cloud API
   before adding the Secomat and automatically discovers its **Secomat ID**.
   A rejected Claim Token shows an authentication error;
   a network or server outage shows a connection error so you can retry later.

For another Secomat, use **Add Entry** on the integration page with its own Claim
Token. Duplicate Secomat IDs are rejected automatically. Setup can also succeed
while the Secomat is offline if the cloud still has its cached state and Secomat ID.
Each Secomat polls every **30 seconds** and can be reloaded or removed independently
without restarting Home Assistant.

No extra Python packages needed — the integration uses Home Assistant's own shared
`aiohttp` client session.

### Updating a Claim Token

In **Settings → Devices & services → Krüger Secomat**, open the Secomat entry's
**⋮ → Reconfigure** menu. Enter the replacement **Claim Token** and submit. Home
Assistant validates that it belongs to the **same Secomat ID**, updates the existing
entry, and reloads it automatically. A token for a different Secomat is rejected
without replacing the current token. The Secomat ID, entities, and history are
unchanged.

If polling or a control command rejects a Claim Token, Home Assistant automatically
prompts you to **Reauthenticate**. Follow that prompt to enter a replacement Claim
Token for the same Secomat. Temporary cloud outages only mark the entities
unavailable; polling recovers automatically when the service returns.

## How it works

The app is a plain Kotlin/Jetpack Compose app (decompiled cleanly with `jadx` — no
Xamarin/Flutter obfuscation to fight). Its `network/SecomatService.kt` is a two-verb
Retrofit interface against a single resource:

```
GET  https://seco.krueger.ch:8080/app1/v1/plc   -> current state
POST https://seco.krueger.ch:8080/app1/v1/plc   -> send a command
```

Both authenticated with two headers: `claim-token` (the per-device secret from BLE
pairing) and `api: 1` (constant). `Content-Type: application/json` is required on POST —
omitting it gets a `500`, not a graceful error.

Commands: `OFF`, `WASH_AUTO`, `WASH_MANUAL_ON`, `WASH_MANUAL_OFF`, `ROOM_ON`,
`ROOM_OFF`, and a generic `CHANGE` (for individual settings like
`residual_moisture_target` or `hmi_backlight`), sent as
`{"command": "...", "args": {...}}`. The device validates commands against its current
state server-side — e.g. it correctly rejects `ROOM_ON` with a `400` while a manual
drying cycle (`operating_mode` = 2, "Manual on") is already active, rather than
silently corrupting its own state.

Manual on sends `WASH_MANUAL_ON` with `{"prg_wash_starttime": 0}` to start immediately.
Both the Power Mode selector and Auto dry switch use `WASH_AUTO` to enter Auto from
Off, but `WASH_MANUAL_OFF` to return from Manual on to Auto: sending `WASH_AUTO`
while Power Mode is `2` is rejected with HTTP 400.
After any successful control command, the integration waits **2 seconds** before
requesting refreshed cloud state, giving the Secomat time to report the change.
Hardware rundown can take longer when returning to Auto; controls continue to show
the reported mode until a later poll confirms the transition, rather than assuming
that the command has already completed.
Rejected commands and network failures surface as Home Assistant service errors
rather than silently reverting the control.

Cloud responses distinguish live state (`src: "ws"`) from cached offline state
(`src: "db"`). The Connectivity diagnostic exposes this as `source`, alongside the
cloud's `age` timestamp, and gates availability of the other entities.

BLE is needed only to [read your Claim Token](#getting-your-claim-token-over-ble)
using a separate tool. The integration does not discover or read Secomats over
Bluetooth at runtime, or provision their Wi-Fi; all runtime monitoring and control
uses the cloud API.

## Development

The default test interpreter is pinned in `.python-version`; dependency versions are
recorded in the tracked `uv.lock`. Use an isolated environment to preserve any
existing `.venv`:

```sh
export UV_PROJECT_ENVIRONMENT=.venv-agent
uv run --locked ruff check .
uv run --locked pytest
```

CI uses the same interpreter and locked commands. Update dependencies deliberately
with `uv lock`; `--locked` rejects a stale lockfile instead of resolving new versions
during checks.

Tests use
`pytest-homeassistant-custom-component` and fake only the Krüger cloud HTTP boundary;
they exercise Home Assistant's flow manager, config entry lifecycle, registries,
entity states, and services without needing a real Secomat or Claim Token.

## Disclaimer

This project is the result of independently observing the official secomat app's own
network behavior on hardware and an account the author owns, for personal
home-automation use. It does not include, redistribute, or depend on any of Krüger's
proprietary application code or assets. No warranty of any kind.

## Acknowledgements

This project started with the original reverse-engineering work by
[@ankushbhatiya](https://github.com/ankushbhatiya), who created the initial Krüger
Secomat Home Assistant integration this repo forked from.

## License

MIT — see [LICENSE](LICENSE). Applies to this project's own code only.
