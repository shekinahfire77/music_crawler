# Create the core crawler implementation
crawler_core = textwrap.dedent("""
#!/usr/bin/env python3
\"\"\"
Core crawler implementation with resource management and async processing
\"\"\"

import asyncio
import aiohttp
import time
import logging
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse, urljoin
from datetime import datetime
import json
import random

class RobotsCache:
    \"\"\"Cache and manage robots.txt files\"\"\"
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 hour
    
    async def can_fetch(self, url: str, session: aiohttp.ClientSession) -> bool:
        \"\"\"Check if URL can be fetched according to robots.txt\"\"\"
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
            
            # Simple robots.txt parsing (basic implementation)
            if robots_txt:
                lines = robots_txt.lower().split('\\n')
                user_agent_section = False
                for line in lines:
                    line = line.strip()
                    if line.startswith('user-agent:'):
                        ua = line.split(':', 1)[1].strip()
                        user_agent_section = ua == '*' or 'musiccrawler' in ua
                    elif user_agent_section and line.startswith('disallow:'):
                        disallow_path = line.split(':', 1)[1].strip()
                        if disallow_path and (disallow_path == '/' or parsed.path.startswith(disallow_path)):
                            return False
            
            return True
            
        except Exception as e:
            logging.warning(f"Robots.txt check failed for {url}: {e}")
            return True  # Be generous on errors

class URLFrontier:
    \"\"\"Manage crawl frontier with Redis backend\"\"\"
    
    def __init__(self, redis_client, config):
        self.redis = redis_client
        self.config = config
        self.seen_urls = set()  # In-memory recent filter
        self.max_seen = 10000  # Limit in-memory set size
        
    def _url_key(self, url: str) -> str:
        \"\"\"Generate cache key for URL\"\"\"
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()
    
    async def add_url(self, url: str, priority: int = 0, depth: int = 0):
        \"\"\"Add URL to frontier\"\"\"
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
        \"\"\"Get next URL from frontier\"\"\"
        result = self.redis.zpopmax("frontier", 1)
        if result:
            data = json.loads(result[0][0])
            return data
        return None
    
    def get_queue_size(self) -> int:
        \"\"\"Get current frontier queue size\"\"\"
        return self.redis.zcard("frontier")

class HostScheduler:
    \"\"\"Manage per-host politeness and rate limiting\"\"\"
    
    def __init__(self, redis_client, config):
        self.redis = redis_client
        self.config = config
    
    async def can_crawl_host(self, url: str) -> bool:
        \"\"\"Check if we can crawl this host now\"\"\"
        parsed = urlparse(url)
        host = parsed.netloc
        
        last_crawl_key = f"last_crawl:{host}"
        last_crawl = self.redis.get(last_crawl_key)
        
        if last_crawl:
            last_time = float(last_crawl)
            min_delay = self.config.default_delay
            
            if time.time() - last_time < min_delay:
                return False
        
        # Update last crawl time
        self.redis.set(last_crawl_key, time.time(), ex=3600)
        return True
    
    async def record_crawl(self, url: str, success: bool):
        \"\"\"Record crawl attempt\"\"\"
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

class WebCrawler:
    \"\"\"Main crawler class with bounded concurrency\"\"\"
    
    def __init__(self, config, resource_monitor, storage, redis_client):
        self.config = config
        self.resource_monitor = resource_monitor
        self.storage = storage
        self.redis = redis_client
        
        # Initialize components
        self.robots_cache = RobotsCache(redis_client)
        self.frontier = URLFrontier(redis_client, config)
        self.host_scheduler = HostScheduler(redis_client, config)
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(config.initial_concurrency)
        self.current_concurrency = config.initial_concurrency
        self.session = None
        
        # Stats
        self.stats = {
            'urls_processed': 0,
            'urls_successful': 0,
            'urls_failed': 0,
            'start_time': time.time()
        }
    
    async def initialize(self):
        \"\"\"Initialize the crawler\"\"\"
        # Create aiohttp session with optimized settings
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=10,  # Max connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        )
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={'User-Agent': self.config.user_agent}
        )
        
        # Initialize storage
        await self.storage.initialize()
        
        # Seed initial URLs
        await self._seed_initial_urls()
    
    async def _seed_initial_urls(self):
        \"\"\"Seed the frontier with initial URLs\"\"\"
        seed_urls = []
        
        for domain in self.config.target_domains:
            # Add main domain pages
            seed_urls.extend([
                f"https://{domain}/",
                f"https://{domain}/sitemap.xml",
                f"https://{domain}/robots.txt"
            ])
            
            # Domain-specific seeds
            if 'ultimate-guitar' in domain:
                seed_urls.extend([
                    f"https://{domain}/tabs",
                    f"https://{domain}/chords"
                ])
            elif 'bandcamp' in domain:
                seed_urls.extend([
                    f"https://{domain}/discover",
                    f"https://{domain}/tag"
                ])
            elif 'last.fm' in domain:
                seed_urls.extend([
                    f"https://{domain}/music",
                    f"https://{domain}/charts"
                ])
        
        # Add to frontier
        for url in seed_urls:
            await self.frontier.add_url(url, priority=10, depth=0)
        
        logging.info(f"Seeded {len(seed_urls)} initial URLs")
    
    async def adjust_concurrency(self):
        \"\"\"Dynamically adjust concurrency based on resources\"\"\"
        if self.resource_monitor.should_scale_down():
            if self.current_concurrency > self.config.min_concurrency:
                self.current_concurrency = max(
                    self.config.min_concurrency,
                    self.current_concurrency - 2
                )
                # Create new semaphore with reduced capacity
                self.semaphore = asyncio.Semaphore(self.current_concurrency)
                logging.info(f"Scaled down concurrency to {self.current_concurrency}")
                
        elif self.resource_monitor.should_scale_up():
            if self.current_concurrency < self.config.max_concurrency:
                self.current_concurrency = min(
                    self.config.max_concurrency,
                    self.current_concurrency + 2
                )
                # Create new semaphore with increased capacity
                self.semaphore = asyncio.Semaphore(self.current_concurrency)
                logging.info(f"Scaled up concurrency to {self.current_concurrency}")
    
    async def crawl_url(self, url_data: Dict) -> Optional[Dict]:
        \"\"\"Crawl a single URL\"\"\"
        url = url_data['url']
        depth = url_data.get('depth', 0)
        
        # Resource and politeness checks
        if not await self.host_scheduler.can_crawl_host(url):
            # Re-queue for later
            await self.frontier.add_url(url, depth=depth)
            return None
        
        if not await self.robots_cache.can_fetch(url, self.session):
            logging.debug(f"Robots.txt disallows {url}")
            await self.host_scheduler.record_crawl(url, False)
            return None
        
        start_time = time.time()
        
        try:
            async with self.session.get(url, 
                                       max_redirects=3,
                                       allow_redirects=True) as response:
                
                # Check content length
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > self.config.max_content_length:
                    logging.warning(f"Content too large: {url} ({content_length} bytes)")
                    return None
                
                # Read response
                content = await response.read()
                if len(content) > self.config.max_content_length:
                    content = content[:self.config.max_content_length]
                
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Process content
                html = content.decode('utf-8', errors='ignore')
                result = await self._process_content(url, html, depth, 
                                                   len(content), response_time_ms)
                
                await self.host_scheduler.record_crawl(url, True)
                self.stats['urls_successful'] += 1
                
                return result
                
        except Exception as e:
            logging.warning(f"Failed to crawl {url}: {e}")
            await self.storage.store_error(url, type(e).__name__, str(e))
            await self.host_scheduler.record_crawl(url, False)
            self.stats['urls_failed'] += 1
            return None
    
    async def _process_content(self, url: str, html: str, depth: int, 
                             response_size: int, response_time_ms: int) -> Dict:
        \"\"\"Process HTML content and extract data\"\"\"
        from crawler_content import ContentExtractor
        
        # Extract content
        content_data = ContentExtractor.extract_content(html, url)
        
        # Extract links for further crawling
        links = ContentExtractor.extract_links(html, url)
        
        # Filter and add new URLs to frontier
        new_urls = 0
        for link in links[:50]:  # Limit links per page
            parsed = urlparse(link)
            if any(domain in parsed.netloc for domain in self.config.target_domains):
                await self.frontier.add_url(link, depth=depth + 1)
                new_urls += 1
        
        # Store result
        await self.storage.store_result(
            url, content_data, len(links), depth, response_size, response_time_ms
        )
        
        logging.debug(f"Processed {url}: {len(links)} links, {new_urls} added")
        
        return {
            'url': url,
            'links_found': len(links),
            'links_added': new_urls,
            'content_data': content_data
        }
    
    async def run_crawler(self, max_pages: int = 10000):
        \"\"\"Main crawler loop\"\"\"
        logging.info(f"Starting crawler with max {max_pages} pages")
        
        async def worker():
            while self.stats['urls_processed'] < max_pages:
                async with self.semaphore:
                    # Get next URL
                    url_data = await self.frontier.get_url()
                    if not url_data:
                        await asyncio.sleep(1)  # No URLs available
                        continue
                    
                    # Crawl URL
                    self.stats['urls_processed'] += 1
                    result = await self.crawl_url(url_data)
                    
                    # Periodic resource adjustment
                    if self.stats['urls_processed'] % 10 == 0:
                        await self.adjust_concurrency()
                        
                        # Force cleanup every 100 pages
                        if self.stats['urls_processed'] % 100 == 0:
                            self.resource_monitor.force_cleanup()
                            await self._log_stats()
        
        # Start worker tasks
        workers = [asyncio.create_task(worker()) for _ in range(self.current_concurrency)]
        
        try:
            await asyncio.gather(*workers, return_exceptions=True)
        except KeyboardInterrupt:
            logging.info("Crawler interrupted by user")
        finally:
            await self.cleanup()
    
    async def _log_stats(self):
        \"\"\"Log current statistics\"\"\"
        runtime = time.time() - self.stats['start_time']
        memory_mb = self.resource_monitor.get_memory_usage_mb()
        cpu_pct = self.resource_monitor.get_cpu_percent()
        queue_size = self.frontier.get_queue_size()
        
        logging.info(
            f"Stats: {self.stats['urls_processed']} processed, "
            f"{self.stats['urls_successful']} successful, "
            f"{self.stats['urls_failed']} failed, "
            f"{memory_mb:.1f}MB RAM, {cpu_pct:.1f}% CPU, "
            f"{queue_size} queued, {runtime:.0f}s runtime"
        )
    
    async def cleanup(self):
        \"\"\"Cleanup resources\"\"\"
        if self.session:
            await self.session.close()
        
        # Export final results
        output_path = f"{self.config.output_dir}/crawl_results_{int(time.time())}.csv"
        await self.storage.export_results_csv(output_path)
        
        await self._log_stats()
        logging.info("Crawler cleanup completed")
""")

with open("crawler_core.py", "w", encoding="utf-8") as f:
    f.write(crawler_core)

print("Created crawler_core.py")
print(f"Length: {len(crawler_core)} characters")