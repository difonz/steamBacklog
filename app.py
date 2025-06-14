import time
import os
import requests
from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2 import connect, OperationalError
from psycopg2.extras import RealDictCursor
import psycopg2.errors
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
SECRET_KEY     = os.getenv("SECRET_KEY")

app = Flask(__name__)
app.secret_key = SECRET_KEY

def get_db_connection():
    url = os.getenv("DATABASE_URL_GAMES")
    if not url:
        raise RuntimeError("DATABASE_URL_GAMES not defined")
    try:
        return connect(url, sslmode='require', cursor_factory=RealDictCursor)
    except Exception as e:
        app.logger.error(f"DB connection error: {e}")
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
    conn = None
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
            flash('Registered! You can now log in.')
            return redirect(url_for('login'))
        except psycopg2.errors.UniqueViolation:
            flash('This email is already registered.')
        except Exception as e:
            flash('DB connection failed.')
        finally:
            if conn:
                conn.close()
    return render_template('register.html')

@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        pw = request.form['password']
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('SELECT id, password FROM users WHERE email = %s', (email,))
            user = cur.fetchone()
        except Exception as e:
            flash('Database error-please try again later.')
            app.logger.error(f"Login Db error: {e}")
            return render_template('login.html')
        finally:
            if conn:
                conn.close()
        if user and check_password_hash(user['password'], pw):
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        else:
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

    page     = request.args.get('page',     type=int, default=1)
    per_page = request.args.get('per_page', type=int, default=20)
    sort     = request.args.get('sort',     default='name')
    order    = request.args.get('order',    default='asc').lower()
    tag      = request.args.get('tag')

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
    base_sql += f' ORDER BY {sort} {order_dir} LIMIT %s OFFSET %s'
    offset = (page - 1) * per_page
    params.extend([per_page, offset])

    cur.execute(base_sql, params)
    games_list = cur.fetchall()

    count_sql = 'SELECT COUNT(*) AS cnt FROM games WHERE user_id = %s'
    if tag:
        count_sql += ' AND %s = ANY(tags)'
    cur.execute(count_sql, [user_id] + ([tag] if tag else []))
    total = cur.fetchone()['cnt']
    total_pages = (total + per_page - 1) // per_page

    conn.close()
    return render_template(
        'games.html',
        games=games_list,
        page=page,
        total_pages=total_pages,
        sort=sort,
        order=order,
        tag=tag
    )

@app.route('/set_steam_id/')
def set_steam_id():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    profile_url = request.form.get('steam_profile_url','').strip()
    steam_id64 = request.form.get('steam_id64', '').strip()
    steam_id = None
    
    if profile_url:
        if "/id/" in profile_url:
            vanity = urlparse(profile_url).path.split("/id/")[1].split("/")[0]
            res = requests.get(
                "https://api.steampowered.com/ISteamUsere/ResolveVanityURL/v1/",
                params = {"key": STEAM_API_KEY, "vanityurl":vanity}
            )
            data = res.json().get('response', {})
            if data.get('success') == 1:
                steam_id = data['steamid']
            else:
                flash("Couldnt resolve your vanity URL.")
                return redirect(url_for('dashboard'))
        elif "/profiles/" in profile_url:
            steam_id = profile_url.split("/profiles/")[1].split("/")[0]
        else:
            flash("Enter a valid steam profile url")
            return redirect(url_for('dashboard'))
    elif steam_id64:
        if steam_id64.isdigit() and len(steam_id64) >= 17:
            steam_id = steam_id64
        else:
            flash("Invalid Steam 64 ID")
            return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
       'Update users SET steam_id = %s where id = %s',steam_id,session['user_id'] 
    )
    conn.commit()
    conn.close()
    flash("Steam ID saved!")
    return redirect(url_for('dashboard'))



if __name__ == '__main__':
    init_db()
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '10000'))
    app.run(host=host, port=port)
