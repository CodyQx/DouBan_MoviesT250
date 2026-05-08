# Douban Top250 Viewer

A small FastAPI + static frontend app to browse scraped Douban Top250 movies and short comments.

Requirements
- Python 3.8+

Quick start
1. Place `douban_movies.db` in the project root (same folder as start.py).
2. Run: python start.py
3. Open http://127.0.0.1:8000 in your browser.

API
- GET /api/movies?page=1&per_page=20&search=xxx&sort_by=rating
- GET /api/movies/{id}
- GET /api/movies/{id}/comments?limit=20
- GET /api/movies/title/{title}/comments?limit=20
- GET /api/stats

Notes
- The frontend is served from /static. Charts use ECharts; word cloud uses echarts-wordcloud.
- If you want to change pagination size, edit static/script.js (per_page variable).
