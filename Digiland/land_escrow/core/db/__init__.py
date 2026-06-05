"""
Database engineering utilities for the Digiland platform.

Provides query optimization, backup/recovery, high-availability
configuration, and migration management — all PostgreSQL-aware with
graceful degradation on SQLite for local development.
"""

from core.db.query_optimizer import (
    QueryOptimizer,
    SlowQueryLog,
    QueryAnalysisResult,
    IndexSuggestion,
)
from core.db.backup_recovery import BackupManager, RecoveryManager
from core.db.ha_config import (
    HighAvailabilityManager,
    ConnectionPoolConfig,
    ReplicationConfig,
    ClusterHealth,
)
from core.db.migration_manager import (
    MigrationManager,
    MigrationChecklist,
    MigrationImpact,
)

__all__ = [
    "QueryOptimizer",
    "SlowQueryLog",
    "QueryAnalysisResult",
    "IndexSuggestion",
    "BackupManager",
    "RecoveryManager",
    "HighAvailabilityManager",
    "ConnectionPoolConfig",
    "ReplicationConfig",
    "ClusterHealth",
    "MigrationManager",
    "MigrationChecklist",
    "MigrationImpact",
]
