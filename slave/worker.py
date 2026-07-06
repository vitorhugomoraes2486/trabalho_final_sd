import hashlib
import itertools
import time
import sys
import psycopg2
import requests

# URL do servidor coordenador Mestre (Flask) para requisições de controle
MESTRE_URL = "http://localhost:5000"

# Configuração de conexão focada estritamente no SLAVE DB (Leitura - Porta 5433)
DB_SLAVE_CONFIG = {
    "host": "localhost",
    "database": "crack_db",
    "user": "postgres",
    "password": "mestre_senha123",
    "port": "5433"
}

# O hash alvo NÃO fica mais fixo aqui. Ele é buscado do Mestre em tempo de
# execução (rota /api/hash-atual), garantindo que todos os Slaves usem o
# mesmo hash que o Cliente enviou na última chamada a /api/iniciar.
HASH_ALVO = None

def buscar_hash_alvo():
    """Consulta o Mestre para descobrir qual é o hash alvo da execução atual."""
    try:
        response = requests.get(f"{MESTRE_URL}/api/hash-atual")
        if response.status_code == 200 and response.json().get("ok"):
            return response.json().get("hash")
    except Exception as e:
        print(f"[ERRO] Não foi possível obter o hash alvo do Mestre: {e}")
    return None

def execucao_finalizada():
    """Consulta o Mestre para saber se algum outro Worker já encontrou a senha.
    É essa checagem que permite a terminação distribuída: como nenhum Worker
    tem visão direta dos outros, todos confiam nessa flag central no Mestre."""
    try:
        response = requests.get(f"{MESTRE_URL}/api/status-execucao")
        if response.status_code == 200 and response.json().get("ok"):
            return response.json().get("status") == "finalizado"
    except Exception as e:
        print(f"[ERRO] Não foi possível consultar o status de execução no Mestre: {e}")
    return False

def buscar_lote_disponivel():
    """Consulta o banco de réplica (5433) para encontrar uma tarefa livre."""
    try:
        conn = psycopg2.connect(**DB_SLAVE_CONFIG)
        cursor = conn.cursor()
        
        # Busca apenas uma tarefa que esteja com o status 'disponivel'
        cursor.execute("SELECT id, letra_inicial FROM tarefas WHERE status = 'disponivel' LIMIT 1;")
        tarefa = cursor.fetchone()
        
        cursor.close()
        conn.close()
        return tarefa  # Retorna (id, letra_inicial) ou None se a fila estiver vazia
    except Exception as e:
        print(f"[ERRO SLAVE-READ] Falha ao ler do Slave DB: {e}")
        return None

def reservar_lote(tarefa_id):
    """Envia um POST HTTP para o Mestre (5000) solicitando travar o lote."""
    try:
        url = f"{MESTRE_URL}/api/atualizar-status"
        payload = {"id": tarefa_id, "status": "processando"}
        response = requests.post(url, json=payload)
        
        if response.status_code == 200 and response.json().get("ok"):
            return True
    except Exception as e:
        print(f"[ERRO SLAVE-WRITE] Não conseguiu contactar o Mestre para reservar: {e}")
    return False

