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


    cur.execute('SELECT steam_id FROM users WHERE ID = %s',(user_id,))
    row = cur.fetchone()
    if not row or not row['steam_id']:
        conn.close()
        flash('Please set your Steam Id first')
        return redirect(url_for('dashboard'))
    steam_id = row['steam_id']
    
    url = 'https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/'
    params = {
        'key': STEAM_API_KEY,
        'steamid': steam_id,
        'include_appinfo': 1,
        'include_played_free_games':1,
        'format': 'json'
    }
    
    for _ in range(3):
        resp = requests.get(url,params=params,timeout=5)
        if(resp.status_code == 200):
            break
        time.sleep(2)
    
    else:
        conn.close()
        flash('Unable to fetch steam games right now.')
        return redirect(url_for('dashboard'))
    gamesData = resp.json().get('response', {}).get('games', [])
    
    for games in gamesData:
        cur.execute('''
        INSERT INTO games (user_id, appid, name, playtime, status, completion)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, appid) DO UPDATE SET
        name = EXCLUDED.name,
        playtime = EXCLUDED.playtime;
        ''', (user_id, games['appid'], games['name'], games['playtime_forever'], 'Backlog', 0.0))
    
    conn.commit()
    
    page     = request.args.get('page',     type=int, default=1)
    per_page = request.args.get('per_page', type=int, default=20)
    sort     = request.args.get('sort',     default='name')
    order    = request.args.get('order',    default='asc').lower()
    tag      = request.args.get('tag')

    if sort not in ('name','playtime','completion'):
        sort = 'name'
    
    orderDir = 'DESC' if order == 'desc' else 'ASC'
    offset = (page-1)*per_page
    
    query = f'''
        SELECT appid,name,playtime,status,completion
        FROM games
        WHERE user_id = %s
        {'AND %s = ANY(tags)' if tag else ''}
        ORDER BY {sort} {orderDir}
        LIMIT %s OFFSET %s
    '''
    
    params = [user_id]
    if tag:
        params.append(tag)
    params += [per_page, offset]
    
    gamesList = cur.fetchall()
    countQuery = 'SELECT COUNT(*) AS cnt FROM games WHERE user_id = %s'
    params = [user_id]
    
    if tag:
        countQuery+= 'AND %s =ANY(tags)'
        params.append(tag)
    
    cur.execute(query,params)
    total = cur.fetchone()['cnt']
    total_pages = (total + per_page -1)
    
    conn.close()
    return render_template(
        'games.html',
        games = games,
        page=page,
        total_pages = total_pages,
        sort=sort,
        order=order,
        tag=tag
    )
    
@app.route('/set_steam_id/', methods =['POST'])
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
                "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/",
                params = {"key": STEAM_API_KEY, "vanityurl":vanity},
                timeout =5
            )
            if res.status_code != 200:
                flash(f"Steam API error: status {res.status_code}")
                return redirect(url_for('dashboard'))
            
            try:
                payload = res.json()
            except ValueError:
                flash("Steam API returned invalid JSON.")
                return redirect(url_for('dashboard'))
            
            data = payload.get('response', {})
            if data.get('success') != 1:
                flash("Couldn't resolve vanity URL.")
                return redirect(url_for('dashboard'))
            steam_id = data['steamid']
        elif "/profile/" in profile_url:
            steam_id = profile_url.split("/profiles/")[1].split("/")[0]
        else:
            flash("Enter a valid Steam profile URL")
            return redirect(url_for('dashboard'))
    elif steam_id64:
        if steam_id64.isdigit() and len(steam_id64) >=17:
            steam_id = steam_id64
        else:
            flash("Invalid steam64 ID")
            return redirect(url_for('dashboard'))
        
            
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
       'Update users SET steam_id = %s where id = %s',(steam_id,session['user_id']) 
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
