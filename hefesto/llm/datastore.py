"""
HEFESTO v4.5 - Abstract Datastore for IRIS

Purpose: Provide a platform-agnostic interface for data storage.
This allows IRIS to work with multiple BigQuery-compatible backends:
- GCP BigQuery (default, production)
- SQLite (local development, testing)
- Other SQL databases (PostgreSQL, MySQL, etc.)
- Custom implementations (REST APIs, etc.)

Architecture:
    DatastoreClient (Protocol)
        |
        +-- GCPBigQueryClient (Google Cloud Platform)
        +-- SQLiteClient (Local development)
        +-- PostgreSQLClient (Future)
        +-- MockClient (Testing)

Usage:
    # Auto-detect backend from environment
    >>> from hefesto.llm.datastore import get_datastore_client
    >>> client = get_datastore_client()
    >>> client.query("SELECT * FROM my_table")

    # Force specific backend
    >>> client = get_datastore_client(backend="sqlite", db_path="./iris.db")

Environment Variables:
    HEFESTO_DATASTORE_BACKEND: "gcp" | "sqlite" | "postgresql" | "mock"
    HEFESTO_DATASTORE_PROJECT: GCP project ID (for GCP backend)
    HEFESTO_DATASTORE_DB_PATH: SQLite database path (for sqlite backend)
    HEFESTO_DATASTORE_CONN_STRING: Connection string (for postgresql)

Copyright 2025 Narapa LLC, Miami, Florida
OMEGA Sports Analytics Foundation
"""

