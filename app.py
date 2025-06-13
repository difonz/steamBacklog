import time
import os
import requests
from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse
from psycopg2 import connect, OperationalError
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import psycopg2.errors

load_dotenv()
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

app = Flask(__name__)
app.secret_key = SECRET_KEY

def get_db_connection(db_key='GAMES'):
    url = os.getenv(f"DATABASE_URL_{db_key}")
    if not url:
        raise RuntimeError(f"DATABASE_URL_{db_key} not defined")
    try:
        return connect(url, sslmode='require', cursor_factory=RealDictCursor)
    except OperationalError as e:
        print("DB connection error:", e)
        raise


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            steam_id TEXT
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS games (
            user_id INTEGER NOT NULL,
            appid BIGINT NOT NULL,
            name TEXT NOT NULL,
            playtime INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Backlog',
            completion NUMERIC,
            PRIMARY KEY (user_id, appid)
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        pw_hash = generate_password_hash(request.form['password'])
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO users (email, password) VALUES (%s, %s)',
                (email, pw_hash)
            )
            conn.commit()
            flash('Registered! Log in below.')
            return redirect(url_for('login'))
        except psycopg2.errors.UniqueViolation:
            flash('Email already exists.')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, password FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/dashboard/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/logout/')
def logout():
    session.pop('user_id', None)
    flash('Logged out.')
    return redirect(url_for('login'))

@app.route('/games/')
def games():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()

    page = request.args.get('page', int, 1)
    per_page = request.args.get('per_page', int, 20)
    sort = request.args.get('sort', 'name')
    order = request.args.get('order', 'asc').lower()
    tag = request.args.get('tag')

    if sort not in ('name', 'playtime', 'completion'):
        sort = 'name'
    order_dir = 'DESC' if order == 'desc' else 'ASC'

    base_sql = '''
        SELECT appid, name, playtime, status, completion
        FROM games
        WHERE user_id = %s
    '''
    params = [user_id]

    if tag:
        base_sql += ' AND %s = ANY(tags)'
        params.append(tag)

    base_sql += f' ORDER BY {sort} {order_dir}'
    offset = (page - 1) * per_page
    base_sql += ' LIMIT %s OFFSET %s'
    params.extend([per_page, offset])

    cur.execute(base_sql, params)
    saved_games = cur.fetchall()

    count_sql = 'SELECT COUNT(*) AS cnt FROM games WHERE user_id = %s' + (
        ' AND %s = ANY(tags)' if tag else ''
    )
    cur.execute(count_sql, [user_id] + ([tag] if tag else []))
    total = cur.fetchone()['cnt']
    total_pages = (total + per_page - 1) // per_page

    conn.close()
    return render_template(
        'games.html',
        games=saved_games,
        page=page,
        total_pages=total_pages,
        sort=sort,
        order=order,
        tag=tag
    )

# Add your steam_id setting & update_status endpoints here...

if __name__ == '__main__':
    init_db()
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 10000))
    app.run(host=host, port=port)
