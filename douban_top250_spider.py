"""
Standalone Scrapy spider for Douban Top 250 movies. Run after installing Scrapy:
    pip install scrapy
Then run:
    python douban_top250_spider.py

Outputs SQLite DB: douban_movies.db (in same folder)
"""

import scrapy
from scrapy.crawler import CrawlerProcess
import sqlite3
import re
import random

# small User-Agent rotation list (extend as needed)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
]

def random_headers():
    ua = random.choice(USER_AGENTS)
    return {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Referer': 'https://www.google.com/',
    }

class DoubanTop250Spider(scrapy.Spider):
    name = 'douban_top250'
    allowed_domains = ['movie.douban.com']
    start_urls = ['https://movie.douban.com/top250']

    def start_requests(self):
        # first request homepage to obtain cookies, then request the Top250
        yield scrapy.Request('https://movie.douban.com/', headers=random_headers(), callback=self.after_home)

    def after_home(self, response):
        # cookies are preserved by Scrapy; now request the Top250 listing
        yield scrapy.Request(self.start_urls[0], headers=random_headers(), callback=self.parse)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conn = sqlite3.connect('douban_movies.db')
        self.cur = self.conn.cursor()
        self.cur.execute('''CREATE TABLE IF NOT EXISTS movies
            (id INTEGER PRIMARY KEY, title TEXT, year TEXT, rating REAL, num_ratings INTEGER, directors TEXT, cast TEXT, genres TEXT, tags TEXT, summary TEXT, url TEXT)''')
        self.cur.execute('''CREATE TABLE IF NOT EXISTS reviews
            (id INTEGER PRIMARY KEY, movie_title TEXT, movie_url TEXT, review_title TEXT, author TEXT, date TEXT, rating TEXT, useful INTEGER, content TEXT, url TEXT)''')
        self.cur.execute('''CREATE TABLE IF NOT EXISTS comments
            (id INTEGER PRIMARY KEY, movie_title TEXT, movie_url TEXT, author TEXT, date TEXT, rating TEXT, useful INTEGER, content TEXT, url TEXT)''')
        self.conn.commit()

    def closed(self, reason):
        self.conn.commit()
        self.conn.close()

    def parse(self, response):
        for sel in response.css('div.item'):
            detail = sel.css('div.hd a::attr(href)').get()
            if detail:
                yield response.follow(detail, callback=self.parse_detail, headers=random_headers())
        next_page = response.css('span.next a::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse, headers=random_headers())

    def parse_detail(self, response):
        title = response.css('span[property="v:itemreviewed"]::text').get(default='').strip()
        rating = response.css('strong[property="v:average"]::text').get()
        num_ratings = response.css('span[property="v:votes"]::text').get()
        directors = ', '.join(response.css('#info a[rel="v:directedBy"]::text').getall()).strip()
        cast = ', '.join(response.css('#info a[rel="v:starring"]::text').getall()).strip()
        genres = ', '.join(response.css('span[property="v:genre"]::text').getall()).strip()
        year_text = response.css('h1 span.year::text').get(default='')
        year_match = re.search(r'\d{4}', year_text)
        year = year_match.group(0) if year_match else ''
        summary = response.css('span[property="v:summary"]::text').getall()
        summary = ' '.join(s.strip() for s in summary).strip()
        tags = ', '.join(response.css('div#db-tags-section a::text').getall()).strip()
        url = response.url

        # Insert into SQLite
        try:
            self.cur.execute('''INSERT INTO movies (title,year,rating,num_ratings,directors,cast,genres,tags,summary,url)
                                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                             (title, year, rating, num_ratings, directors, cast, genres, tags, summary, url))
            self.conn.commit()
        except Exception as e:
            self.logger.error('DB insert failed: %s', e)

        yield {
            'title': title,
            'year': year,
            'rating': rating,
            'num_ratings': num_ratings,
            'directors': directors,
            'cast': cast,
            'genres': genres,
            'tags': tags,
            'summary': summary,
            'url': url,
        }


        # Follow to the movie's short comments (短评) page
        comments_path = response.url.rstrip('/') + '/comments'
        yield response.follow(comments_path, callback=self.parse_comments, meta={'movie_title': title, 'movie_url': url}, headers=random_headers())

    def parse_comments(self, response):
        """Parse short comments list page and extract comments; paginate. Limit to 100 comments per movie."""
        movie_title = response.meta.get('movie_title')
        movie_url = response.meta.get('movie_url')
        scraped = response.meta.get('scraped')
        if scraped is None:
            try:
                scraped = int(self.cur.execute('SELECT COUNT(*) FROM comments WHERE movie_url=?', (movie_url,)).fetchone()[0])
            except Exception:
                scraped = 0

        for c in response.css('div.comment-item'):
            if scraped >= 100:
                break
            author = c.css('a::text').get(default='').strip()
            rating_class = c.css('span.comment-info span::attr(class)').re_first(r'allstar\\d+')
            rating = ''
            if rating_class:
                try:
                    rating = str(int(re.search(r'\\d+', rating_class).group(0))/10.0)
                except Exception:
                    rating = ''
            date = c.css('span.comment-info span::text').re_first(r'\\d{4}-\\d{2}-\\d{2}') or c.css('span.comment-info span::text').get(default='').strip()
            content = c.css('p::text').get(default='').strip()
            useful = c.css('span.votes::text').get() or c.css('span.vote-count::text').get() or '0'
            try:
                useful = int(useful)
            except Exception:
                useful = 0
            url = movie_url

            try:
                self.cur.execute('''INSERT INTO comments (movie_title,movie_url,author,date,rating,useful,content,url)
                                    VALUES (?,?,?,?,?,?,?,?)''',
                                 (movie_title, movie_url, author, date, rating, useful, content, url))
                self.conn.commit()
                scraped += 1
            except Exception as e:
                self.logger.error('Comment DB insert failed: %s', e)

            yield {
                'movie_title': movie_title,
                'author': author,
                'date': date,
                'rating': rating,
                'useful': useful,
                'content': content,
                'url': url,
            }

        # paginate only if we haven't reached the limit
        if scraped < 100:
            next_page = response.css('div.paginator span.next a::attr(href)').get() or response.css('span.next a::attr(href)').get()
            if next_page:
                yield response.follow(next_page, callback=self.parse_comments, meta={'movie_title': movie_title, 'movie_url': movie_url, 'scraped': scraped}, headers=random_headers())


if __name__ == '__main__':
    process = CrawlerProcess({
        'USER_AGENT': 'douban_spider (+https://example.com)',
        'ROBOTSTXT_OBEY': True,
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS': 2,
        # reduce log level if desired
        'LOG_LEVEL': 'INFO',
    })
    process.crawl(DoubanTop250Spider)
    process.start()

    # Export SQLite to Excel (.xlsx) using pandas
    try:
        import pandas as pd
        conn = sqlite3.connect('douban_movies.db')
        df_movies = pd.read_sql_query('SELECT title,year,rating,num_ratings,directors,cast,genres,tags,summary,url FROM movies', conn)
        df_comments = pd.read_sql_query('SELECT movie_title,movie_url,author,date,rating,useful,content,url FROM comments', conn)
        conn.close()
        with pd.ExcelWriter('douban_movies.xlsx', engine='openpyxl') as writer:
            df_movies.to_excel(writer, sheet_name='movies', index=False)
            df_comments.to_excel(writer, sheet_name='comments', index=False)
        print('Wrote douban_movies.xlsx with sheets: movies, comments')
    except ModuleNotFoundError:
        print('pandas not installed. Install with: pip install pandas openpyxl')
    except Exception as e:
        print('Excel export failed:', e)