import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Protocol, Union

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """
    Unified query result structure.

    Attributes:
        rows: List of result rows (each row is a dict)
        row_count: Number of rows returned
        columns: Column names
        success: Whether query succeeded
        error: Error message if failed
    """

    rows: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    success: bool = True
    error: Optional[str] = None

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over result rows."""
        return iter(self.rows)

    def __len__(self) -> int:
        """Return row count."""
        return self.row_count

    def __getitem__(self, index: int) -> Dict[str, Any]:
        """Access row by index."""
        return self.rows[index]


@dataclass
class QueryParameter:
    """
    Query parameter for parameterized queries.

    Attributes:
        name: Parameter name (without @)
        param_type: Data type (STRING, INT64, FLOAT64, BOOL, TIMESTAMP)
        value: Parameter value
    """

    name: str
    param_type: str
    value: Any


class DatastoreClient(Protocol):
    """
    Protocol defining the interface for all datastore backends.

    Any implementation must provide these methods to be compatible
    with IRIS budget tracking and feedback logging.
    """

    def query(
        self,
        sql: str,
        parameters: Optional[List[QueryParameter]] = None,
    ) -> QueryResult:
        """
        Execute a SELECT query.

        Args:
            sql: SQL query string with @param placeholders
            parameters: List of QueryParameter for parameterized queries

        Returns:
            QueryResult with rows and metadata
        """
        ...

    def execute(
        self,
        sql: str,
        parameters: Optional[List[QueryParameter]] = None,
    ) -> bool:
        """
        Execute INSERT/UPDATE/DELETE statement.

        Args:
            sql: SQL statement with @param placeholders
            parameters: List of QueryParameter for parameterized queries

        Returns:
            True if successful, False otherwise
        """
        ...

    def insert_rows(
        self,
        table_id: str,
        rows: List[Dict[str, Any]],
    ) -> bool:
        """
        Insert multiple rows into a table.

        Args:
            table_id: Full table identifier (project.dataset.table or just table)
            rows: List of dictionaries representing rows

        Returns:
            True if successful, False otherwise
        """
        ...

    def ensure_table_exists(
        self,
        table_id: str,
        schema: List[Dict[str, str]],
    ) -> bool:
        """
        Ensure a table exists with the given schema.

        Creates the table if it doesn't exist.

        Args:
            table_id: Full table identifier
            schema: List of column definitions {"name": str, "type": str}

        Returns:
            True if table exists or was created
        """
        ...


class GCPBigQueryClient:
    """
    Google Cloud Platform BigQuery implementation.

    This is the default production backend for IRIS.
    Requires google-cloud-bigquery package and GCP credentials.

    Example:
        >>> client = GCPBigQueryClient(project_id="my-project")
        >>> result = client.query("SELECT * FROM my_dataset.my_table LIMIT 10")
        >>> for row in result:
        ...     print(row)
    """

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize GCP BigQuery client.

        Args:
            project_id: GCP project ID. If None, uses default from environment.
        """
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the BigQuery client."""
        try:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self.project_id)
            logger.info(f"GCP BigQuery client initialized for project: {self.project_id}")
        except ImportError:
            logger.error(
                "google-cloud-bigquery not installed. "
                "Install with: pip install google-cloud-bigquery"
            )
            self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery client: {e}")
            self._client = None

    def query(
        self,
        sql: str,
        parameters: Optional[List[QueryParameter]] = None,
    ) -> QueryResult:
        """Execute a SELECT query against BigQuery."""
        if not self._client:
            return QueryResult(
                rows=[],
                row_count=0,
                columns=[],
                success=False,
                error="BigQuery client not initialized",
            )

        try:
            from google.cloud import bigquery

            job_config = None
            if parameters:
                query_params = [
                    bigquery.ScalarQueryParameter(p.name, p.param_type, p.value)
                    for p in parameters
                ]
                job_config = bigquery.QueryJobConfig(query_parameters=query_params)

            query_job = self._client.query(sql, job_config=job_config)
            results = list(query_job.result())

            if not results:
                return QueryResult(rows=[], row_count=0, columns=[], success=True)

            columns = list(results[0].keys()) if results else []
            rows = [dict(row) for row in results]

            return QueryResult(
                rows=rows,
                row_count=len(rows),
                columns=columns,
                success=True,
            )

        except Exception as e:
            logger.error(f"BigQuery query failed: {e}")
            return QueryResult(
                rows=[],
                row_count=0,
                columns=[],
                success=False,
                error=str(e),
            )

    def execute(
        self,
        sql: str,
        parameters: Optional[List[QueryParameter]] = None,
    ) -> bool:
        """Execute INSERT/UPDATE/DELETE against BigQuery."""
        if not self._client:
            return False

        try:
            from google.cloud import bigquery

            job_config = None
            if parameters:
                query_params = [
                    bigquery.ScalarQueryParameter(p.name, p.param_type, p.value)
                    for p in parameters
                ]
                job_config = bigquery.QueryJobConfig(query_parameters=query_params)

            query_job = self._client.query(sql, job_config=job_config)
            query_job.result()
            return True

        except Exception as e:
            logger.error(f"BigQuery execute failed: {e}")
            return False

    def insert_rows(
        self,
        table_id: str,
        rows: List[Dict[str, Any]],
    ) -> bool:
        """Insert rows using streaming insert."""
        if not self._client:
            return False

        try:
            errors = self._client.insert_rows_json(table_id, rows)
            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
                return False
            return True

        except Exception as e:
            logger.error(f"BigQuery insert failed: {e}")
            return False

    def ensure_table_exists(
        self,
        table_id: str,
        schema: List[Dict[str, str]],
    ) -> bool:
        """Check/create table in BigQuery."""
        if not self._client:
            return False

        try:
            from google.cloud import bigquery

            bq_schema = [
                bigquery.SchemaField(col["name"], col["type"]) for col in schema
            ]

            table = bigquery.Table(table_id, schema=bq_schema)

            try:
                self._client.get_table(table_id)
                return True
            except Exception:
                self._client.create_table(table)
                logger.info(f"Created BigQuery table: {table_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to ensure table exists: {e}")
            return False


class SQLiteClient:
    """
    SQLite implementation for local development and testing.

    Provides BigQuery-compatible interface using SQLite, enabling
    IRIS to run without GCP credentials.

    Example:
        >>> client = SQLiteClient(db_path="./iris_local.db")
        >>> client.ensure_table_exists("llm_events", [...])
        >>> client.insert_rows("llm_events", [...])
    """

    TYPE_MAPPING = {
        "STRING": "TEXT",
        "INT64": "INTEGER",
        "FLOAT64": "REAL",
        "BOOL": "INTEGER",
        "BOOLEAN": "INTEGER",
        "TIMESTAMP": "TEXT",
        "DATE": "TEXT",
        "BYTES": "BLOB",
    }

    def __init__(self, db_path: str = ":memory:"):
        """
        Initialize SQLite client.

        Args:
            db_path: Path to SQLite database file. Use ":memory:" for in-memory.
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Initialize SQLite connection."""
        try:
            self._connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            logger.info(f"SQLite client initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")
            self._connection = None

    def _convert_sql(self, sql: str) -> str:
        """
        Convert BigQuery SQL syntax to SQLite.

        Handles:
        - @param -> :param
        - TIMESTAMP_SUB -> datetime calculations
        - SAFE_DIVIDE -> CASE expressions
        - COUNTIF -> SUM(CASE...)
        """
        converted = sql

        converted = converted.replace("@", ":")

        if "TIMESTAMP_SUB" in converted:
            import re

            converted = re.sub(
                r"TIMESTAMP_SUB\s*\(\s*CURRENT_TIMESTAMP\s*\(\s*\)\s*,\s*INTERVAL\s+:?(\w+)\s+DAY\s*\)",
                r"datetime('now', '-' || :\1 || ' days')",
                converted,
            )

        if "SAFE_DIVIDE" in converted:
            import re

            converted = re.sub(
                r"SAFE_DIVIDE\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)",
                r"CASE WHEN \2 = 0 THEN NULL ELSE CAST(\1 AS REAL) / \2 END",
                converted,
            )

        if "COUNTIF" in converted:
            import re

            converted = re.sub(
                r"COUNTIF\s*\(\s*([^)]+)\s*\)",
                r"SUM(CASE WHEN \1 THEN 1 ELSE 0 END)",
                converted,
            )

        converted = converted.replace("`", "")

        return converted

    def query(
        self,
        sql: str,
        parameters: Optional[List[QueryParameter]] = None,
    ) -> QueryResult:
        """Execute a SELECT query against SQLite."""
        if not self._connection:
            return QueryResult(
                rows=[],
                row_count=0,
                columns=[],
                success=False,
                error="SQLite connection not initialized",
            )

        try:
            converted_sql = self._convert_sql(sql)

            params = {}
            if parameters:
                for p in parameters:
                    if p.param_type == "BOOL":
                        params[p.name] = 1 if p.value else 0
                    elif p.param_type == "TIMESTAMP":
                        if isinstance(p.value, str):
                            params[p.name] = p.value
                        else:
                            params[p.name] = p.value.isoformat() if p.value else None
                    else:
                        params[p.name] = p.value

            cursor = self._connection.execute(converted_sql, params)
            results = cursor.fetchall()

            if not results:
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                return QueryResult(rows=[], row_count=0, columns=columns, success=True)

            columns = list(results[0].keys())
            rows = [dict(row) for row in results]

            return QueryResult(
                rows=rows,
                row_count=len(rows),
                columns=columns,
                success=True,
            )

        except Exception as e:
            logger.error(f"SQLite query failed: {e}")
            return QueryResult(
                rows=[],
                row_count=0,
                columns=[],
                success=False,
                error=str(e),
            )

    def execute(
        self,
        sql: str,
        parameters: Optional[List[QueryParameter]] = None,
    ) -> bool:
        """Execute INSERT/UPDATE/DELETE against SQLite."""
        if not self._connection:
            return False

        try:
            converted_sql = self._convert_sql(sql)

            params = {}
            if parameters:
                for p in parameters:
                    if p.param_type == "BOOL":
                        params[p.name] = 1 if p.value else 0
                    elif p.param_type == "TIMESTAMP":
                        if isinstance(p.value, str):
                            params[p.name] = p.value
                        else:
                            params[p.name] = p.value.isoformat() if p.value else None
                    else:
                        params[p.name] = p.value

            self._connection.execute(converted_sql, params)
            self._connection.commit()
            return True

        except Exception as e:
            logger.error(f"SQLite execute failed: {e}")
            return False

    def insert_rows(
        self,
        table_id: str,
        rows: List[Dict[str, Any]],
    ) -> bool:
        """Insert rows into SQLite table."""
        if not self._connection or not rows:
            return False

        try:
            table_name = table_id.split(".")[-1]

            columns = list(rows[0].keys())
            placeholders = ", ".join([f":{col}" for col in columns])
            columns_str = ", ".join(columns)

            sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

            for row in rows:
                normalized_row = {}
                for k, v in row.items():
                    if isinstance(v, bool):
                        normalized_row[k] = 1 if v else 0
                    elif isinstance(v, datetime):
                        normalized_row[k] = v.isoformat()
                    else:
                        normalized_row[k] = v

                self._connection.execute(sql, normalized_row)

            self._connection.commit()
            return True

        except Exception as e:
            logger.error(f"SQLite insert failed: {e}")
            return False

    def ensure_table_exists(
        self,
        table_id: str,
        schema: List[Dict[str, str]],
    ) -> bool:
        """Create table if it doesn't exist."""
        if not self._connection:
            return False

        try:
            table_name = table_id.split(".")[-1]

            columns_defs = []
            for col in schema:
                sqlite_type = self.TYPE_MAPPING.get(col["type"], "TEXT")
                columns_defs.append(f"{col['name']} {sqlite_type}")

            columns_sql = ", ".join(columns_defs)
            create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_sql})"

            self._connection.execute(create_sql)
            self._connection.commit()

            logger.info(f"Ensured SQLite table exists: {table_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create SQLite table: {e}")
            return False

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


