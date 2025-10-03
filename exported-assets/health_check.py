#!/usr/bin/env python3
"""
Health check service for the web crawler
Provides monitoring endpoint and basic statistics
"""

import os
import json
import redis
import psycopg2
from flask import Flask, jsonify, render_template_string
from datetime import datetime
import psutil

app = Flask(__name__)

# Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/crawler')

def get_redis_stats():
    """Get Redis statistics"""
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        info = r.info()
        
        return {
            'connected': True,
            'memory_used': info.get('used_memory_human'),
            'connected_clients': info.get('connected_clients'),
            'total_commands': info.get('total_commands_processed'),
            'keyspace_hits': info.get('keyspace_hits'),
            'keyspace_misses': info.get('keyspace_misses')
        }
    except Exception as e:
        return {'connected': False, 'error': str(e)}

def get_database_stats():
    """Get database statistics"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            # Get total results
            cur.execute("SELECT COUNT(*) FROM crawl_results")
            total_results = cur.fetchone()[0]
            
            # Get results by domain
            cur.execute("""
                SELECT domain, COUNT(*) as count 
                FROM crawl_results 
                GROUP BY domain 
                ORDER BY count DESC 
                LIMIT 10
            """)
            top_domains = cur.fetchall()
            
            # Get recent activity
            cur.execute("""
                SELECT COUNT(*) FROM crawl_results 
                WHERE crawled_at >= NOW() - INTERVAL '1 hour'
            """)
            recent_results = cur.fetchone()[0]
            
            # Get error count
            cur.execute("SELECT COUNT(*) FROM crawl_errors")
            total_errors = cur.fetchone()[0]
        
        conn.close()
        
        return {
            'connected': True,
            'total_results': total_results,
            'recent_results': recent_results,
            'total_errors': total_errors,
            'top_domains': [{'domain': d[0], 'count': d[1]} for d in top_domains]
        }
    except Exception as e:
        return {'connected': False, 'error': str(e)}

def get_system_stats():
    """Get system resource statistics"""
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        
        return {
            'memory_total_mb': memory.total // 1024 // 1024,
            'memory_used_mb': memory.used // 1024 // 1024,
            'memory_percent': memory.percent,
            'cpu_percent': cpu_percent,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {'error': str(e)}

@app.route('/health')
def health_check():
    """Basic health check endpoint"""
    redis_stats = get_redis_stats()
    db_stats = get_database_stats()
    system_stats = get_system_stats()
    
    status = 'healthy' if (redis_stats.get('connected') and db_stats.get('connected')) else 'unhealthy'
    
    return jsonify({
        'status': status,
        'timestamp': datetime.now().isoformat(),
        'services': {
            'redis': redis_stats,
            'database': db_stats,
            'system': system_stats
        }
    })

@app.route('/stats')
def crawler_stats():
    """Detailed crawler statistics"""
    redis_stats = get_redis_stats()
    db_stats = get_database_stats()
    system_stats = get_system_stats()
    
    # Get frontier queue size
    try:
        r = redis.from_url(REDIS_URL, decode_responses=False)
        queue_size = r.zcard('frontier')
    except:
        queue_size = 0
    
    return jsonify({
        'crawler': {
            'queue_size': queue_size,
            'total_crawled': db_stats.get('total_results', 0),
            'recent_activity': db_stats.get('recent_results', 0),
            'error_count': db_stats.get('total_errors', 0),
            'top_domains': db_stats.get('top_domains', [])
        },
        'system': system_stats,
        'redis': redis_stats,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/')
def dashboard():
    """Simple dashboard view"""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Music Crawler Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .healthy { background-color: #d4edda; border: 1px solid #c3e6cb; }
            .unhealthy { background-color: #f8d7da; border: 1px solid #f5c6cb; }
            .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .card { border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
            .card h3 { margin-top: 0; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        </style>
        <script>
            async function updateStats() {
                try {
                    const response = await fetch('/stats');
                    const data = await response.json();
                    document.getElementById('stats').innerHTML = JSON.stringify(data, null, 2);
                } catch (error) {
                    console.error('Failed to update stats:', error);
                }
            }
            
            setInterval(updateStats, 30000); // Update every 30 seconds
        </script>
    </head>
    <body>
        <h1>🎵 Music Crawler Dashboard</h1>
        
        <div id="status" class="status">
            <h2>System Status</h2>
            <p>Loading...</p>
        </div>
        
        <div class="stats">
            <div class="card">
                <h3>📊 Quick Stats</h3>
                <div id="quick-stats">Loading...</div>
            </div>
            
            <div class="card">
                <h3>🔧 System Resources</h3>
                <div id="resources">Loading...</div>
            </div>
        </div>
        
        <div class="card">
            <h3>📈 Detailed Statistics</h3>
            <pre id="stats">Loading...</pre>
        </div>
        
        <script>
            async function loadDashboard() {
                try {
                    // Load health status
                    const healthResponse = await fetch('/health');
                    const healthData = await healthResponse.json();
                    
                    const statusEl = document.getElementById('status');
                    statusEl.className = `status ${healthData.status}`;
                    statusEl.innerHTML = `<h2>System Status: ${healthData.status.toUpperCase()}</h2>`;
                    
                    // Load stats
                    const statsResponse = await fetch('/stats');
                    const statsData = await statsResponse.json();
                    
                    document.getElementById('quick-stats').innerHTML = `
                        <p>Total Pages Crawled: ${statsData.crawler.total_crawled}</p>
                        <p>Recent Activity (1h): ${statsData.crawler.recent_activity}</p>
                        <p>Queue Size: ${statsData.crawler.queue_size}</p>
                        <p>Errors: ${statsData.crawler.error_count}</p>
                    `;
                    
                    document.getElementById('resources').innerHTML = `
                        <p>Memory: ${statsData.system.memory_used_mb}MB / ${statsData.system.memory_total_mb}MB (${statsData.system.memory_percent.toFixed(1)}%)</p>
                        <p>CPU: ${statsData.system.cpu_percent.toFixed(1)}%</p>
                    `;
                    
                    document.getElementById('stats').innerHTML = JSON.stringify(statsData, null, 2);
                    
                } catch (error) {
                    console.error('Failed to load dashboard:', error);
                }
            }
            
            loadDashboard();
            setInterval(loadDashboard, 30000);
        </script>
    </body>
    </html>
    """
    
    return render_template_string(html_template)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)