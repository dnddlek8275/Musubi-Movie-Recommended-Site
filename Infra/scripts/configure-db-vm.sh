#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

db_address="${DB_PRIVATE_ADDRESS:-10.30.2.185}"
db_network="${DB_ALLOWED_NETWORK:-10.30.2.0/24}"
credential_dir=/etc/cineverse
credential_file="${credential_dir}/db-credentials.env"
pg_hba=/etc/postgresql/17/main/pg_hba.conf

install -d -m 0700 -o root -g root "${credential_dir}"

if [[ ! -s "${credential_file}" ]] \
  || ! grep -q '^CINEVERSE_APP_PASSWORD=' "${credential_file}" \
  || ! grep -q '^CINEVERSE_MIGRATION_PASSWORD=' "${credential_file}"; then
  umask 077
  app_password="$(openssl rand -hex 24)"
  migration_password="$(openssl rand -hex 24)"
  secret_key="$(openssl rand -hex 32)"
  printf "CINEVERSE_APP_PASSWORD='%s'\nCINEVERSE_MIGRATION_PASSWORD='%s'\nCINEVERSE_SECRET_KEY='%s'\n" \
    "${app_password}" "${migration_password}" "${secret_key}" > "${credential_file}"
elif ! grep -q '^CINEVERSE_SECRET_KEY=' "${credential_file}"; then
  printf "CINEVERSE_SECRET_KEY='%s'\n" "$(openssl rand -hex 32)" >> "${credential_file}"
fi

chmod 0600 "${credential_file}"
# shellcheck disable=SC1090
source "${credential_file}"

sudo -u postgres psql \
  --set=ON_ERROR_STOP=1 \
  --set=app_password="${CINEVERSE_APP_PASSWORD}" \
  --set=migration_password="${CINEVERSE_MIGRATION_PASSWORD}" <<'SQL'
SELECT format(
  'CREATE ROLE cineverse_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %L',
  :'app_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cineverse_app') \gexec

SELECT format('ALTER ROLE cineverse_app PASSWORD %L', :'app_password') \gexec

SELECT format(
  'CREATE ROLE cineverse_migration LOGIN NOSUPERUSER CREATEDB NOCREATEROLE INHERIT PASSWORD %L',
  :'migration_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cineverse_migration') \gexec

SELECT format('ALTER ROLE cineverse_migration PASSWORD %L', :'migration_password') \gexec

SELECT 'CREATE DATABASE cineverse OWNER cineverse_migration TEMPLATE template0 ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'cineverse') \gexec

ALTER DATABASE cineverse OWNER TO cineverse_migration;
GRANT CONNECT ON DATABASE cineverse TO cineverse_app;
SQL

sudo -u postgres psql --dbname=cineverse --set=ON_ERROR_STOP=1 <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO cineverse_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cineverse_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO cineverse_app;
ALTER DEFAULT PRIVILEGES FOR ROLE cineverse_migration IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cineverse_app;
ALTER DEFAULT PRIVILEGES FOR ROLE cineverse_migration IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO cineverse_app;
SQL

sudo -u postgres psql --set=ON_ERROR_STOP=1 <<SQL
ALTER SYSTEM SET listen_addresses = '127.0.0.1,${db_address}';
ALTER SYSTEM SET password_encryption = 'scram-sha-256';
ALTER SYSTEM SET log_min_duration_statement = '1000ms';
ALTER SYSTEM SET log_checkpoints = 'on';
ALTER SYSTEM SET max_connections = '100';
SQL

if ! grep -q '# BEGIN CINEVERSE MANAGED ACCESS' "${pg_hba}"; then
  cat >> "${pg_hba}" <<EOF

# BEGIN CINEVERSE MANAGED ACCESS
host    cineverse    cineverse_app         ${db_network}    scram-sha-256
host    cineverse    cineverse_migration   ${db_network}    scram-sha-256
# END CINEVERSE MANAGED ACCESS
EOF
fi

systemctl restart postgresql

sudo -u postgres psql --tuples-only --no-align --dbname=postgres \
  --command="SELECT format(E'\"%s\" \"%s\"', rolname, rolpassword) FROM pg_authid WHERE rolname = 'cineverse_app';" \
  > /etc/pgbouncer/userlist.txt
chown postgres:postgres /etc/pgbouncer/userlist.txt
chmod 0640 /etc/pgbouncer/userlist.txt

cat > /etc/pgbouncer/pgbouncer.ini <<EOF
[databases]
cineverse = host=127.0.0.1 port=5432 dbname=cineverse

[pgbouncer]
logfile = /var/log/postgresql/pgbouncer.log
pidfile = /var/run/postgresql/pgbouncer.pid
listen_addr = 127.0.0.1,${db_address}
listen_port = 6432
unix_socket_dir = /var/run/postgresql
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 200
default_pool_size = 20
min_pool_size = 2
reserve_pool_size = 5
reserve_pool_timeout = 5
server_reset_query = DISCARD ALL
ignore_startup_parameters = extra_float_digits
server_check_query = SELECT 1
server_check_delay = 30
server_idle_timeout = 600
query_timeout = 180
query_wait_timeout = 30
client_idle_timeout = 0
EOF

chown postgres:postgres /etc/pgbouncer/pgbouncer.ini
chmod 0640 /etc/pgbouncer/pgbouncer.ini

systemctl enable --now postgresql pgbouncer
systemctl restart pgbouncer

sudo -u postgres psql --dbname=cineverse --tuples-only --no-align --command='SELECT current_database(), current_setting('\''server_version'\'');'
systemctl is-active postgresql
systemctl is-active pgbouncer
ss -lntp | grep -E ':(5432|6432) '