def marcar_lote_concluido(tarefa_id):
    """Informa ao mestre que o lote inteiro foi varrido e a senha não estava nele."""
    try:
        url = f"{MESTRE_URL}/api/atualizar-status"
        payload = {"id": tarefa_id, "status": "concluido"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[ERRO] Falha ao marcar lote como concluído: {e}")

# Tamanho máximo de senha (em letras minúsculas) que cada lote tenta quebrar.
# Com 5 letras e alfabeto de 26 caracteres, o espaço de busca total é de
# ~12 milhões de combinações por lote (26^4), resolvido em segundos por Worker.
TAMANHO_MAXIMO_SENHA = 5

# A cada quantas tentativas o Worker verifica no Mestre se outro nó já
# encontrou a senha. Com lotes menores (até 5 letras), 10.000 é suficiente
# para responder rápido sem sobrecarregar o Mestre com requisições HTTP.
INTERVALO_VERIFICACAO_TERMINO = 10_000

# Sinal usado para diferenciar "não encontrou nada no lote" de
# "abortou o lote porque outro nó já tinha terminado"
ABORTADO_POR_TERMINO_GLOBAL = object()

def quebrar_forca_bruta(letra_inicial):
    """Gera combinações locais de strings na CPU, todas começando com a letra
    do lote, testando primeiro os tamanhos menores (mais rápido de encontrar
    senhas curtas) e aumentando progressivamente até TAMANHO_MAXIMO_SENHA.
    Periodicamente verifica se outro nó já terminou a execução, para não
    ficar "preso" processando um lote longo sem necessidade."""
    print(f"[PROCESSANDO] Iniciando busca exaustiva para o lote da letra: '{letra_inicial.upper()}'...")

    alfabeto = "abcdefghijklmnopqrstuvwxyz"
    contador = 0

    # Testa primeiro o caso de a senha ser só a própria letra inicial (tamanho 1)
    if hashlib.md5(letra_inicial.encode('utf-8')).hexdigest() == HASH_ALVO:
        return letra_inicial

    # Para os demais tamanhos (2 a TAMANHO_MAXIMO_SENHA), gera o restante da
    # palavra com itertools.product, que é mais eficiente que loops aninhados
    # manuais para um número variável de posições.
    for tamanho in range(2, TAMANHO_MAXIMO_SENHA + 1):
        for sufixo in itertools.product(alfabeto, repeat=tamanho - 1):
            palavra_teste = letra_inicial + "".join(sufixo)
            hash_calculado = hashlib.md5(palavra_teste.encode('utf-8')).hexdigest()

            if hash_calculado == HASH_ALVO:
                return palavra_teste  # Encontrou a senha!

            contador += 1
            if contador % INTERVALO_VERIFICACAO_TERMINO == 0:
                if execucao_finalizada():
                    return ABORTADO_POR_TERMINO_GLOBAL

    return None

def iniciar_worker():
    global HASH_ALVO
    print("[WORKER] Nó de processamento distribuído inicializado com sucesso.")

    # Antes de começar a processar, busca o hash alvo registrado pelo Mestre.
    # Se o Cliente ainda não tiver chamado /api/iniciar, aguarda até existir.
    while not HASH_ALVO:
        HASH_ALVO = buscar_hash_alvo()
        if not HASH_ALVO:
            print("[WORKER] Nenhum hash alvo definido pelo Mestre ainda. Aguardando 5 segundos...")
            time.sleep(5)

    print(f"[WORKER] Hash alvo recebido do Mestre: {HASH_ALVO}")
    
    while True:
        # 0. Antes de tentar pegar um novo lote, verifica se outro Worker já
        #    encontrou a senha. Se sim, este nó se desliga (terminação distribuída).
        if execucao_finalizada():
            print("[WORKER] Outro nó já encontrou a senha. Encerrando este Worker.")
            sys.exit(0)

        # 1. Tenta buscar uma tarefa diretamente na réplica de leitura
        tarefa = buscar_lote_disponivel()
        
        if not tarefa:
            print("[WORKER] Nenhuma tarefa disponível na fila. Aguardando 5 segundos...")
            time.sleep(5)
            continue
            
        tarefa_id, letra_inicial = tarefa
        
        # 2. Tenta fazer a reserva enviando a requisição para o Mestre Flask
        if reservar_lote(tarefa_id):
            print(f"[LOTE CAPTURADO] ID: {tarefa_id} | Letra Inicial: '{letra_inicial}'")
            
            # 3. Executa a computação exaustiva localmente
            resultado = quebrar_forca_bruta(letra_inicial)

            if resultado is ABORTADO_POR_TERMINO_GLOBAL:
                # Outro nó já encontrou a senha enquanto este lote era processado.
                # Não marca o lote como concluído (ele continua incompleto), só se desliga.
                print("[WORKER] Outro nó já encontrou a senha durante o processamento deste lote. Encerrando.")
                sys.exit(0)
            elif resultado:
                print(f"\n[💥 SUCESSO 💥] SENHA ENCONTRADA: {resultado}\n")
                # Notifica o mestre do término global do algoritmo
                requests.post(f"{MESTRE_URL}/api/sucesso", json={"senha": resultado})
                sys.exit(0)
            else:
                # Terminou a busca no lote e não achou? Atualiza para concluído
                marcar_lote_concluido(tarefa_id)
        else:
            # Caso outro Worker tenha sido milisegundos mais rápido e reservado o lote antes,
            # o Mestre vai rejeitar o nosso pedido. O nó apenas avança para o próximo.
            print(f"[CONCORRÊNCIA] O lote {tarefa_id} já foi pego por outro nó. Tentando o próximo...")
            time.sleep(1)

if __name__ == "__main__":
    iniciar_worker()