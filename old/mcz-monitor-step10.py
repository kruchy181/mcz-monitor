"""
MCZ Easy Connect Monitor - STEP 10
Finalny monitor terminalowy
"""

import json,time,requests,sys,random,os
from datetime import datetime

API="https://remote.mcz.it"
CUSTOMER_CODE="354924"
BRAND_ID="1"
UUID="1c3be3cd-360c-4c9f-af15-1f79e9ccbc2a"
EMAIL="lkruszew@gmail.com"
PASSWORD="Xkum#Fkrew40"

DEBUG=False

STATUS_MAP={
0:"OFF",
1:"START",
2:"LOAD PELLETS",
3:"STARTING",
4:"ON",
5:"CLEANING FIRE-POT",
6:"CLEANING FINAL",
7:"ECO STOP",
8:"PELLETS DEPLETED",
9:"IGNITION FAILED",
10:"ALARM",
11:"MEM.ALM",
}

def clear():
    os.system("clear")

def base_headers():
    return{
    "Content-Type":"application/json",
    "Accept":"application/json",
    "id_brand":BRAND_ID,
    "customer_code":CUSTOMER_CODE
    }

def do_login():

    h={**base_headers(),"local":"true","Authorization":UUID}

    requests.post(
        f"{API}/appSignup",
        json={
            "phone_type":"Android",
            "phone_id":UUID,
            "phone_version":"1.0",
            "language":"en",
            "id_app":UUID,
            "push_notification_token":UUID,
            "push_notification_active":False
        },
        headers=base_headers()
    )

    r=requests.post(
        f"{API}/userLogin",
        json={"email":EMAIL,"password":PASSWORD},
        headers=h
    )

    if r.status_code!=200:
        print("Login error")
        sys.exit(1)

    return r.json()["token"]

def auth_headers(token):
    return{**base_headers(),"local":"false","Authorization":token}

def get_device(token):

    r=requests.post(
        f"{API}/deviceList",
        json={},
        headers=auth_headers(token)
    )

    d=r.json()["device"][0]

    return d["id_device"],d["id_product"],d["name"],d["name_product"]

def get_registers(token,id_device,id_product):

    r=requests.post(
        f"{API}/deviceGetRegistersMap",
        json={
            "id_device":id_device,
            "id_product":id_product,
            "last_update":"2018-06-03T08:59:54.043"
        },
        headers=auth_headers(token)
    )

    reg_map={}

    for rm in r.json()["device_registers_map"]["registers_map"]:
        for reg in rm["registers"]:

            reg_map[reg["reg_key"]]={
                "offset":reg["offset"],
                "formula":reg["formula"],
                "mask":reg.get("mask",65535)
            }

    return reg_map

def read_buffer(token,id_device,id_product):

    r=requests.post(
        f"{API}/deviceGetBufferReading",
        json={
            "id_device":id_device,
            "id_product":id_product,
            "BufferId":1
        },
        headers=auth_headers(token)
    )

    id_req=r.json().get("idRequest")

    if not id_req:
        return None

    for _ in range(15):

        time.sleep(2)

        r2=requests.get(
            f"{API}/deviceJobStatus/{id_req}",
            headers=auth_headers(token)
        )

        if r2.status_code==200 and r2.json().get("jobAnswerStatus")=="completed":
            return r2.json().get("jobAnswerData")

    return None

def safe_eval(formula,value):

    try:

        expr=formula.replace("#",str(value))

        if all(c in "0123456789.+-*/() " for c in expr):
            return eval(expr)

        return value

    except:
        return value

def get_value(reg_map,values_dict,key):

    if key not in reg_map:
        return None

    offset=reg_map[key]["offset"]
    mask=reg_map[key]["mask"]
    formula=reg_map[key]["formula"]

    if offset not in values_dict:
        return None

    raw=values_dict[offset] & mask

    return safe_eval(formula,raw)

def monitor(reg_map,vals,name,product):

    status=get_value(reg_map,vals,"status_get")
    power_raw=get_value(reg_map,vals,"real_power_get")
    water=get_value(reg_map,vals,"temp_water_get")
    smoke=get_value(reg_map,vals,"temp_gas_flue_get")
    boiler=get_value(reg_map,vals,"temp_water_boiler_get")

    if power_raw is not None:
        power=max(0,power_raw-9)
    else:
        power=0

    if status is None:
        status_name="?"
    else:
        status_name=STATUS_MAP.get(int(status),"UNKNOWN")

    clear()

    print("MCZ MONITOR")
    print("================================")
    print(name,"(",product,")")
    print("--------------------------------")
    print("STATUS       :",status_name)
    print("REAL POWER   :",power)
    print("WATER TEMP   :",water,"°C")
    print("BOILER TEMP  :",boiler,"°C")
    print("SMOKE TEMP   :",smoke,"°C")
    print("--------------------------------")
    print("Update:",datetime.now().strftime("%H:%M:%S"))
    print("================================")

def main():

    token=do_login()

    id_device,id_product,name,product=get_device(token)

    reg_map=get_registers(token,id_device,id_product)

    while True:

        job=read_buffer(token,id_device,id_product)

        if job:

            vals=dict(zip(job["Items"],job["Values"]))

            monitor(reg_map,vals,name,product)

        sleep_time=random.randint(120,180)

        time.sleep(sleep_time)

if __name__=="__main__":
    main()