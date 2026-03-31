import socket # socket.socket(cria o socket/rede), connect(conecta ao servidor), send(envia dados), recv(recebe dados), close(fecha a conexão), settimeout(configura tempo de espera para operações de recv)
import threading# threading.Thread(cria threads para escutar mensagens do servidor sem bloquear o programa principal), threading.Event(para criar uma flag de encerramento que pode ser setada por qualquer thread), t.start(inicia a thread), t.join(espera a thread terminar)

# configs
CONFIG = {"HOST": "127.0.0.1", "PORTA": 5000}#bind

# flag ao finalizar as threads
encerrado = threading.Event()

def thread_escutar(cli_socket): #Client socket (ponto final da conexão cliente-servidor) - listen
    while not encerrado.is_set(): #Enquanto a flag não for setada, continua escutando
        try:
            msg = cli_socket.recv(4096).decode() #recebe mensagens do servidor
            if not msg: #se a mensagem for vazia, o servidor fechou a conexão
                print("\n[Cliente] O servidor fechou a conexão.")
                encerrado.set() #levanta a flag para encerrar o cliente
                break
            print(f"\n{msg}")
            if "LEILÃO ENCERRADO" in msg or "Saindo do leilão" in msg or "Servidor cheio" in msg: #se a mensagem indicar que o leilão foi encerrado ou que o cliente está saindo, encerra o cliente
                encerrado.set() #Levanta a flag para encerrar o cliente
                break
        except Exception:
            if not encerrado.is_set():#Se a flag de encerramento ainda não foi setada, significa que a conexão foi perdida inesperadamente
                print("\n[Cliente] Conexão perdida com o servidor.")
            encerrado.set()
            break

def ajuda():#menu de comandos
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
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #Cria um socket TCP/IP (IPv4 - SOCK_STREAM = Protocolo TCP)
        cliente.connect((CONFIG["HOST"], CONFIG["PORTA"]))#Conecta ao servidor usando o endereço e porta definidos em CONFIG (compuatdor envia um sinal SYN para iniciar a conexão TCP)
        cliente.settimeout(2.0)#Configura um timeout de 2 segundos para operações de recv, para evitar bloqueio indefinido caso o servidor não responda ou demore a enviar dados.
        buffer_inicial = "" #str vaziapara acumular a mensagem inicial do servidor, que pode vir em partes
        while True:
            try:
                parte = cliente.recv(4096).decode() #lê até 4096 bytes do socket e decodifica para string.
                if not parte:
                    break #fechar loop se o servidor fechou a conexão
                buffer_inicial += parte #acumula a parte recebida no buffer_inicial
                if "participar: " in buffer_inicial: #esperando o usuario digitar o nome para participar, então o servidor deve ter enviado a mensagem completa quando chegar nessa parte
                    break
            except socket.timeout:
                break
        cliente.settimeout(None) #voltando o tempo de espera para o normal, sem timeout, para as operações seguintes
        MARCADOR = "Digite seu nome para participar: " #armazenando o marcador para separar a mensagem de boas-vindas do prompt de nome, caso o servidor envie ambos juntos
        if MARCADOR in buffer_inicial:#se o marcador estiver presente no buffer_inicial, separa a mensagem de boas-vindas do prompt de nome
            exibir, _ = buffer_inicial.split(MARCADOR, 1)
        else:
            exibir = buffer_inicial # se não tiver o marcador, exibe tudo que chegou (pode ser o caso do servidor enviar mensagens menores ou o prompt de nome separado)
        print(exibir.strip(), flush=True)
        if "servidor cheio" in buffer_inicial.lower(): # se o buffer indicar que o servidor está cheio, não tenta participar e encerra o cliente
            print("O servidor está cheio. Tente novamente mais tarde.")
            encerrado.set()# flag para encerrar o cliente
        else:
            nome = input("\nDigite seu nome para participar: ").strip() #pede para o usuário digitar seu nome para participar do leilão, e remove espaços em branco no início e no final
            while not nome: #garante que o nome não seja vazio, pedindo novamente até que o usuário digite algo válido
                print("O nome não pode ser vazio. Tente novamente.")
                nome = input("Digite seu nome para participar: ").strip()
            cliente.send(nome.encode())#envia o nome digitado para o servidor, codificando a string em bytes antes de enviar
            # inicia a thread de escuta ANTES de qualquer input, para não perder mensagens do servidor
            t = threading.Thread(target=thread_escutar, args=(cliente,), daemon=True) #Nascimento da thread de escuta, com as configurações de host e porta definidas em CONFIG, e passando o socket do cliente como argumento para a função thread_escutar. A thread é marcada como daemon para que ela seja encerrada automaticamente quando a thread principal terminar.
            t.start()#inciando
            ajuda()#menu
            while not encerrado.is_set():
                try:
                    comando = input("Sua ação: ").strip() #o programa espera o usuário digitar um comando, e remove espaços em branco no início e no final da string digitada
                except EOFError:
                    break
                if not comando: #se nao for digitado nada (string vazia), o loop continua pedindo um comando válido, sem enviar nada para o servidor
                    continue
                if comando == ":ajuda": #se o comando digitado for ":ajuda", exibe o menu de comandos novamente, sem enviar nada para o servidor
                    ajuda()
                    continue
                if comando == ":quit":#comando de sair
                    print("Saindo...")
                    encerrado.set()#levanta a flag para encerrar o cliente e sair do loop
                    try:
                        cliente.send(comando.encode())#manda o quit em bits para o servidor
                    except Exception:
                        pass
                    break
                try:
                    cliente.send(comando.encode())#manda o comando em bits para o servidor
                except Exception:
                    print("[Cliente] Erro ao enviar o comando.")
                    break
            t.join(timeout=2)#espera a thread de escuta terminar, com um timeout de 2 segundos para evitar bloqueio indefinido caso a thread esteja travada esperando por uma mensagem do servidor
    except ConnectionRefusedError: #rodar sem estar conectado ao servidor, ou se o servidor não estiver em execução, vai cair aqui
        print("\n[ERRO] Não foi possível conectar ao servidor.")
        print("Verifique se o servidor está em execução.")
    except Exception as e:
        print(f"\n[ERRO CRÍTICO] {e}")
    finally: #vai executar sim!
        if cliente:
            try:
                cliente.close()#fecha o socket do cliente (ip e porta) para liberar recursos e encerrar a conexão com o servidor
            except Exception:
                pass

    input("\nPressione ENTER para fechar a janela...")

if __name__ == "__main__": #ponto de entrada do programa, verifica se o script está sendo executado diretamente (em vez de importado como módulo) e chama a função
    main()