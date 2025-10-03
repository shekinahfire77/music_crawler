# Production-Grade Web Crawler for Render

## Overview

This is a resource-constrained, production-grade continuous hybrid roaming web crawler specifically optimized for Render's 0.5 vCPU and 512MB RAM limits. It's designed to crawl music-related websites efficiently while respecting robots.txt and maintaining politeness.

## Architecture

- **Core Stack**: Python 3.9+ with asyncio/aiohttp for non-blocking I/O
- **Concurrency**: Bounded semaphore with dynamic scaling (10-20 concurrent requests)
- **Storage**: PostgreSQL for results, Redis for frontier queue and rate limiting
- **Parsing**: Lightweight selectolax for HTML processing
- **Resource Management**: Continuous monitoring with automatic scaling and cleanup

## Quick Start

### Local Development

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Setup Environment**:
```bash
# Copy and edit configuration
cp config.yaml config.local.yaml

# Set environment variables
export REDIS_URL="redis://localhost:6379"
export DATABASE_URL="postgresql://localhost/crawler"
export LOG_LEVEL="DEBUG"
```

3. **Initialize Database**:
```bash
# Create database
createdb crawler

# Run initialization (done automatically on first run)
python app.py
```

4. **Run Crawler**:
```bash
python app.py
```

### Render Deployment

#### Prerequisites

1. **Render Account**: Sign up at https://render.com
2. **GitHub Repository**: Push this code to a GitHub repository
3. **Redis Instance**: Create a Redis instance on Render
4. **PostgreSQL Database**: Create a PostgreSQL database on Render

#### Deployment Steps

1. **Create Background Worker Service**:
   - Go to Render Dashboard → New → Background Worker
   - Connect your GitHub repository
   - Configure as follows:

2. **Service Configuration**:
```yaml
Name: music-crawler-worker
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: python app.py
```

3. **Environment Variables**:
```bash
# Required - will be provided by Render
REDIS_URL=redis://your-redis-url
DATABASE_URL=postgresql://your-database-url

# Optional - customize as needed
MAX_MEMORY_MB=450
MAX_CPU_PERCENT=60
INITIAL_CONCURRENCY=10
MAX_CONCURRENCY=15
LOG_LEVEL=INFO
OUTPUT_DIR=/tmp/output
MAX_PAGES=10000
```

4. **Instance Type**:
   - Select "Starter" plan (0.5 CPU, 512MB RAM)
   - Enable auto-scaling if needed

#### Resource Configuration

The crawler is pre-configured for Render's constraints:

- **Memory Limit**: 450MB (62MB buffer)
- **CPU Limit**: 60% usage target
- **Concurrency**: Dynamic scaling 5-20 requests
- **Storage**: External Redis/PostgreSQL (no local storage limits)

## Configuration

### Core Settings (`config.yaml`)

```yaml
# Resource limits
max_memory_mb: 450
max_cpu_percent: 60.0
initial_concurrency: 10
max_concurrency: 20

# Request settings
request_timeout: 30
max_content_length: 1048576  # 1MB
user_agent: "MusicCrawler/1.0"

# Politeness
default_delay: 1.0  # 1 RPS per host
robots_cache_ttl: 3600
max_pages_per_domain: 1000
max_depth: 5
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection string | redis://localhost:6379 |
| `DATABASE_URL` | PostgreSQL connection string | postgresql://localhost/crawler |
| `MAX_MEMORY_MB` | Memory limit in MB | 450 |
| `MAX_CPU_PERCENT` | CPU usage limit | 60.0 |
| `INITIAL_CONCURRENCY` | Starting concurrent requests | 10 |
| `MAX_CONCURRENCY` | Maximum concurrent requests | 20 |
| `LOG_LEVEL` | Logging level | INFO |
| `OUTPUT_DIR` | Output directory | ./output |
| `MAX_PAGES` | Maximum pages to crawl | 10000 |

## Target Websites

The crawler targets music-related websites including:

### Lyrics & Chord Sites
- Ultimate-Guitar.com (tabs, chords, ratings)
- AZChords.com (chord progressions)
- E-Chords (international songs)
- Chordie (chord database)

### Music Platforms
- Bandcamp (independent releases)
- SoundCloud (user-generated content)
- Last.fm (scrobbling data)
- Discogs (music database)

### Review & Discovery
- Pitchfork (reviews)
- AllMusic (comprehensive database)
- RateYourMusic (user ratings)
- MusicBrainz (open encyclopedia)

## Resource Management

### Memory Optimization
- Lightweight HTML parsing with selectolax
- Stream processing for large content
- Limited in-memory URL deduplication (10,000 URLs)
- Automatic garbage collection every 100 pages
- Content length limits (1MB max per page)

### CPU Optimization
- Bounded concurrency with semaphore
- Dynamic scaling based on resource usage
- Exponential backoff on errors
- Per-host rate limiting (1 RPS default)

### Scaling Logic
```python
if memory > 85% or cpu > 85%:
    reduce_concurrency()
