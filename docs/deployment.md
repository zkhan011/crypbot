# Deployment

Local deployment uses Docker Compose: API, worker, scheduler, PostgreSQL, Redis, frontend, Nginx, Prometheus, and Grafana. Production must replace development secrets, run migrations in a controlled step, enforce non-root containers, resource limits, read-only filesystems where possible, log rotation, network segmentation, backups, rollback plans, and graceful worker draining.
