# Password_Cracker


O projeto final de Sistemas Distribuídos, tem como objetivo a implementação de características que apresentarão uma possibilidade de escalamento horiontal do projeto, unido a transparência de localização dos nós.


1. Descrição Geral do Projeto.
   
     O trabalho é um sistema distribuído de computação paralela intensiva baseado na arquitetura Mestre/Escravo (Master/Slave), projetado para realizar a quebra de senhas criptografadas em hashes MD5 por meio de força bruta;
  
     O objetivo principal do sistema é demonstrar  a eficiência na divisão de carga ao fatiar um problema complexo em múltiplos lotes independentes compartilhados na rede. O sistema adota Replicação de Banco de Dados para otimizar o fluxo de dados e mitigar gargalos de concorrência.


2. Componentes do Sistema.
   
     O ecossistema é dividido em quatro componentes principais com responsabilidades totalmente isoladas.
  
     2.1 Cliente: É a interface (via script ou página web) utilizada pelo usuário final. Sua única função é enviar o hash alvo para o servidor Mestre e, opcionalmente, monitorar o progresso do sistema;
   
     2.2 Servidor Mestre (Master): Desenvolvido em Python com o micro-framework Flask. Ele atua como o cérebro coordenador do sistema. Não realiza processamento de força bruta; suas funções são receber requisições HTTP, gerar a fila de lotes iniciais no banco de dados, gerenciar as atualizações de estado e centralizar a notificação de término;
   
     2.3 Nós Escravos (Slaves/Workers): Scripts Python independentes executados em paralelo (podendo rodar na mesma máquina ou em múltiplos computadores na rede). Eles contêm a lógica pesada de força bruta (geração de strings e computação de hashes com hashlib) e consomem a fila de tarefas de forma autônoma;
   
     2.4 Camada de Dados Replicada: Dois containers PostgreSQL isolados rodando via Docker.
        Master DB: Banco de escrita exclusiva. Armazena a tabela central de tarefas e recebe atualizações de status;
        Slave DB: Banco de leitura exclusiva. Recebe os dados espelhados do Master e é consultado em massa pelos Slaves.


3. Comunicação Inter-Componentes.
   
     3.1 Inicialização: O Cliente faz uma resolução de nomes via DNS para localizar o endereço lógico "mestre-crack.local" sem precisar conhecer o IP físico do servidor. Ele envia uma requisição contendo o hash;
  
     3.2 Carga e Replicação: O Mestre recebe o hash, limpa o histórico e insere 26 lotes (um para cada letra inicial do alfabeto) com o status de "disponivel" diretamente no Master DB. O mecanismo do Docker realiza a replicação, espelhando instantaneamente esses lotes para o Slave DB;
  
     3.3 Consumo Assíncrono (Read): Os Slaves realizam consultas SQL diretamente no Slave DB para identificar quais lotes estão disponíveis;
  
     3.4 Reserva de Lote (Write): Ao escolher um lote disponível, o Slave faz um desvio na arquitetura e envia uma requisição POST HTTP para o Mestre, solicitando a alteração do status para "processando". O Mestre atualiza no Master DB o status e replica a mudança para o Slave DB, impedindo que outro escravo tente computar a mesma letra;
  
     3.5 Término Distribuído: O Slave processa a força bruta localmente na sua CPU. Se encontrar a senha, ele envia um "sucesso" para o Mestre, que encerra o ecossistema e exibe o resultado.


4. Características de Sistemas Distribuídos Utilizadas.

     4.1 Transparência de Localização: Quando o Cliente envia o hash via requisição HTTP, ele perde o rastro de como o problema será resolvido. Ele não sabe se o Lote 'A' está sendo computado por um script na máquina do da pessoa ao lado, se o Lote 'B' está rodando em uma máquina virtual, ou se os dados estão guardados em um container isolado do Docker;

     4.2 Escalabilidade Horizontal: Como o Mestre não precisa conhecer previamente a identidade ou a quantidade de escravos na rede, pode-se iniciar o processamento com apenas 1 Slave e, no meio da execução, abrir mais terminais rodando o código do slave.
    


<img width="532" height="664" alt="Arquitetura_password_cracker drawio" src="https://github.com/user-attachments/assets/e3957144-4ff3-4793-9147-24e0226446b8" />

5. Descrição da Arquitetura

O sistema é dividido em quatro componentes principais:

   5.1 Cliente (`cliente.py`):** Interface utilizada pelo usuário final. Sua única função é enviar o hash alvo para o servidor Mestre e monitorar o progresso até a conclusão.
* **Servidor Mestre (`mestre.py`):** O cérebro coordenador do sistema (desenvolvido em Flask). Ele não realiza força bruta; suas funções são receber requisições HTTP, gerar a fila de tarefas no banco de dados, gerenciar as atualizações de estado e centralizar a notificação de término.
* **Nós Escravos (`worker.py`):** Scripts autônomos que contêm a lógica pesada de força bruta. Eles geram combinações de strings, computam hashes via `hashlib` na CPU e consomem a fila de tarefas de forma assíncrona.
* **Camada de Dados Replicada (PostgreSQL via Docker):**
    * **Master DB (Porta 5432):** Banco de escrita exclusiva, que armazena a tabela central de tarefas e as configurações globais.
    * **Slave DB (Porta 5433):** Banco de leitura exclusiva, que recebe os dados espelhados do Master via Streaming Replication (logs de WAL) e é consultado em massa pelos Workers.

