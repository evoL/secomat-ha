# Krüger Secomat

Home Assistant integration for monitoring and controlling Krüger Secomat room-air laundry dryers via the Krüger cloud API.

## Language

**Secomat**:
A physical Krüger room-air laundry dryer unit.
_Avoid_: Dryer, unit, PLC

**Secomat ID**:
The unique identifier assigned to a Secomat (e.g. `00.00000`), recorded when the unit is paired in the official mobile app.
_Avoid_: Device ID, serial number

**Claim Token**:
A per-pairing secret bearer token issued during the mobile app's Bluetooth pairing flow that authenticates cloud API requests for a single Secomat.
_Avoid_: Claiming token, credentials, API key, password

**Power Mode**:
The laundry-drying operating state of a Secomat: `Off` (standby), `Auto` (waits for the Eye Sensor to detect hung laundry and dries automatically), or `Manual on` (immediate forced drying).
_Avoid_: Operating mode

**Room Drying**:
A continuous 24-hour dehumidification mode that keeps the room dry independently of hung laundry.
_Avoid_: Dehumidifier mode

**Eye Sensor**:
The optical sensor on a Secomat that detects whether laundry is hung in front of the unit.
_Avoid_: Object sensor
