"""
High-availability configuration for the Digiland platform.

Manages PostgreSQL streaming replication, connection pooling via
PgBouncer, read-routing to replicas, and cluster health monitoring.
"""
import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolConfig:
    """PgBouncer connection-pool configuration."""

    pool_mode: str = "transaction"        # session, transaction, statement
    max_client_conn: int = 1000
    default_pool_size: int = 25
    min_pool_size: int = 5
    reserve_pool_size: int = 5
    reserve_pool_timeout: int = 3
    server_idle_timeout: int = 600
    server_lifetime: int = 3600
    server_connect_timeout: int = 15
    application_name: str = "digiland"


@dataclass
class ReplicationConfig:
    """PostgreSQL streaming-replication configuration."""

    primary_host: str = "localhost"
    primary_port: int = 5432
    replica_hosts: List[str] = field(default_factory=list)
    replication_user: str = "replicator"
    replication_password: str = ""
    wal_keep_size: str = "256MB"
    max_wal_senders: int = 5
    synchronous_commit: str = "on"       # on, remote_apply, remote_write, local, off
    synchronous_standby_names: str = ""   # e.g. "FIRST 2 (replica1, replica2)"


@dataclass
class ClusterHealth:
    """Snapshot of cluster health across all nodes."""

    primary_status: str = "unknown"
    replica_statuses: Dict[str, str] = field(default_factory=dict)
    replication_lag_bytes: int = 0
    replication_lag_seconds: float = 0.0
    active_connections: int = 0
    max_connections: int = 0
    connection_pool_status: str = "unknown"
    issues: List[str] = field(default_factory=list)


