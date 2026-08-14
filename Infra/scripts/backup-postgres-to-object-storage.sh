#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

exec 9>/run/lock/cineverse-postgres-backup.lock
flock -n 9 || {
  echo "another backup is already running" >&2
  exit 1
}

credential_file=/etc/cineverse/db-credentials.env
storage_file=/etc/cineverse/object-storage-backup.env
backup_dir=/var/backups/cineverse/postgresql
uploader=/usr/local/lib/cineverse/upload-db-backup.py
python_path=/opt/cineverse-backup-python

for required_file in "${credential_file}" "${storage_file}" "${uploader}"; do
  [[ -r "${required_file}" ]] || {
    echo "missing required file: ${required_file}" >&2
    exit 1
  }
done

# shellcheck disable=SC1090
source "${credential_file}"
# shellcheck disable=SC1090
source "${storage_file}"

: "${CINEVERSE_MIGRATION_PASSWORD:?missing migration password}"
: "${OBJECT_STORAGE_ACCESS_KEY:?missing object storage access key}"
: "${OBJECT_STORAGE_SECRET_KEY:?missing object storage secret key}"
: "${OBJECT_STORAGE_ENDPOINT:?missing object storage endpoint}"
: "${OBJECT_STORAGE_REGION:?missing object storage region}"
: "${OBJECT_STORAGE_BUCKET:?missing object storage bucket}"

install -d -m 0700 -o root -g root "${backup_dir}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="${backup_dir}/cineverse-${timestamp}.dump"
temporary="${backup}.partial"
checksum="${backup}.sha256"

cleanup() {
  rm -f "${temporary}"
}
trap cleanup EXIT

PGPASSWORD="${CINEVERSE_MIGRATION_PASSWORD}" pg_dump \
  --host=127.0.0.1 \
  --port=5432 \
  --username=cineverse_migration \
  --dbname=cineverse \
  --format=custom \
  --compress=6 \
  --no-owner \
  --file="${temporary}"

pg_restore --list "${temporary}" >/dev/null
mv "${temporary}" "${backup}"
sha256sum "${backup}" >"${checksum}"

export OBJECT_STORAGE_ACCESS_KEY OBJECT_STORAGE_SECRET_KEY
export OBJECT_STORAGE_ENDPOINT OBJECT_STORAGE_REGION OBJECT_STORAGE_BUCKET
export OBJECT_STORAGE_PREFIX="${OBJECT_STORAGE_PREFIX:-backups/postgresql}"
PYTHONPATH="${python_path}" python3 "${uploader}" "${backup}" "${checksum}"

find "${backup_dir}" -type f \
  \( -name 'cineverse-*.dump' -o -name 'cineverse-*.dump.sha256' \) \
  -mtime +2 -delete

echo "backup_complete=${backup}"
