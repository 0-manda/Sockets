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
CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000} #bind

if len(sys.argv) < 4: # usando o sys para ler argumentos da linha de comando, o programa espera 3 argumentos: limite de conexões, nome do item e valor inicial. Se não receber, exibe a mensagem de uso e encerra.  
    print("Uso: python server.py <limite_conexoes> <nome_do_item> <valor_inicial>")
    sys.exit(1)
try:
    LIMITE_CONEXAO = int(sys.argv[1]) #limite de conexões simultâneas, convertido para inteiro
    NOME_ITEM = " ".join(sys.argv[2:-1])#pega o que está no limite de conexão e o valor inicial, e junta como nome do item (suporta nomes com espaços)
    VALOR_INICIAL = float(sys.argv[-1])

    item_leilao = { #dicionário para armazenar as informações do item em leilão
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

lock_usuarios = threading.Lock()#Quando uma thread for acessar o dicionário de usuários para ler ou modificar dados, ela deve adquirir esse lock para garantir que nenhuma outra thread esteja modificando os dados ao mesmo tempo, evitando condições de corrida e garantindo a integridade dos dados dos usuários.

def carregar_usuarios(): 
    if os.path.exists("usuarios.json"):# se tiver no path um arquivo chamado usuarios.json, ele é aberto para leitura, e o conteúdo é carregado como um dicionário. Se o arquivo não existir, retorna um dicionário vazio.
        with open("usuarios.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_usuarios():
    with open("usuarios.json", "w", encoding="utf-8") as f: #abre o arquivo usuarios.json para escrita (criando se não existir, ou sobrescrevendo se já existir), e salva o dicionário de usuários no formato JSON
        json.dump(usuarios, f, indent=4)

usuarios = carregar_usuarios()# dicionário de usuários e seus saldos

# Limpando entradas corrompidas: garante que nenhum usuário tenha saldo total acima de 5000
def sanitizar_usuarios():
    for nome_u, u in usuarios.items():
        # Garante que as chaves existem
        u.setdefault("saldo", 5000.0)
        u.setdefault("saldo_bloqueado", 0.0)
        u.setdefault("itens", []) #Seta todas as informações default para os usuários, caso falte alguma (ex: saldo_bloqueado ou itens)
        # Reseta saldo_bloqueado solto (de sessão encerrada abruptamente)
        total = u["saldo"] + u["saldo_bloqueado"]
        if u["saldo_bloqueado"] > 0 and total <= 5000.0: #dinheiro que saiu de um leilão que não finalizou da forma correta, devolve para o saldo disponível
            u["saldo"] += u["saldo_bloqueado"] #saldo bloqueado volta para default
            u["saldo_bloqueado"] = 0.0
    salvar_usuarios()#salva

sanitizar_usuarios()#executa a limpeza

# garante que todos os bots já existem em usuarios com saldo inicial
NOMES_BOTS = ["Carlos", "Beatriz", "Rafael", "Fernanda", "Thiago"]
with lock_usuarios:
    for bot in NOMES_BOTS:
        if bot not in usuarios:
            usuarios[bot] = {"saldo": 5000.0, "saldo_bloqueado": 0.0, "itens": []}
    salvar_usuarios()

lock = threading.Lock()# lock na memória compartilhada (lock geral)
clientes_conectados = [] #lista de filas de envio para os clientes conectados, usada para enviar mensagens do servidor para os clientes (broadcast) e para cada thread de envio individual. O lock é usado para garantir que a lista seja modificada de forma segura por múltiplas threads.
clientes_lock = threading.Lock() # lock na lista de clientes
conexoes_ativas = 0 #variavel global para contar a quantidade de conexões ativas
conexoes_lock = threading.Lock() # lock para controlar o número de conexões

def broadcast(mensagem):
    with clientes_lock: #lista acessada de forma segura pelas threads
        for fila in clientes_conectados:
            try:
                fila.put(mensagem) #coloca a mensagem na fila de envio de cada cliente, para que as threads de envio possam enviar a mensagem para os clientes sem bloquear o servidor principal
            except Exception:
                pass

# thread de envio (consome a fila e envia ao cliente)
def thread_enviar(conn, fila_envio): #send
    while True:
        try:
            msg = fila_envio.get(timeout=1) #pega a mensagem da fila de envio, com timeout para evitar bloqueio indefinido caso a fila esteja vazia
            if msg is None: # sinal para encerrar por erros ou desconexão
                break
            conn.send(msg.encode()) #envia a mensagem para o cliente, codificando a string em bytes antes de enviar.
        except queue.Empty: # se a fila estiver vazia, apenas verifica o estado do leilão novamente
            with lock:
                if not item_leilao["ativo"]: #se o leilão não estiver mais ativo, encerra a thread de envio
                    break
        except Exception:
            break

# thread de recebimento (processa comandos/lances do cliente)
def thread_receber(conn, addr, fila_envio): #recv
    global conexoes_ativas #variavel global, é necessário avisar que vamos usar ela dentro da função para modificar seu valor
    print(f"[Servidor] Cliente {addr} conectado.")
    with clientes_lock:# tranca lista de clientes
        clientes_conectados.append(fila_envio) #adciona os clientes conectados na lista de fila dos clientes, para que o servidor possa enviar mensagens para eles
    nome = None #bom costume inicializar a variável nome como None
    try:
        # mensagem de boas-vindas com horário
        horario = time.strftime("%H:%M:%S")
        fila_envio.put(f"{horario}: CONECTADO!!")
        time.sleep(0.1)
        # informações iniciais do item
        with lock:# tranca a memória compartilhada para ler os dados do item de forma segura
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
        fila_envio.put(info) #manda a mensagem de boas-vindas e informações do item para o cliente
        time.sleep(0.1)
        fila_envio.put("\nDigite seu nome para participar: ") #pede para o cliente digitar o nome para participar do leilão
        # timeout no recv para não travar indefinidamente
        conn.settimeout(120)
        nome_raw = conn.recv(1024).decode().strip() #recebe o nome digitado pelo cliente, decodifica de bytes para string e remove espaços em branco no início e no final
        conn.settimeout(None) #volta o timeout para None (sem limite) para as operações seguintes
        nome = nome_raw if nome_raw else f"Usuario_{addr[1]}" #se o cliente não digitar um nome, atribui um nome genérico baseado na porta de origem
        with lock_usuarios: #tranca o dicionário de usuários para acessar de forma segura
            if nome not in usuarios: #verifica se o nome digitado já existe no dicionário de usuários, se não existir, cria uma nova conta para o usuário com saldo inicial de R$5000,00 e salva no arquivo. Se já existir, apenas dá as boas-vindas de volta.
                usuarios[nome] = {"saldo": 5000.0, "saldo_bloqueado": 0.0, "itens": []}
                salvar_usuarios()
                fila_envio.put(f"\n[INFO] Conta criada para {nome} com saldo inicial de R$5000,00. Boa sorte no leilão!")
            else:
                u = usuarios[nome]
                fila_envio.put(
                    f"\n[INFO] Bem-vindo de volta, {nome}! "
                    f"Saldo disponível: R${u['saldo']:.2f}, "
                    f"Itens comprados: {len(u['itens'])}" #relembra saldo e informações de users já cadastrados
                )
        # timeout curto no loop principal para não bloquear em recv
        conn.settimeout(1.0)
        # loop principal (listen)
        while True:
            with lock: #tranca a memória compartilhada para ler o estado do leilão de forma segura
                if not item_leilao["ativo"]: #espera, ve se o leilão ainda está ativo, se não estiver, envia a mensagem de encerramento para o cliente e encerra a thread de recebimento
                    fila_envio.put("\n[INFO] O leilão encerrou. Você será desconectado.")
                    break
            try:
                dados = conn.recv(1024).decode().strip() #recebe o comando do cliente, decodifica de bytes para string e remove espaços em branco no início e no final
            except socket.timeout:
                continue  # apenas verifica o estado do leilão novamente
            except Exception:
                break
            ####################################################
            if not dados or dados == ":quit": #se o cliente enviar uma mensagem vazia ou o comando de quit, encerra a thread de recebimento e envia a mensagem de saída para o cliente
                fila_envio.put("\nSaindo do leilão...\n")
                break
            #####################################################
            if dados == ":item": #se o cliente digitar o comando :item, envia as informações do item em leilão para o cliente, lendo os dados de forma segura com lock
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
            elif dados == ":tempo":#se o cliente digitar o comando :tempo, envia o tempo restante do leilão para o cliente, lendo o dado de forma segura com lock
                with lock:
                    t = item_leilao["tempo"]
                fila_envio.put(f"\nTempo restante: {t} segundos")
            #####################################################
            elif dados == ":saldo": #se o cliente digitar o comando :saldo, envia o saldo disponível, bloqueado e total para o cliente, lendo os dados de forma segura com lock_usuarios
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
            elif dados == ":itens": #se o cliente digitar o comando :itens, envia a lista de itens comprados pelo cliente, lendo os dados de forma segura com lock_usuarios. Se o cliente não tiver comprado nenhum item, envia uma mensagem informando isso.
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
                if len(partes) < 3: #ve se o usuario digitou o comando de lance corretamente, verificando se tem pelo menos 3 partes
                    fila_envio.put("\nComando inválido. Use: :Lance <item> <valor>  (ex: :Lance Quadro Monalisa 1200)")
                else:
                    item_alvo = " ".join(partes[1:-1])#o nome do item pode ter espaços, então junta todas as partes do meio para formar o nome do item que o usuário quer dar lance
                    try:
                        novo_lance = float(partes[-1])#tenta converter a última parte do comando para um número, que é o valor do lance
                        if novo_lance <= 0:
                            fila_envio.put("\nValor do lance inválido. O lance deve ser maior que zero.")
                            raise ValueError
                        with lock: #tranca a memória compartilhada para ler os dados do leilão de forma segura
                            item_atual = item_leilao["item"]
                            valor_atual = item_leilao["valor_atual"]
                            lider_atual = item_leilao["vencedor"]
                        if item_alvo.lower() != item_atual.lower():
                            fila_envio.put(f"\nEsse não é o item atual... O item em leilão é '{item_atual}'.")#itens diferentes, recusa o lance
                        elif novo_lance <= valor_atual:
                            fila_envio.put(f"\nLance recusado. O lance mínimo é R${valor_atual + 0.01:.2f}.") #lance menor ou igual ao atual, recusa o lance
                        else:
                            lance_aceito = False #flag para controlar se o lance foi aceito, para só salvar os usuários e enviar mensagens de sucesso se o lance realmente for aceito
                            with lock_usuarios: #tranca o dicionário de usuários para acessar de forma segura
                                u = usuarios[nome] #pega os dados do usuário que está dando o lance
                                # saldo efetivo: se o jogador já é líder, o bloqueado será devolvido, então conta como disponível
                                saldo_efetivo = u["saldo"] + (u["saldo_bloqueado"] if lider_atual == nome else 0.0)
                                if saldo_efetivo < novo_lance: #saldo insuficiente para dar o lance, recusa o lance e informa o saldo
                                    fila_envio.put(
                                        f"\nSaldo insuficiente. "
                                        f"Seu saldo total é R${u['saldo'] + u['saldo_bloqueado']:.2f} "
                                        f"e o lance é R${novo_lance:.2f}."
                                    )
                                else:
                                    # ve o valor atual com lock para evitar race entre a checagem e a atualização
                                    with lock:
                                        if novo_lance <= item_leilao["valor_atual"]: #outro lance foi aceito antes que esse, recusa o lance e informa o novo valor atual
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
                                    if lance_aceito: #se o lance foi aceito, salva os usuários e envia as mensagens de sucesso e atualização para os clientes
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
            elif dados.lower().startswith(":vender"): #se o cliente digitar o comando :vender, tenta vender o item especificado pelo cliente por 90% do valor pago, lendo os dados de forma segura com lock_usuarios. Se o cliente não tiver o item, ou se o comando estiver mal formatado, envia uma mensagem de erro
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
    finally: #vai executar simmmmm!
        if nome and nome in usuarios: #se o cliente tinha um nome válido e estava registrado nos usuários, verifica se ele era o vencedor do leilão.
            with lock:
                venceu = item_leilao["vencedor"] == nome 
            with lock_usuarios:
                if not venceu and usuarios[nome]["saldo_bloqueado"] > 0: #s o cliente não era o líder atual, mas tinha um lance bloqueado (ou seja, tinha dado um lance que foi superado por outro), devolve o saldo bloqueado para o saldo disponível
                    usuarios[nome]["saldo"] += usuarios[nome]["saldo_bloqueado"]
                    usuarios[nome]["saldo_bloqueado"] = 0.0
                    salvar_usuarios()#salva
        fila_envio.put(None)
        with clientes_lock:
            if fila_envio in clientes_conectados: #verifica se a fila de envio do cliente ainda está na lista de clientes conectados (pode ter sido removida por outra thread em casos de erro), e remove para parar de enviar mensagens para esse cliente
                clientes_conectados.remove(fila_envio)
        with conexoes_lock:
            conexoes_ativas -= 1 #decrementa o contador de conexões ativas, indicando que um cliente se desconectou
        try:
            conn.close() #fecha a conexão com o cliente para liberar recursos e encerrar a comunicação
        except Exception:
            pass
        print(f"[Servidor] Cliente {addr} desconectado.")

# thread do cronômetro regressivo
def thread_cronometro():
    try:
        while True:
            time.sleep(1)
            with lock:
                if not item_leilao["ativo"]: #se o leilão não estiver mais ativo, encerra a thread do cronômetro
                    break
                item_leilao["tempo"] -= 1 #decrementa o tempo restante do leilão a cada segundo
                tempo_atual = item_leilao["tempo"] #armazena o tempo atual em uma variável para usar nas mensagens, evitando acessar o dicionário várias vezes
            if tempo_atual in (15, 10, 5):
                broadcast(f"\nAtenção! {tempo_atual} segundos restantes!") #envia mensagens de alerta para os clientes quando o tempo restante chegar a 15, 10 e 5 segundos
            if tempo_atual <= 0: #quando o tempo chegar a zero, encerra o leilão, determina o vencedor e o valor final, atualiza os dados do vencedor (desbloqueia o saldo bloqueado e adiciona o item comprado), salva os usuários, envia a mensagem de encerramento para os clientes e encerra o servidor após um tempo para os clientes lerem a mensagem
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
                broadcast(msg) #envia a mensagem de encerramento para os clientes
                print(f"[Servidor] Leilão encerrado. Vencedor: {vencedor} — R${valor:.2f}")
                print("[Servidor] Fechando servidor em 5 segundos...")
                time.sleep(5) 
                os._exit(0) #fecha o servidor imediatamente, encerrando todas as threads e conexões, para garantir que os clientes sejam desconectados e o programa seja finalizado após o leilão encerrar
    finally:
        print("[Servidor] Cronômetro encerrado.")

# thread dos bots
def thread_bots():
    time.sleep(5)
    while True:
        time.sleep(random.uniform(30, 40)) #espera um tempo aleatório entre 30 e 40 segundos antes de cada tentativa de lance dos bots, para simular um comportamento mais humano e imprevisível
        with lock:
            if not item_leilao["ativo"]: #se o leilão não estiver mais ativo, encerra a thread dos bots
                break
            valor_base = item_leilao["valor_atual"]#pega o valor atual do leilão para calcular os lances dos bots, garantindo que eles sempre tentem superar o lance atual
            lider_atual = item_leilao["vencedor"]#pega o nome do líder atual para evitar que o bot tente dar lance se ele já for o líder, e para escolher um bot diferente para dar o lance
        # escolhe um bot que NÃO seja o líder atual para dar o lance
        bots_disponiveis = [b for b in NOMES_BOTS if b != lider_atual]
        if not bots_disponiveis:
            continue
        bot_nome = random.choice(bots_disponiveis) #escolhe aleatoriamente um bot da lista de bots disponíveis para dar o lance
        variacao = random.uniform(0.01, 0.08) #gera uma variação aleatória entre 1% e 8% para calcular o valor do lance
        novo_lance = round(valor_base * (1 + variacao), 2)
        # saldo efetivo do bot = saldo livre + bloqueado (que será devolvido se ele der novo lance)
        with lock_usuarios:
            b = usuarios[bot_nome]
            saldo_efetivo = b["saldo"] + b["saldo_bloqueado"]#pega dados do bot para calcular o saldo efetivo, que é a soma do saldo disponível e do saldo bloqueado
        # bot não pode dar lance acima do seu saldo total (limite de R$5000)
        if novo_lance > saldo_efetivo:
            continue
        with lock:
            if not item_leilao["ativo"]:
                break
            # verifica novamente após os locks — outro thread pode ter mudado o valor
            if novo_lance <= item_leilao["valor_atual"]:
                continue
            item_leilao["valor_atual"] = novo_lance #atualiza o valor atual do leilão com o novo lance do bot
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
                if lider_atual not in NOMES_BOTS: #se o líder anterior não for um bot, ou seja, for um humano, envia uma mensagem de que o lance dele foi superado e o saldo desbloqueado
                    broadcast(f"\n[INFO] Um bot superou seu lance! Seu saldo foi desbloqueado.")
            salvar_usuarios()
        update = (
            f"\n[{bot_nome}] deu um lance de R${novo_lance:.2f}!\n"
            f"   Novo líder: {bot_nome} — Lance atual: R${novo_lance:.2f}"
        )
        broadcast(update) # manda a mensagem de atualização do lance do bot para os clientes
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
signal.signal(signal.SIGINT, encerrar_servidor)#configura o handler para o sinal de interrupção (SIGINT), que é enviado quando o usuário pressiona Ctrl+C no terminal. Quando o servidor recebe esse sinal, a função encerrar_servidor é chamada, que salva os dados dos usuários, fecha o socket do servidor e encerra o programa de forma limpa.

# inicializando o servidor
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #cria um socket TCP/IP usando IPv4. O socket é o ponto de comunicação que o servidor usará para aceitar conexões dos clientes e enviar/receber dados.
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #configura o socket para permitir que o endereço seja reutilizado imediatamente após o servidor ser encerrado, evitando erros de "endereço já em uso" ao reiniciar o servidor rapidamente. O SO_REUSEADDR é uma opção de socket que permite que um socket seja vinculado a um endereço que já está em uso, o que é útil para desenvolvimento e testes
server.bind((CONFIG["HOST"], CONFIG["PORTA"])) #procura o servidor e porta definifos para vincular o socket, ou seja, associar o socket a um endereço IP e número de porta específicos. O servidor ficará "escutando" nesse endereço e porta para aceitar conexões dos clientes.
server.listen()#coloca o servidor em modo de escuta, permitindo que ele aceite conexões dos clientes.

print(f"Servidor pronto.")
print(f"Item: {item_leilao['item']}")
print(f"Lance inicial: R${item_leilao['valor_atual']:.2f}")
print(f"Aguardando conexões em {CONFIG['HOST']}:{CONFIG['PORTA']}...\n")

threading.Thread(target=thread_cronometro, daemon=True).start() #inicia a thread do cronômetro regressivo, que vai controlar o tempo do leilão e enviar mensagens de alerta para os clientes. A thread é configurada como daemon, o que significa que ela será encerrada automaticamente quando o programa principal for finalizado, garantindo que o servidor possa ser encerrado de forma limpa mesmo se o cronômetro ainda estiver rodando.
threading.Thread(target=thread_bots, daemon=True).start()#incia a thread dos bots, que vai simular lances automáticos de bots durante o leilão. A thread também é configurada como daemon para garantir que ela seja encerrada automaticamente quando o programa principal for finalizado.

while True:
    try:
        conn, addr = server.accept() #aceita uma conexão de um cliente
        with conexoes_lock:#tranca o lock de conexões para verificar e atualizar o número de conexões ativas de forma segura
            if conexoes_ativas >= LIMITE_CONEXAO:
                conn.send("\nServidor cheio. Tente novamente mais tarde.".encode())
                conn.close()
                print(f"[Servidor] Rejeitou conexão de {addr} — limite atingido.")
                continue
            conexoes_ativas += 1#incrementa o contador de conexões ativas, indicando que um novo cliente se conectou.
        fila_envio = queue.Queue()#cria uma fila de mensagens para enviar ao cliente, que será usada pelas threads de envio para enviar mensagens do servidor para o cliente (cada cliente com a sua própria fila)
        t_recv = threading.Thread(target=thread_receber, args=(conn, addr, fila_envio), daemon=True) #inicia a thread de recebimento para o cliente
        t_send = threading.Thread(target=thread_enviar, args=(conn, fila_envio), daemon=True) #inicia a thread de envio para o cliente
        t_recv.start() #starta as threads de recebimento e envio
        t_send.start()
    except OSError:
        # socket fechado pelo handler de SIGINT
        break
    except KeyboardInterrupt:
        encerrar_servidor(None, None)