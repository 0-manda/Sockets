import socket
import threading
import time

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

# Banco de dados temporário (em memória) para a fase 2
usuarios = {}
lock = threading.Lock() # Protege a memória compartilhada

# thread 1 (recebendo comandos do cliente)
def thread_receber(conn, addr):
    print(f"[Servidor] Cliente {addr} conectado.")
    try:
        # Pergunta o nome antes de entrar no loop de lances
        conn.send("Digite seu nome para entrar no leilão: ".encode())
        nome = conn.recv(1024).decode().strip()
        
        with lock:
            if nome not in usuarios:
                # Se for novo, cria a conta com 5000
                usuarios[nome] = {"saldo": 5000.0, "itens": []}
                msg = f"\nBem-vindo, {nome}! Você recebeu R$5000.00 de saldo inicial."
            else:
                # Se já existe, recupera o saldo
                msg = f"\nBem-vindo de volta, {nome}! Saldo: R${usuarios[nome]['saldo']:.2f}"
        conn.send(msg.encode())

        while True:
            with lock:
                if not item_leilao["ativo"]:
                    break
            
            # recebe os bytes do socket e transforma em texto
            dados = conn.recv(1024).decode().strip()
            if not dados or dados == ":quit":
                break

            if dados == ":item":
                with lock:
                    resposta = (
                        f"\n--- INFO ITEM ---\n"
                        f"Item: {item_leilao['item']}\n"
                        f"Lance Atual: R${item_leilao['valor_atual']:.2f}\n"
                        f"Maior lance: {item_leilao['vencedor']}\n"
                        f"------------------"
                    )
                conn.send(resposta.encode())
            
            # Lógica de lances (ainda sem o bloqueio, para testares a conexão primeiro)
            else:
                try:
                    novo_lance = float(dados)
                    with lock:
                        if novo_lance > item_leilao["valor_atual"]:
                            item_leilao["valor_atual"] = novo_lance
                            item_leilao["vencedor"] = nome # Agora o vencedor é o NOME
                            item_leilao["tempo"] = 30 # restart do tempo
                            resposta = f"\n[SUCESSO] Lance aceito! Liderança: {nome}"
                        else:
                            resposta = f"\n[RECUSADO] Lance baixo! Atual: R${item_leilao['valor_atual']:.2f}"
                    conn.send(resposta.encode())
                except ValueError:
                    conn.send("\nComando inválido. Use :item, :tempo ou valor.".encode())
    except:
        break
    finally:
        conn.close()
        print(f"[Servidor] Conexão com {addr} encerrada.")

# thread 2 (cronometro)
def thread_cronometro():
    # O cronômetro agora é GLOBAL para o item
    try:
        while True:
            time.sleep(1) # cadencia a contagem regressiva
            with lock:
                if not item_leilao["ativo"]:
                    break
                item_leilao["tempo"] -= 1
                tempo_atual = item_leilao["tempo"]
            
            if tempo_atual <= 0:
                with lock:
                    item_leilao["ativo"] = False
                print(f"Tempo acabou. Vencedor: {item_leilao['vencedor']}")
                break
    finally:
        print("[Servidor] Cronômetro encerrado.")

# inicializando o server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # criação do socket TCP/IPv4
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # evita erro de endereço em uso
server.bind((CONFIG["HOST"], CONFIG["PORTA"]))
server.listen()

print(f"Servidor pronto.\nItem: {item_leilao['item']}\nLance inicial: R${item_leilao['valor_atual']:.2f}")

# dispara o cronômetro uma única vez para o leilão
t_clock = threading.Thread(target=thread_cronometro, daemon=True)
t_clock.start()

while True:
    try:
        # server fica esperando qualquer pessoa se conectar
        conn, addr = server.accept()
        
        # thread para ouvir o comando dos clientes
        t1 = threading.Thread(target=thread_receber, args=(conn, addr), daemon=True)
        t1.start() 
    
    except KeyboardInterrupt: # ctrl C faz o servidor desligar
        print("\nDesligando servidor...")
        break

server.close() # fecha a porta e encerra o socket
