import psycopg2
from flask import Flask, jsonify, request

app = Flask(__name__)

# Configurações de conexão com o Postgres Master (Porta 5432)
DB_CONFIG = {
    "host": "localhost",
    "database": "crack_db",
    "user": "postgres",
    "password": "mestre_senha123",
    "port": "5432"
}

def inicializar_banco_master():
    """Conecta no Master DB para criar a tabela de lotes se não existir."""
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
        conn.commit()
        cursor.close()
        conn.close()
        print("[DATABASE] Tabela 'tarefas' verificada/criada com sucesso no Master DB.")
    except Exception as e:
        print(f"[ERRO DATABASE] Não foi possível inicializar o banco: {e}")

@app.route("/api/iniciar", methods=["POST"])
def iniciar_quebra():
    """Gera os lotes correspondentes às letras do alfabeto no Master DB."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Limpa execuções anteriores
        cursor.execute("TRUNCATE TABLE tarefas;")
        
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
        
        print("[MESTRE] Lotes gerados no Master DB com sucesso!")
        return jsonify({"ok": True, "msg": "Lotes criados no Master DB com sucesso!"}), 201
        
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500

@app.route("/api/atualizar-status", methods=["POST"])
def atualizar_status():
    """Endpoint HTTP (Linha Write do Slave) para atualizar o status da tarefa."""
    data = request.get_json()
    tarefa_id = data.get("id")
    novo_status = data.get("status")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tarefas SET status = %s WHERE id = %s;",
            (novo_status, tarefa_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[MESTRE] Tarefa {tarefa_id} atualizada para: {novo_status}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500

@app.route("/api/sucesso", methods=["POST"])
def sucesso():
    """Sinaliza o término do processamento quando a senha é encontrada."""
    data = request.get_json()
    senha_descoberta = data.get("senha")
    print(f"\n[SUCESSO] Um slave encontrou a senha: {senha_descoberta}!\n")
    return jsonify({"ok": True})

if __name__ == "__main__":
    inicializar_banco_master()
    # Roda o Flask na porta 5000
    app.run(debug=True, host="0.0.0.0", port=5000)