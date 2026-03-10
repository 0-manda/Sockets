import socket
import threading
import time
import random

#configs
CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000}

item_leilao = {
    "item": "Quadro Monalisa",
    "descricao": "Obra-prima de Leonardo da Vinci, século XVI.",
    "valor_atual": 900000.0,
    "vencedor": "ninguém",
    "tempo": 60,
    "ativo": True,
}

lock = threading.Lock()  # Protege a memória compartilhada

#thread 1 (recebendo comandos do cliente)
def thread_receber(conn, addr):
    print(f"[Servidor] Cliente {addr} conectado.")
    while True:
        with lock:
            ainda_ativo = item_leilao["ativo"]
        if not ainda_ativo:
            break
        try:
            dados = conn.recv(1024).decode().strip()
            if not dados:
                break
            if dados == ":quit":
                conn.send("Saindo do leilão...".encode())
                with lock:
                    item_leilao["ativo"] = False
                break
            elif dados == ":item":
                with lock:
                    resposta = (
                        f"\n---ITEM---\n"
                        f"Item       : {item_leilao['item']}\n"
                        f"Descrição  : {item_leilao['descricao']}\n"
                        f"Lance atual: R${item_leilao['valor_atual']:.2f}\n"
                        f"Líder      : {item_leilao['vencedor']}\n"
                    )
                conn.send(resposta.encode())
            elif dados == ":tempo":
                with lock:
                    resposta = f"\nTempo restante: {item_leilao['tempo']} segundos!"
                conn.send(resposta.encode())
            else:
                try:
                    novo_lance = float(dados)
                    with lock:
                        if novo_lance > item_leilao["valor_atual"]:
                            item_leilao["valor_atual"] = novo_lance
                            item_leilao["vencedor"] = f"Você (porta {addr[1]})"
                            item_leilao["tempo"] = 30 #restart do tempo
                            resposta = f"\n[SUCESSO] Lance de R${novo_lance:.2f} ACEITO! Você está no topo!"
                        else:
                            resposta = (
                                f"\n[RECUSADO] Lance baixo! "
                                f"O valor é R${item_leilao['valor_atual']:.2f}"
                            )
                    conn.send(resposta.encode())
                except ValueError:
                    conn.send(
                        "\nComando inválido. Use: :item | :tempo | :quit | <valor numérico>".encode()
                    )
        except Exception:
            break
    conn.close()
    print(f"[Servidor] Conexão com {addr} encerrada.")


#thread 2 (cronometro)
def thread_cronometro(conn):
    try:
        while True:
            time.sleep(1)
            with lock:
                if not item_leilao["ativo"]:
                    break
                item_leilao["tempo"] -= 1
                tempo_atual = item_leilao["tempo"]
            if tempo_atual%5 == 0 and tempo_atual >0:
                try:
                    conn.send(f"\nAtenção! O leilão encerra em {tempo_atual}s!".encode())
                except Exception:
                    break
            if tempo_atual <= 0:
                with lock:
                    item_leilao["ativo"] = False
                    vencedor = item_leilao["vencedor"]
                    valor_final = item_leilao["valor_atual"]
                try:
                    conn.send(
                        f"\nLEILÃO ENCERRADO!\n"
                        f"Item vendido: {item_leilao['item']}\n"
                        f"Valor final : R${valor_final:.2f}\n"
                        f"Vencedor    : {vencedor}\n"
                        f"Pressione ENTER para fechar.".encode()
                    )
                except Exception:
                    pass
                break
    finally:
        print("[Servidor] Cronômetro encerrado.")

# inicializando o server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((CONFIG["HOST"], CONFIG["PORTA"]))
server.listen()
print(
    f"[Servidor] Aguardando conexão...\n"
    f"Item   : {item_leilao['item']}\n"
    f"Lance inicial: R${item_leilao['valor_atual']:.2f}"
)
conn, addr = server.accept()
horario = time.strftime("%H:%M")
mensagem_inicial = (
    f"\n{horario}: CONECTADO!!\n"
    f"{'='*40}\n"
    f"Item      : {item_leilao['item']}\n"
    f"Descrição : {item_leilao['descricao']}\n"
    f"Lance base: R${item_leilao['valor_atual']:.2f}\n"
    f"{'='*40}\n"
    f"Comandos  : :item | :tempo | :quit | <valor do lance>\n"
)
conn.send(mensagem_inicial.encode())

# inicia as 2 threads do servidor
t1 = threading.Thread(target=thread_receber, args=(conn, addr), daemon=True)
t2 = threading.Thread(target=thread_cronometro, args=(conn,), daemon=True)

t1.start()
t2.start()

try:
    while True:
        with lock:
            if not item_leilao["ativo"]:
                break
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[Servidor] Desligando via Ctrl+C...")
    with lock:
        item_leilao["ativo"] = False

server.close()
print("[Servidor] Socket fechado. Encerrando.")