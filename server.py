import socket

# Configurações do Servidor (host e porta do servidor)
CONFIG = {
    "HOST": "127.0.0.1", # Localhost para testes internos
    "PORTA": 5000         # Guichê de atendimento do leilão
}


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


server.bind((CONFIG["HOST"], CONFIG["PORTA"]))
server.listen() 
print("Servidor pronto e ouvindo na porta 5000...")
conn, addr = server.accept()