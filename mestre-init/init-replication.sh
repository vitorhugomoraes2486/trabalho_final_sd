#!/bin/bash
# Executado automaticamente pelo Postgres na primeira inicialização do Master
set -e

echo "[MASTER-INIT] Criando role de replicacao..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'replica_senha123';
EOSQL

echo "[MASTER-INIT] Liberando pg_hba.conf para conexoes de replicacao..."
{
  echo "host replication replicator all md5"
  echo "host all all all md5"
} >> "$PGDATA/pg_hba.conf"

echo "[MASTER-INIT] Concluido. O Master esta pronto para aceitar um standby."
