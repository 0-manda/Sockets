import socket
CONFIG = {
    "HOST": "127.0.0.1", # Localhost para testes internos
    "PORTA": 5000         # Guichê de atendimento do leilão
}

cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

cliente.connect((CONFIG["HOST"], CONFIG["PORTA"]))

dados_iniciais = cliente.recv(1024).decode() #meio que faz ele receber os dados e só pode receber até 1024 bytes de uma vez
print(dados_iniciais)