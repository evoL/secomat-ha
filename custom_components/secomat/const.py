"""Constants for the Krüger Secomat integration."""

DOMAIN = "secomat"

DEFAULT_API_BASE_URL = "https://seco.krueger.ch:8080/app1/v1/"
DEFAULT_SCAN_INTERVAL = 30  # seconds

DEFAULT_NAME = "Secomat"
CONF_SECOMAT_ID = "secomat_id"
CONF_CLAIM_TOKEN = "claim_token"

# ch.krueger.secomat.network.SecomatCommand
CMD_OFF = "OFF"
CMD_WASH_AUTO = "WASH_AUTO"
CMD_WASH_MANUAL_ON = "WASH_MANUAL_ON"
CMD_WASH_MANUAL_OFF = "WASH_MANUAL_OFF"
CMD_ROOM_ON = "ROOM_ON"
CMD_ROOM_OFF = "ROOM_OFF"
CMD_CHANGE = "CHANGE"

# ch.krueger.secomat.network.SecomatCommandArgument
ARG_WASH_START_TIME = "prg_wash_starttime"
ARG_WASH_RESIDUAL_MOISTURE_TARGET = "residual_moisture_target"
ARG_WASH_LOCK_MOISTURE_TARGET = "lock_residual_moisture_target"
ARG_HMI_BACKLIGHT = "hmi_backlight"

# ch.krueger.secomat.redux.PowerMode -> payload.operating_mode
POWER_MODE_STAND_BY = 0  # off
POWER_MODE_READY = 1  # auto (waits for laundry / eye sensor)
POWER_MODE_ON = 2  # laundry drying (entered automatically or by a manual start)

POWER_MODE_TO_COMMAND = {
    POWER_MODE_STAND_BY: CMD_OFF,
    POWER_MODE_READY: CMD_WASH_AUTO,
    POWER_MODE_ON: CMD_WASH_MANUAL_ON,
}
POWER_MODE_NAMES = {
    POWER_MODE_STAND_BY: "Off",
    POWER_MODE_READY: "Auto",
    POWER_MODE_ON: "Manual on",
}
