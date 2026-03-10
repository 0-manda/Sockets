import socket
import threading

#configs
CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000}

#flag ao finalizar as threads
encerrado = threading.Event()

def thread_escutar(cli_socket):
    while not encerrado.is_set():
        try:
            msg = cli_socket.recv(1024).decode()
            if not msg:
                print("\n[Cliente] O servidor fechou a conexão.")
                encerrado.set()
                break
            print(f"\n{msg}")
            # encerra o cliente ao fim do leilão
            if "LEILÃO ENCERRADO" in msg or "Saindo do leilão" in msg:
                encerrado.set()
                break
            print("Sua ação: ", end="", flush=True)
        except Exception:
            if not encerrado.is_set():
                print("\n[Cliente] Conexão perdida com o servidor.")
            encerrado.set()
            break
#thread 1 (leitura de comandos)
try:
    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cliente.connect((CONFIG["HOST"], CONFIG["PORTA"]))
	
	#recebendo dados
    dados_iniciais = cliente.recv(1024).decode()
    print(dados_iniciais)
	
    # inicia a escuta
    t = threading.Thread(target=thread_escutar, args=(cliente,), daemon=True)
    t.start()
    while not encerrado.is_set():
        try:
            comando = input("Sua ação: ")
        except EOFError:
            break
        if not comando.strip():
            continue
        try:
            cliente.send(comando.encode())
        except Exception:
            print("[Cliente] Erro ao enviar o comando.")
            break
        if comando.strip() == ":quit":
            print("Saindo...")
            encerrado.set()
            break
    t.join(timeout=2)
except Exception as e:
    print(f"\n[ERRO CRÍTICO] {e}")
finally:
    cliente.close()
    input("\nPressione ENTER para fechar a janela...")