import socket
import threading
import time
import random #vou usar nao tira nao

# configurações do servidor
CONFIG = {
    "HOST": "127.0.0.1",
    "PORTA": 5000
}

#o item do leilao atual que vai anunciar
item_leilao = {
    "item": "Quadro Monalisa",
    "valor_atual": 900000,
    "vencedor": "ninguém",
    "tempo": 60,
    "ativo":True
}

lock = threading.Lock() #penas uma memória mexe na memória compartilhada

# thread 1: recebe e processa a mensagem do cliente
def thread_receber(conn, addr)
    print(f"[Servidor] Cliente {addr} conectado.")
    while item_leilao ["ativo"]:
        try:
            dados = conn.recv(1024).decode.strip()
            if not dados:
                break
            # comando quitt
            if dados == ":quit":
                conn.send("Saindo do leilão...".encode())
                break
            # comando item
            elif dados == ":item":
                with lock:
                    resposta = (
                        f"Item: {item_leilao["nome"]}"
                        f"/n Lance: {item_leilao['valor_atual']:.2f}"
                        f"/n Maior lance: {item_leilao["vencedor"]}"
                    )
                conn.send(resposta.encode())
            # tempo
            elif dados == ":tempo":
                with lock:
                    t = item_leilao["tempo"]
                resposta = f"Tempo restante:{t} segundos!"
                conn.send(resposta.encode())
            # lance
            else:
                try:
                    novo_lance = float (dados)
                    with lock:
                        if novo_lance > item_leilao["valor_atual"]:
                            item_leilao["valor_atual"] = novo_lance
                            item_leilao["vencedor"] = f"Vc mesmo({addr[0]})!"
                            item_leilao["tempo"] = 90
                            resposta = (
                                f"Lance de R${novo_lance:.2f} aceito! Você está ganhando!"
                            )
                        else:
                            with lock:
                                atual = item_leilao["valor_atual"]
                            resposta = (
                                f"Lance negado... O lance atual é de R${atual:.2f}, tente novamente."
                            )
                    conn.send(resposta.encode())
                except ValueError:
                    conn.send(f"Comando inválido...".encode())
        except(ConnectionResetError, BrokenPipeError):
            print(f"[Servidor] Conexão com o {addr} acabou.")
            break
    conn.close()

#thread 2: cronometro, bots e atualizacoes

#iniciando o servidor

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((CONFIG["HOST"], CONFIG["PORTA"]))
server.listen() 

print(f"Servidor pronto. \nItem: {item_leilao['nome']} \nLance inicial: R${item_leilao['valor_atual']:.2f} \nConectando...")

conn, addr = server.accept()
horario = time.strftime("%H:%M")

mensagem_inicial = (f"{horario}: CONECTADO!!\n\n"
    f"Item em leilão: {item_leilao['nome']}\n"
    f"Lance inicial: R${item_leilao['valor_atual']:.2f}\n"
    f"⏱Tempo: {item_leilao['tempo']} segundos\n\n"
    f"Comandos: :item | :tempo | :quit | ou envie um valor para dar um lance\n"
)
conn.send(mensagem_inicial.encode()) #envia para o cliente(codificar para bytes(pq o cabo de rede só entende bytes, bits etc))

#soltando as threads
t1 = threading.Thread(target=thread_receber, args=(conn,addr), daemon = True) #fazer o mesmo com a thread 2

t1.start()

t1.join()

print("[Servidor] Leilão encerrado. Fechando...")
server.close()