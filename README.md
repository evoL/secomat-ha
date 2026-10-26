# secomat-ha

Home Assistant integration for the **Krüger Secomat** — a Swiss room-air laundry dryer
("Raumluftwäschetrockner") — reverse-engineered from the official **secomat** Android
app's cloud API. No local network protocol, no extra hardware: this talks to the same
cloud API the app does.

> **Unofficial project.** Not affiliated with, endorsed by, or supported by Krüger + Co.
> AG. Built by observing the official app's own network behavior for personal use with
> hardware I own. Use at your own risk — see [Disclaimer](#disclaimer).

## What this gives you

A Home Assistant device with nine entities per configured Secomat:

- `sensor.secomat_temperature`, `sensor.secomat_humidity` — live room readings
- `sensor.secomat_target_humidity_level`, `sensor.secomat_firmware_version`
- `binary_sensor.secomat_laundry_detected` — the optical Eye Sensor that detects hung
  laundry
- `binary_sensor.secomat_room_drying_enabled`
- `select.secomat_power_mode` — Off / Auto / Manual on
- `switch.secomat_auto_dry` — one-tap Auto drying control
- `switch.secomat_room_drying` — 24h Room Drying

All entities belong to a single Secomat device in **Settings → Devices & services**,
showing its Secomat ID and live firmware version. The entity IDs above use the default
name, **Secomat**; custom names change the default entity ID prefix.

## Requirements

- A Krüger Secomat, already set up and working with the official **secomat** app
- Home Assistant (any host with outbound internet — this is a cloud-polling
  integration, no Bluetooth/local network requirement at runtime)
- Your **Secomat ID** and **Claim Token** — see below, this is the part you can't skip

## Getting your Secomat ID and Claim Token

There's no shared/default Claim Token — each phone that pairs with a Secomat gets its own,
issued during the app's BLE "claim" pairing flow. You need to extract yours from an app
instance that's already paired with your Secomat.

The straightforward route (`adb backup`) doesn't work: the app's local
`files/state.json` (which holds the token in plaintext) is fully backup-eligible per its
manifest, but Android 12+ returns an **empty archive** for `adb backup` on any regular
(non-debuggable) release-signed app, regardless of the `allowBackup` flag — this is a
platform restriction, not something specific to this app.

What does work, without root:

1. Download the official APK (e.g. via apkcombo/apkpure — package `ch.krueger.secomat`).
2. Decode it with [`apktool`](https://apktool.org/), add `android:debuggable="true"` to
   the `<application>` tag in the decoded manifest, rebuild with `apktool b`.
3. Sign the rebuilt APK with any throwaway keystore (`zipalign` + `apksigner sign`,
   both in the Android SDK build-tools).
4. On your phone (USB debugging enabled): `adb uninstall ch.krueger.secomat` (this
   destroys the app's current local data — expected), then `adb install` the patched
   APK.
5. Open the patched app and **re-pair with your physical Secomat** — same BLE claim
   flow as your original setup, just needs to happen once more.
6. Pull the fresh state: `adb shell run-as ch.krueger.secomat cat files/state.json`
   (works without root because the app is now debuggable). The JSON has a
   `claimedSecomats` map — copy `claimingToken` (**Claim Token**) and `secomatId`
   (**Secomat ID**, e.g. `00.00000`). The Bluetooth address is not needed.
7. Uninstall the patched app, reinstall the **real one from the Play Store** (sideloading
   the original signed APK back over the patched one is blocked by Google Play
   Protect verification — expected, don't fight it), and re-pair normally to restore
   your regular working setup.

Re-claiming didn't appear to invalidate anything account-wide in testing — it looks like
each app install just gets its own independent token (the app has no login/account
system at all), so your phone's regular app kept working fine afterward. Can't
guarantee that's true for every account/device combination, so this does carry *some*
small risk to your existing pairing — go in aware of that.

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
3. Enter your **Secomat ID** and **Claim Token**. Optionally enter a **Name**; the
   default is **Secomat**. The Claim Token input is masked.
4. Submit. Home Assistant validates the Claim Token against the Krüger cloud API
   before adding the Secomat. A rejected Claim Token shows an authentication error;
   a network or server outage shows a connection error so you can retry later.

For another Secomat, use **Add Entry** on the integration page and enter its own
Secomat ID and Claim Token. Duplicate Secomat IDs are rejected. Each Secomat polls
every 60 seconds and can be reloaded or removed independently without restarting
Home Assistant.

No extra Python packages needed — the integration uses Home Assistant's own shared
`aiohttp` client session.

### Updating a Claim Token

In **Settings → Devices & services → Krüger Secomat**, open the Secomat entry's
**⋮ → Reconfigure** menu. Enter the replacement **Claim Token** and submit. Home
Assistant validates it, updates the existing entry, and reloads it automatically.
The Secomat ID, entities, and history are unchanged.

If polling rejects a Claim Token, Home Assistant automatically prompts you to
**Reauthenticate**. Follow that prompt to enter a replacement Claim Token. Temporary
cloud outages only mark the entities unavailable; polling recovers automatically
when the service returns.

### Moving from the legacy setup

The old file-based configuration is no longer supported and is not imported
automatically. Remove its legacy configuration, then add each Secomat through the UI
using the same Secomat ID and Claim Token. Existing entity unique IDs are preserved;
the default name **Secomat** also preserves the documented default entity IDs, so
dashboards, automations, and long-term sensor statistics continue to use those
identities.

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

BLE is used **only once**, during the app's own device-claim/pairing flow — this
integration doesn't re-implement that handshake, it piggybacks on a token obtained via
the app's normal pairing (see [Getting your Secomat ID and Claim Token](#getting-your-secomat-id-and-claim-token)
above). At runtime there's no Bluetooth involved at all — this is genuinely a
cloud-only device once paired, matching Krüger's own support documentation.

## Known limitations

- `target_humidity_level` and the app's `CHANGE`/`residual_moisture_target` argument
  are exposed as read-only in this integration. The underlying enum ordinals
  (`FinalHumidity`: LOWEST/LOW/MEDIUM/HIGH → 0-3) are confirmed from the decompiled
  source, but which end means "extra dry" vs. "ironing damp" wasn't independently
  verified against the real app UI, so no write control was built around an unverified
  guess.
- Only tested against one Secomat. Should work the same for any Secomat with
  Bluetooth pairing/app support, but only one has actually been verified.

## Development

Run `uvx ruff check .` and `uv run pytest`. Tests use
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
