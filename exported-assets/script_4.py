# Create the storage module
storage_module = textwrap.dedent("""
#!/usr/bin/env python3
\"\"\"
PostgreSQL storage module for crawler results
Optimized for efficient storage and retrieval
\"\"\"

import psycopg2
import psycopg2.extras
import psycopg2.pool
import json
import csv
import logging
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse
import os

class PostgresStorage:
    \"\"\"PostgreSQL storage for crawl results with connection pooling\"\"\"
    
    def __init__(self, connection_string: str, pool_size: int = 5):
        self.connection_string = connection_string
        self.pool_size = pool_size
        self.pool = None
    
    async def initialize(self):
        \"\"\"Initialize database tables and connection pool\"\"\"
        # Register JSON adapter
        psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)
        
        # Create connection pool
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                1, self.pool_size, self.connection_string
            )
            logging.info(f"Created PostgreSQL connection pool (size: {self.pool_size})")
        except Exception as e:
            logging.error(f"Failed to create connection pool: {e}")
            raise
        
        # Create tables
        await self._create_tables()
    
    async def _create_tables(self):
        \"\"\"Create necessary database tables\"\"\"
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Main crawl results table
                cur.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS crawl_results (
                        id SERIAL PRIMARY KEY,
                        url TEXT UNIQUE NOT NULL,
                        domain TEXT NOT NULL,
                        path TEXT,
                        title TEXT,
                        description TEXT,
                        content_data JSONB,
                        music_data JSONB,
                        structured_data JSONB,
                        links_count INTEGER DEFAULT 0,
                        crawled_at TIMESTAMP DEFAULT NOW(),
                        depth INTEGER DEFAULT 0,
                        response_size INTEGER DEFAULT 0,
                        response_time_ms INTEGER DEFAULT 0,
                        status_code INTEGER DEFAULT 200,
                        content_type TEXT,
                        language TEXT,
                        last_modified TIMESTAMP
                    );
                \"\"\")
                
                # Create indexes for performance
                cur.execute(\"\"\"
                    CREATE INDEX IF NOT EXISTS idx_crawl_results_domain 
                    ON crawl_results(domain);
                \"\"\")
                
                cur.execute(\"\"\"
                    CREATE INDEX IF NOT EXISTS idx_crawl_results_crawled_at 
                    ON crawl_results(crawled_at);
                \"\"\")
                
                cur.execute(\"\"\"
                    CREATE INDEX IF NOT EXISTS idx_crawl_results_music_data 
                    ON crawl_results USING GIN(music_data);
                \"\"\")
                
                # Crawl errors table
                cur.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS crawl_errors (
                        id SERIAL PRIMARY KEY,
                        url TEXT NOT NULL,
                        domain TEXT NOT NULL,
                        error_type TEXT NOT NULL,
                        error_message TEXT,
                        status_code INTEGER,
                        occurred_at TIMESTAMP DEFAULT NOW(),
                        retry_count INTEGER DEFAULT 0,
                        resolved BOOLEAN DEFAULT FALSE
                    );
                \"\"\")
                
                cur.execute(\"\"\"
                    CREATE INDEX IF NOT EXISTS idx_crawl_errors_domain 
                    ON crawl_errors(domain);
                \"\"\")
                
                # Crawl statistics table
                cur.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS crawl_stats (
                        id SERIAL PRIMARY KEY,
                        date DATE DEFAULT CURRENT_DATE,
                        domain TEXT NOT NULL,
                        pages_crawled INTEGER DEFAULT 0,
                        pages_successful INTEGER DEFAULT 0,
                        pages_failed INTEGER DEFAULT 0,
                        avg_response_time_ms FLOAT DEFAULT 0,
                        total_data_mb FLOAT DEFAULT 0,
                        unique_links_found INTEGER DEFAULT 0,
                        UNIQUE(date, domain)
                    );
                \"\"\")
                
                # Music-specific extraction table
                cur.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS music_content (
                        id SERIAL PRIMARY KEY,
                        crawl_result_id INTEGER REFERENCES crawl_results(id) ON DELETE CASCADE,
                        artist_name TEXT,
                        track_title TEXT,
                        album_title TEXT,
                        genre TEXT,
                        release_year INTEGER,
                        rating FLOAT,
                        tags TEXT[],
                        lyrics_sample TEXT,
                        chords_available BOOLEAN DEFAULT FALSE,
                        tabs_available BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                \"\"\")
                
                cur.execute(\"\"\"
                    CREATE INDEX IF NOT EXISTS idx_music_content_artist 
                    ON music_content(artist_name);
                \"\"\")
                
                cur.execute(\"\"\"
                    CREATE INDEX IF NOT EXISTS idx_music_content_track 
                    ON music_content(track_title);
                \"\"\")
                
                conn.commit()
                logging.info("Database tables created/verified successfully")
                
        except Exception as e:
            logging.error(f"Failed to create database tables: {e}")
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    async def store_result(self, url: str, content_data: Dict, 
                          links_count: int = 0, depth: int = 0,
                          response_size: int = 0, response_time_ms: int = 0,
                          status_code: int = 200, content_type: str = None):
        \"\"\"Store crawl result in database\"\"\"
        conn = self.pool.getconn()
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            path = parsed.path
            
            with conn.cursor() as cur:
                # Insert or update crawl result
                cur.execute(\"\"\"
                    INSERT INTO crawl_results 
                    (url, domain, path, title, description, content_data, music_data, 
                     structured_data, links_count, depth, response_size, response_time_ms,
                     status_code, content_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        content_data = EXCLUDED.content_data,
                        music_data = EXCLUDED.music_data,
                        structured_data = EXCLUDED.structured_data,
                        links_count = EXCLUDED.links_count,
                        response_size = EXCLUDED.response_size,
                        response_time_ms = EXCLUDED.response_time_ms,
                        status_code = EXCLUDED.status_code,
                        content_type = EXCLUDED.content_type,
                        crawled_at = NOW()
                    RETURNING id
                \"\"\", (
                    url, domain, path,
                    content_data.get('title', ''),
                    content_data.get('description', ''),
                    content_data,
                    content_data.get('music_data', {}),
                    content_data.get('structured_data', {}),
                    links_count, depth, response_size, response_time_ms,
                    status_code, content_type
                ))
                
                result_id = cur.fetchone()[0]
                
                # Store music-specific data if available
                music_data = content_data.get('music_data', {})
                if music_data and any(music_data.values()):
                    await self._store_music_content(cur, result_id, music_data)
                
                # Update daily statistics
                await self._update_crawl_stats(cur, domain, True, response_time_ms, response_size, links_count)
                
                conn.commit()
                logging.debug(f"Stored result for {url} (ID: {result_id})")
                
        except Exception as e:
            logging.error(f"Failed to store result for {url}: {e}")
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    async def _store_music_content(self, cursor, crawl_result_id: int, music_data: Dict):
        \"\"\"Store music-specific content in separate table\"\"\"
        try:
            # Extract music fields
            artist_name = music_data.get('artist', music_data.get('artist_name', ''))
            track_title = music_data.get('song_title', music_data.get('track_title', ''))
            album_title = music_data.get('album_title', '')
            genre = music_data.get('genre', '')
            tags = music_data.get('tags', [])
            
            # Extract rating (handle various formats)
            rating = None
            rating_str = music_data.get('rating', music_data.get('review_score', ''))
            if rating_str:
                try:
                    # Extract numeric rating
                    import re
                    rating_match = re.search(r'(\\d+\\.?\\d*)', str(rating_str))
                    if rating_match:
                        rating = float(rating_match.group(1))
                except:
                    pass
            
            # Detect content types
            chords_available = any(term in str(music_data).lower() for term in ['chord', 'tab'])
            tabs_available = any(term in str(music_data).lower() for term in ['tab', 'guitar', 'bass'])
            
            cursor.execute(\"\"\"
                INSERT INTO music_content 
                (crawl_result_id, artist_name, track_title, album_title, genre, 
                 rating, tags, chords_available, tabs_available)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            \"\"\", (
                crawl_result_id, artist_name or None, track_title or None, 
                album_title or None, genre or None, rating, 
                tags if tags else None, chords_available, tabs_available
            ))
            
        except Exception as e:
            logging.warning(f"Failed to store music content: {e}")
    
    async def _update_crawl_stats(self, cursor, domain: str, success: bool, 
                                response_time_ms: int, response_size: int, links_found: int):
        \"\"\"Update daily crawl statistics\"\"\"
        try:
            cursor.execute(\"\"\"
                INSERT INTO crawl_stats 
                (date, domain, pages_crawled, pages_successful, pages_failed,
                 avg_response_time_ms, total_data_mb, unique_links_found)
                VALUES (CURRENT_DATE, %s, 1, %s, %s, %s, %s, %s)
                ON CONFLICT (date, domain) DO UPDATE SET
                    pages_crawled = crawl_stats.pages_crawled + 1,
                    pages_successful = crawl_stats.pages_successful + EXCLUDED.pages_successful,
                    pages_failed = crawl_stats.pages_failed + EXCLUDED.pages_failed,
                    avg_response_time_ms = (crawl_stats.avg_response_time_ms * crawl_stats.pages_crawled + %s) / (crawl_stats.pages_crawled + 1),
                    total_data_mb = crawl_stats.total_data_mb + %s,
                    unique_links_found = crawl_stats.unique_links_found + %s
            \"\"\", (
                domain, 
                1 if success else 0,
                0 if success else 1,
                response_time_ms,
                response_size / 1024 / 1024,  # Convert to MB
                links_found,
                response_time_ms,
                response_size / 1024 / 1024,
                links_found
            ))
            
        except Exception as e:
            logging.warning(f"Failed to update crawl stats: {e}")
    
    async def store_error(self, url: str, error_type: str, error_message: str, 
                         retry_count: int = 0, status_code: int = None):
        \"\"\"Store crawl error\"\"\"
        conn = self.pool.getconn()
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            
            with conn.cursor() as cur:
                cur.execute(\"\"\"
                    INSERT INTO crawl_errors 
                    (url, domain, error_type, error_message, status_code, retry_count)
                    VALUES (%s, %s, %s, %s, %s, %s)
                \"\"\", (url, domain, error_type, error_message, status_code, retry_count))
                
                # Update stats for failed crawl
                await self._update_crawl_stats(cur, domain, False, 0, 0, 0)
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"Failed to store error for {url}: {e}")
            conn.rollback()
        finally:
            self.pool.putconn(conn)
    
    async def get_domain_stats(self, domain: str = None, days: int = 7) -> List[Dict]:
        \"\"\"Get crawl statistics for domains\"\"\"
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if domain:
                    cur.execute(\"\"\"
                        SELECT * FROM crawl_stats 
                        WHERE domain = %s AND date >= CURRENT_DATE - INTERVAL '%s days'
                        ORDER BY date DESC
                    \"\"\", (domain, days))
                else:
                    cur.execute(\"\"\"
                        SELECT domain, 
                               SUM(pages_crawled) as total_pages,
                               SUM(pages_successful) as total_successful,
                               SUM(pages_failed) as total_failed,
                               AVG(avg_response_time_ms) as avg_response_time,
                               SUM(total_data_mb) as total_data_mb,
                               SUM(unique_links_found) as total_links
                        FROM crawl_stats 
                        WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                        GROUP BY domain
                        ORDER BY total_pages DESC
                    \"\"\", (days,))
                
                return [dict(row) for row in cur.fetchall()]
                
        except Exception as e:
            logging.error(f"Failed to get domain stats: {e}")
            return []
        finally:
            self.pool.putconn(conn)
    
    async def export_results_csv(self, output_path: str, limit: int = 10000, 
                                domain: str = None, start_date: str = None):
        \"\"\"Export results to CSV\"\"\"
        conn = self.pool.getconn()
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with conn.cursor() as cur:
                query = \"\"\"
                    SELECT 
                        r.url, r.domain, r.title, r.description,
                        r.content_data->>'text_sample' as text_sample,
                        r.links_count, r.crawled_at, r.depth, 
                        r.response_size, r.response_time_ms,
                        m.artist_name, m.track_title, m.album_title, m.genre, m.rating
                    FROM crawl_results r
                    LEFT JOIN music_content m ON r.id = m.crawl_result_id
                    WHERE 1=1
                \"\"\"
                
                params = []
                if domain:
                    query += " AND r.domain = %s"
                    params.append(domain)
                
                if start_date:
                    query += " AND r.crawled_at >= %s"
                    params.append(start_date)
                
                query += " ORDER BY r.crawled_at DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                
                with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow([
                        'url', 'domain', 'title', 'description', 'text_sample',
                        'links_count', 'crawled_at', 'depth', 'response_size', 'response_time_ms',
                        'artist_name', 'track_title', 'album_title', 'genre', 'rating'
                    ])
                    
                    # Write data
                    for row in cur.fetchall():
                        writer.writerow(row)
            
            logging.info(f"Exported {cur.rowcount} results to {output_path}")
            
        except Exception as e:
            logging.error(f"Failed to export results: {e}")
            raise
        finally:
            self.pool.putconn(conn)
    
    async def export_music_data_json(self, output_path: str, limit: int = 5000):
        \"\"\"Export music-specific data to JSON\"\"\"
        conn = self.pool.getconn()
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(\"\"\"
                    SELECT 
                        r.url, r.domain, r.title,
                        m.artist_name, m.track_title, m.album_title, 
                        m.genre, m.rating, m.tags,
                        m.chords_available, m.tabs_available,
                        r.music_data
                    FROM crawl_results r
                    INNER JOIN music_content m ON r.id = m.crawl_result_id
                    WHERE m.artist_name IS NOT NULL OR m.track_title IS NOT NULL
                    ORDER BY r.crawled_at DESC
                    LIMIT %s
                \"\"\", (limit,))
                
                results = [dict(row) for row in cur.fetchall()]
                
                with open(output_path, 'w', encoding='utf-8') as jsonfile:
                    json.dump(results, jsonfile, indent=2, default=str)
            
            logging.info(f"Exported {len(results)} music records to {output_path}")
            
        except Exception as e:
            logging.error(f"Failed to export music data: {e}")
            raise
        finally:
            self.pool.putconn(conn)
    
    async def cleanup_old_data(self, days_old: int = 30):
        \"\"\"Clean up old crawl data to save space\"\"\"
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Clean old errors
                cur.execute(\"\"\"
                    DELETE FROM crawl_errors 
                    WHERE occurred_at < NOW() - INTERVAL '%s days'
                \"\"\", (days_old,))
                
                errors_deleted = cur.rowcount
                
                # Clean old stats (keep aggregated data)
                cur.execute(\"\"\"
                    DELETE FROM crawl_stats 
                    WHERE date < CURRENT_DATE - INTERVAL '%s days'
                \"\"\", (days_old,))
                
                stats_deleted = cur.rowcount
                
                conn.commit()
                logging.info(f"Cleaned up {errors_deleted} old errors and {stats_deleted} old stats")
                
        except Exception as e:
            logging.error(f"Failed to cleanup old data: {e}")
            conn.rollback()
        finally:
            self.pool.putconn(conn)
    
    async def close(self):
        \"\"\"Close connection pool\"\"\"
        if self.pool:
            self.pool.closeall()
            logging.info("Closed PostgreSQL connection pool")

class StorageUtils:
    \"\"\"Utility functions for storage operations\"\"\"
    
    @staticmethod
    def create_database_if_not_exists(connection_string: str, database_name: str):
        \"\"\"Create database if it doesn't exist\"\"\"
        try:
            # Connect to postgres database to create new database
            import psycopg2
            from urllib.parse import urlparse
            
            parsed = urlparse(connection_string)
            admin_conn_string = connection_string.replace(f"/{database_name}", "/postgres")
            
            conn = psycopg2.connect(admin_conn_string)
            conn.autocommit = True
            
            with conn.cursor() as cur:
                cur.execute(f"SELECT 1 FROM pg_database WHERE datname='{database_name}'")
                if not cur.fetchone():
                    cur.execute(f'CREATE DATABASE "{database_name}"')
                    logging.info(f"Created database: {database_name}")
                else:
                    logging.info(f"Database already exists: {database_name}")
            
            conn.close()
            
        except Exception as e:
            logging.warning(f"Could not create database {database_name}: {e}")
    
    @staticmethod
    def test_connection(connection_string: str) -> bool:
        \"\"\"Test database connection\"\"\"
        try:
            conn = psycopg2.connect(connection_string)
            conn.close()
            return True
        except Exception as e:
            logging.error(f"Database connection test failed: {e}")
            return False
""")

with open("crawler_storage.py", "w", encoding="utf-8") as f:
    f.write(storage_module)

print("Created crawler_storage.py")
print(f"Length: {len(storage_module)} characters")