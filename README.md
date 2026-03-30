O sistema simula um leilão em tempo real onde múltiplos clientes podem se conectar a um servidor central para disputar um item. Segue uma breve descrição da implementação:

-Concorrência: O servidor usa threading para lidar com vários clientes simultaneamente e um cronômetro regressivo.
-Persistência: Os dados dos usuários (saldo e itens comprados) são salvos em um arquivo usuarios.json, permitindo que o progresso seja mantido entre sessões.
-Mecanismo de Lances: Ao dar um lance, o valor é "bloqueado" do saldo do usuário. Se alguém superar o lance, o valor é devolvido.
-Bots Inteligentes: O servidor possui bots (Carlos, Beatriz, etc.) que entram na disputa automaticamente, aumentando a interatividade.
-Sincronização: Uso de Locks para evitar que dois usuários comprem o mesmo item ou corrompam o saldo ao mesmo tempo.


Modo de uso:
Para rodar o projeto, você precisará de um terminal para o Servidor e um (ou mais) terminais para os Clientes.
O servidor precisa de 3 argumentos para começar: o limite de pessoas, o nome do item e o valor inicial: py server.py 3 Monalisa 1500
Conectando como ClienteEm outro terminal (ou outro computador na mesma rede): py client.py
O sistema pedirá seu nome. Se você já jogou antes, seu saldo antigo será carregado.


Comandos Disponíveis:
- :Lance <item> <valor> -> Oferece um valor pelo item.
- :item -> Mostra detalhes do item e quem está vencendo.
- :saldo -> Verifica seu dinheiro disponível e o que está preso em lances.
- :tempo -> Mostra quantos segundos faltam para acabar.
- :itensLista -> todos os itens que você já arrematou.
- :Vender <item> -> Vende um item seu de volta para a banca (por 90% do valor).
- :ajuda -> Mostra a lista de comandos.
- :quit -> Sai do leilão com segurança.


Regras do Jogo: Sempre que um novo lance é aceito, o cronômetro reseta dando chance para outros reagirem.

Vitória: Quando o tempo chega a zero, o maior lance vence, o valor é descontado definitivamente e o item vai para o inventário do vencedor.

Bots: Fique atento! Os bots dão lances aleatórios entre 1% e 8% acima do valor atual. Eles têm um limite de R$ 5.000,00 de saldo.
