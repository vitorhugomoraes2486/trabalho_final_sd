import time
import psycopg2
from flask import Flask, jsonify, request

app = Flask(__name__)

# Configurações de conexão com o Postgres Master (Porta 5432).

DB_CONFIG = {
    "host": "postgres-master",
    "database": "crack_db",
    "user": "postgres",
    "password": "mestre_senha123",
    "port": "5432"
}

def inicializar_banco_master():
    """Conecta no Master DB para criar a tabela de lotes se não existir.
    Tenta repetidamente até o postgres-master estar pronto — necessário porque
    o container mestre-app pode subir antes do banco aceitar conexões."""
    while True:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tarefas (
                    id SERIAL PRIMARY KEY,
                    letra_inicial CHAR(1) NOT NULL,
                    status VARCHAR(20) NOT NULL
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    chave VARCHAR(50) PRIMARY KEY,
                    valor VARCHAR(255) NOT NULL
                );
            ''')
            conn.commit()
            cursor.close()
            conn.close()
            print("[DATABASE] Tabela 'tarefas' verificada/criada com sucesso no Master DB.")
            break
        except Exception as e:
            print(f"[DATABASE] Banco ainda não disponível, tentando novamente em 3s... ({e})")
            time.sleep(3)

@app.route("/api/iniciar", methods=["POST"])
def iniciar_quebra():
    """Recebe o hash do Cliente, grava na config e gera os lotes correspondentes às letras do alfabeto no Master DB."""
    data = request.get_json(silent=True) or {}
    hash_alvo = data.get("hash")

    if not hash_alvo:
        return jsonify({"ok": False, "erro": "Campo 'hash' não informado pelo Cliente."}), 400

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Limpa execuções anteriores (RESTART IDENTITY reseta o contador de IDs para 1)
        cursor.execute("TRUNCATE TABLE tarefas RESTART IDENTITY;")

        # Centraliza o hash alvo da execução atual (upsert na tabela config)
        cursor.execute(
            """
            INSERT INTO config (chave, valor) VALUES ('hash_alvo', %s)
            ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor;
            """,
            (hash_alvo,)
        )

        # Reseta a flag de término distribuído
        cursor.execute(
            """
            INSERT INTO config (chave, valor) VALUES ('status_execucao', 'em_andamento')
            ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor;
            """
        )

        # Insere um lote para cada letra do alfabeto (a-z)
        alfabeto = "abcdefghijklmnopqrstuvwxyz"
        for letra in alfabeto:
            cursor.execute(
                "INSERT INTO tarefas (letra_inicial, status) VALUES (%s, 'disponivel');",
                (letra,)
            )

        conn.commit()
        cursor.close()
        conn.close()

        print(f"[MESTRE] Hash alvo '{hash_alvo}' registrado e lotes gerados no Master DB com sucesso!")
        return jsonify({"ok": True, "msg": "Hash registrado e lotes criados no Master DB com sucesso!"}), 201

    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500

@app.route("/api/atualizar-status", methods=["POST"])
def atualizar_status():
    """Endpoint HTTP para atualizar o status da tarefa.
    Quando o novo status é 'processando', o UPDATE só é aplicado se o lote
    ainda estiver 'disponivel' — isso impede race condition entre Workers."""
    data = request.get_json()
    tarefa_id = data.get("id")
    novo_status = data.get("status")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        if novo_status == "processando":
            cursor.execute(
                "UPDATE tarefas SET status = %s WHERE id = %s AND status = 'disponivel';",
                (novo_status, tarefa_id)
            )
        else:
            cursor.execute(
                "UPDATE tarefas SET status = %s WHERE id = %s;",
                (novo_status, tarefa_id)
            )

        linhas_afetadas = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()

        reserva_valida = linhas_afetadas > 0

        if reserva_valida:
            print(f"[MESTRE] Tarefa {tarefa_id} atualizada para: {novo_status}")
        else:
            print(f"[MESTRE] Tarefa {tarefa_id} já estava reservada por outro Slave. Pedido rejeitado.")

        return jsonify({"ok": reserva_valida})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500

@app.route("/api/hash-atual", methods=["GET"])
def hash_atual():
    """Permite que os Slaves consultem qual é o hash alvo da execução em curso."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM config WHERE chave = 'hash_alvo';")
        linha = cursor.fetchone()
        cursor.close()
        conn.close()

        if not linha:
            return jsonify({"ok": False, "erro": "Nenhum hash alvo definido ainda."}), 404

        return jsonify({"ok": True, "hash": linha[0]})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500

@app.route("/api/status-execucao", methods=["GET"])
def status_execucao():
    """Permite que os Workers consultem se a execução atual já terminou."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM config WHERE chave = 'status_execucao';")
        linha = cursor.fetchone()
        cursor.close()
        conn.close()

        status = linha[0] if linha else "em_andamento"
        return jsonify({"ok": True, "status": status})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500

@app.route("/api/resultado", methods=["GET"])
def resultado():
    """Permite que o Cliente consulte o resultado final."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT chave, valor FROM config WHERE chave IN ('status_execucao', 'senha_encontrada');"
        )
        linhas = dict(cursor.fetchall())
        cursor.close()
        conn.close()

        status = linhas.get("status_execucao", "em_andamento")
        senha = linhas.get("senha_encontrada")

        return jsonify({"ok": True, "status": status, "senha": senha})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500

@app.route("/api/sucesso", methods=["POST"])
def sucesso():
    """Sinaliza o término do processamento quando a senha é encontrada."""
    data = request.get_json()
    senha_descoberta = data.get("senha")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO config (chave, valor) VALUES ('status_execucao', 'finalizado')
            ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor;
            """
        )
        cursor.execute(
            """
            INSERT INTO config (chave, valor) VALUES ('senha_encontrada', %s)
            ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor;
            """,
            (senha_descoberta,)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[ERRO] Não foi possível marcar status_execucao como finalizado: {e}")

    print(f"\n[SUCESSO] Um slave encontrou a senha: {senha_descoberta}!\n")
    return jsonify({"ok": True})

if __name__ == "__main__":
    inicializar_banco_master()
    app.run(debug=True, host="0.0.0.0", port=5000)