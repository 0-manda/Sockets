import socket
import threading
import time
import random

# Configurações do servidor
CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000}

# Memória Compartilhada
item_leilao = {
    "item": "Quadro Monalisa",
    "descricao": "Obra-prima de Leonardo da Vinci, século XVI.",
    "valor_atual": 900000.0,
    "vencedor": "ninguém",
    "tempo": 60,
    "ativo": True,
}

lock = threading.Lock()          # lock na memória compartilhada
clientes_conectados = []
clientes_lock = threading.Lock() # lock na lista de clientes


def broadcast(mensagem):
    "envia mensagem para todos os clientes conectados"
    with clientes_lock:
        for conn in clientes_conectados:
            try:
                conn.send(mensagem.encode())
            except Exception:
                pass


# thread 1 (recebe e valida lances/comandos do cliente)
def thread_receber(conn, addr):
    print(f"[Servidor] Cliente {addr} conectado.")
    with clientes_lock:
        clientes_conectados.append(conn)

    try:
        # mensagem de boas-vindas com horário
        horario = time.strftime("%H:%M:%S")
        conn.send(f"{horario}: CONECTADO!!".encode())
        time.sleep(0.1)

        # informações iniciais do item
        with lock:
            info = (
                f"\n=== LEILÃO ONLINE ===\n"
                f"Item: {item_leilao['item']}\n"
                f"Descrição: {item_leilao['descricao']}\n"
                f"Lance inicial: R${item_leilao['valor_atual']:.2f}\n"
                f"Tempo restante: {item_leilao['tempo']}s\n"
                f"====================\n"
                f"Use :item, :tempo, :quit ou envie um valor para dar um lance."
            )
        conn.send(info.encode())

        # pede o nome do usuário
        time.sleep(0.1)
        conn.send("\nDigite seu nome para participar: ".encode())
        nome = conn.recv(1024).decode().strip()
        if not nome:
            nome = f"Usuario_{addr[1]}"
        conn.send(f"\nBem-vindo(a), {nome}! Boa sorte no leilão!\n".encode())

        # loop principal (espera comandos/lances do cliente)
        while True:
            with lock:
                if not item_leilao["ativo"]:
                    break

            dados = conn.recv(1024).decode().strip()
            if not dados or dados == ":quit":
                conn.send("\nSaindo do leilão...\n".encode())
                break

            if dados == ":item":
                with lock:
                    resposta = (
                        f"\n--- INFO DO ITEM ---\n"
                        f"Item: {item_leilao['item']}\n"
                        f"Descrição: {item_leilao['descricao']}\n"
                        f"Lance atual: R${item_leilao['valor_atual']:.2f}\n"
                        f"Maior lance de: {item_leilao['vencedor']}\n"
                        f"--------------------"
                    )
                conn.send(resposta.encode())

            elif dados == ":tempo":
                with lock:
                    t = item_leilao["tempo"]
                conn.send(f"\nTempo restante: {t} segundos".encode())

            else:
                try:
                    novo_lance = float(dados)
                    with lock:
                        if novo_lance > item_leilao["valor_atual"]:
                            item_leilao["valor_atual"] = novo_lance
                            item_leilao["vencedor"] = nome
                            item_leilao["tempo"] = 30  # reseta o cronômetro
                            resposta = (
                                f"\n[SUCESSO] Lance de R${novo_lance:.2f} aceito!\n"
                                f"Você está na liderança, {nome}!"
                            )
                        else:
                            resposta = (
                                f"\n[RECUSADO] Lance abaixo do atual.\n"
                                f"Lance mínimo: R${item_leilao['valor_atual']:.2f}"
                            )
                    conn.send(resposta.encode())
                except ValueError:
                    conn.send(
                        "\nComando inválido. Use :item, :tempo, :quit ou envie um número.".encode()
                    )

    except Exception:
        pass
    finally:
        with clientes_lock:
            if conn in clientes_conectados:
                clientes_conectados.remove(conn)
        conn.close()
        print(f"[Servidor] Conexão com {addr} encerrada.")


# thread 2 (cronômetro regressivo e encerramento do leilão)
def thread_cronometro():
    try:
        while True:
            time.sleep(1)
            with lock:
                if not item_leilao["ativo"]:
                    break
                item_leilao["tempo"] -= 1
                tempo_atual = item_leilao["tempo"]

            # avisos nos marcos de tempo
            if tempo_atual in (30, 15, 10, 5):
                broadcast(f"\n⏱  Atenção! {tempo_atual} segundos restantes!")

            if tempo_atual <= 0:
                with lock:
                    item_leilao["ativo"] = False
                    vencedor = item_leilao["vencedor"]
                    valor = item_leilao["valor_atual"]
                    item = item_leilao["item"]

                msg = (
                    f"\n{'='*35}\n"
                    f"LEILÃO ENCERRADO!\n"
                    f"Item: {item}\n"
                    f"Valor final: R${valor:.2f}\n"
                    f"Vencedor: {vencedor}\n"
                    f"{'='*35}"
                )
                broadcast(msg)
                print(f"[Servidor] Leilão encerrado. Vencedor: {vencedor} — R${valor:.2f}")
                break
    finally:
        print("[Servidor] Cronômetro encerrado.")


# simulação de outros usuários (bots)
NOMES_BOTS = ["Carlos", "Beatriz", "Rafael", "Fernanda", "Thiago"]

def thread_bots():
    "gera lances aleatórios de bots para simular múltiplos usuários"
    time.sleep(5)  # espera o leilão estar em andamento
    while True:
        with lock:
            if not item_leilao["ativo"]:
                break
            valor_base = item_leilao["valor_atual"]

        # intervalo aleatório entre lances dos bots
        time.sleep(random.uniform(8, 20))

        with lock:
            if not item_leilao["ativo"]:
                break

            # lance do bot: entre 1% e 8% acima do valor atual
            variacao = random.uniform(0.01, 0.08)
            novo_lance = round(valor_base * (1 + variacao), 2)
            bot_nome = random.choice(NOMES_BOTS)

            if novo_lance > item_leilao["valor_atual"]:
                item_leilao["valor_atual"] = novo_lance
                item_leilao["vencedor"] = bot_nome
                item_leilao["tempo"] = 30  # reseta o cronômetro

        update = (
            f"\n[{bot_nome}] deu um lance de R${novo_lance:.2f}!\n"
            f"   Novo líder: {bot_nome} — Lance atual: R${novo_lance:.2f}"
        )
        broadcast(update)
        print(f"[Bot] {bot_nome} — R${novo_lance:.2f}")


# inicializando o servidor
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP/IPv4
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((CONFIG["HOST"], CONFIG["PORTA"]))
server.listen()

print(f"Servidor pronto.")
print(f"Item: {item_leilao['item']}")
print(f"Lance inicial: R${item_leilao['valor_atual']:.2f}")
print(f"Aguardando conexões em {CONFIG['HOST']}:{CONFIG['PORTA']}...\n")

# dispara o cronômetro e os bots como threads do servidor
threading.Thread(target=thread_cronometro, daemon=True).start()
threading.Thread(target=thread_bots, daemon=True).start()

while True:
    try:
        conn, addr = server.accept()
        t = threading.Thread(target=thread_receber, args=(conn, addr), daemon=True)
        t.start()
    except KeyboardInterrupt:
        print("\nDesligando servidor...")
        break

server.close()
