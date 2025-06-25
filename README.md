# 🎮 Steam Backlog Tracker

A **Flask-based web app** to track your Steam game backlog. Automatically fetches your game library, playtime, and achievement data — then lets you **filter**, **sort**, and **manage** your collection in a clean dashboard.

---

## 🎬 Demo

▶️ **[Click here to watch the full demo video](steambacklogDemo/steambacklogDemo.webm)**

<details>
<summary>GIF Preview</summary>

![Steam Backlog Tracker Demo](steambacklogDemo/steambacklogDemo.gif)

</details>

---

## ✅ Features

- 🔐 **User Authentication**
  - Secure password hashing via `Werkzeug`
  - Session handling with Flask and `.env` secrets

- 🛢️ **PostgreSQL Integration**
  - `users` and `games` tables managed via `psycopg2`

- 🎮 **Steam API Integration**
  - Resolves custom URLs to SteamID64
  - Fetches owned games with titles & playtime
  - Pulls achievement completion % (where available)

- 📋 **Game Dashboard**
  - Store & view: game ID, name, playtime, status, achievement %
  - Filter, sort, and paginate your Steam library

---

## 🧭 Roadmap

- [x] Update game status (Backlog, In Progress, Completed)
- [ ] Add **game tags** (DB + UI filters)
- [ ] Show **cover art** for each game
- [ ] Improve sort by **achievement completion %**
- [ ] Add **unit & integration tests**
- [ ] Deploy to production (Render + GitHub Pages or Flask backend)

---

## 🚀 Getting Started

### 🔧 Prerequisites

- Python 3.10+
- PostgreSQL
- Steam API Key

> 🛠️ Add your credentials in a `.env` file:

