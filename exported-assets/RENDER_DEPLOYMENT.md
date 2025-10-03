# 🚀 Render Deployment Guide for Music Web Crawler

## Step-by-Step Render Deployment

### 1. Prerequisites Setup

**A. GitHub Repository**
1. Create a new repository on GitHub
2. Clone this repository locally:
```bash
git clone https://github.com/yourusername/music-crawler.git
cd music-crawler
```
3. Add all crawler files to the repository:
```bash
git add .
git commit -m "Initial crawler implementation"
git push origin main
```

**B. Render Account**
- Sign up at [render.com](https://render.com) if you haven't already
- Connect your GitHub account to Render

### 2. Create Required Services

**A. PostgreSQL Database**
1. Go to Render Dashboard → New → PostgreSQL
2. Configure:
   - **Name**: `music-crawler-db`
   - **Plan**: Starter ($7/month) - 256MB RAM, 1GB storage
   - **PostgreSQL Version**: 15
3. Note the connection details (will be auto-populated in `DATABASE_URL`)

**B. Redis Instance**
1. Go to Render Dashboard → New → Redis
2. Configure:
   - **Name**: `music-crawler-redis`
   - **Plan**: Starter ($7/month) - 25MB RAM
   - **Maxmemory Policy**: `allkeys-lru`
3. Note the connection URL (will be auto-populated in `REDIS_URL`)

### 3. Deploy Background Worker

**A. Create Background Worker Service**
1. Go to Render Dashboard → New → Background Worker
2. Connect your GitHub repository
3. Configure the service:

```yaml
Service Configuration:
├── Name: music-crawler-worker
├── Environment: Python 3
├── Branch: main
├── Build Command: chmod +x build.sh && ./build.sh
├── Start Command: python app.py
└── Instance Type: Starter ($7/month)
```

**B. Environment Variables**
Set these in the Render dashboard under Environment Variables:

```bash
# Required (auto-populated by Render)
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://user:pass@host:port

# Crawler Configuration
MAX_MEMORY_MB=450
MAX_CPU_PERCENT=60
INITIAL_CONCURRENCY=10
MAX_CONCURRENCY=15
MAX_PAGES=10000

# Logging & Output
LOG_LEVEL=INFO
OUTPUT_DIR=/tmp/output
USER_AGENT=MusicCrawler/1.0 (+https://your-domain.com)

# Optional: Custom domains (comma-separated)
# TARGET_DOMAINS=ultimate-guitar.com,bandcamp.com,last.fm
```

### 4. Advanced Configuration (Optional)

**A. Custom Build Configuration**
If you need custom build steps, create `.render.yaml` in your repository root:

```yaml
services:
  - type: worker
    name: music-crawler
    env: python
    plan: starter
    buildCommand: pip install -r requirements.txt
    startCommand: python app.py
    envVars:
      - key: MAX_MEMORY_MB
        value: 450
      - key: MAX_CPU_PERCENT
        value: 60
      - key: INITIAL_CONCURRENCY
        value: 10
```

**B. Health Check Service (Optional)**
If you want a web interface for monitoring:

1. Create new Web Service
2. Same repository, different start command:
```bash
Start Command: python health_check.py
Port: 10000
```

### 5. Deployment Process

**A. Initial Deployment**
1. Click "Create Background Worker"
2. Render will automatically:
   - Clone your repository
   - Run the build command
   - Install dependencies
   - Start the crawler

**B. Monitor Deployment**
Watch the build logs for:
```
🚀 Starting Render build process...
📦 Installing Python dependencies...
✅ All dependencies installed successfully
🎉 Build completed successfully!
```

**C. Verify Services**
Check that all services are running:
- ✅ PostgreSQL: Connected
- ✅ Redis: Connected  
- ✅ Background Worker: Running

### 6. Post-Deployment Monitoring

**A. Check Logs**
Monitor the crawler through Render's log viewer:
```
2024-10-03 04:05:15 - INFO - Starting crawler with max 10000 pages
2024-10-03 04:05:16 - INFO - Redis connection established
2024-10-03 04:05:17 - INFO - PostgreSQL storage initialized
2024-10-03 04:05:18 - INFO - Crawler initialized
2024-10-03 04:05:20 - INFO - Seeded 48 initial URLs
```

**B. Resource Usage**
Watch for memory and CPU usage patterns:
```
2024-10-03 04:06:15 - INFO - Stats: 100 processed, 95 successful, 5 failed, 234.5MB RAM, 45.2% CPU, 500 queued
```

**C. Database Verification**
Connect to your PostgreSQL database to verify data:
```sql
SELECT COUNT(*) FROM crawl_results;
SELECT domain, COUNT(*) FROM crawl_results GROUP BY domain;
```

### 7. Scaling and Optimization

**A. Performance Tuning**
Adjust environment variables based on performance:

```bash
# For better performance (if within limits)
MAX_CONCURRENCY=20
MAX_PAGES_PER_DOMAIN=2000

# For memory conservation
MAX_CONCURRENCY=8
MAX_CONTENT_LENGTH=512000
```

**B. Multiple Workers**
Scale horizontally by creating additional workers:
1. Create second background worker
2. Same configuration, different name
3. Both workers will share Redis/PostgreSQL

**C. Upgrade Plans**
Consider upgrading if needed:
- **Standard**: 1 CPU, 2GB RAM ($25/month)
- **Pro**: 2 CPU, 4GB RAM ($85/month)

### 8. Troubleshooting

**A. Common Issues**

**Build Failures:**
```bash
# Check Python version
python --version  # Should be 3.9+

# Verify dependencies
pip check
```

**Memory Issues:**
```bash
# Reduce concurrency
MAX_CONCURRENCY=5
MAX_MEMORY_MB=400
```

**Connection Issues:**
```bash
# Verify environment variables
echo $DATABASE_URL
echo $REDIS_URL
```

**B. Debug Commands**
Add these to troubleshoot:
```bash
# Test connections
python -c "import redis; r=redis.from_url('$REDIS_URL'); print(r.ping())"
python -c "import psycopg2; conn=psycopg2.connect('$DATABASE_URL'); print('DB OK')"

# Check memory
python -c "import psutil; print(f'RAM: {psutil.virtual_memory().total//1024//1024}MB')"
```

### 9. Cost Optimization

**Monthly Costs (Starter Plans):**
- Background Worker: $7/month
- PostgreSQL: $7/month  
- Redis: $7/month
- **Total**: $21/month

**Cost Reduction Tips:**
- Use shared databases for multiple projects
- Consider free tier alternatives for development
- Monitor usage to avoid overages

### 10. Maintenance

**A. Regular Tasks**
- Monitor crawler performance weekly
- Check database size monthly
- Update dependencies quarterly
- Review and rotate logs

**B. Updates**
To update the crawler:
```bash
git add .
git commit -m "Update crawler configuration"
git push origin main
# Render will auto-deploy
```

**C. Backup**
Regular database backups:
- Render provides automatic backups
- Export CSV data weekly for extra safety

## Ready to Deploy! 🎉

Your crawler is now production-ready for Render. The system will automatically:
- Scale resources based on load
- Respect robots.txt and rate limits
- Store data efficiently in PostgreSQL
- Provide comprehensive logging and monitoring

Start with the Starter plan and scale up as needed based on your crawling requirements!