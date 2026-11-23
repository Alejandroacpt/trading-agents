"""
ALERTAS POR TELEGRAM
--------------------
Envía mensajes a tu chat de Telegram a través de tu bot.

Necesita dos datos, que NUNCA se escriben en el código: se guardan
como "secretos" de GitHub y llegan como variables de entorno:
  - TELEGRAM_BOT_TOKEN : el token que te da @BotFather
  - TELEGRAM_CHAT_ID   : el número de tu chat con el bot

Si faltan, el mensaje se imprime por pantalla en lugar de enviarse
(así el pipeline funciona aunque Telegram aún no esté configurado).
"""

import os

import requests

API = "https://api.telegram.org/bot{token}/{metodo}"
LIMITE_CARACTERES = 4000  # Telegram admite 4096 por mensaje; dejamos margen


def configurado() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def _trocear(texto: str, limite: int = LIMITE_CARACTERES) -> list[str]:
    """Divide un texto largo en varios mensajes, cortando por líneas."""
    trozos, actual = [], ""
    for linea in texto.splitlines(keepends=True):
        if len(actual) + len(linea) > limite and actual:
            trozos.append(actual)
            actual = ""
        actual += linea
    if actual:
        trozos.append(actual)
    return trozos or [""]


def send_message(texto: str, silencioso: bool = False) -> bool:
    """Envía un mensaje. Devuelve True si se envió correctamente.

    silencioso=True: llega sin sonido (útil para informes rutinarios;
    las alertas de compra/venta irán con sonido).
    """
    if not configurado():
        print("[Telegram no configurado] Mensaje que se habría enviado:\n" + texto)
        return False

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    ok = True
    for trozo in _trocear(texto):
        r = requests.post(
            API.format(token=token, metodo="sendMessage"),
            json={"chat_id": chat_id, "text": trozo, "disable_notification": silencioso},
            timeout=20,
        )
        if r.status_code != 200:
            # Mostramos el error SIN el token, para no filtrarlo en los logs
            print(f"Error de Telegram ({r.status_code}): {r.text[:300]}")
            ok = False
    return ok


def find_chat_id() -> list[dict]:
    """Busca los chats que han escrito a tu bot (para averiguar tu chat_id).

    Antes de usarla: abre tu bot en Telegram y mándale cualquier mensaje.
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.get(API.format(token=token, metodo="getUpdates"), timeout=20)
    r.raise_for_status()
    chats = {}
    for upd in r.json().get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat")
        if chat:
            chats[chat["id"]] = {
                "chat_id": chat["id"],
                "nombre": chat.get("first_name") or chat.get("title", ""),
            }
    return list(chats.values())
