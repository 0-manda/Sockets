import socket
import threading

#configs
CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000}

#flag ao finalizar as threads
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
            # encerra o cliente ao fim do leilão
            if "LEILÃO ENCERRADO" in msg or "Saindo do leilão" in msg or "Servidor cheio" in msg:
                encerrado.set()
                break
            # do loop principal, embaralhando o terminal
        except Exception:
            if not encerrado.is_set():
                print("\n[Cliente] Conexão perdida com o servidor.")
            encerrado.set()
            break

#thread 1 (leitura de comandos)
def ajuda():
    print("\nComandos disponíveis:\n")
    print(":Lance <item> <valor>  — Dar um lance (ex: :Lance Quadro Monalisa 1200)\n")
    print(":Vender <item> — Vender item por 90% do valor (ex: :Vender Quadro Monalisa)\n")
    print(":item — Info do item em leilão\n")
    print(":tempo — Exibe o tempo restante do leilão\n")
    print(":saldo — Exibe seu saldo disponível e bloqueado\n")
    print(":itens — Lista seus itens comprados\n")
    print(":ajuda — Exibe esta mensagem\n")
    print(":quit — Sair do leilão\n")

def main ():
    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect((CONFIG["HOST"], CONFIG["PORTA"]))
        #recebendo dados
        dados_iniciais = cliente.recv(4096).decode()
        print(dados_iniciais)
        if "servidor cheio" in dados_iniciais.lower():
            print("O servidor está cheio. Tente novamente mais tarde.")
            # usa encerrado.set() e pula o restante com else
            encerrado.set()
        else:
            nome = input("Digite seu nome: ").strip()
            while not nome:
                print("O nome não pode ser vazio. Tente novamente.")
                nome = input("Digite seu nome: ").strip()
            cliente.send(nome.encode())
            resposta = cliente.recv(4096).decode()
            print(resposta)
            # inicia a escuta
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
    except ConnectionRefusedError:
        print("\n[ERRO] Não foi possível conectar ao servidor.")
        print("Verifique se o servidor está em execução.")
    except Exception as e:
        print(f"\n[ERRO CRÍTICO] {e}")
    finally:
        cliente.close()
    input("\nPressione ENTER para fechar a janela...")

if __name__ == "__main__":
    main()