class MockClient:
    """
    Mock implementation for unit testing.

    Stores data in memory and provides predictable responses.

    Example:
        >>> client = MockClient()
        >>> client.set_query_response([{"count": 10}])
        >>> result = client.query("SELECT COUNT(*) as count FROM table")
        >>> print(result.rows[0]["count"])
        10
    """

    def __init__(self):
        """Initialize mock client."""
        self._tables: Dict[str, List[Dict[str, Any]]] = {}
        self._query_responses: List[QueryResult] = []
        self._query_index = 0

    def set_query_response(
        self,
        rows: List[Dict[str, Any]],
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Set the response for the next query."""
        columns = list(rows[0].keys()) if rows else []
        self._query_responses.append(
            QueryResult(
                rows=rows,
                row_count=len(rows),
                columns=columns,
                success=success,
                error=error,
            )
        )

    def query(
        self,
        sql: str,
        parameters: Optional[List[QueryParameter]] = None,
    ) -> QueryResult:
        """Return pre-configured response."""
        if self._query_responses:
            response = self._query_responses[self._query_index % len(self._query_responses)]
            self._query_index += 1
            return response

        return QueryResult(rows=[], row_count=0, columns=[], success=True)

    def execute(
        self,
        sql: str,
        parameters: Optional[List[QueryParameter]] = None,
    ) -> bool:
        """Always return success."""
        return True

    def insert_rows(
        self,
        table_id: str,
        rows: List[Dict[str, Any]],
    ) -> bool:
        """Store rows in memory."""
        if table_id not in self._tables:
            self._tables[table_id] = []
        self._tables[table_id].extend(rows)
        return True

    def ensure_table_exists(
        self,
        table_id: str,
        schema: List[Dict[str, str]],
    ) -> bool:
        """Always return success."""
        if table_id not in self._tables:
            self._tables[table_id] = []
        return True

    def get_inserted_rows(self, table_id: str) -> List[Dict[str, Any]]:
        """Get all rows inserted into a table (for test assertions)."""
        return self._tables.get(table_id, [])

    def reset(self) -> None:
        """Reset all state."""
        self._tables.clear()
        self._query_responses.clear()
        self._query_index = 0


_datastore_client: Optional[Union[GCPBigQueryClient, SQLiteClient, MockClient]] = None


def get_datastore_client(
    backend: Optional[str] = None,
    **kwargs: Any,
) -> Union[GCPBigQueryClient, SQLiteClient, MockClient]:
    """
    Get the datastore client singleton.

    Auto-detects backend from environment or uses specified backend.

    Args:
        backend: Force specific backend ("gcp", "sqlite", "mock")
        **kwargs: Backend-specific configuration
            - project_id: GCP project ID (for gcp backend)
            - db_path: SQLite database path (for sqlite backend)

    Returns:
        Configured datastore client

    Environment Variables:
        HEFESTO_DATASTORE_BACKEND: Default backend if not specified
        HEFESTO_DATASTORE_PROJECT: GCP project ID
        HEFESTO_DATASTORE_DB_PATH: SQLite database path

    Example:
        >>> # Auto-detect from environment
        >>> client = get_datastore_client()

        >>> # Force SQLite for local development
        >>> client = get_datastore_client(backend="sqlite", db_path="./iris.db")

        >>> # Force GCP for production
        >>> client = get_datastore_client(backend="gcp", project_id="my-project")
    """
    global _datastore_client

    if _datastore_client is not None and backend is None:
        return _datastore_client

    if backend is None:
        backend = os.getenv("HEFESTO_DATASTORE_BACKEND", "gcp")

    backend = backend.lower()

    if backend == "gcp":
        project_id = kwargs.get("project_id") or os.getenv("HEFESTO_DATASTORE_PROJECT")
        _datastore_client = GCPBigQueryClient(project_id=project_id)

    elif backend == "sqlite":
        db_path = kwargs.get("db_path") or os.getenv("HEFESTO_DATASTORE_DB_PATH", ":memory:")
        _datastore_client = SQLiteClient(db_path=db_path)

    elif backend == "mock":
        _datastore_client = MockClient()

    else:
        raise ValueError(
            f"Unknown datastore backend: {backend}. "
            f"Valid options: gcp, sqlite, mock"
        )

    logger.info(f"Datastore client initialized: {backend}")
    return _datastore_client


def reset_datastore_client() -> None:
    """Reset the singleton client (useful for testing)."""
    global _datastore_client
    if isinstance(_datastore_client, SQLiteClient):
        _datastore_client.close()
    _datastore_client = None


__all__ = [
    "DatastoreClient",
    "GCPBigQueryClient",
    "SQLiteClient",
    "MockClient",
    "QueryResult",
    "QueryParameter",
    "get_datastore_client",
    "reset_datastore_client",
]
