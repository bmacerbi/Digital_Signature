import random
import hashlib
import json
import string
from aux import sign_message, verify_signature
import binascii
from cryptography.hazmat.primitives.serialization import load_pem_public_key
import os

class Miner():
    def __init__(self, broker_adress, id, mqtt_client, private_key, controller_key):
        self.mqq_miner = mqtt_client
        self.id = id
        self.broker_adress = broker_adress
        self.transactions = {}
        self.private_key = private_key
        self.controller_key = controller_key

        self.life = True
    
    def on_connect(self, client, userdata, flags, rc):
        self.mqq_miner.subscribe("sd/challenge")
        self.mqq_miner.subscribe("sd/finish")
        self.mqq_miner.subscribe(f"sd/{self.id}/result")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)

        key_bytes = binascii.unhexlify(self.controller_key)
        controller_key = load_pem_public_key(
            key_bytes
        )

        if topic == "sd/challenge":
            msg = data['challenge']
            sig = data['signature']
            if verify_signature(controller_key, bytes(msg), binascii.unhexlify(sig)):
                os.system("clear")
                print(f"Miner {self.id}: Desafio de dificuldade {data['challenge']} recebido, procurando uma resposta...")

                solution = self.__lookForAnswer(data['challenge'])
                if self.transactions.keys():
                    transactionId = max(self.transactions.keys()) + 1
                    self.transactions[transactionId] = {
                        'challenge': data['challenge'], 
                        'solution': None, 
                        'winner': -1
                        }
                else:
                    self.transactions[0] = {
                        'challenge': data['challenge'],
                        'solution': None,
                        'winner': -1
                        }
                    
                    transactionId = 0

                signature = sign_message(self.private_key, solution.encode())
                solution_msg = {
                    "ClientID": self.id,
                    "TransactionID": transactionId,
                    "Solution": solution,
                    "signature": signature.hex()
                }

                print("Enviando solucao ao servidor...")
                self.mqq_miner.publish("sd/solution", json.dumps(solution_msg))

        elif topic == f"sd/{self.id}/result":
            msg = data['Result']
            sig = data['signature']
            if verify_signature(controller_key, bytes(msg), binascii.unhexlify(sig)):
                solution = data['Solution']
                if data['Result'] == 0:
                    if solution == None:
                        print(f"Miner {self.id}: Solução ({solution}) Negada pelo Servidor!")
                    else:
                        print(f"Miner {self.id}: O servidor já possui solução para o id {data['TransactionID']}! Solução: {solution} / Vencedor: {data['ClientID']}. Atualizando tabela local.")
                        self.transactions[data["TransactionID"]]['solution'] = solution
                        self.transactions[data["TransactionID"]]['winner'] = data['ClientID']
                else:
                    print(f"Miner {self.id}: Solução ({solution}) Aceita pelo Servidor! Atualizando tabela local.")
                    self.transactions[data["TransactionID"]]['solution'] = solution
                    self.transactions[data["TransactionID"]]['winner'] = self.id

                self.__printTransations()

        elif topic == "sd/finish":
            sig = data['signature']
            msg = data['code']
            if verify_signature(controller_key, bytes(msg), binascii.unhexlify(sig)):
                if msg == 1:
                    print("Finalizando Minerador.")
                    self.life = False

    def __lookForAnswer(self, challenger):
        count = 0
        while True:
            count += 1

            solution = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            hash = hashlib.sha1(solution.encode('utf-8')).digest()
            binary_hash = bin(int.from_bytes(hash, byteorder='big'))[2:]

            if binary_hash[1:challenger+1] == '0' * challenger:
                return solution
            
    def __printTransations(self):
        print("----------------------------------------------------")
        print("Transactions Table")
        for transaction in self.transactions:
            print(f"Challenge: {self.transactions[transaction]['challenge']} / Soluction; {self.transactions[transaction]['solution']} / Winner: {self.transactions[transaction]['winner']}")
        print("----------------------------------------------------\n")

    def runMiner(self):
        print()
        print()
        self.mqq_miner.on_message = self.on_message
        self.mqq_miner.on_connect = self.on_connect

        self.mqq_miner.connect(self.broker_adress)
        self.mqq_miner.loop_start()

        while self.life:
            continue