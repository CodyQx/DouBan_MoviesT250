import subprocess
import sys
import os

REPO_DIR = os.path.dirname(__file__)
DB_FILE = os.path.join(REPO_DIR, 'douban_movies.db')

def install_requirements():
    print('Installing python requirements...')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

if __name__ == '__main__':
    try:
        install_requirements()
    except Exception as e:
        print('Failed to install requirements:', e)
        print('You can install manually: pip install -r requirements.txt')

    if not os.path.exists(DB_FILE):
        print('Database file douban_movies.db not found in project folder.')
        print('Please put the SQLite file in this folder and re-run start.py')
        sys.exit(1)

    print('Starting server at http://127.0.0.1:8000')
    subprocess.check_call([sys.executable, '-m', 'uvicorn', 'app:app', '--reload'])