class HighAvailabilityManager:
    """Configure and monitor PostgreSQL high-availability.

    Covers primary/replica setup, PgBouncer connection pooling,
    read-routing, and cluster health checks.
    """

    PGBOUNCER_CONFIG_PATH = getattr(settings, "PGBOUNCER_CONFIG_PATH", "/etc/pgbouncer/pgbouncer.ini")

    def __init__(self, replication_config: Optional[ReplicationConfig] = None,
                 pool_config: Optional[ConnectionPoolConfig] = None):
        self.repl_config = replication_config or ReplicationConfig()
        self.pool_config = pool_config or ConnectionPoolConfig()

    # ── Primary / Replica configuration ───────────────────────

    def configure_primary(self) -> Dict[str, Any]:
        """Configure the primary DB for streaming replication."""
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": f"Replication not supported on {connection.vendor}"}

        params = {
            "wal_level": "replica",
            "max_wal_senders": str(self.repl_config.max_wal_senders),
            "wal_keep_size": self.repl_config.wal_keep_size,
            "synchronous_commit": self.repl_config.synchronous_commit,
            "hot_standby": "on",
            "listen_addresses": "*",
        }
        try:
            with connection.cursor() as cursor:
                for key, val in params.items():
                    cursor.execute(f"ALTER SYSTEM SET {key} = %s", [val])
                cursor.execute("SELECT pg_reload_conf()")
            return {"status": "success", "parameters": params,
                    "note": "A PostgreSQL restart may be required for some parameters"}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    def configure_replica(self, host: str) -> Dict[str, Any]:
        """Configure a read replica at the given *host*.

        In production this would SSH into the replica and set up
        standby.signal + primary_conninfo.
        """
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": f"Replication not supported on {connection.vendor}"}

        primary_conninfo = (
            f"host={self.repl_config.primary_host} "
            f"port={self.repl_config.primary_port} "
            f"user={self.repl_config.replication_user} "
            f"password={self.repl_config.replication_password} "
            f"application_name={host}"
        )
        return {
            "status": "configured_remotely",
            "replica_host": host,
            "primary_conninfo": primary_conninfo,
            "note": "Run pg_basebackup on replica and create standby.signal",
        }

    # ── Replication monitoring ────────────────────────────────

    def check_replication_lag(self) -> Dict[str, Any]:
        """Monitor replication lag across all replicas."""
        if connection.vendor != "postgresql":
            return {"status": "skipped", "lag_seconds": 0, "lag_bytes": 0}

        try:
            with connection.cursor() as cursor:
                # Check if we are on primary
                cursor.execute("SELECT pg_is_in_recovery()")
                in_recovery = cursor.fetchone()[0]

                if not in_recovery:
                    # Primary: check replica lag
                    cursor.execute(
                        """
                        SELECT client_addr, state, sent_lsn, replay_lsn,
                               (sent_lsn - replay_lsn) AS lag_bytes
                        FROM pg_stat_replication
                        """
                    )
                    replicas = []
                    for addr, state, sent, replay, lag in cursor.fetchall():
                        replicas.append({
                            "host": str(addr), "state": state,
                            "sent_lsn": str(sent), "replay_lsn": str(replay),
                            "lag_bytes": lag if lag else 0,
                        })
                    return {"status": "primary", "replicas": replicas}
                else:
                    # Replica: report own lag
                    cursor.execute(
                        """
                        SELECT now() - pg_last_xact_replay_timestamp() AS lag_interval,
                               pg_last_xact_replay_timestamp()
                        """
                    )
                    lag_interval, replay_ts = cursor.fetchone()
                    lag_seconds = lag_interval.total_seconds() if lag_interval else 0
                    return {"status": "replica", "lag_seconds": lag_seconds,
                            "replay_timestamp": str(replay_ts)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def promote_replica(self, replica_host: str) -> Dict[str, Any]:
        """Failover: promote a replica to primary."""
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": "PostgreSQL-only feature"}

        # On the replica host, we would run: SELECT pg_promote();
        logger.warning("Promoting replica %s to primary — this is a manual operation", replica_host)
        return {
            "status": "action_required",
            "replica_host": replica_host,
            "command": "psql -h {host} -c 'SELECT pg_promote(true, 60)'".format(host=replica_host),
            "note": "After promotion, update Django DATABASES config to point to new primary",
        }

    # ── Connection pooling ────────────────────────────────────

    def configure_connection_pooling(self) -> Dict[str, Any]:
        """Generate PgBouncer configuration file."""
        cfg = self.pool_config
        db_name = connection.settings_dict.get("NAME", "digiland")
        db_host = connection.settings_dict.get("HOST", "localhost")
        db_port = connection.settings_dict.get("PORT", 5432)
        db_user = connection.settings_dict.get("USER", "postgres")

        ini_content = (
            f"[databases]\n"
            f"{db_name} = host={db_host} port={db_port}\n\n"
            f"[pgbouncer]\n"
            f"listen_addr = 0.0.0.0\n"
            f"listen_port = 6432\n"
            f"auth_type = scram-sha-256\n"
            f"auth_file = /etc/pgbouncer/userlist.txt\n"
            f"pool_mode = {cfg.pool_mode}\n"
            f"max_client_conn = {cfg.max_client_conn}\n"
            f"default_pool_size = {cfg.default_pool_size}\n"
            f"min_pool_size = {cfg.min_pool_size}\n"
            f"reserve_pool_size = {cfg.reserve_pool_size}\n"
            f"reserve_pool_timeout = {cfg.reserve_pool_timeout}\n"
            f"server_idle_timeout = {cfg.server_idle_timeout}\n"
            f"server_lifetime = {cfg.server_lifetime}\n"
            f"server_connect_timeout = {cfg.server_connect_timeout}\n"
            f"application_name_add = 1\n"
            f"admin_users = {db_user}\n"
            f"stats_users = {db_user}\n"
            f"log_connections = 0\n"
            f"log_disconnections = 0\n"
        )
        try:
            os.makedirs(os.path.dirname(self.PGBOUNCER_CONFIG_PATH), exist_ok=True)
            with open(self.PGBOUNCER_CONFIG_PATH, "w") as f:
                f.write(ini_content)
            return {"status": "success", "config_path": self.PGBOUNCER_CONFIG_PATH}
        except Exception as exc:
            return {"status": "failed", "error": str(exc), "config": ini_content}

    # ── Cluster health ────────────────────────────────────────

    def get_cluster_health(self) -> ClusterHealth:
        """Health-check all nodes in the cluster."""
        health = ClusterHealth()
        if connection.vendor != "postgresql":
            health.primary_status = "unknown (non-PG)"
            return health

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_is_in_recovery()")
                in_recovery = cursor.fetchone()[0]
                health.primary_status = "replica_mode" if in_recovery else "primary"

                # Active connections
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                health.active_connections = cursor.fetchone()[0]
                cursor.execute("SHOW max_connections")
                health.max_connections = int(cursor.fetchone()[0])

                # Replica statuses
                if not in_recovery:
                    cursor.execute(
                        "SELECT client_addr, state, sync_state FROM pg_stat_replication"
                    )
                    for addr, state, sync in cursor.fetchall():
                        health.replica_statuses[str(addr)] = f"{state} ({sync})"

                # Replication lag
                lag_info = self.check_replication_lag()
                health.replication_lag_seconds = lag_info.get("lag_seconds", 0.0)
                if lag_info.get("lag_bytes"):
                    health.replication_lag_bytes = lag_info["lag_bytes"]

                # Detect issues
                if health.active_connections > health.max_connections * 0.8:
                    health.issues.append(
                        f"Connection usage high: {health.active_connections}/{health.max_connections}"
                    )
                for host, status in health.replica_statuses.items():
                    if "streaming" not in status:
                        health.issues.append(f"Replica {host} not streaming: {status}")

        except Exception as exc:
            health.issues.append(f"Health check error: {exc}")
        return health

    # ── Read routing ──────────────────────────────────────────

    def configure_read_routing(self) -> Dict[str, Any]:
        """Configure Django database router to send reads to replicas."""
        replicas = self.repl_config.replica_hosts
        if not replicas:
            return {"status": "skipped", "reason": "No replica hosts configured"}

        router_code = (
            "class ReadReplicaRouter:\n"
            "    \"\"\"Route read queries to replica databases.\"\"\"\n\n"
            "    def db_for_read(self, model, **hints):\n"
            "        import random\n"
            f"        return random.choice({replicas!r})\n\n"
            "    def db_for_write(self, model, **hints):\n"
            "        return 'default'\n\n"
            "    def allow_relation(self, obj1, obj2, **hints):\n"
            "        return True\n\n"
            "    def allow_migrate(self, db, app_label, model_name=None, **hints):\n"
            "        return db == 'default'\n"
        )
        return {"status": "success", "router_code": router_code,
                "replica_hosts": replicas,
                "note": "Add router_code to DATABASE_ROUTERS in settings.py"}
