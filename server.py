import socket
import threading
import time
import random 

# Configurações do servidor
CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000}

# Memória Compartilhada
item_leilao = {
    "item": "Quadro Monalisa",
    "valor_atual": 900000.0,
    "vencedor": "ninguém",
    "tempo": 60,
    "ativo": True
}

lock = threading.Lock() # Protege a memória compartilhada

def thread_cronometro(conexao):
    #Controla o tempo e evita erro de socket fechado
    try:
        while item_leilao["tempo"] > 0 and item_leilao["ativo"]:
            time.sleep(1) #cadencia a contagem regressiva
            with lock:
                item_leilao["tempo"] -= 1
            
            # Avisa o cliente nos últimos 10 segundos
            if 0 < item_leilao["tempo"] <= 10:
                try:
                    conexao.send(f"\nO leilão encerra em {item_leilao['tempo']}s!".encode())
                except:
                    break 

        if item_leilao["ativo"]:
            with lock: #solicita permissão para acessar a memoria compartilhada
                item_leilao["ativo"] = False #altera pra falso o status do leilao
            try:
                conexao.send(f"\nLeilão encerrado! Vencedor: {item_leilao['vencedor']}".encode())
            except:
                pass
    finally:
        print("Tempo acabou")

def thread_receber(conn, addr):
    print(f"[Servidor] Cliente {addr} conectado.")
    while item_leilao["ativo"]:
        try:
            dados = conn.recv(1024).decode().strip() #recebe os bytes do socket e transforma em texto
            if not dados: break

            if dados == ":quit":
                conn.send("Saindo do leilão...".encode())
                break
            
            elif dados == ":item":
                with lock:
                    resposta = (
                        f"\n--- INFO ITEM ---\n"
                        f"Item: {item_leilao['item']}\n"
                        f"Lance Atual: R${item_leilao['valor_atual']:.2f}\n"
                        f"Maior lance: {item_leilao['vencedor']}\n"
                        f"------------------"
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
                            item_leilao["vencedor"] = f"Você ({addr[1]})"
                            item_leilao["tempo"] = 30 # Dá mais tempo ao aceitar lance
                            resposta = f"\n[SUCESSO]: Lance de R${novo_lance:.2f} ACEITO!"
                        else:
                            resposta = f"\nLance baixo! O valor atual é R${item_leilao['valor_atual']:.2f}"
                    conn.send(resposta.encode())
                except ValueError:
                    conn.send("\nDigite um valor numérico ou comando (:item, :tempo).".encode())
        except:
            break
    conn.close()


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #criação do socket com IPv4(AF_NET) e transporte TCP (SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #garante que se o servidor cair e tentar rodar novamente, ele nao de erro
server.bind((CONFIG["HOST"], CONFIG["PORTA"]))
server.listen()

print(f"Servidor pronto.\nItem: {item_leilao['item']}\nLance inicial: R${item_leilao['valor_atual']:.2f}")

conn, addr = server.accept()
horario = time.strftime("%H:%M")

mensagem_inicial = (
    f"\n{horario}: CONECTADO!!\n"
    f"Item: {item_leilao['item']} | Valor: R${item_leilao['valor_atual']:.2f}\n"
    f"Comandos: :item | :tempo | :quit | ou digite o valor do lance\n"
)
conn.send(mensagem_inicial.encode())

#Threads
t1 = threading.Thread(target=thread_receber, args=(conn, addr), daemon=True)
t1.start() #thread para ouvir o comando dos clientes

t2 = threading.Thread(target=thread_cronometro, args=(conn,), daemon=True)
t2.start() #thread de controlar o tempo do leilão

try:
    while item_leilao["ativo"]:
        time.sleep(1)
except KeyboardInterrupt: #ctrl C faz o socket cair ou servidor seila
    print("\nDesligando servidor...")
    item_leilao["ativo"] = False

server.close() #fecha a porta e encerra o socket