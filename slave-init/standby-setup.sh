# =============================================================================
# standby-setup.sh — Entrypoint customizado do container postgres-slave
#
# Responsabilidade: configurar o Slave DB como uma réplica física (hot standby)
# do Master DB, usando Streaming Replication nativa do PostgreSQL.
#
# Fluxo de execução:
#   1ª vez (volume vazio):
#     - Aguarda o Master ficar disponível na rede
#     - Clona fisicamente o Master via pg_basebackup
#     - A flag -R cria automaticamente o standby.signal e o primary_conninfo,
#       colocando o Postgres em modo réplica ao subir
#     - A partir daí, o Slave recebe atualizações contínuas via logs WAL
#
#   Execuções seguintes (volume já populado):
#     - Pula a clonagem e sobe normalmente
#     - O Postgres retoma a replicação de onde parou automaticamente
# =============================================================================
set -e

PGDATA_DIR="/var/lib/postgresql/data"

if [ -z "$(ls -A "$PGDATA_DIR" 2>/dev/null)" ]; then
    echo "[SLAVE-INIT] Volume vazio. Clonando dados do Master..."

    # Arquivo de senha para autenticacao automatica (sem expor a senha no conninfo).
    # IMPORTANTE: precisa ficar na home do usuario "postgres" (/var/lib/postgresql),
    # pois é esse usuario que o processo do Postgres assume em runtime -- e é ele
    # quem precisa dessa senha para manter a conexao de streaming replication aberta
    # continuamente com o Master, nao so durante o pg_basebackup inicial.
    echo "postgres-master:5432:*:replicator:replica_senha123" > /var/lib/postgresql/.pgpass
    chmod 0600 /var/lib/postgresql/.pgpass
    chown postgres:postgres /var/lib/postgresql/.pgpass
    export PGPASSFILE=/var/lib/postgresql/.pgpass

    until pg_basebackup -h postgres-master -p 5432 -D "$PGDATA_DIR" -U replicator -Fp -Xs -P -R; do
        echo "[SLAVE-INIT] Master ainda nao disponivel, tentando novamente em 3s..."
        sleep 3
    done

    chmod 0700 "$PGDATA_DIR"
    chown -R postgres:postgres "$PGDATA_DIR"
    echo "[SLAVE-INIT] Clonagem concluida. standby.signal criado, entrando em modo replica."
else
    echo "[SLAVE-INIT] Volume ja populado, retomando replicacao existente."
fi

exec docker-entrypoint.sh postgres
