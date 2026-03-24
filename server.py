import socket
import threading
import time
import random
import sys
import json
import os
import queue

# configs do servidor
CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000}

if len(sys.argv) < 2:
    print("Uso: python server.py <limite de conexão>")
    sys.exit(1)
try:
    LIMITE_CONEXAO = int(sys.argv[1])
except ValueError:
    print("Limite de conexão inválido. Deve ser um número inteiro.")
    sys.exit(1)

lock_usuarios = threading.Lock()  # lock para acessar a lista de usuários

def carregar_usuarios():
    if os.path.exists("usuarios.json"):
        with open("usuarios.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_usuarios():
    with open("usuarios.json", "w", encoding="utf-8") as f:
        json.dump(usuarios, f, indent=4)

usuarios = carregar_usuarios()  # dicionário de usuários e seus saldos

# memória Compartilhada
item_leilao = {
    "item": "Quadro Monalisa",
    "descricao": "Obra-prima de Leonardo da Vinci, século XVI.",
    "valor_atual": 1000.0,
    "vencedor": "ninguém",
    "tempo": 60,
    "ativo": True,
}

lock = threading.Lock()          # lock na memória compartilhada
clientes_conectados = []
clientes_lock = threading.Lock() # lock na lista de clientes
conexoes_ativas = 0
conexoes_lock = threading.Lock() # lock para controlar o número de conexões

def broadcast(mensagem):
    with clientes_lock:
        for fila in clientes_conectados:
            try:
                fila.put(mensagem)
            except Exception:
                pass

# thread 1 (recebe e valida lances/comandos do cliente)
def thread_enviar(conn, fila_envio):
    while True:
        try:
            msg = fila_envio.get(timeout=1)  # espera por mensagens para enviar
            if msg is None:  # sinal para encerrar a thread
                break
            conn.send(msg.encode())
        except queue.Empty:
            with lock:
                if not item_leilao["ativo"]:
                    break
        except Exception:
            break

def thread_receber(conn, addr, fila_envio):
    global conexoes_ativas
    print(f"[Servidor] Cliente {addr} conectado.")
    with clientes_lock:
        clientes_conectados.append(fila_envio)
    nome = None
    try:
        # mensagem de boas-vindas com horário
        horario = time.strftime("%H:%M:%S")
        fila_envio.put(f"{horario}: CONECTADO!!")
        time.sleep(0.1)
        # informações iniciais do item
        with lock:
            info = (
                f"\n LEILÃO ONLINE \n"
                f"-----------------------------------------------------\n"
                f"Item: {item_leilao['item']}\n"
                f"Descrição: {item_leilao['descricao']}\n"
                f"Lance inicial: R${item_leilao['valor_atual']:.2f}\n"
                f"Tempo restante: {item_leilao['tempo']}s\n"
                f"-----------------------------------------------------\n"
                f"Comandos -> :Lance <item> <valor> | :Vender <item> | "
                f":item | :tempo | :saldo | :itens | :quit"
            )
        fila_envio.put(info)
        # pede o nome do usuário
        time.sleep(0.1)
        fila_envio.put("\nDigite seu nome para participar: ")
        nome = conn.recv(1024).decode().strip()
        if not nome:
            nome = f"Usuario_{addr[1]}"
        with lock_usuarios:
            if nome not in usuarios:
                usuarios[nome] = {"saldo": 5000.0, "saldo_bloqueado": 0.0, "itens": []}
                salvar_usuarios()
                fila_envio.put(f"\n[INFO] Conta criada para {nome} com saldo inicial de R$5000,00. Boa sorte no leilão!")
            else:
                u = usuarios[nome]
                fila_envio.put(f"\n[INFO] Bem-vindo de volta, {nome}! Saldo disponível: R${u['saldo']:.2f}, Itens comprados: {len(u['itens'])}")
        # loop principal (espera comandos/lances do cliente)
        while True:
            with lock:
                if not item_leilao["ativo"]:
                    break
            dados = conn.recv(1024).decode().strip()
            if not dados or dados == ":quit":
                fila_envio.put("\nSaindo do leilão...\n")
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
                fila_envio.put(resposta)
            elif dados == ":tempo":
                with lock:
                    t = item_leilao["tempo"]
                fila_envio.put(f"\nTempo restante: {t} segundos")
            elif dados == ":saldo":
                with lock_usuarios:
                    u = usuarios.get(nome, {})
                    saldo = u.get("saldo", 0.0)
                    bloqueado = u.get("saldo_bloqueado", 0.0)
                    fila_envio.put(f"\nSaldo disponível: R${saldo:.2f}\nSaldo bloqueado: R${bloqueado:.2f}\nSaldo total: R${saldo + bloqueado:.2f}")
            elif dados == ":itens":
                with lock_usuarios:
                    intens = usuarios.get(nome, {}).get("itens", [])
                if not intens:
                    fila_envio.put("\nVocê ainda não comprou nenhum item.")
                else:
                    linhas = "\n".join(
                        f"  - {it['item']}  "
                        f"(pago: R${it['valor_pago']:.2f} | "
                        f"revenda: R${it['valor_pago'] * 0.9:.2f})"
                        for it in intens
                    )
                    fila_envio.put(f"\n--- SEUS ITENS ---\n{linhas}\n------------------")
            elif dados.lower().startswith(":lance"):
                partes = dados.split()
                if len(partes) < 3:
                    fila_envio.put("\nComando inválido.")
                else:
                    item_alvo = " ".join(partes[1:-1])
                    try:
                        novo_lance = float(partes[-1])
                        with lock:
                            item_atual = item_leilao["item"]
                            valor_atual = item_leilao["valor_atual"]
                            lider_atual = item_leilao["vencedor"]
                        if item_alvo.lower() != item_atual.lower():
                            fila_envio.put(f"\nEsse não é o item atual... O item em leilão é '{item_atual}'.")
                        elif novo_lance <= valor_atual:
                            fila_envio.put(f"\nLance recusado. O lance mínimo é R${valor_atual:.2f}.")
                        else:
                            with lock_usuarios:
                                u = usuarios[nome]
                                if u["saldo"] < novo_lance:
                                    fila_envio.put(f"\nSaldo insuficiente. Seu saldo disponível é R${u['saldo']:.2f} e o lance é R${novo_lance:.2f}.")
                                else:
                                    if lider_atual in usuarios:
                                        anterior = usuarios[lider_atual]
                                        anterior["saldo"] += anterior["saldo_bloqueado"]
                                        anterior["saldo_bloqueado"] = 0.0
                                        broadcast(f"\n[INFO] O lance de {lider_atual} foi superado por {nome}! Saldo de {lider_atual} desbloqueado.")
                                    u["saldo"] -= novo_lance
                                    u["saldo_bloqueado"] += novo_lance
                                    salvar_usuarios()
                            # (mesma ordem que thread_cronometro: lock → lock_usuarios)
                            with lock:
                                item_leilao["valor_atual"] = novo_lance
                                item_leilao["vencedor"] = nome
                                item_leilao["tempo"] = 30  # reseta o cronômetro
                            fila_envio.put(f"\n[SUCESSO] Lance de R${novo_lance:.2f} aceito! Você está no topo, {nome}!")
                            broadcast(f"\n[ATUALIZAÇÃO] Novo lance de R${novo_lance:.2f} por {nome}! Lance atual: R${novo_lance:.2f}")
                    except ValueError:
                        fila_envio.put("\nValor do lance inválido. Use um número para o lance.")
            elif dados.lower().startswith(":vender"):
                item_vender = dados[8:].strip()
                with lock_usuarios:
                    u = usuarios[nome]
                    encontrado = next((it for it in u["itens"] if it["item"].lower() == item_vender.lower()), None)
                    if not encontrado:
                        fila_envio.put(f"\nVocê não possui o item '{item_vender}'.")
                    else:
                        valor_venda = round(encontrado["valor_pago"] * 0.9, 2)
                        u["saldo"] += valor_venda
                        u["itens"].remove(encontrado)
                        salvar_usuarios()
                        fila_envio.put(f"\n[SUCESSO] Item '{encontrado['item']}' vendido por R${valor_venda:.2f}. Saldo atualizado: R${u['saldo']:.2f}.")
            else:
                fila_envio.put("\nComando desconhecido. Use :item, :tempo, :saldo, :itens, :vender <item> ou envie um valor para dar um lance.")
    except Exception:
        pass
    finally:
        if nome and nome in usuarios:
            # evita deadlock causado por aquisição em ordem inversa
            with lock:
                venceu = item_leilao["vencedor"] == nome
            with lock_usuarios:
                if not venceu and usuarios[nome]["saldo_bloqueado"] > 0:
                    usuarios[nome]["saldo"] += usuarios[nome]["saldo_bloqueado"]
                    usuarios[nome]["saldo_bloqueado"] = 0.0
                    salvar_usuarios()
        fila_envio.put(None)
        with clientes_lock:
            if fila_envio in clientes_conectados:
                clientes_conectados.remove(fila_envio)
        with conexoes_lock:
            conexoes_ativas -= 1
        conn.close()
        print(f"[Servidor] Cliente {addr} desconectado.")


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
            if tempo_atual in (15, 10, 5):
                broadcast(f"\nAtenção! {tempo_atual} segundos restantes!")
            if tempo_atual <= 0:
                with lock:
                    item_leilao["ativo"] = False
                    vencedor = item_leilao["vencedor"]
                    valor = item_leilao["valor_atual"]
                    item = item_leilao["item"]
                with lock_usuarios:
                    if vencedor in usuarios:
                        u = usuarios[vencedor]
                        u["saldo_bloqueado"] = 0.0
                        u["itens"].append({"item": item, "valor_pago": valor})
                        salvar_usuarios()
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
            lider_atual = item_leilao["vencedor"]
            if lider_atual in NOMES_BOTS:
                continue
            variacao = random.uniform(0.01, 0.08)
            novo_lance = round(valor_base * (1 + variacao), 2)
            if novo_lance <= item_leilao["valor_atual"]:
                continue
            bot_nome = random.choice(NOMES_BOTS)
            item_leilao["valor_atual"] = novo_lance
            item_leilao["vencedor"] = bot_nome
            item_leilao["tempo"] = 30  # reseta o cronômetro

        if lider_atual in usuarios:
            with lock_usuarios:
                prev = usuarios[lider_atual]
                prev["saldo"] += prev["saldo_bloqueado"]
                prev["saldo_bloqueado"] = 0.0
                salvar_usuarios()
            broadcast(f"\n[INFO] Um bot superou seu lance! Seu saldo foi desbloqueado.")

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
        with conexoes_lock:
            if conexoes_ativas >= LIMITE_CONEXAO:
                conn.send("\nServidor cheio. Tente novamente mais tarde.".encode())
                conn.close()
                print(f"[Servidor] Rejeitou conexão de {addr} — limite de conexões atingido.")
                continue
            conexoes_ativas += 1
        fila_envio = queue.Queue()
        t_recv = threading.Thread(target=thread_receber, args=(conn, addr, fila_envio), daemon=True)
        t_send = threading.Thread(target=thread_enviar, args=(conn, fila_envio), daemon=True)
        t_recv.start()
        t_send.start()
    except KeyboardInterrupt:
        print("\nDesligando servidor...")
        break

server.close()
