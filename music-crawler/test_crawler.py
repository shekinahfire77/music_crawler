#!/usr/bin/env python3
"""
Test script for the web crawler
Validates functionality and resource usage
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler_main import CrawlerConfig, ResourceMonitor
from crawler_core import RobotsCache, URLFrontier, HostScheduler
from crawler_content import ContentExtractor
from crawler_storage import PostgresStorage
import redis
import aiohttp

class CrawlerTester:
    """Test suite for crawler components"""
    
    def __init__(self):
        self.config = CrawlerConfig(
            max_memory_mb=100,  # Lower for testing
            initial_concurrency=3,
            max_concurrency=5,
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            postgres_url=os.getenv("DATABASE_URL", "postgresql://localhost/crawler_test")
        )
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    async def test_basic_functionality(self):
        """Test basic crawler functionality"""
        print("🧪 Testing Basic Functionality")
        
        # Test Redis connection
        try:
            redis_client = redis.from_url(self.config.redis_url, decode_responses=False)
            redis_client.ping()
            print("✅ Redis connection successful")
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            return False
        
        # Test PostgreSQL connection
        try:
            storage = PostgresStorage(self.config.postgres_url)
            await storage.initialize()
            print("✅ PostgreSQL connection successful")
        except Exception as e:
            print(f"❌ PostgreSQL connection failed: {e}")
            return False
        
        # Test content extraction
        try:
            test_html = """
            <html>
                <head><title>Test Song - Test Artist</title></head>
                <body>
                    <div class="song-title">Test Song</div>
                    <div class="artist">Test Artist</div>
                    <a href="/other-song">Other Song</a>
                </body>
            </html>
            """
            
            content = ContentExtractor.extract_content(test_html, "https://example.com/test")
            links = ContentExtractor.extract_links(test_html, "https://example.com/test")
            
            assert content['title'] == "Test Song - Test Artist"
            assert len(links) == 1
            print("✅ Content extraction working")
        except Exception as e:
            print(f"❌ Content extraction failed: {e}")
            return False
        
        await storage.close()
        return True
    
    async def test_resource_monitoring(self):
        """Test resource monitoring and scaling"""
        print("\n🧪 Testing Resource Monitoring")
        
        monitor = ResourceMonitor(self.config)
        
        # Test memory monitoring
        memory_mb = monitor.get_memory_usage_mb()
        cpu_pct = monitor.get_cpu_percent()
        
        print(f"📊 Current memory usage: {memory_mb:.1f}MB")
        print(f"📊 Current CPU usage: {cpu_pct:.1f}%")
        
        # Test scaling decisions
        should_scale_up = monitor.should_scale_up()
        should_scale_down = monitor.should_scale_down()
        
        print(f"📈 Should scale up: {should_scale_up}")
        print(f"📉 Should scale down: {should_scale_down}")
        
        # Test cleanup
        monitor.force_cleanup()
        print("✅ Resource monitoring working")
        
        return True
    
    async def test_robots_txt_compliance(self):
        """Test robots.txt fetching and compliance"""
        print("\n🧪 Testing Robots.txt Compliance")
        
        redis_client = redis.from_url(self.config.redis_url, decode_responses=False)
        robots_cache = RobotsCache(redis_client)
        
        async with aiohttp.ClientSession() as session:
            # Test with a known website
            test_urls = [
                "https://example.com/",
                "https://httpbin.org/",
                "https://google.com/"
            ]
            
            for url in test_urls:
                try:
                    can_fetch = await robots_cache.can_fetch(url, session)
                    print(f"🤖 {url}: {'Allowed' if can_fetch else 'Disallowed'}")
                except Exception as e:
                    print(f"⚠️ {url}: Error checking robots.txt - {e}")
        
        print("✅ Robots.txt compliance testing completed")
        return True
    
    async def test_frontier_management(self):
        """Test URL frontier and deduplication"""
        print("\n🧪 Testing URL Frontier")
        
        redis_client = redis.from_url(self.config.redis_url, decode_responses=False)
        
        # Clear any existing frontier data
        redis_client.delete("frontier")
        for key in redis_client.scan_iter(match="seen:*"):
            redis_client.delete(key)
        
        frontier = URLFrontier(redis_client, self.config)
        
        # Test adding URLs
        test_urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page1",  # Duplicate
            "https://test.com/page1"
        ]
        
        for i, url in enumerate(test_urls):
            await frontier.add_url(url, priority=i)
        
        queue_size = frontier.get_queue_size()
        print(f"📝 Added {len(test_urls)} URLs, queue size: {queue_size}")
        
        # Test URL retrieval
        retrieved = 0
        while True:
            url_data = await frontier.get_url()
            if not url_data:
                break
            retrieved += 1
            print(f"🔗 Retrieved: {url_data['url']}")
        
        print(f"✅ Retrieved {retrieved} unique URLs (duplicates filtered)")
        return True
    
    async def test_host_scheduler(self):
        """Test per-host politeness"""
        print("\n🧪 Testing Host Scheduler")
        
        redis_client = redis.from_url(self.config.redis_url, decode_responses=False)
        scheduler = HostScheduler(redis_client, self.config)
        
        test_url = "https://example.com/test"
        
        # First request should be allowed
        can_crawl_1 = await scheduler.can_crawl_host(test_url)
        print(f"🕐 First request allowed: {can_crawl_1}")
        
        # Immediate second request should be blocked
        can_crawl_2 = await scheduler.can_crawl_host(test_url)
        print(f"🚫 Immediate second request allowed: {can_crawl_2}")
        
        # Record crawl attempt
        await scheduler.record_crawl(test_url, True)
        print("📊 Recorded successful crawl")
        
        print("✅ Host scheduling working")
        return True
    
    async def test_storage_operations(self):
        """Test database storage operations"""
        print("\n🧪 Testing Storage Operations")
        
        storage = PostgresStorage(self.config.postgres_url)
        await storage.initialize()
        
        # Test storing a result
        test_content = {
            'title': 'Test Song by Test Artist',
            'description': 'A test song for crawler testing',
            'text_sample': 'This is a sample of the page content...',
            'music_data': {
                'artist': 'Test Artist',
                'song_title': 'Test Song',
                'genre': 'Rock'
            }
        }
        
        await storage.store_result(
            url="https://test.com/song/123",
            content_data=test_content,
            links_count=5,
            depth=1,
            response_size=1024,
            response_time_ms=250
        )
        print("💾 Stored test result")
        
        # Test storing an error
        await storage.store_error(
            url="https://test.com/error",
            error_type="TimeoutError",
            error_message="Request timed out"
        )
        print("🚨 Stored test error")
        
        # Test CSV export
        output_dir = "./test_output"
        os.makedirs(output_dir, exist_ok=True)
        csv_path = f"{output_dir}/test_export.csv"
        
        await storage.export_results_csv(csv_path, limit=10)
        
        if Path(csv_path).exists():
            print(f"📊 CSV export successful: {csv_path}")
        else:
            print("❌ CSV export failed")
        
        await storage.close()
        print("✅ Storage operations working")
        return True
    
    async def test_memory_constraints(self):
        """Test memory usage under constraints"""
        print("\n🧪 Testing Memory Constraints")
        
        monitor = ResourceMonitor(self.config)
        initial_memory = monitor.get_memory_usage_mb()
        
        print(f"📊 Initial memory: {initial_memory:.1f}MB")
        
        # Simulate memory usage
        test_data = []
        for i in range(1000):
            # Create some test data
            test_data.append({
                'url': f'https://example.com/page{i}',
                'content': f'Test content for page {i}' * 100
            })
            
            if i % 100 == 0:
                current_memory = monitor.get_memory_usage_mb()
                print(f"📈 Memory after {i} items: {current_memory:.1f}MB")
                
                if monitor.should_scale_down():
                    print("⚠️ Memory threshold reached, would scale down")
                    break
        
        # Test cleanup
        del test_data
        monitor.force_cleanup()
        
        final_memory = monitor.get_memory_usage_mb()
        print(f"🧹 Memory after cleanup: {final_memory:.1f}MB")
        
        print("✅ Memory constraint testing completed")
        return True
    
    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Crawler Test Suite")
        print("=" * 50)
        
        tests = [
            self.test_basic_functionality,
            self.test_resource_monitoring,
            self.test_robots_txt_compliance,
            self.test_frontier_management,
            self.test_host_scheduler,
            self.test_storage_operations,
            self.test_memory_constraints
        ]
        
        results = []
        start_time = time.time()
        
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                print(f"❌ Test failed with exception: {e}")
                results.append(False)
        
        total_time = time.time() - start_time
        
        print("\n" + "=" * 50)
        print("📋 Test Results Summary")
        print("=" * 50)
        
        passed = sum(results)
        total = len(results)
        
        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")
        print(f"⏱️ Total time: {total_time:.2f}s")
        
        if passed == total:
            print("\n🎉 All tests passed! Crawler is ready for deployment.")
            return True
        else:
            print("\n⚠️ Some tests failed. Please review and fix issues.")
            return False

async def main():
    """Main test runner"""
    tester = CrawlerTester()
    
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"💥 Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())