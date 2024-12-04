import websocket
import json
from threading import Thread, Event
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
        self.ping_interval = 8 * 60  # 8 minutes
        self.ping_thread = None
        self.stop_event = Event()


    def connect(self, request_payload, callback):
        def run():
            def on_open(ws):
                print("Connection opened.")
                self.connected = True
                if request_payload:
                    self.send_request(request_payload)
                self.start_ping()

            def on_close(ws, *args):
                print("Connection closed.")
                self.connected = False
                self.stop_ping()

            def on_message(ws, msg):
                try:
                    message = json.loads(msg, object_hook=datetime_decoder)
                    action = message.get("action")

                    if action == "pong":
                        self.handle_pong()
                    elif action == "sendArticle":
                        self.receive_article(message, callback)
                    else:
                        print(f"Unknown action received: {action}")
                except Exception as e:
                    print(f"Error processing message: {e}")
                    
            def on_error(ws, err):
                print(f"Error: {err}")
                self.connected = False

            self.ws = websocket.WebSocketApp(
                self.config["wss_url"],
                header=[f"x-api-key: {self.config['api_key']}"],
                on_message=on_message,
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
            
    def start_ping(self):
        def ping():
            while not self.stop_event.is_set():
                if self.ws and self.connected:
                    print("PING")
                    self.ws.send(json.dumps({"action": "ping"}))
                sleep(self.ping_interval)
        self.ping_thread = Thread(target=ping, daemon=True)
        self.ping_thread.start()

    def stop_ping(self):
        self.stop_event.set()
        if self.ping_thread:
            self.ping_thread.join()

    def receive_article(self, response, callback):
        try:
            data = response.get("data", {})
            callback(data)
        except Exception as e:
            print(f"Error processing article: {e}")

    def handle_pong(self):
        print("PONG")
