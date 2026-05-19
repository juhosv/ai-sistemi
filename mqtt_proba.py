import json
import random
import time
from paho.mqtt import client as mqtt_client

# Konfiguráció
BROKER = 'localhost'
PORT = 51883
TOPIC = "haz/nappali/homerseklet"
CLIENT_ID = f'python-mqtt-{random.randint(0, 1000)}'


def connect_mqtt():
    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("Sikeresen csatlakozva az EMQX brókerhez!")
        else:
            print(f"Hiba a csatlakozás során, kód: {rc}")

    client = mqtt_client.Client(client_id=CLIENT_ID, callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    return client


def publish(client):
    while True:
        time.sleep(2)
        # Teszt adat generálása JSON formátumban
        payload = {
            "homerseklet": round(random.uniform(20.0, 25.0), 1),
            "idobelyeg": int(time.time())
        }
        msg = json.dumps(payload)

        result = client.publish(TOPIC, msg)
        status = result[0]

        if status == 0:
            print(f"Küldve: {msg} -> Téma: {TOPIC}")
        else:
            print(f"Nem sikerült üzenetet küldeni a {TOPIC} témába")


def run():
    client = connect_mqtt()
    client.loop_start()
    try:
        publish(client)
    except KeyboardInterrupt:
        print("\nLeállítás...")
        client.loop_stop()
        client.disconnect()


if __name__ == '__main__':
    run()
