#!/usr/bin/env python3
"""
Main application entry point for the production web crawler
Optimized for Render deployment with 0.5 vCPU and 512MB RAM
"""

import asyncio
import logging
import signal
import sys
import os
import yaml
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler_main import CrawlerConfig, ResourceMonitor
from crawler_core import WebCrawler
from crawler_storage import PostgresStorage
import redis
import psutil

class CrawlerApp:
    """Main crawler application"""
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.setup_logging()
        
        # Initialize components
        self.resource_monitor = ResourceMonitor(self.config)
        self.redis_client = None
        self.storage = None
        self.crawler = None
        
        # Graceful shutdown handling
        self.shutdown_event = asyncio.Event()
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self, config_path: str = None) -> CrawlerConfig:
        """Load configuration from file or environment"""
        config_data = {}
        
        # Load from YAML file if provided
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            logging.info(f"Loaded config from {config_path}")
        
        # Override with environment variables
        env_mapping = {
            'REDIS_URL': 'redis_url',
            'DATABASE_URL': 'postgres_url',
            'MAX_MEMORY_MB': 'max_memory_mb',
            'MAX_CPU_PERCENT': 'max_cpu_percent',
            'INITIAL_CONCURRENCY': 'initial_concurrency',
            'MAX_CONCURRENCY': 'max_concurrency',
            'USER_AGENT': 'user_agent',
            'OUTPUT_DIR': 'output_dir',
            'LOG_LEVEL': 'log_level'
        }
        
        for env_var, config_key in env_mapping.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                # Convert numeric values
                if config_key in ['max_memory_mb', 'initial_concurrency', 'max_concurrency']:
                    value = int(value)
                elif config_key == 'max_cpu_percent':
                    value = float(value)
                
                config_data[config_key] = value
        
        return CrawlerConfig(**config_data)
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(f"{self.config.output_dir}/crawler.log")
            ]
        )
        
        # Reduce noise from external libraries
        logging.getLogger('aiohttp').setLevel(logging.WARNING)
        logging.getLogger('psycopg2').setLevel(logging.WARNING)
        
        logging.info("Logging initialized")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logging.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_event.set()
    
    async def initialize(self):
        """Initialize all components"""
        logging.info("Initializing crawler components...")
        
        # Create output directory
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        # Initialize Redis
        try:
            self.redis_client = redis.from_url(
                self.config.redis_url,
                decode_responses=False,
                socket_timeout=30,
                socket_connect_timeout=30,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            logging.info("Redis connection established")
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {e}")
            raise
        
        # Initialize PostgreSQL storage
        try:
            self.storage = PostgresStorage(
                self.config.postgres_url,
                pool_size=3  # Small pool for memory efficiency
            )
            await self.storage.initialize()
            logging.info("PostgreSQL storage initialized")
        except Exception as e:
            logging.error(f"Failed to initialize storage: {e}")
            raise
        
        # Initialize crawler
        self.crawler = WebCrawler(
            self.config,
            self.resource_monitor,
            self.storage,
            self.redis_client
        )
        await self.crawler.initialize()
        logging.info("Crawler initialized")
    
    async def run(self):
        """Main application loop"""
        logging.info("Starting crawler application...")
        
        try:
            await self.initialize()
            
            # Log initial system state
            memory_mb = self.resource_monitor.get_memory_usage_mb()
            logging.info(f"Initial memory usage: {memory_mb:.1f}MB")
            logging.info(f"System info: {psutil.cpu_count()} CPUs, {psutil.virtual_memory().total // 1024 // 1024}MB total RAM")
            
            # Start periodic health checks
            health_check_task = asyncio.create_task(self._health_check_loop())
            
            # Start main crawler
            max_pages = int(os.getenv('MAX_PAGES', '10000'))
            crawler_task = asyncio.create_task(self.crawler.run_crawler(max_pages))
            
            # Wait for completion or shutdown signal
            done, pending = await asyncio.wait(
                [crawler_task, health_check_task, asyncio.create_task(self.shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            logging.info("Crawler completed")
            
        except Exception as e:
            logging.error(f"Application error: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()
    
    async def _health_check_loop(self):
        """Periodic health monitoring"""
        while not self.shutdown_event.is_set():
            try:
                memory_mb = self.resource_monitor.get_memory_usage_mb()
                cpu_pct = self.resource_monitor.get_cpu_percent()
                
                # Log resource usage
                if memory_mb > self.config.max_memory_mb * 0.8:
                    logging.warning(f"High memory usage: {memory_mb:.1f}MB")
                
                if cpu_pct > self.config.max_cpu_percent * 0.8:
                    logging.warning(f"High CPU usage: {cpu_pct:.1f}%")
                
                # Check Redis connectivity
                try:
                    self.redis_client.ping()
                except Exception as e:
                    logging.error(f"Redis health check failed: {e}")
                
                # Emergency brake if memory is critical
                if memory_mb > self.config.max_memory_mb * 0.95:
                    logging.critical("Critical memory usage - forcing cleanup")
                    self.resource_monitor.force_cleanup()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Health check error: {e}")
                await asyncio.sleep(30)
    
    async def cleanup(self):
        """Cleanup resources"""
        logging.info("Cleaning up resources...")
        
        if self.crawler:
            await self.crawler.cleanup()
        
        if self.storage:
            await self.storage.close()
        
        if self.redis_client:
            try:
                self.redis_client.close()
            except:
                pass
        
        logging.info("Cleanup completed")

async def main():
    """Main entry point"""
    config_path = os.getenv('CONFIG_PATH', 'config.yaml')
    
    app = CrawlerApp(config_path)
    
    try:
        await app.run()
    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
    except Exception as e:
        logging.error(f"Application failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Run the crawler
    asyncio.run(main())