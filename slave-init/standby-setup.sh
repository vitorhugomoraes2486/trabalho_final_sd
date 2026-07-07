#!/bin/bash
# Entrypoint customizado do container postgres-slave
# Configura o Slave DB como replica fisica do Master DB
# usando Streaming Replication nativa do PostgreSQL.
#
# 1a vez (volume vazio):
#   - Clona o Master via pg_basebackup;
#   - Flag -R cria standby.signal + primary_conninfo automaticamente;
#   - Slave passa a receber atualizacoes via logs WAL.
#
# Execucoes seguintes (volume populado):
#   - Sobe normalmente e retoma a replicacao existente.
set -e

PGDATA_DIR="/var/lib/postgresql/data"

if [ -z "$(ls -A "$PGDATA_DIR" 2>/dev/null)" ]; then
    echo "[SLAVE-INIT] Volume vazio. Clonando dados do Master..."

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
