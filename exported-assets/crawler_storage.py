#!/usr/bin/env python3
"""
PostgreSQL storage module for crawler results
Optimized for efficient storage and retrieval
"""

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
    """PostgreSQL storage for crawl results with connection pooling"""
    
    def __init__(self, connection_string: str, pool_size: int = 5):
        self.connection_string = connection_string
        self.pool_size = pool_size
        self.pool = None
    
    async def initialize(self):
        """Initialize database tables and connection pool"""
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
        """Create necessary database tables"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Main crawl results table
                cur.execute("""
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
                """)
                
                # Create indexes for performance
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_crawl_results_domain 
                    ON crawl_results(domain);
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_crawl_results_crawled_at 
                    ON crawl_results(crawled_at);
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_crawl_results_music_data 
                    ON crawl_results USING GIN(music_data);
                """)
                
                # Crawl errors table
                cur.execute("""
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
                """)
                
                # Music-specific extraction table
                cur.execute("""
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
                """)
                
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
        """Store crawl result in database"""
        conn = self.pool.getconn()
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            path = parsed.path
            
            with conn.cursor() as cur:
                # Insert or update crawl result
                cur.execute("""
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
                """, (
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
                conn.commit()
                logging.debug(f"Stored result for {url} (ID: {result_id})")
                
        except Exception as e:
            logging.error(f"Failed to store result for {url}: {e}")
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    async def store_error(self, url: str, error_type: str, error_message: str, 
                         retry_count: int = 0, status_code: int = None):
        """Store crawl error"""
        conn = self.pool.getconn()
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO crawl_errors 
                    (url, domain, error_type, error_message, status_code, retry_count)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (url, domain, error_type, error_message, status_code, retry_count))
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"Failed to store error for {url}: {e}")
            conn.rollback()
        finally:
            self.pool.putconn(conn)
    
    async def export_results_csv(self, output_path: str, limit: int = 10000):
        """Export results to CSV"""
        conn = self.pool.getconn()
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        url, domain, title, description,
                        content_data->>'text_sample' as text_sample,
                        links_count, crawled_at, depth, 
                        response_size, response_time_ms
                    FROM crawl_results 
                    ORDER BY crawled_at DESC 
                    LIMIT %s
                """, (limit,))
                
                with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow([
                        'url', 'domain', 'title', 'description', 'text_sample',
                        'links_count', 'crawled_at', 'depth', 'response_size', 'response_time_ms'
                    ])
                    
                    # Write data
                    for row in cur.fetchall():
                        writer.writerow(row)
            
            logging.info(f"Exported results to {output_path}")
            
        except Exception as e:
            logging.error(f"Failed to export results: {e}")
            raise
        finally:
            self.pool.putconn(conn)
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            self.pool.closeall()
            logging.info("Closed PostgreSQL connection pool")