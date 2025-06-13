import time
from flask import Flask, render_template,redirect,url_for,request,session,flash
from werkzeug.security import generate_password_hash,check_password_hash
import psycopg2 
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import requests
from urllib.parse import urlparse 

load_dotenv()
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

app = Flask(__name__)
app.secret_key = SECRET_KEY


def get_db_connection():
    return psycopg2.connect(
        ##database connection
        dbname = 'steamtracker',
        user ='fonz',
        password='test',
        host='localhost',
        cursor_factory = RealDictCursor
    )

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
                CREATE TABLE IF NOT EXISTS users(
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                steam_id TEXT
                );''')
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
        password = generate_password_hash(request.form['password'])
        try:
            conn = get_db_connection()
            cur =conn.cursor()
            cur.execute('INSERT INTO users (email,password) VALUES (%s, %s)', (email,password))
            conn.commit()
            flash('Register completed. Please Login.')
            return redirect(url_for('login'))
        except psycopg2.errors.UniqueViolation:
            flash('Email already registered.')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login/', methods =['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        print(f"Login attempt: {email} / {password}")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, password FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        conn.close()

        print("DB result:", user)

        if user:
            print("Stored hash:", user['password'])
            print("Password match:", check_password_hash(user['password'], password))

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            print("Login successful")
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials')
            print("Login failed")

    return render_template('login.html')

@app.route('/dashboard/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/logout/')
def logout():
    session.pop('user_id',None)
    flash('Logged out sucessfully.')
    return redirect(url_for('login'))


@app.route('/games/')
def games():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()

        ## Adding sorting and pagination
    page = request.args.get('page', type = int, default=1)
    per_page = request.args.get('per_page', type = int , default =20)
    sort = request.args.get('sort', default = 'name')
    order = request.args.get('order', default = 'asc').lower()
    tag = request.args.get('tag')
    
    base_sql = """
    SELECT appid, name, playtime, status, completion
    FROM games
    WHERE user_id = %s
    """
    
    params = [user_id]
    
    if tag:
        base_sql += "AND %s = ANY(tags)"
        params.append(tag)
    
    
    if sort not in ('name','playtime','completion'):
        sort = 'name'
    order_dir = 'DESC' if order == 'desc' else 'ASC'
    base_sql += f"ORDER BY {sort} {order_dir}"
    
    offset =(page -1)*per_page
    base_sql += " LIMIT %s OFFSET %s"
    params +=[per_page,offset]
    
    cur.execute(base_sql,params)
    games = cur.fetchall()
    count_sql = "SELECT COUNT(*) FROM games WHERE user_id = %s" + (" AND %s = ANY(tags)" if tag else "")
    cur.execute(count_sql, [user_id] + ([tag] if tag else []))
    total = cur.fetchone()['count']
    total_pages = (total + per_page -1)
    
    cur.execute('SELECT steam_id FROM users WHERE id = %s',(user_id,))
    result = cur.fetchone()


    if not result or not result['steam_id']:
        conn.close()
        flash("Steam Id not set. Return to dashboard and enter it")
        return redirect(url_for('dashboard'))
    
    steam_id = result['steam_id']

    url ='http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/'

    params = {
        'key': STEAM_API_KEY,
        'steamid' : steam_id,
        'include_appinfo': 1,
        'include_played_free_games':1,
        'format' : 'json',
        'skip_unvetted_apps': 'false'
    }
    for attempt in range(3):  # try up to 3 times
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json().get('response', {}).get('games', [])
            if data:
                break
        time.sleep(5)  # wait before retrying
    else:
        conn.close()
        flash("Cannot fetch games from Steam right now. Try again later.")
        return redirect(url_for('dashboard'))

    
    data = response.json().get('response', {}).get('games',[])



    cur.execute(
        'SELECT appid,status from games WHERE user_id = %s',(user_id,)
    )
    status_map = {r['appid']: r['status'] for r in cur.fetchall()}

    displayed = []



    for game in data:
        aid = game['appid']
        ach_resp = requests.get(
            'https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/',
            params={
                'key': STEAM_API_KEY,
                'steamid': steam_id,
                'appid': aid,
                'l': 'en'
                }
        )
    
        try:
            ach_json = ach_resp.json()
        except ValueError:
            print(f"Bad JSON for app {aid}: {ach_resp.text[:200]}")
            unlocked = 0
            total = 0
        else:
            stats = ach_json.get('playerstats', {})
            if stats.get('success') is False or 'achievements' not in stats:
                unlocked = 0
                total = 0
            else:
                ach_list = stats.get('achievements', [])
                unlocked = sum(a.get('achieved', 0) == 1 for a in ach_list)
                total = len(ach_list)

        completionPercent = round(unlocked / total * 100, 1) if total else 0
        status = status_map.get(aid,'Backlog')
        cur.execute('''
    INSERT INTO games
      (user_id, appid, name, playtime, status, completion)
    VALUES
      (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id, appid) DO UPDATE
    SET
      name = EXCLUDED.name,
      playtime = EXCLUDED.playtime,
      status = EXCLUDED.status,
      completion = EXCLUDED.completion;
    ''',
    (user_id, aid, game['name'], game.get('playtime_forever', 0), status, completionPercent))
        displayed.append({
            'appid': aid,
            'name': game['name'],
            'playtime': game.get('playtime_forever', 0),
            'completion': completionPercent,
            'status': status
        })

  
  
    conn.commit()

    cur.execute('SELECT appid, name, playtime, status,completion FROM games WHERE user_id = %s', (user_id,))
    saved_games = cur.fetchall()
    conn.close()
    return render_template('games.html', games=saved_games,
                           page = page,
                           total_pages = total_pages,
                           sort = sort,
                           order = order,
                           tag = tag)

@app.route('/set_steam_id/',methods = ['POST'])
def set_steam_id():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    profile_url = request.form.get('steam_profile_url','').strip()
    steam_id64 = request.form.get('steam_id64','').strip()
    user_id =session['user_id']
    steam_id = None

    print("profile_url:", profile_url)
    print("steam_id64: " , steam_id64)

    if not profile_url and not steam_id64:
        flash("You must enter either a steam profile url or a steamID64.")
        return redirect(url_for("dashboard"))
    
    if profile_url:
        if "steamcommunity.com/id/" in profile_url:
            path = urlparse(profile_url).path
            vanity = path.split("/id/")[1].split("/")[0]
            res = requests.get("https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/", params={
            "key": STEAM_API_KEY,
            "vanityurl" : vanity
            })
            try: 
                data = res.json()
            except ValueError:
                flash("Unexpected response from Steam API")
                return redirect(url_for('dashboard'))
            
            if data['response']['success']==1:
                steam_id = data['response']['steamid']
                flash("Steam Id resolved succesffully.")
            else:
                flash("Failed to resolve custom steam URL.")
                return redirect(url_for('dashboard'))
        elif "steamcommunity.com/profiles/" in profile_url:
            steam_id =profile_url.split("/profiles/")[1].split("/")[0]
            flash("Steam Url saved.")
            print(steam_id)
        else:
            flash("Invalid steam profile url format.")
    elif steam_id64:
        if steam_id64.isdigit() and len(steam_id64) >= 17:
            steam_id =steam_id64
            flash("Steam U64 saved.")
        else:
            flash("Invalid SteamID64 format.")
            return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE users SET steam_id = %s WHERE id = %s',(steam_id,session['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    
    flash('Steam ID saved!')
    return redirect(url_for('dashboard'))


@app.route('/update_status/<int:appid>/',methods=['POST'])
def update_status(appid):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    new_status = request.form.get('status')
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
         'UPDATE games SET status = %s WHERE user_id = %s AND appid = %s',
        (new_status, user_id, appid)
    )
    conn.commit()
    cur.close()
    conn.close()

    flash(f"Updated game {appid} to '{new_status}'")
    return redirect(url_for('games'))



if __name__ == '__main__':
    init_db()
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 10000))
    app.run(host=host, port=port)