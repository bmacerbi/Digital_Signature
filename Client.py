import random
import json
import sys
import time
import paho.mqtt.client as mqtt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
import binascii
from cryptography.hazmat.primitives.serialization import load_pem_public_key

class Client:
    def __init__(self, broker_adress, min_clients):
        self.cid = random.randint(0, 65335)
        self.min_clients = min_clients

        self.broker_adress = broker_adress
        self.mqtt_client = mqtt.Client(str(self.cid))

        self.__generate_key_pair()
        self.__init_broker()

        self.pb_keys = {}
        self.clients_list = []
        self.votes= {}

    def __init_broker(self):
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_connect = self.on_connect

        self.mqtt_client.connect(self.broker_adress)
        self.mqtt_client.loop_start()

    def __generate_key_pair(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=1024
        )
        public_key = private_key.public_key()

        self.private_key = private_key
        self.public_key = public_key

    def on_connect(self, client, userdata, flags, rc):
        print(f"Client {self.cid} conectado ao broker MQTT")
        self.mqtt_client.subscribe("sd/init")
        self.mqtt_client.subscribe("sd/pubkey")
        self.mqtt_client.subscribe("sd/ElectionMsg")
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)

        if topic == "sd/init":
            cid = data['cid']
            if cid != self.cid and self.__new_cid(cid):
                self.clients_list.append(cid)

        elif topic == "sd/pubkey":
            cid = data['cid']
            if cid != self.cid and self.__new_key(cid):
                self.pb_keys[cid] = data['key']

        elif topic == "sd/ElectionMsg":
            cid = data['cid']
            if cid != self.cid and self.__new_vote(cid):
                vote = data['vote']
                signature = data['signature']
                # print(data)

                key_bytes = binascii.unhexlify(self.pb_keys[cid])
                public_key = load_pem_public_key(
                    key_bytes
                )

                if self.verify_signature(public_key, bytes(vote), signature.encode()):
                    self.votes[cid] = vote
                    print("foi")
                else:
                    print("nao foi")

    def __new_cid(self, cid):
        for know_cid in self.clients_list:
            if cid == know_cid:
                return False
        return True
    
    def __new_key(self, cid):
        if cid in self.pb_keys:
            return False
        return True
    
    def __new_vote(self, cid):
        if cid in self.votes:
            return False
        return True
    
    def publish_cid(self):
        msg = {
            'cid': self.cid,
        }
        while True:
            print("Enviando CID...")
            self.mqtt_client.publish("sd/init", json.dumps(msg))
            time.sleep(1)
            if len(self.clients_list) == self.min_clients - 1:
                break

    def publish_key(self):
        public_key_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        msg = {
            'cid': self.cid,
            'key': public_key_bytes.hex() 
        }

        while True:
            print("Publicando chave publica...")
            self.mqtt_client.publish("sd/pubkey", json.dumps(msg))
            time.sleep(1)
            if len(self.pb_keys) == self.min_clients - 1:
                break

    def vote(self):
        vote = random.randint(0, 65335)
        self.votes[self.cid] = vote
        signature = self.sign_message(self.private_key, bytes(vote))
        msg = {
            'cid': self.cid,
            'vote': vote,
            'signature': signature.hex()
        }

        while True:
            self.mqtt_client.publish("sd/ElectionMsg", json.dumps(msg))
            
            time.sleep(5)
            if len(self.votes) == self.min_clients:
                break

        print()
        
    def sign_message(self, private_key, message):
        signature = private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return signature

    def verify_signature(self, public_key, message, signature):
        try:
            public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False


if __name__ == "__main__":
    broker_adress = "127.0.0.1"
    min_clients = int(sys.argv[1])
    
    client = Client(broker_adress, min_clients)
    time.sleep(1)
    client.publish_cid()
    client.publish_key()
    client.vote()

    print(client.votes)

