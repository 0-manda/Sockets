import socket
import threading
import time

# Configurações do Servidor (host e porta do servidor)
CONFIG = {
    "HOST": "127.0.0.1", # Localhost para testes internos
    "PORTA": 5000         # Guichê de atendimento do leilão
}

#o item do leilao atual que vai anunciar
item_leilao = {
    "item": "Quadro Monalisa",
    "valor_atual": 900000,
    "tempo": 60
}

lock = threading.Lock() # apenas uma memória mexe na memória compartilhada


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


server.bind((CONFIG["HOST"], CONFIG["PORTA"]))
server.listen() 

print("Servidor pronto. \nItem: {0}\nLance inicial: R${1}",(item_leilao['item'],item_leilao["valor_atual"]))

conn, addr = server.accept()
horario = time.strftime("%H:%M")


mensagem_inicial = f"Leilão aberto, são {horario} \n\n\nItem:{item_leilao['item']} \nValor: R${item_leilao['valor_atual']}"
conn.send(mensagem_inicial.encode()) #envia para o cliente(codificar para bytes(pq o cabo de rede só entende bytes, bits etc))
