import socket
import threading
import time
import random
import sys
import json
import os
import queue
import signal

# configs do servidor
CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000}

if len(sys.argv) < 4:
    print("Uso: python server.py <limite_conexoes> <nome_do_item> <valor_inicial>")
    sys.exit(1)
try:
    LIMITE_CONEXAO = int(sys.argv[1])
    NOME_ITEM = " ".join(sys.argv[2:-1])
    VALOR_INICIAL = float(sys.argv[-1])

    item_leilao = {
        "item": NOME_ITEM,
        "descricao": f"Item leiloado nesta sessão: {NOME_ITEM}",
        "valor_atual": VALOR_INICIAL,
        "vencedor": "ninguém",
        "tempo": 60,
        "ativo": True,
    }

except (ValueError, IndexError):
    print("Argumentos inválidos. Deve ser: <limite_conexoes> <nome_do_item> <valor_inicial>")
    sys.exit(1)

lock_usuarios = threading.Lock()# lock para acessar a lista de usuários

def carregar_usuarios():
    if os.path.exists("usuarios.json"):
        with open("usuarios.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_usuarios():
    # deve ser chamada sempre dentro de lock_usuarios
    with open("usuarios.json", "w", encoding="utf-8") as f:
        json.dump(usuarios, f, indent=4)

usuarios = carregar_usuarios()# dicionário de usuários e seus saldos

# Sanitiza entradas corrompidas: garante que nenhum usuário tenha saldo total acima de 5000
def sanitizar_usuarios():
    for nome_u, u in usuarios.items():
        # Garante que as chaves existem
        u.setdefault("saldo", 5000.0)
        u.setdefault("saldo_bloqueado", 0.0)
        u.setdefault("itens", [])
        # Reseta saldo_bloqueado solto (de sessão encerrada abruptamente)
        total = u["saldo"] + u["saldo_bloqueado"]
        if u["saldo_bloqueado"] > 0 and total <= 5000.0:
            # Devolve bloqueado que ficou preso ao fechar o servidor
            u["saldo"] += u["saldo_bloqueado"]
            u["saldo_bloqueado"] = 0.0
    salvar_usuarios()

sanitizar_usuarios()

# garante que todos os bots já existem em usuarios com saldo inicial
NOMES_BOTS = ["Carlos", "Beatriz", "Rafael", "Fernanda", "Thiago"]
with lock_usuarios:
    for bot in NOMES_BOTS:
        if bot not in usuarios:
            usuarios[bot] = {"saldo": 5000.0, "saldo_bloqueado": 0.0, "itens": []}
    salvar_usuarios()

lock = threading.Lock()# lock na memória compartilhada
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

# thread de envio (consome a fila e envia ao cliente)
def thread_enviar(conn, fila_envio):
    while True:
        try:
            msg = fila_envio.get(timeout=1)
            if msg is None: # sinal para encerrar
                break
            conn.send(msg.encode())
        except queue.Empty:
            with lock:
                if not item_leilao["ativo"]:
                    break
        except Exception:
            break

# thread de recebimento (processa comandos/lances do cliente)
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
        time.sleep(0.1)
        fila_envio.put("\nDigite seu nome para participar: ")
        # timeout no recv para não travar indefinidamente
        conn.settimeout(120)
        nome_raw = conn.recv(1024).decode().strip()
        conn.settimeout(None)
        nome = nome_raw if nome_raw else f"Usuario_{addr[1]}"
        with lock_usuarios:
            if nome not in usuarios:
                usuarios[nome] = {"saldo": 5000.0, "saldo_bloqueado": 0.0, "itens": []}
                salvar_usuarios()
                fila_envio.put(f"\n[INFO] Conta criada para {nome} com saldo inicial de R$5000,00. Boa sorte no leilão!")
            else:
                u = usuarios[nome]
                fila_envio.put(
                    f"\n[INFO] Bem-vindo de volta, {nome}! "
                    f"Saldo disponível: R${u['saldo']:.2f}, "
                    f"Itens comprados: {len(u['itens'])}"
                )
        # timeout curto no loop principal para não bloquear em recv
        conn.settimeout(1.0)
        # loop principal
        while True:
            with lock:
                if not item_leilao["ativo"]:
                    fila_envio.put("\n[INFO] O leilão encerrou. Você será desconectado.")
                    break
            try:
                dados = conn.recv(1024).decode().strip()
            except socket.timeout:
                continue  # apenas verifica o estado do leilão novamente
            except Exception:
                break
            ####################################################
            if not dados or dados == ":quit":
                fila_envio.put("\nSaindo do leilão...\n")
                break
            #####################################################
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
            #####################################################
            elif dados == ":tempo":
                with lock:
                    t = item_leilao["tempo"]
                fila_envio.put(f"\nTempo restante: {t} segundos")
            #####################################################
            elif dados == ":saldo":
                with lock_usuarios:
                    u = usuarios.get(nome, {})
                    saldo = u.get("saldo", 0.0)
                    bloqueado = u.get("saldo_bloqueado", 0.0)
                fila_envio.put(
                    f"\nSaldo disponível: R${saldo:.2f}\n"
                    f"Saldo bloqueado: R${bloqueado:.2f}\n"
                    f"Saldo total: R${saldo + bloqueado:.2f}"
                )
            #####################################################
            elif dados == ":itens":
                with lock_usuarios:
                    itens = list(usuarios.get(nome, {}).get("itens", []))
                if not itens:
                    fila_envio.put("\nVocê ainda não comprou nenhum item.")
                else:
                    linhas = "\n".join(
                        f"  - {it['item']}  "
                        f"(pago: R${it['valor_pago']:.2f} | "
                        f"revenda: R${it['valor_pago'] * 0.9:.2f})"
                        for it in itens
                    )
                    fila_envio.put(f"\n--- SEUS ITENS ---\n{linhas}\n------------------")
            #####################################################
            elif dados.lower().startswith(":lance"):
                partes = dados.split()
                if len(partes) < 3:
                    fila_envio.put("\nComando inválido. Use: :Lance <item> <valor>  (ex: :Lance Quadro Monalisa 1200)")
                else:
                    item_alvo = " ".join(partes[1:-1])
                    try:
                        novo_lance = float(partes[-1])
                        if novo_lance <= 0:
                            fila_envio.put("\nValor do lance inválido. O lance deve ser maior que zero.")
                            raise ValueError
                        with lock:
                            item_atual = item_leilao["item"]
                            valor_atual = item_leilao["valor_atual"]
                            lider_atual = item_leilao["vencedor"]
                        if item_alvo.lower() != item_atual.lower():
                            fila_envio.put(f"\nEsse não é o item atual... O item em leilão é '{item_atual}'.")
                        elif novo_lance <= valor_atual:
                            fila_envio.put(f"\nLance recusado. O lance mínimo é R${valor_atual + 0.01:.2f}.")
                        else:
                            lance_aceito = False
                            with lock_usuarios:
                                u = usuarios[nome]
                                # saldo efetivo: se o jogador já é líder, o bloqueado será devolvido, então conta como disponível
                                saldo_efetivo = u["saldo"] + (u["saldo_bloqueado"] if lider_atual == nome else 0.0)
                                if saldo_efetivo < novo_lance:
                                    fila_envio.put(
                                        f"\nSaldo insuficiente. "
                                        f"Seu saldo total é R${u['saldo'] + u['saldo_bloqueado']:.2f} "
                                        f"e o lance é R${novo_lance:.2f}."
                                    )
                                else:
                                    # ve o valor atual com lock para evitar race entre a checagem e a atualização
                                    with lock:
                                        if novo_lance <= item_leilao["valor_atual"]:
                                            fila_envio.put(
                                                f"\nLance recusado. Outro lance foi aceito antes. "
                                                f"O mínimo agora é R${item_leilao['valor_atual'] + 0.01:.2f}."
                                            )
                                        else:
                                            # Desbloqueia saldo do líder anterior
                                            if lider_atual in usuarios:
                                                anterior = usuarios[lider_atual]
                                                anterior["saldo"] += anterior["saldo_bloqueado"]
                                                anterior["saldo_bloqueado"] = 0.0
                                                if lider_atual not in NOMES_BOTS and lider_atual != nome:
                                                    broadcast(
                                                        f"\n[INFO] O lance de {lider_atual} foi superado "
                                                        f"por {nome}! Saldo de {lider_atual} desbloqueado."
                                                    )
                                            # Cobra o novo lance
                                            u["saldo"] -= novo_lance
                                            u["saldo_bloqueado"] += novo_lance
                                            # Atualiza o leilão dentro do mesmo lock
                                            item_leilao["valor_atual"] = novo_lance
                                            item_leilao["vencedor"] = nome
                                            item_leilao["tempo"] = 30
                                            lance_aceito = True
                                    if lance_aceito:
                                        salvar_usuarios()
                            if lance_aceito:
                                fila_envio.put(
                                    f"\n[SUCESSO] Lance de R${novo_lance:.2f} aceito! "
                                    f"Você está no topo, {nome}!"
                                )
                                broadcast(
                                    f"\n[ATUALIZAÇÃO] Novo lance de R${novo_lance:.2f} por {nome}! "
                                    f"Lance atual: R${novo_lance:.2f}"
                                )
                    except ValueError:
                        fila_envio.put("\nValor do lance inválido. Use um número para o lance.")
            #####################################################
            elif dados.lower().startswith(":vender"):
                item_vender = dados[8:].strip()
                with lock_usuarios:
                    u = usuarios[nome]
                    encontrado = next(
                        (it for it in u["itens"] if it["item"].lower() == item_vender.lower()),
                        None
                    )
                    if not encontrado:
                        fila_envio.put(f"\nVocê não possui o item '{item_vender}'.")
                    else:
                        valor_venda = round(encontrado["valor_pago"] * 0.9, 2)
                        u["saldo"] += valor_venda
                        u["itens"].remove(encontrado)
                        salvar_usuarios()
                        fila_envio.put(
                            f"\n[SUCESSO] Item '{encontrado['item']}' vendido por "
                            f"R${valor_venda:.2f}. Saldo atualizado: R${u['saldo']:.2f}."
                        )
            else:
                fila_envio.put(
                    "\nComando desconhecido. Use :item, :tempo, :saldo, :itens, "
                    ":Lance <item> <valor>, :Vender <item> ou :quit."
                )
#####################################################
    except Exception as e:
        # loga o erro real
        print(f"[Servidor] Erro na thread do cliente {addr}: {e}")
    finally:
        if nome and nome in usuarios:
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
        try:
            conn.close()
        except Exception:
            pass
        print(f"[Servidor] Cliente {addr} desconectado.")

# thread do cronômetro regressivo
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
                print("[Servidor] Fechando servidor em 5 segundos...")
                time.sleep(5) 
                os._exit(0)
    finally:
        print("[Servidor] Cronômetro encerrado.")

# thread dos bots
def thread_bots():
    time.sleep(5)
    while True:
        time.sleep(random.uniform(30, 40))
        with lock:
            if not item_leilao["ativo"]:
                break
            valor_base = item_leilao["valor_atual"]
            lider_atual = item_leilao["vencedor"]
        # escolhe um bot que NÃO seja o líder atual para dar o lance
        bots_disponiveis = [b for b in NOMES_BOTS if b != lider_atual]
        if not bots_disponiveis:
            continue
        bot_nome = random.choice(bots_disponiveis)
        variacao = random.uniform(0.01, 0.08)
        novo_lance = round(valor_base * (1 + variacao), 2)
        # saldo efetivo do bot = saldo livre + bloqueado (que será devolvido se ele der novo lance)
        with lock_usuarios:
            b = usuarios[bot_nome]
            saldo_efetivo = b["saldo"] + b["saldo_bloqueado"]
        # bot não pode dar lance acima do seu saldo total (limite de R$5000)
        if novo_lance > saldo_efetivo:
            continue
        with lock:
            if not item_leilao["ativo"]:
                break
            # verifica novamente após os locks — outro thread pode ter mudado o valor
            if novo_lance <= item_leilao["valor_atual"]:
                continue
            item_leilao["valor_atual"] = novo_lance
            item_leilao["vencedor"] = bot_nome
            item_leilao["tempo"] = 30

        # atualiza saldos: devolve bloqueado do bot anterior (se for bot), cobra novo lance do bot vencedor, desbloqueia humano se era o líder
        with lock_usuarios:
            # devolve lance anterior do bot escolhido (caso ele já tivesse bloqueado algo)
            b = usuarios[bot_nome]
            b["saldo"] += b["saldo_bloqueado"]
            b["saldo_bloqueado"] = 0.0
            # cobra o novo lance
            b["saldo"] -= novo_lance
            b["saldo_bloqueado"] += novo_lance
            # desbloqueia saldo do líder anterior
            if lider_atual in usuarios:
                prev = usuarios[lider_atual]
                prev["saldo"] += prev["saldo_bloqueado"]
                prev["saldo_bloqueado"] = 0.0
                if lider_atual not in NOMES_BOTS:
                    broadcast(f"\n[INFO] Um bot superou seu lance! Seu saldo foi desbloqueado.")
            salvar_usuarios()
        update = (
            f"\n[{bot_nome}] deu um lance de R${novo_lance:.2f}!\n"
            f"   Novo líder: {bot_nome} — Lance atual: R${novo_lance:.2f}"
        )
        broadcast(update)
        print(f"[Bot] {bot_nome} — R${novo_lance:.2f}")

# salva dados ao receber SIGINT (Ctrl+C) antes de encerrar
def encerrar_servidor(sig, frame):
    print("\n[Servidor] Encerrando... salvando dados.")
    with lock_usuarios:
        salvar_usuarios()
    try:
        server.close()
    except Exception:
        pass
    sys.exit(0)
signal.signal(signal.SIGINT, encerrar_servidor)

# inicializando o servidor
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((CONFIG["HOST"], CONFIG["PORTA"]))
server.listen()

print(f"Servidor pronto.")
print(f"Item: {item_leilao['item']}")
print(f"Lance inicial: R${item_leilao['valor_atual']:.2f}")
print(f"Aguardando conexões em {CONFIG['HOST']}:{CONFIG['PORTA']}...\n")

threading.Thread(target=thread_cronometro, daemon=True).start()
threading.Thread(target=thread_bots, daemon=True).start()

while True:
    try:
        conn, addr = server.accept()
        with conexoes_lock:
            if conexoes_ativas >= LIMITE_CONEXAO:
                conn.send("\nServidor cheio. Tente novamente mais tarde.".encode())
                conn.close()
                print(f"[Servidor] Rejeitou conexão de {addr} — limite atingido.")
                continue
            conexoes_ativas += 1
        fila_envio = queue.Queue()
        t_recv = threading.Thread(target=thread_receber, args=(conn, addr, fila_envio), daemon=True)
        t_send = threading.Thread(target=thread_enviar, args=(conn, fila_envio), daemon=True)
        t_recv.start()
        t_send.start()
    except OSError:
        # socket fechado pelo handler de SIGINT
        break
    except KeyboardInterrupt:
        encerrar_servidor(None, None)