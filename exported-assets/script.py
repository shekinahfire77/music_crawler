# Let's create the complete web crawler implementation
# I'll start with the main crawler module

crawler_main = '''
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

class RobotsCache:
    """Cache and manage robots.txt files"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 hour
    
    async def can_fetch(self, url: str, session: aiohttp.ClientSession) -> bool:
        """Check if URL can be fetched according to robots.txt"""
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            # Check cache first
            cache_key = f"robots:{parsed.netloc}"
            cached = self.redis.get(cache_key)
            
            if cached:
                robots_txt = cached.decode('utf-8')
            else:
                # Fetch robots.txt
                try:
                    async with session.get(robots_url, timeout=10) as response:
                        if response.status == 200:
                            robots_txt = await response.text()
                            self.redis.setex(cache_key, self.cache_ttl, robots_txt)
                        else:
                            # No robots.txt = allow all
                            robots_txt = ""
                            self.redis.setex(cache_key, self.cache_ttl, "")
                except Exception:
                    # Network error = allow (be generous)
                    robots_txt = ""
                    self.redis.setex(cache_key, 300, "")  # Short cache for errors
            
            # Parse robots.txt
            rp = RobotFileParser()
            rp.set_url(robots_url)
            if robots_txt:
                lines = robots_txt.split('\\n')
                for line in lines:
                    rp.feed(line)
            
            return rp.can_fetch("*", url)
            
        except Exception as e:
            logging.warning(f"Robots.txt check failed for {url}: {e}")
            return True  # Be generous on errors

class URLFrontier:
    """Manage crawl frontier with Redis backend"""
    
    def __init__(self, redis_client, config: CrawlerConfig):
        self.redis = redis_client
        self.config = config
        self.seen_urls: Set[str] = set()  # In-memory recent filter
        self.max_seen = 10000  # Limit in-memory set size
        
    def _url_key(self, url: str) -> str:
        """Generate cache key for URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    async def add_url(self, url: str, priority: int = 0, depth: int = 0):
        """Add URL to frontier"""
        if depth > self.config.max_depth:
            return
            
        url_key = self._url_key(url)
        
        # Check if already seen (in-memory filter)
        if url_key in self.seen_urls:
            return
            
        # Check Redis for more complete deduplication
        if self.redis.exists(f"seen:{url_key}"):
            return
            
        # Add to frontier
        frontier_data = {
            'url': url,
            'priority': priority,
            'depth': depth,
            'added_at': time.time()
        }
        
        self.redis.zadd("frontier", {json.dumps(frontier_data): priority})
        self.redis.setex(f"seen:{url_key}", 86400, "1")  # Mark as seen for 24h
        
        # Add to in-memory filter
        self.seen_urls.add(url_key)
        
        # Trim in-memory set if too large
        if len(self.seen_urls) > self.max_seen:
            # Remove random 20% of entries
            to_remove = random.sample(list(self.seen_urls), self.max_seen // 5)
            for item in to_remove:
                self.seen_urls.discard(item)
    
    async def get_url(self) -> Optional[Dict]:
        """Get next URL from frontier"""
        result = self.redis.zpopmax("frontier", 1)
        if result:
            data = json.loads(result[0][0])
            return data
        return None
    
    def get_queue_size(self) -> int:
        """Get current frontier queue size"""
        return self.redis.zcard("frontier")

class HostScheduler:
    """Manage per-host politeness and rate limiting"""
    
    def __init__(self, redis_client, config: CrawlerConfig):
        self.redis = redis_client
        self.config = config
    
    async def can_crawl_host(self, url: str) -> bool:
        """Check if we can crawl this host now"""
        parsed = urlparse(url)
        host = parsed.netloc
        
        last_crawl_key = f"last_crawl:{host}"
        last_crawl = self.redis.get(last_crawl_key)
        
        if last_crawl:
            last_time = float(last_crawl)
            min_delay = self.config.default_delay
            
            # Check for custom delay in robots.txt cache
            robots_key = f"robots:{host}"
            robots_data = self.redis.get(robots_key)
            if robots_data:
                robots_txt = robots_data.decode('utf-8')
                for line in robots_txt.split('\\n'):
                    if 'crawl-delay' in line.lower():
                        try:
                            delay = float(line.split(':')[1].strip())
                            min_delay = max(min_delay, delay)
                        except:
                            pass
            
            if time.time() - last_time < min_delay:
                return False
        
        # Update last crawl time
        self.redis.set(last_crawl_key, time.time(), ex=3600)
        return True
    
    async def get_host_stats(self, host: str) -> Dict:
        """Get crawling stats for host"""
        today = datetime.now().strftime("%Y-%m-%d")
        count_key = f"count:{host}:{today}"
        error_key = f"errors:{host}:{today}"
        
        return {
            'count': int(self.redis.get(count_key) or 0),
            'errors': int(self.redis.get(error_key) or 0),
            'last_crawl': self.redis.get(f"last_crawl:{host}")
        }
    
    async def record_crawl(self, url: str, success: bool):
        """Record crawl attempt"""
        parsed = urlparse(url)
        host = parsed.netloc
        today = datetime.now().strftime("%Y-%m-%d")
        
        count_key = f"count:{host}:{today}"
        self.redis.incr(count_key)
        self.redis.expire(count_key, 86400)  # Expire after 24h
        
        if not success:
            error_key = f"errors:{host}:{today}"
            self.redis.incr(error_key)
            self.redis.expire(error_key, 86400)

class ContentExtractor:
    """Extract and parse content from HTML"""
    
    @staticmethod
    def extract_links(html: str, base_url: str) -> List[str]:
        """Extract links from HTML using selectolax"""
        try:
            tree = HTMLParser(html)
            links = []
            
            for link in tree.css('a[href]'):
                href = link.attributes.get('href')
                if href:
                    # Resolve relative URLs
                    full_url = urljoin(base_url, href)
                    # Remove fragment
                    full_url, _ = urldefrag(full_url)
                    if full_url.startswith(('http://', 'https://')):
                        links.append(full_url)
            
            return links
        except Exception as e:
            logging.warning(f"Link extraction failed for {base_url}: {e}")
            return []
    
    @staticmethod
    def extract_content(html: str, url: str) -> Dict:
        """Extract structured content from HTML"""
        try:
            tree = HTMLParser(html)
            
            # Basic content extraction
            title = ""
            title_tag = tree.css_first('title')
            if title_tag:
                title = title_tag.text(strip=True)
            
            # Extract text content (sample)
            text_content = ""
            body = tree.css_first('body')
            if body:
                # Get first 500 chars of text
                text_content = body.text(strip=True)[:500]
            
            # Extract meta information
            meta_description = ""
            meta_tag = tree.css_first('meta[name="description"]')
            if meta_tag:
                meta_description = meta_tag.attributes.get('content', '')
            
            # Music-specific extraction
            music_data = ContentExtractor._extract_music_data(tree, url)
            
            return {
                'title': title,
                'description': meta_description,
                'text_sample': text_content,
                'music_data': music_data,
                'extracted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.warning(f"Content extraction failed for {url}: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def _extract_music_data(tree: HTMLParser, url: str) -> Dict:
        """Extract music-specific data based on domain"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        music_data = {}
        
        try:
            if 'ultimate-guitar' in domain:
                # Extract chord/tab information
                song_title = tree.css_first('.t_title')
                if song_title:
                    music_data['song_title'] = song_title.text(strip=True)
                
                artist = tree.css_first('.t_artist')
                if artist:
                    music_data['artist'] = artist.text(strip=True)
                
                rating = tree.css_first('.rating')
                if rating:
                    music_data['rating'] = rating.text(strip=True)
            
            elif 'bandcamp' in domain:
                # Extract album/track info
                track_title = tree.css_first('.trackTitle')
                if track_title:
                    music_data['track_title'] = track_title.text(strip=True)
                
                artist_name = tree.css_first('.albumTitle')
                if artist_name:
                    music_data['album_title'] = artist_name.text(strip=True)
            
            elif 'last.fm' in domain:
                # Extract artist/track/album info
                for selector in ['.header-new-title', '.artist-name', '.album-name']:
                    element = tree.css_first(selector)
                    if element:
                        music_data[selector.replace('.', '').replace('-', '_')] = element.text(strip=True)
            
            elif 'discogs' in domain:
                # Extract release information
                release_title = tree.css_first('.profile-title')
                if release_title:
                    music_data['release_title'] = release_title.text(strip=True)
                
                artist = tree.css_first('.profile-artist')
                if artist:
                    music_data['release_artist'] = artist.text(strip=True)
        
        except Exception as e:
            logging.debug(f"Music data extraction failed for {domain}: {e}")
        
        return music_data

class PostgresStorage:
    """PostgreSQL storage for crawl results"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None
    
    async def initialize(self):
        """Initialize database tables"""
        import psycopg2.extensions
        psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)
        
        conn = psycopg2.connect(self.connection_string)
        with conn.cursor() as cur:
            # Create tables
            cur.execute("""
                CREATE TABLE IF NOT EXISTS crawl_results (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    domain TEXT NOT NULL,
                    title TEXT,
                    content_data JSONB,
                    links_count INTEGER DEFAULT 0,
                    crawled_at TIMESTAMP DEFAULT NOW(),
                    depth INTEGER DEFAULT 0,
                    response_size INTEGER DEFAULT 0,
                    response_time_ms INTEGER DEFAULT 0
                );
                
                CREATE INDEX IF NOT EXISTS idx_crawl_results_domain 
                ON crawl_results(domain);
                
                CREATE INDEX IF NOT EXISTS idx_crawl_results_crawled_at 
                ON crawl_results(crawled_at);
                
                CREATE TABLE IF NOT EXISTS crawl_errors (
                    id SERIAL PRIMARY KEY,
                    url TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    error_message TEXT,
                    occurred_at TIMESTAMP DEFAULT NOW(),
                    retry_count INTEGER DEFAULT 0
                );
            """)
            conn.commit()
        conn.close()
    
    async def store_result(self, url: str, content_data: Dict, 
                          links_count: int = 0, depth: int = 0,
                          response_size: int = 0, response_time_ms: int = 0):
        """Store crawl result"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            
            conn = psycopg2.connect(self.connection_string)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO crawl_results 
                    (url, domain, title, content_data, links_count, depth, response_size, response_time_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE SET
                        content_data = EXCLUDED.content_data,
                        crawled_at = NOW()
                """, (
                    url, domain, 
                    content_data.get('title', ''),
                    json.dumps(content_data),
                    links_count, depth, response_size, response_time_ms
                ))
                conn.commit()
            conn.close()
            
        except Exception as e:
            logging.error(f"Failed to store result for {url}: {e}")
    
    async def store_error(self, url: str, error_type: str, error_message: str, retry_count: int = 0):
        """Store crawl error"""
        try:
            conn = psycopg2.connect(self.connection_string)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO crawl_errors (url, error_type, error_message, retry_count)
                    VALUES (%s, %s, %s, %s)
                """, (url, error_type, error_message, retry_count))
                conn.commit()
            conn.close()
            
        except Exception as e:
            logging.error(f"Failed to store error for {url}: {e}")
    
    async def export_results_csv(self, output_path: str, limit: int = 10000):
        """Export results to CSV"""
        try:
            conn = psycopg2.connect(self.connection_string)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT url, domain, title, content_data->>'text_sample' as text_sample,
                           links_count, crawled_at, depth, response_size
                    FROM crawl_results 
                    ORDER BY crawled_at DESC 
                    LIMIT %s
                """, (limit,))
                
                with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['url', 'domain', 'title', 'text_sample', 'links_count', 'crawled_at', 'depth', 'response_size'])
                    
                    for row in cur.fetchall():
                        writer.writerow(row)
            
            conn.close()
            logging.info(f"Exported results to {output_path}")
            
        except Exception as e:
            logging.error(f"Failed to export results: {e}")

# Save the main crawler code to a file
with open("crawler_main.py", "w") as f:
    f.write(crawler_main)

print("Created crawler_main.py - Main crawler implementation")
print(f"File size: {len(crawler_main)} characters")