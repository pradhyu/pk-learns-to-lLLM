"""
Neo4j connection utilities.

This module provides classes for managing connections to Neo4j databases,
including connection pooling, authentication, and security features.
"""
import logging
import ssl
import time
from contextlib import contextmanager
from typing import Dict, List, Optional, Union, Any, Generator, Callable

from neo4j import GraphDatabase, Session, Driver, Result, Auth, basic_auth, kerberos_auth, custom_auth
from neo4j.exceptions import Neo4jError, ServiceUnavailable, ClientError, TransientError
from neo4j.work.transaction import Transaction

# Configure logging
logger = logging.getLogger(__name__)


class Neo4jConnectionError(Exception):
    """Exception raised for Neo4j connection errors."""
    pass


class Neo4jQueryError(Exception):
    """Exception raised for Neo4j query errors."""
    pass


class Neo4jRetryableError(Exception):
    """Exception raised for Neo4j errors that can be retried."""
    pass


class Neo4jConnection:
    """
    A class to manage Neo4j database connections with connection pooling.
    """

    def __init__(
        self, 
        uri: str, 
        username: str, 
        password: str, 
        database: str = "neo4j",
        max_connection_lifetime: int = 3600,  # 1 hour
        max_connection_pool_size: int = 50,
        connection_acquisition_timeout: int = 60,
        encrypted: bool = True,
        trust_strategy: Optional[str] = None,
        auth_type: str = "basic",
        auth_token: Optional[Dict[str, Any]] = None,
        max_retry_time: int = 30,
        retry_delay: int = 1
    ) -> None:
        """
        Initialize the Neo4j connection with connection pooling.

        Args:
            uri: The URI of the Neo4j database.
            username: The username for authentication.
            password: The password for authentication.
            database: The name of the database to connect to.
            max_connection_lifetime: Maximum lifetime of a connection in seconds.
            max_connection_pool_size: Maximum size of the connection pool.
            connection_acquisition_timeout: Timeout for acquiring a connection from the pool.
            encrypted: Whether to use TLS encryption for the connection.
            trust_strategy: SSL trust strategy (TRUST_ALL_CERTIFICATES, TRUST_SYSTEM_CA_SIGNED_CERTIFICATES).
            auth_type: Authentication type ('basic', 'kerberos', 'custom').
            auth_token: Custom authentication token for advanced auth scenarios.
            max_retry_time: Maximum time to retry failed operations in seconds.
            retry_delay: Delay between retry attempts in seconds.
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.max_connection_lifetime = max_connection_lifetime
        self.max_connection_pool_size = max_connection_pool_size
        self.connection_acquisition_timeout = connection_acquisition_timeout
        self.encrypted = encrypted
        self.trust_strategy = trust_strategy
        self.auth_type = auth_type
        self.auth_token = auth_token
        self.max_retry_time = max_retry_time
        self.retry_delay = retry_delay
        self.driver = None
        self._connect()

    def _get_auth(self) -> Auth:
        """
        Get the appropriate authentication method based on configuration.
        
        Returns:
            Neo4j authentication object.
        
        Raises:
            ValueError: If an invalid authentication type is specified.
        """
        if self.auth_token:
            return custom_auth(**self.auth_token)
        
        if self.auth_type == "basic":
            return basic_auth(self.username, self.password)
        elif self.auth_type == "kerberos":
            return kerberos_auth()
        elif self.auth_type == "custom" and self.auth_token:
            return custom_auth(**self.auth_token)
        else:
            raise ValueError(f"Invalid authentication type: {self.auth_type}")

    def _get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """
        Create an SSL context based on the trust strategy.
        
        Returns:
            SSL context or None if encryption is disabled.
        """
        if not self.encrypted:
            return None
            
        context = ssl.create_default_context()
        
        if self.trust_strategy == "TRUST_ALL_CERTIFICATES":
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        elif self.trust_strategy == "TRUST_SYSTEM_CA_SIGNED_CERTIFICATES":
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
        
        return context

    def _connect(self) -> None:
        """
        Connect to the Neo4j database with connection pooling.
        
        Raises:
            Neo4jConnectionError: If connection to the database fails.
        """
        try:
            # Configure connection pooling and security
            ssl_context = self._get_ssl_context()
            auth = self._get_auth()
            
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=auth,
                encrypted=self.encrypted,
                trust=ssl_context,
                max_connection_lifetime=self.max_connection_lifetime,
                max_connection_pool_size=self.max_connection_pool_size,
                connection_acquisition_timeout=self.connection_acquisition_timeout
            )
            
            # Test the connection
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
                
            logger.info(f"Connected to Neo4j database at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j database: {e}")
            raise Neo4jConnectionError(f"Failed to connect to Neo4j database: {e}")

    def close(self) -> None:
        """
        Close the Neo4j connection and release all resources.
        """
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
            self.driver = None

    def get_session(self) -> Session:
        """
        Get a Neo4j session from the connection pool.

        Returns:
            A Neo4j session.
            
        Raises:
            Neo4jConnectionError: If the connection is not available.
        """
        if not self.driver:
            self._connect()
        
        try:
            return self.driver.session(database=self.database)
        except Exception as e:
            logger.error(f"Failed to get Neo4j session: {e}")
            raise Neo4jConnectionError(f"Failed to get Neo4j session: {e}")

    @contextmanager
    def get_transaction(self, access_mode: str = "WRITE") -> Generator[Transaction, None, None]:
        """
        Get a Neo4j transaction as a context manager.
        
        Args:
            access_mode: Access mode for the transaction ("WRITE" or "READ").
            
        Yields:
            A Neo4j transaction.
            
        Raises:
            Neo4jConnectionError: If the connection is not available.
        """
        with self.get_session() as session:
            if access_mode == "WRITE":
                with session.begin_transaction() as tx:
                    yield tx
            else:
                with session.begin_transaction(access_mode="READ") as tx:
                    yield tx

    def _execute_with_retry(
        self, 
        operation: Callable[[], Any], 
        retryable_exceptions: tuple = (ServiceUnavailable, TransientError)
    ) -> Any:
        """
        Execute an operation with retry logic for transient errors.
        
        Args:
            operation: The operation to execute.
            retryable_exceptions: Exceptions that should trigger a retry.
            
        Returns:
            The result of the operation.
            
        Raises:
            Neo4jRetryableError: If the operation fails after all retries.
        """
        start_time = time.time()
        last_exception = None
        
        while time.time() - start_time < self.max_retry_time:
            try:
                return operation()
            except retryable_exceptions as e:
                last_exception = e
                logger.warning(f"Retryable error occurred: {e}. Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
        
        logger.error(f"Operation failed after {self.max_retry_time} seconds of retries: {last_exception}")
        raise Neo4jRetryableError(f"Operation failed after retries: {last_exception}")

    def execute_query(
        self, query: str, parameters: Optional[Dict] = None, retry: bool = True
    ) -> List[Dict]:
        """
        Execute a Cypher query with retry logic for transient errors.

        Args:
            query: The Cypher query to execute.
            parameters: The parameters for the query.
            retry: Whether to retry on transient errors.

        Returns:
            The result of the query as a list of dictionaries.
            
        Raises:
            Neo4jQueryError: If the query execution fails.
        """
        if parameters is None:
            parameters = {}

        try:
            operation = lambda: self._execute_query_internal(query, parameters)
            if retry:
                return self._execute_with_retry(operation)
            else:
                return operation()
        except Neo4jRetryableError as e:
            raise Neo4jQueryError(f"Query failed after retries: {e}")
        except Neo4jError as e:
            logger.error(f"Neo4j query error: {e}")
            raise Neo4jQueryError(f"Query execution failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during query execution: {e}")
            raise Neo4jQueryError(f"Unexpected error during query execution: {e}")

    def _execute_query_internal(self, query: str, parameters: Dict) -> List[Dict]:
        """
        Internal method to execute a query without retry logic.
        
        Args:
            query: The Cypher query to execute.
            parameters: The parameters for the query.
            
        Returns:
            The result of the query as a list of dictionaries.
        """
        with self.get_session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]

    def execute_write_query(
        self, query: str, parameters: Optional[Dict] = None, retry: bool = True
    ) -> Union[List[Dict], None]:
        """
        Execute a write query (CREATE, MERGE, DELETE, etc.) with retry logic.

        Args:
            query: The Cypher query to execute.
            parameters: The parameters for the query.
            retry: Whether to retry on transient errors.

        Returns:
            The result of the query as a list of dictionaries, or None if no results.
            
        Raises:
            Neo4jQueryError: If the query execution fails.
        """
        if parameters is None:
            parameters = {}

        try:
            operation = lambda: self._execute_write_query_internal(query, parameters)
            if retry:
                return self._execute_with_retry(operation)
            else:
                return operation()
        except Neo4jRetryableError as e:
            raise Neo4jQueryError(f"Write query failed after retries: {e}")
        except Neo4jError as e:
            logger.error(f"Neo4j write query error: {e}")
            raise Neo4jQueryError(f"Write query execution failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during write query execution: {e}")
            raise Neo4jQueryError(f"Unexpected error during write query execution: {e}")

    def _execute_write_query_internal(self, query: str, parameters: Dict) -> List[Dict]:
        """
        Internal method to execute a write query without retry logic.
        
        Args:
            query: The Cypher query to execute.
            parameters: The parameters for the query.
            
        Returns:
            The result of the query as a list of dictionaries.
        """
        with self.get_session() as session:
            result = session.execute_write(
                lambda tx: tx.run(query, parameters).data()
            )
            return result

    def execute_read_query(
        self, query: str, parameters: Optional[Dict] = None, retry: bool = True
    ) -> List[Dict]:
        """
        Execute a read query (MATCH, etc.) with retry logic.

        Args:
            query: The Cypher query to execute.
            parameters: The parameters for the query.
            retry: Whether to retry on transient errors.

        Returns:
            The result of the query as a list of dictionaries.
            
        Raises:
            Neo4jQueryError: If the query execution fails.
        """
        if parameters is None:
            parameters = {}

        try:
            operation = lambda: self._execute_read_query_internal(query, parameters)
            if retry:
                return self._execute_with_retry(operation)
            else:
                return operation()
        except Neo4jRetryableError as e:
            raise Neo4jQueryError(f"Read query failed after retries: {e}")
        except Neo4jError as e:
            logger.error(f"Neo4j read query error: {e}")
            raise Neo4jQueryError(f"Read query execution failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during read query execution: {e}")
            raise Neo4jQueryError(f"Unexpected error during read query execution: {e}")

    def _execute_read_query_internal(self, query: str, parameters: Dict) -> List[Dict]:
        """
        Internal method to execute a read query without retry logic.
        
        Args:
            query: The Cypher query to execute.
            parameters: The parameters for the query.
            
        Returns:
            The result of the query as a list of dictionaries.
        """
        with self.get_session() as session:
            result = session.execute_read(
                lambda tx: tx.run(query, parameters).data()
            )
            return result

    def execute_batch(
        self, 
        queries: List[Dict[str, Any]], 
        batch_size: int = 1000,
        retry: bool = True
    ) -> List[Union[List[Dict], Exception]]:
        """
        Execute a batch of queries with transaction batching for efficiency.
        
        Args:
            queries: List of query dictionaries with 'query' and 'parameters' keys.
            batch_size: Number of queries to execute in a single transaction.
            retry: Whether to retry on transient errors.
            
        Returns:
            List of results or exceptions for each query.
        """
        results = []
        
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i+batch_size]
            batch_results = self._execute_batch_transaction(batch, retry)
            results.extend(batch_results)
            
        return results

    def _execute_batch_transaction(
        self, 
        queries: List[Dict[str, Any]], 
        retry: bool = True
    ) -> List[Union[List[Dict], Exception]]:
        """
        Execute a batch of queries in a single transaction.
        
        Args:
            queries: List of query dictionaries with 'query' and 'parameters' keys.
            retry: Whether to retry on transient errors.
            
        Returns:
            List of results or exceptions for each query.
        """
        def run_batch_tx(tx: Transaction) -> List[Union[List[Dict], Exception]]:
            results = []
            for query_dict in queries:
                query = query_dict.get('query', '')
                parameters = query_dict.get('parameters', {})
                try:
                    result = tx.run(query, parameters)
                    results.append([record.data() for record in result])
                except Exception as e:
                    logger.error(f"Error executing query in batch: {e}")
                    results.append(e)
            return results
        
        try:
            operation = lambda: self._execute_batch_transaction_internal(run_batch_tx)
            if retry:
                return self._execute_with_retry(operation)
            else:
                return operation()
        except Neo4jRetryableError as e:
            logger.error(f"Batch transaction failed after retries: {e}")
            return [e] * len(queries)
        except Exception as e:
            logger.error(f"Unexpected error during batch transaction: {e}")
            return [e] * len(queries)

    def _execute_batch_transaction_internal(self, tx_function: Callable[[Transaction], Any]) -> Any:
        """
        Internal method to execute a batch transaction without retry logic.
        
        Args:
            tx_function: Function that takes a transaction and returns results.
            
        Returns:
            The result of the transaction function.
        """
        with self.get_session() as session:
            return session.execute_write(tx_function)

    def check_connection_health(self) -> bool:
        """
        Check if the connection to Neo4j is healthy.
        
        Returns:
            True if the connection is healthy, False otherwise.
        """
        try:
            with self.get_session() as session:
                result = session.run("RETURN 1 as n")
                return result.single()["n"] == 1
        except Exception as e:
            logger.error(f"Connection health check failed: {e}")
            return False

    def get_server_info(self) -> Dict[str, Any]:
        """
        Get information about the Neo4j server.
        
        Returns:
            Dictionary with server information.
        """
        try:
            with self.get_session() as session:
                result = session.run("CALL dbms.components() YIELD name, versions, edition")
                record = result.single()
                return {
                    "name": record["name"],
                    "version": record["versions"][0],
                    "edition": record["edition"]
                }
        except Exception as e:
            logger.error(f"Failed to get server info: {e}")
            return {"error": str(e)}


class Neo4jConnectionPool:
    """
    A singleton class to manage multiple Neo4j connections.
    """
    _instance = None
    _connections = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jConnectionPool, cls).__new__(cls)
        return cls._instance

    def get_connection(
        self, 
        connection_id: str = "default", 
        **connection_params
    ) -> Neo4jConnection:
        """
        Get a Neo4j connection from the pool or create a new one.
        
        Args:
            connection_id: Identifier for the connection.
            **connection_params: Parameters for creating a new connection.
            
        Returns:
            A Neo4j connection.
        """
        if connection_id not in self._connections:
            self._connections[connection_id] = Neo4jConnection(**connection_params)
        return self._connections[connection_id]

    def close_connection(self, connection_id: str = "default") -> None:
        """
        Close a specific Neo4j connection.
        
        Args:
            connection_id: Identifier for the connection to close.
        """
        if connection_id in self._connections:
            self._connections[connection_id].close()
            del self._connections[connection_id]
            logger.info(f"Closed Neo4j connection: {connection_id}")

    def close_all_connections(self) -> None:
        """
        Close all Neo4j connections in the pool.
        """
        for connection_id, connection in list(self._connections.items()):
            connection.close()
            del self._connections[connection_id]
        logger.info("Closed all Neo4j connections")

    def get_connection_ids(self) -> List[str]:
        """
        Get the IDs of all active connections.
        
        Returns:
            List of connection IDs.
        """
        return list(self._connections.keys())

    def check_all_connections(self) -> Dict[str, bool]:
        """
        Check the health of all connections.
        
        Returns:
            Dictionary mapping connection IDs to health status.
        """
        return {
            connection_id: connection.check_connection_health()
            for connection_id, connection in self._connections.items()
        }