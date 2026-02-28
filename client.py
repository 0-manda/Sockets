import socket
CONFIG = {
    "HOST": "localhost", # Localhost para testes internos
    "PORTA": 5000         # Guichê de atendimento do leilão
}

cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

cliente.connect((CONFIG["HOST"], CONFIG["PORTA"]))