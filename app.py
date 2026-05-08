from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sqlite3
import math
from typing import Optional

app = FastAPI(title='Douban Top250 API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# serve frontend
app.mount('/static', StaticFiles(directory='static'), name='static')

DB_FILE = 'douban_movies.db'


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


@app.get('/')
async def index():
    return FileResponse('static/index.html')


@app.get('/api/movies')
async def list_movies(page: int = 1, per_page: int = 20,
                      sort_by: Optional[str] = Query(None, regex='^(rating|year|title|num_ratings)$'),
                      order: str = Query('desc', regex='^(asc|desc)$'),
                      search: Optional[str] = None,
                      genre: Optional[str] = None):
    """Return paginated movies with optional search, sort and genre filter."""
    conn = get_db()
    cur = conn.cursor()

    where = []
    params = []
    if search:
        like = f"%{search}%"
        where.append('(title LIKE ? OR directors LIKE ? OR cast LIKE ?)')
        params.extend([like, like, like])
    if genre:
        where.append('genres LIKE ?')
        params.append(f"%{genre}%")

    where_clause = 'WHERE ' + ' AND '.join(where) if where else ''

    # count
    count_q = f"SELECT COUNT(*) as cnt FROM movies {where_clause}"
    total = cur.execute(count_q, params).fetchone()['cnt']

    order_clause = ''
    if sort_by:
        order_clause = f'ORDER BY {sort_by} {order.upper()}'

    offset = (page - 1) * per_page
    q = f"SELECT id,title,year,rating,num_ratings,directors,cast,genres,tags,summary,url FROM movies {where_clause} {order_clause} LIMIT ? OFFSET ?"
    rows = cur.execute(q, params + [per_page, offset]).fetchall()
    movies = [dict(r) for r in rows]
    conn.close()

    return {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': math.ceil(total / per_page) if per_page else 0,
        'items': movies,
    }


@app.get('/api/movies/{movie_id}')
async def get_movie(movie_id: int):
    conn = get_db()
    cur = conn.cursor()
    r = cur.execute('SELECT id,title,year,rating,num_ratings,directors,cast,genres,tags,summary,url FROM movies WHERE id=?', (movie_id,)).fetchone()
    conn.close()
    if not r:
        raise HTTPException(status_code=404, detail='Movie not found')
    return dict(r)


@app.get('/api/movies/title/{title}/comments')
async def get_comments_by_title(title: str, limit: int = 100):
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute('SELECT movie_title,author,date,rating,useful,content,url FROM comments WHERE movie_title=? ORDER BY date DESC LIMIT ?', (title, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get('/api/movies/{movie_id}/comments')
async def get_comments(movie_id: int, limit: int = 100):
    conn = get_db()
    cur = conn.cursor()
    movie = cur.execute('SELECT url,title FROM movies WHERE id=?', (movie_id,)).fetchone()
    if not movie:
        conn.close()
        raise HTTPException(status_code=404, detail='Movie not found')
    movie_url = movie['url']
    rows = cur.execute('SELECT movie_title,author,date,rating,useful,content,url FROM comments WHERE movie_url=? ORDER BY date DESC LIMIT ?', (movie_url, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get('/api/stats')
async def stats():
    """Return stats: rating distribution, year distribution, genre counts."""
    conn = get_db()
    cur = conn.cursor()

    # rating distribution: group by rounded integer rating
    rating_rows = cur.execute("SELECT ROUND(rating) as r, COUNT(*) as cnt FROM movies WHERE rating IS NOT NULL GROUP BY r ORDER BY r").fetchall()
    rating_dist = [{'rating': int(r['r']) if r['r'] is not None else None, 'count': r['cnt']} for r in rating_rows]

    # year distribution
    year_rows = cur.execute("SELECT year, COUNT(*) as cnt FROM movies WHERE year IS NOT NULL AND year!='' GROUP BY year ORDER BY year").fetchall()
    year_dist = [{'year': r['year'], 'count': r['cnt']} for r in year_rows]

    # genres: split by comma and aggregate in Python
    genre_rows = cur.execute('SELECT genres FROM movies WHERE genres IS NOT NULL').fetchall()
    genre_count = {}
    for gr in genre_rows:
        if not gr['genres']:
            continue
        for g in gr['genres'].split(','):
            g = g.strip()
            if not g:
                continue
            genre_count[g] = genre_count.get(g, 0) + 1
    genre_list = [{'genre': k, 'count': v} for k, v in sorted(genre_count.items(), key=lambda x: -x[1])]

    conn.close()
    return {
        'rating_distribution': rating_dist,
        'year_distribution': year_dist,
        'genre_distribution': genre_list,
    }


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=True)