elif memory < 70% and cpu < 70%:
    increase_concurrency()
```

## Output & Data Export

### Database Schema

**crawl_results**: Main results table
- url, domain, title, description
- content_data (JSONB), music_data (JSONB)
- response metrics, crawl depth

**music_content**: Extracted music data
- artist_name, track_title, album_title
- genre, rating, tags
- chords_available, tabs_available

**crawl_errors**: Error tracking
- url, error_type, error_message
- retry_count, status_code

### CSV Export
```bash
# Automatic export on completion
/tmp/output/crawl_results_<timestamp>.csv

# Manual export
python -c "
from crawler_storage import PostgresStorage
import asyncio
storage = PostgresStorage(os.getenv('DATABASE_URL'))
asyncio.run(storage.export_results_csv('export.csv'))
"
```

## Monitoring & Health Checks

### Built-in Monitoring
- Memory usage tracking
- CPU usage monitoring
- Redis connectivity checks
- Queue depth monitoring
- Crawl rate statistics

### Log Output
```
2024-01-15 10:30:15 - INFO - Stats: 1000 processed, 950 successful, 50 failed, 234.5MB RAM, 45.2% CPU, 500 queued, 1800s runtime
```

### Health Check Endpoint
The crawler includes a simple health check server:
```bash
# Optional: Add health check service
python health_check.py  # Runs on port 8080
```

## Legal & Ethical Considerations

### Robots.txt Compliance
- Automatic robots.txt fetching and caching
- Respects disallow directives
- Honors crawl-delay settings
- Conservative default behavior

### Rate Limiting
- 1 RPS per host by default
- Respects server-specified delays
- Exponential backoff on errors
- Connection pooling limits

### Content Handling
- Only crawls publicly available content
- Respects copyright and terms of service
- Limited content extraction (samples only)
- No personal data collection

## Troubleshooting

### Common Issues

1. **Memory Errors**:
   - Reduce `max_concurrency`
   - Decrease `max_content_length`
   - Enable more aggressive cleanup

2. **Slow Crawling**:
   - Check robots.txt delays
   - Verify network connectivity
   - Monitor rate limiting

3. **Database Errors**:
   - Check PostgreSQL connection
   - Verify database permissions
   - Monitor connection pool

### Performance Tuning

1. **For Higher Memory Environments**:
```yaml
max_memory_mb: 900  # For 1GB instances
max_concurrency: 30
```

2. **For Slower Sites**:
```yaml
request_timeout: 60
default_delay: 2.0
```

3. **For Higher Volume**:
```yaml
max_pages_per_domain: 5000
max_depth: 7
```

## Scaling for Future

### Browser Automation Support
When resources allow, add browser automation:
```python
# Future enhancement
from playwright.async_api import async_playwright

class BrowserCrawler:
    async def crawl_spa(self, url):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            # Handle JavaScript-heavy sites
```

### Distributed Crawling
For multi-instance deployment:
```yaml
# render.yaml - Multiple workers
services:
  - type: worker
    name: crawler-worker-1
    env: python
    plan: starter
  - type: worker
    name: crawler-worker-2
    env: python
    plan: starter
```

### Advanced Features
- Machine learning for content classification
- Real-time analytics dashboard
- Advanced duplicate detection
- Content similarity analysis

## Support

For issues and questions:
1. Check logs for error details
2. Review resource usage patterns
3. Verify configuration settings
4. Test network connectivity

The crawler is designed to be robust and self-healing, with automatic recovery from most common issues.