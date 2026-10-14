# Backup and restore

Back up PostgreSQL using a service account limited to the application database, encrypt backups at rest, and retain them according to the customer policy. A typical command is `pg_dump --format=custom --file=crypbot.dump "$DATABASE_URL"`; restore only into an isolated maintenance environment with `pg_restore --clean --if-exists` after verifying the target.

Test restores at least quarterly. Record backup/restore exercises in the audit system, rotate encryption material through a documented KMS procedure, and never include exchange secrets, session tokens, or production `.env` files in support bundles.
