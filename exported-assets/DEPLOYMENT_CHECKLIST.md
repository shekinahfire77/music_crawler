# 📋 Render Deployment Checklist

## Pre-Deployment (5 minutes)

### GitHub Setup
- [ ] Create GitHub repository
- [ ] Upload all crawler files to repository
- [ ] Verify `main` branch is ready

### Render Account
- [ ] Create account at render.com
- [ ] Connect GitHub account
- [ ] Verify billing information

## Service Creation (10 minutes)

### Database Services
- [ ] Create PostgreSQL database
  - Name: `music-crawler-db`
  - Plan: Starter ($7/month)
  - Version: PostgreSQL 15
  - Save `DATABASE_URL`

- [ ] Create Redis instance
  - Name: `music-crawler-redis` 
  - Plan: Starter ($7/month)
  - Policy: `allkeys-lru`
  - Save `REDIS_URL`

### Background Worker
- [ ] Create Background Worker service
  - Name: `music-crawler-worker`
  - Environment: Python 3
  - Repository: Your GitHub repo
  - Branch: `main`
  - Build Command: `chmod +x build.sh && ./build.sh`
  - Start Command: `python app.py`
  - Plan: Starter ($7/month)

## Configuration (5 minutes)

### Environment Variables
Set these in the worker's Environment tab:

**Resource Limits:**
- [ ] `MAX_MEMORY_MB` = `450`
- [ ] `MAX_CPU_PERCENT` = `60`
- [ ] `INITIAL_CONCURRENCY` = `10`
- [ ] `MAX_CONCURRENCY` = `15`

**Crawler Settings:**
- [ ] `MAX_PAGES` = `10000`
- [ ] `LOG_LEVEL` = `INFO`
- [ ] `OUTPUT_DIR` = `/tmp/output`
- [ ] `USER_AGENT` = `MusicCrawler/1.0 (+https://your-domain.com)`

**Auto-populated by Render:**
- [ ] `DATABASE_URL` (from PostgreSQL service)
- [ ] `REDIS_URL` (from Redis service)

## Deployment (2 minutes)

### Launch
- [ ] Click "Create Background Worker"
- [ ] Monitor build logs for success messages
- [ ] Verify all services show "Running" status

### Initial Verification
- [ ] Check logs for successful startup:
  ```
  ✅ Redis connection established
  ✅ PostgreSQL storage initialized  
  ✅ Crawler initialized
  ✅ Seeded initial URLs
  ```

## Post-Deployment Monitoring (Ongoing)

### First Hour
- [ ] Monitor memory usage (should be 200-450MB)
- [ ] Check CPU usage (should be 30-60%)
- [ ] Verify pages are being crawled
- [ ] Confirm data is being stored in database

### First Day
- [ ] Check total pages crawled (should be 500-2000)
- [ ] Monitor error rates (should be <10%)
- [ ] Verify robots.txt compliance
- [ ] Review performance metrics

### Weekly
- [ ] Export data to CSV for analysis
- [ ] Review domain-specific statistics
- [ ] Optimize concurrency if needed
- [ ] Clean up old error logs

## Total Monthly Cost: $21

- Background Worker (Starter): $7
- PostgreSQL (Starter): $7  
- Redis (Starter): $7

## Success Metrics

**✅ Deployment Successful When:**
- All services show "Running" status
- Logs show successful database connections
- Pages are being crawled and stored
- Resource usage is within limits

**📊 Performance Targets:**
- 500-2000 pages/hour crawl rate
- <10% error rate
- Memory usage: 200-450MB
- CPU usage: 30-60%

## Quick Commands for Troubleshooting

```bash
# Test database connection
python -c "import psycopg2; conn=psycopg2.connect('$DATABASE_URL'); print('✅ DB Connected')"

# Test Redis connection  
python -c "import redis; r=redis.from_url('$REDIS_URL'); print('✅ Redis:', r.ping())"

# Check system resources
python -c "import psutil; print(f'RAM: {psutil.virtual_memory().available//1024//1024}MB available')"

# Test crawler components
python test_crawler.py
```

## Support Resources

- **Render Docs**: https://render.com/docs
- **PostgreSQL Docs**: https://render.com/docs/databases  
- **Background Workers**: https://render.com/docs/background-workers
- **Environment Variables**: https://render.com/docs/environment-variables

---

**Estimated Total Setup Time: 20 minutes**

**Ready to crawl music websites efficiently! 🎵🚀**