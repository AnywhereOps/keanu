"""data - external data, project ops, CI."""

from keanu.data.database import detect_schema, analyze_query, generate_model
from keanu.data.migrate import diff_schemas, detect_migration_system, create_migration_file
from keanu.data.rag import build_index, search, get_index_stats
from keanu.data.changelog import generate_changelog
from keanu.data.ci import run_tests, health_summary, get_history
from keanu.data.bisect import binary_search_commits, analyze_bisect_log, BisectResult
from keanu.data.depupdate import check_outdated, find_manifest, parse_manifest
from keanu.data.githooks import install_hook, uninstall_hook, install_all
