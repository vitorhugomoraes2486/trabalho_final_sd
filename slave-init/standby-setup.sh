#!/bin/bash
# Entrypoint customizado do Slave DB.
# Na primeira execucao (volume vazio), clona o Master inteiro via pg_basebackup
# e configura o modo standby (-R cria standby.signal + primary_conninfo automaticamente).
# Nas execucoes seguintes (volume ja populado), apenas sobe o Postgres normalmente
# e ele retoma a replicacao a partir de onde parou.
set -e

PGDATA_DIR="/var/lib/postgresql/data"

if [ -z "$(ls -A "$PGDATA_DIR" 2>/dev/null)" ]; then
    echo "[SLAVE-INIT] Volume vazio. Clonando dados do Master..."

    # Arquivo de senha para autenticacao automatica
    echo "postgres-master:5432:*:replicator:replica_senha123" > ~/.pgpass
    chmod 0600 ~/.pgpass
    export PGPASSFILE=~/.pgpass

    until pg_basebackup -h postgres-master -p 5432 -D "$PGDATA_DIR" -U replicator -Fp -Xs -P -R; do
        echo "[SLAVE-INIT] Master ainda nao disponivel, tentando novamente em 3s..."
        sleep 3
    done

    chmod 0700 "$PGDATA_DIR"
    echo "[SLAVE-INIT] Clonagem concluida. standby.signal criado, entrando em modo replica."
else
    echo "[SLAVE-INIT] Volume ja populado, retomando replicacao existente."
fi

exec docker-entrypoint.sh postgres
