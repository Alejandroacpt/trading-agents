"""
Comprueba que las conexiones externas funcionan:
  - Telegram: envía un mensaje de prueba (o lista tus chats para
    averiguar el chat_id si todavía no lo tienes).
  - Alpaca paper: lee el estado de tu cuenta de simulación.

Se lanza a mano desde GitHub (pestaña Actions -> "Probar conexiones").
"""

import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.alerts import telegram  # noqa: E402

ALPACA_PAPER_URL = "https://paper-api.alpaca.markets/v2/account"


def probar_telegram() -> None:
    print("--- Telegram ---")
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        print("Falta el secreto TELEGRAM_BOT_TOKEN")
        return
    if not os.getenv("TELEGRAM_CHAT_ID"):
        print("Falta TELEGRAM_CHAT_ID. Chats que han escrito a tu bot:")
        chats = telegram.find_chat_id()
        if not chats:
            print("  (ninguno: abre tu bot en Telegram, mándale un 'hola' y vuelve a lanzar esto)")
        for c in chats:
            print(f"  chat_id = {c['chat_id']}  ({c['nombre']})")
        return
    ok = telegram.send_message("🤖 Prueba de conexión: el bot de agentes de trading funciona.")
    print("Mensaje enviado" if ok else "No se pudo enviar el mensaje")


def probar_alpaca() -> None:
    print("--- Alpaca (paper) ---")
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not (key and secret):
        print("Faltan los secretos ALPACA_API_KEY / ALPACA_SECRET_KEY")
        return
    r = requests.get(
        ALPACA_PAPER_URL,
        headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
        timeout=20,
    )
    if r.status_code != 200:
        print(f"Error {r.status_code}: {r.text[:200]}")
        return
    cuenta = r.json()
    print(f"Cuenta paper OK · estado: {cuenta.get('status')} · "
          f"capital simulado: {float(cuenta.get('equity', 0)):,.2f} {cuenta.get('currency', '')}")


if __name__ == "__main__":
    probar_telegram()
    probar_alpaca()
