#!/usr/bin/env python3
"""
Content extraction and parsing utilities
Optimized for music-related websites
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from datetime import datetime
import logging
import re
from typing import List, Dict, Optional

class ContentExtractor:
    """Extract and parse content from HTML using BeautifulSoup"""

    @staticmethod
    def extract_links(html: str, base_url: str) -> List[str]:
        """Extract links from HTML using BeautifulSoup"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            links = []

            # Extract from <a href> tags
            for link in soup.select('a[href]'):
                href = link.get('href')
                if href:
                    # Resolve relative URLs
                    full_url = urljoin(base_url, href)
                    # Remove fragment
                    full_url, _ = urldefrag(full_url)
                    if full_url.startswith(('http://', 'https://')):
                        links.append(full_url)

            # Also check for links in sitemap files
            if 'sitemap' in base_url.lower():
                for loc in soup.select('loc'):
                    if loc.get_text():
                        links.append(loc.get_text().strip())

            return list(set(links))  # Remove duplicates

        except Exception as e:
            logging.warning(f"Link extraction failed for {base_url}: {e}")
            return []

    @staticmethod
    def extract_content(html: str, url: str) -> Dict:
        """Extract structured content from HTML"""
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Basic content extraction
            title = ""
            title_tag = soup.select_one('title')
            if title_tag:
                title = title_tag.get_text(strip=True)

            # Extract meta description
            meta_description = ""
            meta_tag = soup.select_one('meta[name="description"]')
            if meta_tag:
                meta_description = meta_tag.get('content', '')

            # Extract meta keywords
            meta_keywords = ""
            keywords_tag = soup.select_one('meta[name="keywords"]')
            if keywords_tag:
                meta_keywords = keywords_tag.get('content', '')

            # Extract main content text (limited to save memory)
            text_content = ContentExtractor._extract_text_content(soup)

            # Music-specific extraction
            music_data = ContentExtractor._extract_music_data(soup, url)

            # Extract structured data (JSON-LD, microdata)
            structured_data = ContentExtractor._extract_structured_data(soup)

            return {
                'title': title[:500] if title else "",  # Limit length
                'description': meta_description[:1000] if meta_description else "",
                'keywords': meta_keywords[:500] if meta_keywords else "",
                'text_sample': text_content,
                'music_data': music_data,
                'structured_data': structured_data,
                'extracted_at': datetime.now().isoformat(),
                'url': url
            }

        except Exception as e:
            logging.warning(f"Content extraction failed for {url}: {e}")
            return {
                'error': str(e),
                'url': url,
                'extracted_at': datetime.now().isoformat()
            }

    @staticmethod
    def _extract_text_content(soup: BeautifulSoup) -> str:
        """Extract main text content, limited to save memory"""
        # Remove script and style elements
        for element in soup.select('script, style, nav, footer, header'):
            element.decompose()

        # Extract text from main content areas
        main_selectors = [
            'main', 'article', '.content', '.main-content', 
            '.post-content', '.entry-content', '#content'
        ]

        text_content = ""
        for selector in main_selectors:
            main_element = soup.select_one(selector)
            if main_element:
                text_content = main_element.get_text(strip=True)
                break

        # Fallback to body if no main content found
        if not text_content:
            body = soup.select_one('body')
            if body:
                text_content = body.get_text(strip=True)

        # Limit text length to save memory
        return text_content[:1000] if text_content else ""

    @staticmethod
    def _extract_music_data(soup: BeautifulSoup, url: str) -> Dict:
        """Extract music-specific data based on domain"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        music_data = {}

        try:
            if 'ultimate-guitar' in domain:
                music_data.update(ContentExtractor._extract_ultimate_guitar(soup))
            elif 'bandcamp' in domain:
                music_data.update(ContentExtractor._extract_bandcamp(soup))
            elif 'last.fm' in domain:
                music_data.update(ContentExtractor._extract_lastfm(soup))
            elif 'discogs' in domain:
                music_data.update(ContentExtractor._extract_discogs(soup))
            elif 'soundcloud' in domain:
                music_data.update(ContentExtractor._extract_soundcloud(soup))
            elif 'musicbrainz' in domain:
                music_data.update(ContentExtractor._extract_musicbrainz(soup))
            elif 'pitchfork' in domain:
                music_data.update(ContentExtractor._extract_pitchfork(soup))
            elif 'allmusic' in domain:
                music_data.update(ContentExtractor._extract_allmusic(soup))

            # Generic music-related content extraction
            music_data.update(ContentExtractor._extract_generic_music(soup))

        except Exception as e:
            logging.debug(f"Music data extraction failed for {domain}: {e}")

        return music_data

    @staticmethod
    def _extract_ultimate_guitar(soup: BeautifulSoup) -> Dict:
        """Extract Ultimate Guitar specific data"""
        data = {}

        # Song and artist info
        song_title = soup.select_one('.t_title, [data-song-title]')
        if song_title:
            data['song_title'] = song_title.get_text(strip=True)

        artist = soup.select_one('.t_artist, [data-artist-name]')
        if artist:
            data['artist'] = artist.get_text(strip=True)

        # Tab/chord type
        tab_type = soup.select_one('.js-tab-type')
        if tab_type:
            data['tab_type'] = tab_type.get_text(strip=True)

        # Rating
        rating = soup.select_one('.rating, .js-rating')
        if rating:
            data['rating'] = rating.get_text(strip=True)

        # Difficulty
        difficulty = soup.select_one('.difficulty')
        if difficulty:
            data['difficulty'] = difficulty.get_text(strip=True)

        return data

    @staticmethod
    def _extract_bandcamp(soup: BeautifulSoup) -> Dict:
        """Extract Bandcamp specific data"""
        data = {}

        # Track/album title
        track_title = soup.select_one('.trackTitle, .track_info .title')
        if track_title:
            data['track_title'] = track_title.get_text(strip=True)

        # Artist/band name
        artist_name = soup.select_one('.albumTitle .title, .band-name')
        if artist_name:
            data['artist_name'] = artist_name.get_text(strip=True)

        # Album art
        album_art = soup.select_one('.popupImage img')
        if album_art:
            data['album_art_url'] = album_art.get('src', '')

        # Genre tags
        tags = []
        for tag in soup.select('.tag'):
            tag_text = tag.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)
        if tags:
            data['tags'] = tags[:10]  # Limit tags

        # Price/release date
        price = soup.select_one('.price')
        if price:
            data['price'] = price.get_text(strip=True)

        return data

    @staticmethod
    def _extract_lastfm(soup: BeautifulSoup) -> Dict:
        """Extract Last.fm specific data"""
        data = {}

        # Page type detection
        canonical = soup.select_one('link[rel="canonical"]')
        if canonical:
            href = canonical.get('href', '')
            if '/artist/' in href:
                data['page_type'] = 'artist'
            elif '/album/' in href:
                data['page_type'] = 'album'
            elif '/music/' in href:
                data['page_type'] = 'track'

        # Artist name
        artist = soup.select_one('.header-new-title, .artist-name')
        if artist:
            data['artist_name'] = artist.get_text(strip=True)

        # Track/album name
        track_album = soup.select_one('.track-name, .album-name')
        if track_album:
            data['track_album_name'] = track_album.get_text(strip=True)

        # Play count
        play_count = soup.select_one('.header-new-crumb')
        if play_count:
            data['play_count'] = play_count.get_text(strip=True)

        # Tags
        tags = []
        for tag in soup.select('.tag'):
            tag_text = tag.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)
        if tags:
            data['tags'] = tags[:10]

        return data

    @staticmethod
    def _extract_discogs(soup: BeautifulSoup) -> Dict:
        """Extract Discogs specific data"""
        data = {}

        # Release title
        release_title = soup.select_one('.profile-title, h1')
        if release_title:
            data['release_title'] = release_title.get_text(strip=True)

        # Artist
        artist = soup.select_one('.profile-artist, .artist')
        if artist:
            data['artist'] = artist.get_text(strip=True)

        # Year
        year = soup.select_one('.profile-year')
        if year:
            data['year'] = year.get_text(strip=True)

        # Genre and style
        genre = soup.select_one('.profile-genre')
        if genre:
            data['genre'] = genre.get_text(strip=True)

        style = soup.select_one('.profile-style')
        if style:
            data['style'] = style.get_text(strip=True)

        # Format
        format_info = soup.select_one('.profile-format')
        if format_info:
            data['format'] = format_info.get_text(strip=True)

        return data

    @staticmethod
    def _extract_soundcloud(soup: BeautifulSoup) -> Dict:
        """Extract SoundCloud specific data"""
        data = {}

        # Track title
        title = soup.select_one('.soundTitle__title, .sc-title')
        if title:
            data['track_title'] = title.get_text(strip=True)

        # Artist/user
        artist = soup.select_one('.soundTitle__username, .sc-username')
        if artist:
            data['artist'] = artist.get_text(strip=True)

        # Play count
        play_count = soup.select_one('.sc-ministats-plays')
        if play_count:
            data['play_count'] = play_count.get_text(strip=True)

        return data

    @staticmethod
    def _extract_musicbrainz(soup: BeautifulSoup) -> Dict:
        """Extract MusicBrainz specific data"""
        data = {}

        # Entity type from URL or page
        entity_type = soup.select_one('.entity-type')
        if entity_type:
            data['entity_type'] = entity_type.get_text(strip=True)

        # Name/title
        name = soup.select_one('.entity-name, h1')
        if name:
            data['name'] = name.get_text(strip=True)

        # MBID
        mbid = soup.select_one('.mbid')
        if mbid:
            data['mbid'] = mbid.get_text(strip=True)

        return data

    @staticmethod
    def _extract_pitchfork(soup: BeautifulSoup) -> Dict:
        """Extract Pitchfork specific data"""
        data = {}

        # Review score
        score = soup.select_one('.score')
        if score:
            data['review_score'] = score.get_text(strip=True)

        # Album/artist
        album = soup.select_one('.single-album-tombstone__title')
        if album:
            data['album_title'] = album.get_text(strip=True)

        artist = soup.select_one('.artist-links')
        if artist:
            data['artist'] = artist.get_text(strip=True)

        return data

    @staticmethod
    def _extract_allmusic(soup: BeautifulSoup) -> Dict:
        """Extract AllMusic specific data"""
        data = {}

        # Artist/album name
        name = soup.select_one('.page-title, h1')
        if name:
            data['name'] = name.get_text(strip=True)

        # Rating
        rating = soup.select_one('.rating')
        if rating:
            data['rating'] = rating.get_text(strip=True)

        # Genre
        genre = soup.select_one('.genre')
        if genre:
            data['genre'] = genre.get_text(strip=True)

        return data

    @staticmethod
    def _extract_generic_music(soup: BeautifulSoup) -> Dict:
        """Extract generic music-related content"""
        data = {}

        # Look for common music-related terms in text
        text_content = soup.get_text(strip=True).lower()

        # Count mentions of music terms
        music_terms = [
            'album', 'song', 'track', 'artist', 'band', 'music', 
            'guitar', 'bass', 'drums', 'vocals', 'lyrics', 'chord'
        ]

        term_counts = {}
        for term in music_terms:
            count = text_content.count(term)
            if count > 0:
                term_counts[term] = count

        if term_counts:
            data['music_term_frequency'] = term_counts

        # Extract any JSON-LD music schema
        json_ld = soup.select('script[type="application/ld+json"]')
        for script in json_ld:
            try:
                import json
                ld_data = json.loads(script.string)
                if isinstance(ld_data, dict) and ld_data.get('@type') in ['MusicRecording', 'MusicAlbum', 'MusicGroup']:
                    data['schema_org'] = ld_data
                    break
            except:
                pass

        return data

    @staticmethod
    def _extract_structured_data(soup: BeautifulSoup) -> Dict:
        """Extract structured data from JSON-LD and microdata"""
        structured_data = {}

        # JSON-LD extraction
        json_ld_scripts = soup.select('script[type="application/ld+json"]')
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.string)
                if data:
                    structured_data['json_ld'] = data
                    break
            except:
                pass

        # OpenGraph data
        og_data = {}
        og_tags = soup.select('meta[property^="og:"]')
        for tag in og_tags:
            property_name = tag.get('property', '')
            content = tag.get('content', '')
            if property_name and content:
                og_data[property_name] = content

        if og_data:
            structured_data['open_graph'] = og_data

        # Twitter Card data
        twitter_data = {}
        twitter_tags = soup.select('meta[name^="twitter:"]')
        for tag in twitter_tags:
            name = tag.get('name', '')
            content = tag.get('content', '')
            if name and content:
                twitter_data[name] = content

        if twitter_data:
            structured_data['twitter_card'] = twitter_data

        return structured_data

# Utility functions for content processing
def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    if not text:
        return ""

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Remove control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

    return text

def extract_emails(text: str) -> List[str]:
    """Extract email addresses from text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(email_pattern, text)

def extract_urls(text: str) -> List[str]:
    """Extract URLs from text"""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)
