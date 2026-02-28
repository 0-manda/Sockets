# Trabalho Sockets

## Fase 1: Inicialmente, os alunos deverão implementar para um usuário remoto
somente.
Detalhamentos para os temas
### 1. Leilão Online
O sistema de leilão implementará uma aplicação onde o servidor gerencia a venda de um item e o usuário
pode enviar lances em tempo real.
O usuário, através do cliente da aplicação, iniciará a conexão ao servidor e receberá, de imediato, uma
mensagem no formato “<HORARIO>: CONECTADO!!” e as informações do item sendo leiloado (nome e
lance inicial – Inicialmente, um único ítem).
Duas threads serão criadas no servidor e no cliente para manipulação da conexão:
*No Cliente: A Thread 1 aguardará o usuário digitar comandos ou valores. Se o usuário digitar
apenas um número, será tratado como um lance. Comandos específicos devem começar com ":".
A Thread 2 ficará em loop recebendo do socket e imprimindo na tela as atualizações do leilão
enviadas pelo servidor.
* No Servidor: A Thread 1 receberá os lances, validará se o valor é maior que o atual na memória
compartilhada e armazenará o novo recorde. A Thread 2 funcionará como um cronômetro
regressivo (ex: 60 segundos). A cada lance novo, o tempo pode ser resetado ou apenas monitorado.
Ao final do tempo, a Thread 2 envia a mensagem de "Item Vendido" para o cliente com o valor final.
#### Comandos mínimos:
* :item (Exibe descrição do item e lance atual)
* :tempo (Consulta quanto tempo resta para o fim do leilão)
* VALOR (Aposta de um novo lance)
* :quit (Sair da aplicação)
Simulação de outros usuários: é interessante que seja desenvolvida uma rotina que simule outros
usuários, que, de forma aleatória, gere lances ligeiramente próximos ao último lance válido, acima ou
abaixo dele. Quando houver esta interação, o usuário conectado deverá receber a atualização em real time
em seu client para poder optar por enviar novo lance. Esta implementação será necessária para simular um
ambiente com múltiplos usuários.
