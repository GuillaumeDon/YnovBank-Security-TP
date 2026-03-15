from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
import sqlite3
import subprocess
import os
import html
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-123")

def get_db():
    conn = sqlite3.connect('bank.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- CSS ORIGINAL RÉINTÉGRÉ ---
CSS = '''
<style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f1117; color: #e8e8f0; margin: 0; padding: 20px; }
    .header { background: linear-gradient(135deg, #1a0533, #0d1b2a); padding: 20px; border-radius: 8px; margin-bottom: 20px; border-bottom: 2px solid #6c3fc5; }
    .header h1 { color: #a78bfa; margin: 0; display: flex; align-items: center; gap: 10px; }
    nav { background: #1e1e2e; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 20px; }
    nav a { color: #a78bfa; text-decoration: none; font-weight: bold; transition: 0.3s; }
    nav a:hover { color: #ffffff; }
    .card { background: #1e1e2e; border: 1px solid #2d2d44; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    input, textarea { background: #0f1117; border: 1px solid #2d2d44; color: white; padding: 10px; border-radius: 4px; margin: 5px 0; width: 100%; box-sizing: border-box; }
    button { background: #6c3fc5; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; }
    button:hover { background: #7c4ee4; }
    pre { background: #000; padding: 15px; border-radius: 4px; color: #10b981; border: 1px solid #2d2d44; }
    .comment { border-bottom: 1px solid #2d2d44; padding: 10px 0; }
    .comment b { color: #a78bfa; }
</style>
'''

LAYOUT = f'''
<!DOCTYPE html>
<html>
<head>{CSS}</head>
<body>
    <div class="header"><h1>🏦 YnovBank</h1></div>
    <nav>
        <a href="/">🏠 Accueil</a>
        <a href="/login">🔐 Connexion</a>
        <a href="/search">🔍 Recherche</a>
        <a href="/comments">💬 Commentaires</a>
        <a href="/ping">📡 Ping</a>
    </nav>
    <div class="card">{{{{ content | safe }}}}</div>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(LAYOUT, content="<h2>Tableau de bord</h2><p>Bienvenue sur votre interface bancaire sécurisée.</p>")

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        # Correction SQLi : Requête paramétrée
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", 
                            (request.form.get('username'), request.form.get('password'))).fetchone()
        conn.close()
        if user:
            session['user'] = user['username']
            return redirect(url_for('index'))
        error = "Identifiants invalides"
    
    content = f'''
        <h2>Connexion</h2>
        <form method="post">
            <input name="username" placeholder="Nom d'utilisateur"><br>
            <input type="password" name="password" placeholder="Mot de passe"><br>
            <button type="submit">Se connecter</button>
        </form>
        {"<p style='color:#ef4444'>"+error+"</p>" if error else ""}
    '''
    return render_template_string(LAYOUT, content=content)

@app.route('/search')
def search():
    name = request.args.get('name', '')
    results_html = "<h2>Recherche d'utilisateurs</h2><form><input name='name' placeholder='Nom...'><button>Chercher</button></form>"
    if name:
        # Correction SQLi : Requête paramétrée
        conn = get_db()
        rows = conn.execute("SELECT username, role, balance FROM users WHERE username=?", (name,)).fetchall()
        conn.close()
        results_html += "<ul>"
        for r in rows:
            results_html += f"<li>{r['username']} - {r['role']} ({r['balance']}€)</li>"
        results_html += "</ul>"
    return render_template_string(LAYOUT, content=results_html)

@app.route('/comments')
def view_comments():
    conn = get_db()
    rows = conn.execute("SELECT author, content FROM comments ORDER BY id DESC").fetchall()
    conn.close()
    
    comments_list = "".join([f"<div class='comment'><b>{r['author']}</b>: {r['content']}</div>" for r in rows])
    content = f'''
        <h2>Commentaires</h2>
        <div id="list">{comments_list}</div>
        <hr>
        <h3>Ajouter un message</h3>
        <input id="a" placeholder="Votre nom">
        <textarea id="c" placeholder="Votre message"></textarea>
        <button onclick="send()">Envoyer</button>
        <script>
            function send() {{
                fetch('/comment', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{author: document.getElementById('a').value, content: document.getElementById('c').value}})
                }}).then(() => location.reload())
            }}
        </script>
    '''
    return render_template_string(LAYOUT, content=content)

@app.route('/comment', methods=['POST'])
def add_comment():
    data = request.json
    # Correction XSS : html.escape
    author = html.escape(data.get('author', 'Anonyme'))
    content = html.escape(data.get('content', ''))
    conn = get_db()
    conn.execute("INSERT INTO comments (author, content) VALUES (?, ?)", (author, content))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/ping')
def ping():
    host = request.args.get('host', '')
    output = ""
    if host:
        try:
            # Correction OS Injection : shell=False
            res = subprocess.run(["ping", "-c", "2", host], shell=False, capture_output=True, text=True, timeout=5)
            output = res.stdout + res.stderr
        except Exception as e:
            output = str(e)
    
    content = f'''
        <h2>Diagnostic Réseau</h2>
        <form><input name="host" placeholder="8.8.8.8"><button>Ping</button></form>
        <pre>{output}</pre>
    '''
    return render_template_string(LAYOUT, content=content)

if __name__ == '__main__':
    # Correction Debug : False
    app.run(debug=False, host='0.0.0.0', port=5000)
