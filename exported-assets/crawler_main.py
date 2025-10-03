
#!/usr/bin/env python3
"""
Production-Grade Continuous Hybrid Roaming Web Crawler for Render
Optimized for 0.5 vCPU and 512MB RAM constraints

Architecture:
- Asyncio/aiohttp for non-blocking I/O
- Redis for crawl frontier and rate limiting
- PostgreSQL for results storage
- Lightweight HTML parsing with selectolax
- Comprehensive resource management and scaling
"""

import asyncio
import aiohttp
import aiofiles
import redis
import psycopg2
import psycopg2.extras
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
import os
import sys
import json
import time
import gc
import logging
import hashlib
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Set, List, Dict, Optional, Tuple
import yaml
import psutil
import signal
from selectolax.parser import HTMLParser
import csv

# Configuration
@dataclass
class CrawlerConfig:
    """Crawler configuration with resource constraints"""
    # Resource limits
    max_memory_mb: int = 450  # Leave 62MB buffer from 512MB limit
    max_cpu_percent: float = 60.0
    initial_concurrency: int = 10
    max_concurrency: int = 20
    min_concurrency: int = 5

    # Request settings
    request_timeout: int = 30
    max_content_length: int = 1024 * 1024  # 1MB max page size
    user_agent: str = "MusicCrawler/1.0 (+https://github.com/musiccrawler)"

    # Politeness
    default_delay: float = 1.0  # Default 1 RPS per host
    robots_cache_ttl: int = 3600  # Cache robots.txt for 1 hour
    max_pages_per_domain: int = 1000  # Conservative limit
    max_depth: int = 5

    # Storage
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    postgres_url: str = os.getenv("DATABASE_URL", "postgresql://localhost/crawler")

    # Output
    output_dir: str = "./output"
    log_level: str = "INFO"

    # Target domains
    target_domains: List[str] = None

    def __post_init__(self):
        if self.target_domains is None:
            self.target_domains = [
                "ultimate-guitar.com",
                "azchords.com", 
                "e-chords.com",
                "chordie.com",
                "songsterr.com",
                "chordify.com",
                "azlyrics.com",
                "bandcamp.com",
                "soundcloud.com",
                "last.fm",
                "discogs.com",
                "musicbrainz.org",
                "reverbnation.com",
                "pitchfork.com",
                "allmusic.com",
                "rateyourmusic.com"
            ]

class ResourceMonitor:
    """Monitor and manage system resources"""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.process = psutil.Process()
        self.start_time = time.time()

    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB"""
        return self.process.memory_info().rss / 1024 / 1024

    def get_cpu_percent(self) -> float:
        """Get current CPU usage percentage"""
        return self.process.cpu_percent()

    def should_scale_down(self) -> bool:
        """Check if we should reduce concurrency"""
        memory_mb = self.get_memory_usage_mb()
        cpu_pct = self.get_cpu_percent()

        return (memory_mb > self.config.max_memory_mb * 0.85 or 
                cpu_pct > self.config.max_cpu_percent * 0.85)

    def should_scale_up(self) -> bool:
        """Check if we can increase concurrency"""
        memory_mb = self.get_memory_usage_mb()
        cpu_pct = self.get_cpu_percent()

        return (memory_mb < self.config.max_memory_mb * 0.7 and 
                cpu_pct < self.config.max_cpu_percent * 0.7)

    def force_cleanup(self):
        """Force garbage collection and cleanup"""
        gc.collect()
        logging.info(f"Memory cleanup: {self.get_memory_usage_mb():.1f}MB")

if __name__ == "__main__":
    print("Crawler main module - import to use classes and functions")
