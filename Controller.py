import random
import hashlib
import json
import os
from signature import verify_signature, sign_message
import time
import binascii
from cryptography.hazmat.primitives.serialization import load_pem_public_key

class Controller():
    def __init__(self, broker_adress, mqtt_client, pb_keys, private_key):
        self.mqtt_miner = mqtt_client
        self.broker_adress = broker_adress
        self.transactions = {}
        self.pb_keys = pb_keys
        self.private_key = private_key

    def on_connect(self, client, userdata, flags, rc):
        self.mqtt_miner.subscribe("sd/solution")  

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)

        key_bytes = binascii.unhexlify(self.pb_keys[data['ClientID']])
        clientKey = load_pem_public_key(
            key_bytes
        )
        sig = data['signature']

        if topic == "sd/solution":
            msg = data['Solution']
            if verify_signature(clientKey, msg.encode(), binascii.unhexlify(sig)):
                transactionId = data["TransactionID"]
                solution = data["Solution"]

                if self.transactions[transactionId]['solution'] == None and self.__validSolution(transactionId, solution):
                    print("\nSolução Encontrada!")

                    signature = sign_message(self.private_key, bytes(1))
                    result_payload = json.dumps({
                        "ClientID": data["ClientID"],
                        "TransactionID": transactionId, 
                        "Solution": data["Solution"],
                        "Result": 1,
                        "signature": signature.hex()})
                    self.mqtt_miner.publish(f"sd/{data['ClientID']}/result", result_payload)

                    self.transactions[transactionId]['winner'] = data["ClientID"]
                    self.transactions[transactionId]['solution'] = data["Solution"]
                    self.__printTransations()

                    print("Enviando resposta aos Mineradores...")
                else:
                    signature = sign_message(self.private_key, bytes(0))
                    result_payload = json.dumps({
                        "ClientID": self.transactions[transactionId]['winner'],
                        "TransactionID": transactionId, 
                        "Solution": self.transactions[transactionId]['solution'],
                        "Result": 0,
                        "signature": signature.hex()})
                    self.mqtt_miner.publish(f"sd/{data['ClientID']}/result", result_payload)
    
    def __validSolution(self, transactionId, solution):
        if(transactionId > max(self.transactions.keys())):
            return False

        hash = hashlib.sha1(solution.encode('utf-8')).digest()
        binary_hash = bin(int.from_bytes(hash, byteorder='big'))[2:]

        if binary_hash[1:self.transactions[transactionId]['challenge']+1] == '0' * self.transactions[transactionId]['challenge']:
            return True

        return False

    def __newChallenge(self):
        while input() != 'e':
            os.system("clear")
            ch = random.randint(14, 20)
            signature = sign_message(self.private_key, bytes(ch))
            if self.transactions.keys():
                newTransactionId = max(self.transactions.keys()) + 1
                self.transactions[newTransactionId] = {
                    'challenge': ch, 
                    'solution': None, 
                    'winner': -1,
                    'signature': signature.hex()
                    }
            else:
                self.transactions[0] = {
                    'challenge': ch, 
                    'solution': None, 
                    'winner': -1,
                    'signature': signature.hex(),
                    }
                newTransactionId = 0

            self.mqtt_miner.publish("sd/challenge", json.dumps(self.transactions[newTransactionId]))
            print("Gerando Novo Desafio!")
            self.__printTransations()

            while self.transactions[newTransactionId]['solution'] == None:
                continue
            
        signature = sign_message(self.private_key, bytes(1))
        f_msg = {
            'code': 1,
            'signature': signature.hex()
        }
        self.mqtt_miner.publish("sd/finish", json.dumps(f_msg))
        time.sleep(1)
            
    def __printTransations(self):
        print("----------------------------------------------------")
        print("Transactions Table") 
        for transaction in self.transactions:
            print(f"Challenge: {self.transactions[transaction]['challenge']} / Soluction; {self.transactions[transaction]['solution']} / Winner: {self.transactions[transaction]['winner']}")
        print("----------------------------------------------------\n")

    def runController(self):
        self.mqtt_miner.on_message = self.on_message
        self.mqtt_miner.on_connect = self.on_connect

        self.mqtt_miner.connect(self.broker_adress)
        self.mqtt_miner.loop_start()

        try:
            print("\n----------------------------------------------------")
            print("Controller iniciado. Para sair digite 'e', para gerar novo desafio aperte enter...")
            self.__newChallenge()
                
        except KeyboardInterrupt:
            self.mqtt_miner.loop_stop()
            self.mqtt_miner.disconnect()
            print("Servidor MQTT desconectado")
            self.mqtt_miner.publish("sd/finish", json.dumps({}))
