# Create the content extraction module
content_extractor = textwrap.dedent("""
#!/usr/bin/env python3
\"\"\"
Content extraction and parsing utilities
Optimized for music-related websites
\"\"\"

from selectolax.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag
from datetime import datetime
import logging
import re
from typing import List, Dict, Optional

class ContentExtractor:
    \"\"\"Extract and parse content from HTML using selectolax for speed\"\"\"
    
    @staticmethod
    def extract_links(html: str, base_url: str) -> List[str]:
        \"\"\"Extract links from HTML using selectolax\"\"\"
        try:
            tree = HTMLParser(html)
            links = []
            
            # Extract from <a href> tags
            for link in tree.css('a[href]'):
                href = link.attributes.get('href')
                if href:
                    # Resolve relative URLs
                    full_url = urljoin(base_url, href)
                    # Remove fragment
                    full_url, _ = urldefrag(full_url)
                    if full_url.startswith(('http://', 'https://')):
                        links.append(full_url)
            
            # Also check for links in sitemap files
            if 'sitemap' in base_url.lower():
                for loc in tree.css('loc'):
                    if loc.text():
                        links.append(loc.text().strip())
            
            return list(set(links))  # Remove duplicates
            
        except Exception as e:
            logging.warning(f"Link extraction failed for {base_url}: {e}")
            return []
    
    @staticmethod
    def extract_content(html: str, url: str) -> Dict:
        \"\"\"Extract structured content from HTML\"\"\"
        try:
            tree = HTMLParser(html)
            
            # Basic content extraction
            title = ""
            title_tag = tree.css_first('title')
            if title_tag:
                title = title_tag.text(strip=True)
            
            # Extract meta description
            meta_description = ""
            meta_tag = tree.css_first('meta[name="description"]')
            if meta_tag:
                meta_description = meta_tag.attributes.get('content', '')
            
            # Extract meta keywords
            meta_keywords = ""
            keywords_tag = tree.css_first('meta[name="keywords"]')
            if keywords_tag:
                meta_keywords = keywords_tag.attributes.get('content', '')
            
            # Extract main content text (limited to save memory)
            text_content = ContentExtractor._extract_text_content(tree)
            
            # Music-specific extraction
            music_data = ContentExtractor._extract_music_data(tree, url)
            
            # Extract structured data (JSON-LD, microdata)
            structured_data = ContentExtractor._extract_structured_data(tree)
            
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
    def _extract_text_content(tree: HTMLParser) -> str:
        \"\"\"Extract main text content, limited to save memory\"\"\"
        # Remove script and style elements
        for element in tree.css('script, style, nav, footer, header'):
            element.decompose()
        
        # Extract text from main content areas
        main_selectors = [
            'main', 'article', '.content', '.main-content', 
            '.post-content', '.entry-content', '#content'
        ]
        
        text_content = ""
        for selector in main_selectors:
            main_element = tree.css_first(selector)
            if main_element:
                text_content = main_element.text(strip=True)
                break
        
        # Fallback to body if no main content found
        if not text_content:
            body = tree.css_first('body')
            if body:
                text_content = body.text(strip=True)
        
        # Limit text length to save memory
        return text_content[:1000] if text_content else ""
    
    @staticmethod
    def _extract_music_data(tree: HTMLParser, url: str) -> Dict:
        \"\"\"Extract music-specific data based on domain\"\"\"
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        music_data = {}
        
        try:
            if 'ultimate-guitar' in domain:
                music_data.update(ContentExtractor._extract_ultimate_guitar(tree))
            elif 'bandcamp' in domain:
                music_data.update(ContentExtractor._extract_bandcamp(tree))
            elif 'last.fm' in domain:
                music_data.update(ContentExtractor._extract_lastfm(tree))
            elif 'discogs' in domain:
                music_data.update(ContentExtractor._extract_discogs(tree))
            elif 'soundcloud' in domain:
                music_data.update(ContentExtractor._extract_soundcloud(tree))
            elif 'musicbrainz' in domain:
                music_data.update(ContentExtractor._extract_musicbrainz(tree))
            elif 'pitchfork' in domain:
                music_data.update(ContentExtractor._extract_pitchfork(tree))
            elif 'allmusic' in domain:
                music_data.update(ContentExtractor._extract_allmusic(tree))
            
            # Generic music-related content extraction
            music_data.update(ContentExtractor._extract_generic_music(tree))
        
        except Exception as e:
            logging.debug(f"Music data extraction failed for {domain}: {e}")
        
        return music_data
    
    @staticmethod
    def _extract_ultimate_guitar(tree: HTMLParser) -> Dict:
        \"\"\"Extract Ultimate Guitar specific data\"\"\"
        data = {}
        
        # Song and artist info
        song_title = tree.css_first('.t_title, [data-song-title]')
        if song_title:
            data['song_title'] = song_title.text(strip=True)
        
        artist = tree.css_first('.t_artist, [data-artist-name]')
        if artist:
            data['artist'] = artist.text(strip=True)
        
        # Tab/chord type
        tab_type = tree.css_first('.js-tab-type')
        if tab_type:
            data['tab_type'] = tab_type.text(strip=True)
        
        # Rating
        rating = tree.css_first('.rating, .js-rating')
        if rating:
            data['rating'] = rating.text(strip=True)
        
        # Difficulty
        difficulty = tree.css_first('.difficulty')
        if difficulty:
            data['difficulty'] = difficulty.text(strip=True)
        
        return data
    
    @staticmethod
    def _extract_bandcamp(tree: HTMLParser) -> Dict:
        \"\"\"Extract Bandcamp specific data\"\"\"
        data = {}
        
        # Track/album title
        track_title = tree.css_first('.trackTitle, .track_info .title')
        if track_title:
            data['track_title'] = track_title.text(strip=True)
        
        # Artist/band name
        artist_name = tree.css_first('.albumTitle .title, .band-name')
        if artist_name:
            data['artist_name'] = artist_name.text(strip=True)
        
        # Album art
        album_art = tree.css_first('.popupImage img')
        if album_art:
            data['album_art_url'] = album_art.attributes.get('src', '')
        
        # Genre tags
        tags = []
        for tag in tree.css('.tag'):
            tag_text = tag.text(strip=True)
            if tag_text:
                tags.append(tag_text)
        if tags:
            data['tags'] = tags[:10]  # Limit tags
        
        # Price/release date
        price = tree.css_first('.price')
        if price:
            data['price'] = price.text(strip=True)
        
        return data
    
    @staticmethod
    def _extract_lastfm(tree: HTMLParser) -> Dict:
        \"\"\"Extract Last.fm specific data\"\"\"
        data = {}
        
        # Page type detection
        if '/artist/' in tree.css_first('link[rel="canonical"]').attributes.get('href', ''):
            data['page_type'] = 'artist'
        elif '/album/' in tree.css_first('link[rel="canonical"]').attributes.get('href', ''):
            data['page_type'] = 'album'
        elif '/music/' in tree.css_first('link[rel="canonical"]').attributes.get('href', ''):
            data['page_type'] = 'track'
        
        # Artist name
        artist = tree.css_first('.header-new-title, .artist-name')
        if artist:
            data['artist_name'] = artist.text(strip=True)
        
        # Track/album name
        track_album = tree.css_first('.track-name, .album-name')
        if track_album:
            data['track_album_name'] = track_album.text(strip=True)
        
        # Play count
        play_count = tree.css_first('.header-new-crumb')
        if play_count:
            data['play_count'] = play_count.text(strip=True)
        
        # Tags
        tags = []
        for tag in tree.css('.tag'):
            tag_text = tag.text(strip=True)
            if tag_text:
                tags.append(tag_text)
        if tags:
            data['tags'] = tags[:10]
        
        return data
    
    @staticmethod
    def _extract_discogs(tree: HTMLParser) -> Dict:
        \"\"\"Extract Discogs specific data\"\"\"
        data = {}
        
        # Release title
        release_title = tree.css_first('.profile-title, h1')
        if release_title:
            data['release_title'] = release_title.text(strip=True)
        
        # Artist
        artist = tree.css_first('.profile-artist, .artist')
        if artist:
            data['artist'] = artist.text(strip=True)
        
        # Year
        year = tree.css_first('.profile-year')
        if year:
            data['year'] = year.text(strip=True)
        
        # Genre and style
        genre = tree.css_first('.profile-genre')
        if genre:
            data['genre'] = genre.text(strip=True)
        
        style = tree.css_first('.profile-style')
        if style:
            data['style'] = style.text(strip=True)
        
        # Format
        format_info = tree.css_first('.profile-format')
        if format_info:
            data['format'] = format_info.text(strip=True)
        
        return data
    
    @staticmethod
    def _extract_soundcloud(tree: HTMLParser) -> Dict:
        \"\"\"Extract SoundCloud specific data\"\"\"
        data = {}
        
        # Track title
        title = tree.css_first('.soundTitle__title, .sc-title')
        if title:
            data['track_title'] = title.text(strip=True)
        
        # Artist/user
        artist = tree.css_first('.soundTitle__username, .sc-username')
        if artist:
            data['artist'] = artist.text(strip=True)
        
        # Play count
        play_count = tree.css_first('.sc-ministats-plays')
        if play_count:
            data['play_count'] = play_count.text(strip=True)
        
        return data
    
    @staticmethod
    def _extract_musicbrainz(tree: HTMLParser) -> Dict:
        \"\"\"Extract MusicBrainz specific data\"\"\"
        data = {}
        
        # Entity type from URL or page
        entity_type = tree.css_first('.entity-type')
        if entity_type:
            data['entity_type'] = entity_type.text(strip=True)
        
        # Name/title
        name = tree.css_first('.entity-name, h1')
        if name:
            data['name'] = name.text(strip=True)
        
        # MBID
        mbid = tree.css_first('.mbid')
        if mbid:
            data['mbid'] = mbid.text(strip=True)
        
        return data
    
    @staticmethod
    def _extract_pitchfork(tree: HTMLParser) -> Dict:
        \"\"\"Extract Pitchfork specific data\"\"\"
        data = {}
        
        # Review score
        score = tree.css_first('.score')
        if score:
            data['review_score'] = score.text(strip=True)
        
        # Album/artist
        album = tree.css_first('.single-album-tombstone__title')
        if album:
            data['album_title'] = album.text(strip=True)
        
        artist = tree.css_first('.artist-links')
        if artist:
            data['artist'] = artist.text(strip=True)
        
        return data
    
    @staticmethod
    def _extract_allmusic(tree: HTMLParser) -> Dict:
        \"\"\"Extract AllMusic specific data\"\"\"
        data = {}
        
        # Artist/album name
        name = tree.css_first('.page-title, h1')
        if name:
            data['name'] = name.text(strip=True)
        
        # Rating
        rating = tree.css_first('.rating')
        if rating:
            data['rating'] = rating.text(strip=True)
        
        # Genre
        genre = tree.css_first('.genre')
        if genre:
            data['genre'] = genre.text(strip=True)
        
        return data
    
    @staticmethod
    def _extract_generic_music(tree: HTMLParser) -> Dict:
        \"\"\"Extract generic music-related content\"\"\"
        data = {}
        
        # Look for common music-related terms in text
        text_content = tree.text(strip=True).lower()
        
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
        json_ld = tree.css('script[type="application/ld+json"]')
        for script in json_ld:
            try:
                import json
                ld_data = json.loads(script.text())
                if isinstance(ld_data, dict) and ld_data.get('@type') in ['MusicRecording', 'MusicAlbum', 'MusicGroup']:
                    data['schema_org'] = ld_data
                    break
            except:
                pass
        
        return data
    
    @staticmethod
    def _extract_structured_data(tree: HTMLParser) -> Dict:
        \"\"\"Extract structured data from JSON-LD and microdata\"\"\"
        structured_data = {}
        
        # JSON-LD extraction
        json_ld_scripts = tree.css('script[type="application/ld+json"]')
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.text())
                if data:
                    structured_data['json_ld'] = data
                    break
            except:
                pass
        
        # OpenGraph data
        og_data = {}
        og_tags = tree.css('meta[property^="og:"]')
        for tag in og_tags:
            property_name = tag.attributes.get('property', '')
            content = tag.attributes.get('content', '')
            if property_name and content:
                og_data[property_name] = content
        
        if og_data:
            structured_data['open_graph'] = og_data
        
        # Twitter Card data
        twitter_data = {}
        twitter_tags = tree.css('meta[name^="twitter:"]')
        for tag in twitter_tags:
            name = tag.attributes.get('name', '')
            content = tag.attributes.get('content', '')
            if name and content:
                twitter_data[name] = content
        
        if twitter_data:
            structured_data['twitter_card'] = twitter_data
        
        return structured_data

# Utility functions for content processing
def clean_text(text: str) -> str:
    \"\"\"Clean and normalize text content\"\"\"
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\\s+', ' ', text).strip()
    
    # Remove control characters
    text = re.sub(r'[\\x00-\\x1f\\x7f-\\x9f]', '', text)
    
    return text

def extract_emails(text: str) -> List[str]:
    \"\"\"Extract email addresses from text\"\"\"
    email_pattern = r'\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b'
    return re.findall(email_pattern, text)

def extract_urls(text: str) -> List[str]:
    \"\"\"Extract URLs from text\"\"\"
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)
""")

with open("crawler_content.py", "w", encoding="utf-8") as f:
    f.write(content_extractor)

print("Created crawler_content.py")
print(f"Length: {len(content_extractor)} characters")