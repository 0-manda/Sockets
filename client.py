import socket
import threading

# configs
CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000}

# flag ao finalizar as threads
encerrado = threading.Event()

def thread_escutar(cli_socket):
    while not encerrado.is_set():
        try:
            msg = cli_socket.recv(4096).decode()
            if not msg:
                print("\n[Cliente] O servidor fechou a conexão.")
                encerrado.set()
                break
            print(f"\n{msg}")
            if "LEILÃO ENCERRADO" in msg or "Saindo do leilão" in msg or "Servidor cheio" in msg:
                encerrado.set()
                break
        except Exception:
            if not encerrado.is_set():
                print("\n[Cliente] Conexão perdida com o servidor.")
            encerrado.set()
            break

def ajuda():
    print("\nComandos disponíveis:")
    print("  :Lance <item> <valor>  — Dar um lance (ex: :Lance Quadro Monalisa 1200)")
    print("  :Vender <item>         — Vender item por 90% do valor (ex: :Vender Quadro Monalisa)")
    print("  :item                  — Info do item em leilão")
    print("  :tempo                 — Exibe o tempo restante do leilão")
    print("  :saldo                 — Exibe seu saldo disponível e bloqueado")
    print("  :itens                 — Lista seus itens comprados")
    print("  :ajuda                 — Exibe esta mensagem")
    print("  :quit                  — Sair do leilão\n")

def main():
    cliente = None
    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect((CONFIG["HOST"], CONFIG["PORTA"]))

        # Recebe mensagens iniciais do servidor até o prompt de nome
        cliente.settimeout(2.0)
        buffer_inicial = ""
        while True:
            try:
                parte = cliente.recv(4096).decode()
                if not parte:
                    break
                buffer_inicial += parte
                if "participar: " in buffer_inicial:
                    break
            except socket.timeout:
                break
        cliente.settimeout(None)

        # Remove o trecho do prompt que o servidor já mandou para não duplicar
        MARCADOR = "Digite seu nome para participar: "
        if MARCADOR in buffer_inicial:
            exibir, _ = buffer_inicial.split(MARCADOR, 1)
        else:
            exibir = buffer_inicial
        print(exibir.strip(), flush=True)

        if "servidor cheio" in buffer_inicial.lower():
            print("O servidor está cheio. Tente novamente mais tarde.")
            encerrado.set()
        else:
            nome = input("\nDigite seu nome para participar: ").strip()
            while not nome:
                print("O nome não pode ser vazio. Tente novamente.")
                nome = input("Digite seu nome para participar: ").strip()
            cliente.send(nome.encode())
            # inicia a thread de escuta ANTES de qualquer input,
            # para não perder mensagens do servidor
            t = threading.Thread(target=thread_escutar, args=(cliente,), daemon=True)
            t.start()
            ajuda()
            while not encerrado.is_set():
                try:
                    comando = input("Sua ação: ").strip()
                except EOFError:
                    break
                if not comando:
                    continue
                if comando == ":ajuda":
                    ajuda()
                    continue
                if comando == ":quit":
                    print("Saindo...")
                    encerrado.set()
                    try:
                        cliente.send(comando.encode())
                    except Exception:
                        pass
                    break
                try:
                    cliente.send(comando.encode())
                except Exception:
                    print("[Cliente] Erro ao enviar o comando.")
                    break
            t.join(timeout=2)
    except ConnectionRefusedError:
        print("\n[ERRO] Não foi possível conectar ao servidor.")
        print("Verifique se o servidor está em execução.")
    except Exception as e:
        print(f"\n[ERRO CRÍTICO] {e}")
    finally:
        if cliente:
            try:
                cliente.close()
            except Exception:
                pass

    input("\nPressione ENTER para fechar a janela...")

if __name__ == "__main__":
    main()