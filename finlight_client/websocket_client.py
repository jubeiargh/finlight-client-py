import websocket
import json
from threading import Thread
from time import sleep
import json
from datetime import datetime


def datetime_decoder(dct):
    for key, value in dct.items():
        if isinstance(value, str):
            try:
                # Attempt to parse datetime strings
                dct[key] = datetime.fromisoformat(value)
            except ValueError:
                pass  # Leave the value unchanged if not a valid datetime string
    return dct


class WebSocketClient:
    def __init__(self, config):
        self.config = config
        self.ws = None
        self.connected = False

    def connect(self, request_payload, on_message):
        def run():
            def on_open(ws):
                print("Connection opened.")
                self.connected = True
                if request_payload:
                    self.send_request(request_payload)

            def on_close(ws, *args):
                print("Connection closed.")
                self.connected = False

            def on_error(ws, err):
                print(f"Error: {err}")
                self.connected = False

            self.ws = websocket.WebSocketApp(
                self.config["wss_url"],
                header=[f"x-api-key: {self.config['api_key']}"],
                on_message=lambda ws, msg: on_message(
                    json.loads(msg, object_hook=datetime_decoder)
                ),
                on_open=on_open,
                on_error=on_error,
                on_close=on_close,
            )
            self.ws.run_forever()

        Thread(target=run, daemon=True).start()

    def send_request(self, payload):
        if self.ws and self.connected:
            self.ws.send(json.dumps(payload))
        else:
            print("Cannot send message: WebSocket not connected.")

    def disconnect(self):
        if self.ws and self.connected:
            self.ws.close()
        else:
            print("WebSocket already disconnected.")
