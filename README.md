# Password_Cracker


O projeto final de Sistemas Distribuídos, tem como objetivo a implementação de características que apresentarão uma possibilidade de escalamento horiontal do projeto, unido a transparência de localização dos nós.


1. Descrição Geral do Projeto.
   
     O trabalho é um sistema distribuído de computação paralela intensiva baseado na arquitetura Mestre/Escravo (Master/Slave), projetado para realizar a quebra de senhas criptografadas em hashes MD5 por meio de força bruta;
  
     O objetivo principal do sistema é demonstrar  a eficiência na divisão de carga ao fatiar um problema complexo em múltiplos lotes independentes compartilhados na rede. O sistema adota Replicação de Banco de Dados para otimizar o fluxo de dados e mitigar gargalos de concorrência.


2. Descrição da Arquitetura

O sistema é dividido em quatro componentes principais:

* **Cliente (`cliente.py`):** Interface utilizada pelo usuário final. Sua única função é enviar o hash alvo para o servidor Mestre e monitorar o progresso até a conclusão.
* **Servidor Mestre (`mestre.py`):** O cérebro coordenador do sistema (desenvolvido em Flask). Ele não realiza força bruta; suas funções são receber requisições HTTP, gerar a fila de tarefas no banco de dados, gerenciar as atualizações de estado e centralizar a notificação de término.
* **Nós Escravos (`worker.py`):** Scripts autônomos que contêm a lógica pesada de força bruta. Eles geram combinações de strings, computam hashes via `hashlib` na CPU e consomem a fila de tarefas de forma assíncrona.
* **Camada de Dados Replicada (PostgreSQL via Docker):**
    * **Master DB (Porta 5432):** Banco de escrita exclusiva, que armazena a tabela central de tarefas e as configurações globais.
    * **Slave DB (Porta 5433):** Banco de leitura exclusiva, que recebe os dados espelhados do Master via Streaming Replication (logs de WAL) e é consultado em massa pelos Workers.


3. Interface e Endpoints (API do Mestre)

O Servidor Coordenador (Mestre) expõe uma interface de comunicação via API HTTP/JSON para interagir com o Cliente e com os Workers:

| Endpoint | Método | Quem Usa | Descrição |
| :--- | :--- | :--- | :--- |
| `/api/iniciar` | `POST` | Cliente | Recebe o hash alvo, limpa o histórico e gera os 26 lotes no Master DB. |
| `/api/atualizar-status`| `POST` | Worker | Solicita a reserva de um lote (muda para `processando` apenas se o status atual for `disponivel`, evitando condições de corrida).|
| `/api/hash-atual` | `GET` | Worker | Retorna o hash MD5 ativo que está sendo quebrado na execução atual. |
| `/api/status-execucao` | `GET` | Worker | Verifica se a senha já foi encontrada por algum outro nó na rede (mecanismo de terminação distribuída). |
| `/api/resultado` | `GET` | Cliente | Retorna o status atual da execução e a senha encontrada, se finalizado. |
| `/api/sucesso` | `POST` | Worker | Informa ao Mestre que a senha foi descriptografada com sucesso, encerrando o fluxo global. |

4. Fluxos Principais do Sistema

   4.1 **Inicialização e DNS:** O Cliente faz uma resolução de nomes via DNS local para localizar o endereço lógico `mestre-crack.local` e envia o hash de destino.
   
   4.2 **Carga e Replicação Física:** O Mestre recebe o hash e insere 26 tarefas (uma para cada letra inicial do alfabeto de 'a' a 'z') com o status de `disponivel` no Master DB. O mecanismo interno do PostgreSQL replica instantaneamente essas linhas para o Slave DB.
   
   4.3 **Consumo Assíncrono (Read):** Os Workers consultam continuamente o Slave DB (Porta 5433) em busca de lotes livres.
   
   4.4 **Reserva Segura (Write):** Ao escolher um lote, o Worker envia um `POST` ao Mestre. O Mestre aplica o `UPDATE` no Master DB apenas se a linha ainda estiver livre, propagando a trava pela replicação e impedindo concorrência.
   
   4.5 **Término Distribuído:** O Worker executa a força bruta localmente. Se encontrar o resultado, notifica o endpoint `/api/sucesso`. Os demais nós percebem a mudança de estado global nas suas checagens periódicas e abortam a execução.


5. Características de Sistemas Distribuídos Implementadas

* **Transparência de Localização:** O Cliente e os Workers interagem com a rede utilizando apenas o nome abstrato `http://mestre-crack.local:5000`. A topologia física é oculta: o processamento e o banco de dados podem ser movidos de máquina na rede sem necessidade de alterar uma única linha de código nos programas.
* **Escalabilidade Horizontal:** A arquitetura adota um modelo descentralizado. Como o Mestre e o Slave DB não controlam ativamente a quantidade de nós, o sistema é elástico: novos terminais rodando o script do `worker.py` podem ser iniciados e acoplados ao processamento em tempo de execução para dividir a carga e acelerar a busca.

6. Tecnologias Utilizadas

* **Linguagem:** Python 3;
* **Framework Web:** Flask (Servidor Coordenador);
* **Driver de Banco de Dados:** Psycopg2;
* **Banco de Dados:** PostgreSQL 15 (Configurado para Streaming Replication);
* **Conteinerização:** Docker & Docker Compose.


## 7. Como Executar o Projeto

### Pré-requisitos
* Docker e Docker Compose instalados.
* Python 3 instalado com as bibliotecas `requests` e `psycopg2-binary`.

### Passo 1: Subir os Bancos Replicados (Docker)
Na raiz do projeto, limpe os volumes antigos e inicie os containers:
```bash
docker compose down -v
docker compose up -d
```

### Passo 2: Configurar o DNS Local (Windows)
Para habilitar o uso do endereço lógico mestre-crack.local nativamente, execute o seu editor de texto como Administrador e abra o arquivo: C:\Windows\System32\drivers\etc\hosts. Adicione na linha abaixo ao final do arquivo e salve:
```bash
127.0.0.1       mestre-crack.local
```

### Passo 3: Iniciar o Servidor Mestre
```bash
python mestre.py
```

### Passo 4: Iniciar o Cliente e Enviar o Hash
```bash
python cliente.py
```
Insira o hash MD5 de teste.

### Passo 5: Iniciar um ou mais Workers
Abra um ou múltiplos terminais em paralelo e execute o worker para ver a divisão de carga em tempo real:
```bash
python worker.py
```


<img width="532" height="664" alt="Arquitetura_password_cracker drawio" src="https://github.com/user-attachments/assets/e3957144-4ff3-4793-9147-24e0226446b8" />



