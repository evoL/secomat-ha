# Krüger Secomat

Home Assistant integration for monitoring and controlling Krüger Secomat room-air laundry dryers via the Krüger cloud API.

## Language

**Secomat**:
A physical Krüger room-air laundry dryer unit.
_Avoid_: Dryer, unit, PLC

**Secomat ID**:
The unique identifier assigned to a Secomat (e.g. `00.00000`), exposed over Bluetooth Low Energy and in cloud state reports.
_Avoid_: Device ID, serial number

**Claim Token**:
A secret bearer token exposed over a Secomat's Bluetooth Low Energy interface during pairing that authenticates cloud API requests for that Secomat.
_Avoid_: Claiming token, credentials, API key, password

**Power Mode**:
The laundry-drying operating state of a Secomat: `Off` (standby), `Auto` (waits for the Eye Sensor to detect hung laundry and dries automatically), or `Manual on` (immediate forced drying).
_Avoid_: Operating mode

**Room Drying**:
A continuous 24-hour dehumidification mode that keeps the room dry independently of hung laundry.
_Avoid_: Dehumidifier mode

**Drying State**:
The physical operating state of a Secomat's fan and compressor: `Idle`, `Fan only`, or `Drying`.
_Avoid_: Secomat state, hardware state, PLC state

**Target Humidity Level**:
The desired residual moisture level at which a Secomat stops a laundry drying cycle: `Very dry`, `Dry`, `Medium`, or `Humid`.
_Avoid_: Final humidity, residual moisture target

**Target Humidity Level Lock**:
A setting that persists the chosen Target Humidity Level across drying cycles instead of resetting after one cycle.
_Avoid_: Residual moisture target lock

**Control Light**:
The status light on a Secomat's physical panel.
_Avoid_: HMI backlight, display backlight

**Eye Sensor**:
The optical sensor on a Secomat that detects whether laundry is hung in front of the unit.
_Avoid_: Object sensor
