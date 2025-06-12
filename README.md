# Steam Backlog Tracker 🚀

A Flask‑based app to track your Steam game backlog — fetches your library, playtime, achievements %, and lets you filter, sort, and paginate your collection.

---

## 🧾 Features Completed

- **User Authentication** with secure password hashing (Werkzeug)
- **Session Management** via Flask `secret_key` from `.env`
- **PostgreSQL Integration** (`users`, `games` tables via psycopg2)
- **Steam API Integration**:
  - Store SteamID64 or custom URL and resolve vanity names
  - Pull owned games (with title and playtime)
  - Fetch achievement completion %
- **Game Dashboard**:
  - Store/retrieve game data (`appid`, `name`, `playtime`, `status`, `completion`)
  - Filter, sort, and paginate your game list

---

## 🛠️ Roadmap: What’s Next

- [ ] Add **tags** support (new DB column + UI filter)
- [ ] Allow users to **update game status** (Playing, Completed, etc.)
- [ ] Display **game cover icons**
- [ ] Enhance table sorting (especially by completion %)
- [ ] Write **unit & integration tests**
- [ ] Deploy to production (Render / GitHub Pages + API host)

---

## 🚀 How to Get Started

### Prerequisites

- Python 3.10+  
- PostgreSQL  
- A valid **Steam API key** – set in `.env`# steamBacklog
