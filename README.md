# secomat-ha

Home Assistant integration for the **Krüger secomat** — a Swiss room-air laundry dryer
("Raumluftwäschetrockner") — reverse-engineered from the official **secomat** Android
app's cloud API. No local network protocol, no extra hardware: this talks to the same
cloud API the app does.

> **Unofficial project.** Not affiliated with, endorsed by, or supported by Krüger + Co.
> AG. Built by observing the official app's own network behavior for personal use with
> hardware I own. Use at your own risk — see [Disclaimer](#disclaimer).

## What this gives you

A Home Assistant `sensor`/`binary_sensor`/`select`/`switch` set per configured secomat:

- `sensor.secomat_temperature`, `sensor.secomat_humidity` — live room readings
- `sensor.secomat_target_humidity_level`, `sensor.secomat_firmware_version`
- `binary_sensor.secomat_laundry_detected` — the optical "eye" sensor that detects hung
  laundry
- `binary_sensor.secomat_room_drying_enabled`
- `select.secomat_power_mode` — Off / Auto / Manual on
- `switch.secomat_room_drying` — 24h room-drying mode

## Requirements

- A Krüger secomat, already set up and working with the official **secomat** app
- Home Assistant (any host with outbound internet — this is a cloud-polling
  integration, no Bluetooth/local network requirement at runtime)
- Your own **claim-token** for the device — see below, this is the part you can't skip

## Getting your own claim-token

There's no shared/default token — each phone that pairs with a secomat gets its own,
issued during the app's BLE "claim" pairing flow. You need to extract yours from an app
instance that's already paired with your device.

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
5. Open the patched app and **re-pair with your physical secomat** — same BLE claim
   flow as your original setup, just needs to happen once more.
6. Pull the fresh state: `adb shell run-as ch.krueger.secomat cat files/state.json`
   (works without root because the app is now debuggable). The JSON has a
   `claimedSecomats` map — pull out `claimingToken`, `secomatId`, `bluetoothAddress`.
7. Uninstall the patched app, reinstall the **real one from the Play Store** (sideloading
   the original signed APK back over the patched one is blocked by Google Play
   Protect verification — expected, don't fight it), and re-pair normally to restore
   your regular working setup.

Re-claiming didn't appear to invalidate anything account-wide in testing — it looks like
each app install just gets its own independent token (the app has no login/account
system at all), so your phone's regular app kept working fine afterward. Can't
guarantee that's true for every account/device combination, so this does carry *some*
small risk to your existing pairing — go in aware of that.

Copy `credentials.example.json` to `credentials.json` and fill in the fields from step 6.

**Treat `credentials.json` like a password** — it can read and control your real device.
It's gitignored; never commit your real one.

## Installing the Home Assistant integration

1. Copy `custom_components/secomat/` into your HA config's `custom_components/`
   directory.
2. Put your filled-in `credentials.json` somewhere HA can read (e.g.
   `/config/secomat_credentials.json`), `chmod 600` it.
3. Add to `configuration.yaml`:
   ```yaml
   secomat:
     credentials_file: /config/secomat_credentials.json
   ```
4. Restart Home Assistant.

No extra Python packages needed — the integration uses Home Assistant's own shared
`aiohttp` client session.

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
the app's normal pairing (see [Getting your own claim-token](#getting-your-own-claim-token)
above). At runtime there's no Bluetooth involved at all — this is genuinely a
cloud-only device once paired, matching Krüger's own support documentation.

## Known limitations

- `target_humidity_level` and the app's `CHANGE`/`residual_moisture_target` argument
  are exposed as read-only in this integration. The underlying enum ordinals
  (`FinalHumidity`: LOWEST/LOW/MEDIUM/HIGH → 0-3) are confirmed from the decompiled
  source, but which end means "extra dry" vs. "ironing damp" wasn't independently
  verified against the real app UI, so no write control was built around an unverified
  guess.
- Only tested against one secomat unit. Should work the same for any secomat with
  Bluetooth pairing/app support, but only one has actually been verified.
- No config flow / UI setup — YAML + a credentials file only, matching this project's
  sibling [bluesecur-ha](https://github.com/ankushbhatiya/bluesecur-ha). This also means
  entities aren't linked to a proper HA "Device" (Settings → Devices) — that would
  require migrating to `config_entries`, not done here.

## Disclaimer

This project is the result of independently observing the official secomat app's own
network behavior on hardware and an account the author owns, for personal
home-automation use. It does not include, redistribute, or depend on any of Krüger's
proprietary application code or assets. No warranty of any kind.

## License

MIT — see [LICENSE](LICENSE). Applies to this project's own code only.
