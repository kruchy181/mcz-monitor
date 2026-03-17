"""
MCZ Easy Connect Monitor v9 - STEP 2
Dodano:
- poprawną interpretację ECO STOP / STAND-BY
"""

import json, time, requests, sys
from datetime import datetime

API = "https://remote.mcz.it"
CUSTOMER_CODE = "354924"
BRAND_ID = "1"
UUID = "1c3be3cd-360c-4c9f-af15-1f79e9ccbc2a"
EMAIL = "lkruszew@gmail.com"
PASSWORD = "Xkum#Fkrew40"
CHECK_INTERVAL = 180


STATUS_MAP = {
    0: "OFF",
    1: "START",
    2: "LOAD PELLETS",
    3: "FLAME LIGHT",
    4: "ON",
    5: "CLEANING FIRE-POT",
    6: "CLEANING FINAL",
    7: "ECO STOP",
    8: "PELLETS DEPLETED",
    9: "IGNITION FAILED",
    10: "ALARM",
    11: "MEM.ALM",
}


ALARM_MAP = {
    0: "BRAK",
    1: "BLACK OUT",
    2: "NO SWITCH ON (A02)",
    3: "PELLETS FINISHED",
    4: "SMOKE TEMPERATURE",
    5: "EXTRACTOR ROTATIONS",
    6: "FAULTY SMOKE EXTRACTOR",
    9: "PELLET AUGER BLOCKED",
    14: "THERMOSTAT MANUAL RESET",
    15: "FIRE DOOR / ASH PAN OPEN",
    16: "PELLET TANK DOOR OPEN",
}


def is_alarm_state(status, alarm):

    NORMAL_STATES = {0,1,2,3,4,5,6,7}

    try:
        s = int(status)
    except:
        return False

    if s not in NORMAL_STATES:
        return True

    if alarm is not None and int(alarm) != 0:
        return True

    return False


def interpret_status(status, power):
    """
    Poprawna interpretacja statusu pieca
    """

    if status is None:
        return "?"

    s = int(status)

    if s == 7:

        if power == 0 or power is None:
            return "STAND-BY"

        return "ECO STOP"

    return STATUS_MAP.get(s, f"NIEZNANY ({s})")


def base_headers():
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "id_brand": BRAND_ID,
        "customer_code": CUSTOMER_CODE,
    }


def do_login():

    h = {**base_headers(), "local": "true", "Authorization": UUID}

    requests.post(
        f"{API}/appSignup",
        json={
            "phone_type": "Android",
            "phone_id": UUID,
            "phone_version": "1.0",
            "language": "en",
            "id_app": UUID,
            "push_notification_token": UUID,
            "push_notification_active": False,
        },
        headers=base_headers(),
    )

    r = requests.post(
        f"{API}/userLogin",
        json={"email": EMAIL, "password": PASSWORD},
        headers=h,
    )

    if r.status_code != 200:
        print(f"[!] Blad logowania: {r.text}")
        sys.exit(1)

    return r.json()["token"]


def auth_headers(token):
    return {**base_headers(), "local": "false", "Authorization": token}


def get_device(token):

    r = requests.post(
        f"{API}/deviceList",
        json={},
        headers=auth_headers(token),
    )

    d = r.json()["device"][0]

    print(f"[+] Piec: {d['name']} ({d['name_product']}) Online: {d['is_online']}")

    return d["id_device"], d["id_product"]


def get_registers(token, id_device, id_product):

    r = requests.post(
        f"{API}/deviceGetRegistersMap",
        json={
            "id_device": id_device,
            "id_product": id_product,
            "last_update": "2018-06-03T08:59:54.043",
        },
        headers=auth_headers(token),
    )

    reg_map = {}

    for rm in r.json()["device_registers_map"]["registers_map"]:
        for reg in rm["registers"]:
            reg_map[reg["reg_key"]] = {
                "offset": reg["offset"],
                "formula": reg["formula"],
                "mask": reg.get("mask", 65535),
            }

    return reg_map


def read_buffer(token, id_device, id_product):

    r = requests.post(
        f"{API}/deviceGetBufferReading",
        json={
            "id_device": id_device,
            "id_product": id_product,
            "BufferId": 1,
        },
        headers=auth_headers(token),
    )

    id_req = r.json().get("idRequest")

    if not id_req:
        return None

    for _ in range(15):

        time.sleep(2)

        r2 = requests.get(
            f"{API}/deviceJobStatus/{id_req}",
            headers=auth_headers(token),
        )

        if r2.status_code == 200 and r2.json().get("jobAnswerStatus") == "completed":
            return r2.json().get("jobAnswerData")

    return None


def safe_eval(formula, value):

    try:

        expr = formula.replace("#", str(value))

        if all(c in "0123456789.+-*/() " for c in expr):
            return eval(expr)

        return value

    except:
        return value


def get_value(reg_map, values_dict, key):

    if key not in reg_map:
        return None

    offset = reg_map[key]["offset"]
    mask = reg_map[key]["mask"]
    formula = reg_map[key]["formula"]

    if offset not in values_dict:
        return None

    raw = values_dict[offset] & mask

    return safe_eval(formula, raw)


def print_status(reg_map, values_dict):

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    status = get_value(reg_map, values_dict, "status_get")
    alarm = get_value(reg_map, values_dict, "alarms_get")
    power = get_value(reg_map, values_dict, "real_power_get")

    water = get_value(reg_map, values_dict, "temp_water_get")
    smoke = get_value(reg_map, values_dict, "temp_gas_flue_get")
    boiler = get_value(reg_map, values_dict, "temp_boiler_get")

    s_name = interpret_status(status, power)
    a_name = ALARM_MAP.get(int(alarm), "BRAK") if alarm is not None else "BRAK"

    print(f"\n{'='*50}")
    print(f"  MCZ Monitor - {now}")
    print(f"{'='*50}")
    print(f"  STATUS:      {s_name}")
    print(f"  ALARM:       {a_name}")

    if is_alarm_state(status, alarm):
        print("  !!! ALARM STATE DETECTED !!!")

    if water is not None:
        print(f"  Water Temp:  {water}°C")

    if smoke is not None:
        print(f"  Smoke Temp:  {smoke}°C")

    if boiler is not None:
        print(f"  Boiler Temp: {boiler}°C")

    print(f"{'='*50}")


def main():

    print("=" * 50)
    print("  MCZ Easy Connect Monitor v9 - STEP 2")
    print("=" * 50)

    token = do_login()

    id_device, id_product = get_device(token)

    reg_map = get_registers(token, id_device, id_product)

    print(f"\n[*] Monitorowanie co {CHECK_INTERVAL}s (Ctrl+C = stop)\n")

    while True:

        print("[*] Odczyt danych...")

        job = read_buffer(token, id_device, id_product)

        if job:

            vals = dict(zip(job["Items"], job["Values"]))

            print_status(reg_map, vals)

        else:

            print("[!] Brak danych")

        print(f"[*] Nastepny odczyt za {CHECK_INTERVAL}s...")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()