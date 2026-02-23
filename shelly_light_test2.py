#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import json
import requests
import warnings
from pathlib import Path
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

# suppress warning safely
try:
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
except ImportError:
    pass


# ===== ВСТАВТЕ СВОЇ ДАНІ =====
SHELLY_IP = "185.179.213.130:6789"
SHELLY_USER = "admin"
SHELLY_PASS = "TdTge3Yq-CTV9iZf"          # якщо без пароля — залиш ""
BOT_TOKEN = "8218450455:AAFXLlKm4rGAlka7t_yxIaeCAlEndFNIvOs"            # токен бота

CHAT_IDS = [
    -1003787965924   # твоя група
]
SHELLY_INTERVAL = 5
TG_INTERVAL = 1

# ===========================


RPC_URL = f"http://{SHELLY_IP}/rpc"
RPC_CMD = {"id":1,"method":"EM.GetStatus","params":{"id":0}}

STATE_FILE = Path(__file__).with_name("light_state.json")

LAST_UPDATE_ID = None


# ========= UTILS =========

def fmt(sec):

    sec = int(sec)

    h = sec // 3600
    m = (sec % 3600) // 60

    return f"{h} год {m} хв"


# ========= TELEGRAM =========


def send_msg(text, chat_ids=None):

    ids = chat_ids if chat_ids else CHAT_IDS

    for chat_id in ids:

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id":chat_id,"text":text},
            timeout=10
        )


def send_keyboard(chat_id):

    keyboard = {
        "keyboard":[
            ["Статус"]
        ],
        "resize_keyboard":True,
        "persistent":True
    }

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id":chat_id,
            "text":"Керування:",
            "reply_markup":keyboard
        }
    )


def check_tg(st):

    global LAST_UPDATE_ID

    try:

        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={
                "offset": LAST_UPDATE_ID + 1 if LAST_UPDATE_ID else None,
                "timeout": 0
            },
            timeout=10
        ).json()

        for upd in r.get("result", []):

            LAST_UPDATE_ID = upd["update_id"]

            msg = upd.get("message", {}).get("text", "")
            chat_id = upd.get("message", {}).get("chat", {}).get("id")

            if not msg:
                continue

            msg = msg.strip()

            # ПРАВИЛЬНА ОБРОБКА ДЛЯ ГРУП І SLASH-МЕНЮ

            if msg == "/status" or msg.startswith("/status@"):

                send_msg(status_text(st), [chat_id])

    except Exception as e:

        print("Telegram error:", e)



# ========= SHELLY =========


def get_shelly():

    for auth in [HTTPDigestAuth,HTTPBasicAuth,None]:

        try:

            r = requests.post(
                RPC_URL,
                json=RPC_CMD,
                auth=auth(SHELLY_USER,SHELLY_PASS) if auth else None,
                timeout=10
            )

            r.raise_for_status()

            return r.json()

        except:

            continue

    print("Shelly недоступний")

    return None


def voltage_on(data):

    if not data:
        return False

    d = data.get("result",data)

    return (
        d.get("a_voltage",0)>0 or
        d.get("b_voltage",0)>0 or
        d.get("c_voltage",0)>0
    )


# ========= STATE =========


def load_state():

    if STATE_FILE.exists():

        return json.loads(STATE_FILE.read_text())

    return {

        "state":None,
        "since":None

    }


def save_state(st):

    STATE_FILE.write_text(json.dumps(st))


def status_text(st):

    if st["state"] is None:

        return "нема даних"

    dur = time.time()-st["since"]

    if st["state"]:

        return f"🟢 Світло є вже {fmt(dur)}"

    else:

        return f"🔴 Світла нема вже {fmt(dur)}"


# ========= MAIN =========


print("Моніторинг старт")


st = load_state()

for cid in CHAT_IDS:
    send_keyboard(cid)


next_shelly = 0
next_tg = 0


while True:

    now = time.time()


    if now>=next_tg:

        check_tg(st)

        next_tg = now+TG_INTERVAL


    if now>=next_shelly:

        data = get_shelly()

        cur = voltage_on(data)

        prev = st["state"]


        if prev is None:

            st["state"]=cur
            st["since"]=now

            send_msg(
                f"Старт: {'🟢 Світло є' if cur else '🔴 Світла нема'}"
            )


        elif cur!=prev:

            dur = now-st["since"]

            if cur:

                msg=f"🟢 Світло УВІМК — світла не було {fmt(dur)}"

            else:

                msg=f"🔴 Світло ВИМК — світло було {fmt(dur)}"


            print(msg)

            send_msg(msg)


            st["state"]=cur
            st["since"]=now


        save_state(st)

        next_shelly = now+SHELLY_INTERVAL


    time.sleep(0.1)
