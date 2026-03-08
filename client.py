import socket
import threading
import sys

CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000}

def escutar_servidor(cli_socket):
    #Fica ouvindo o servidor em segundo plano
    while True:
        try:
            msg = cli_socket.recv(1024).decode()
            if not msg: 
                print("\nO servidor fechou a conexão.")
                break
            print(f"\n{msg}")
            print("Sua ação: ", end="", flush=True)
        except:
            break

try:
    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cliente.connect((CONFIG["HOST"], CONFIG["PORTA"]))

    # Recebe boas-vindas
    dados_iniciais = cliente.recv(1024).decode()
    print(dados_iniciais)

    t = threading.Thread(target=escutar_servidor, args=(cliente,), daemon=True)
    t.start()

    while True:
        comando = input("Sua ação: ") 
        
        if not comando:
            continue

        cliente.send(comando.encode())

        if comando.strip() == ":quit":
            print("Saindo...")
            break

except Exception as e:
    print(f"\nERRO CRÍTICO: {e}")
finally:
    cliente.close()
    input("\nPressione ENTER para fechar a janela...") # Impede o fechamento súbito