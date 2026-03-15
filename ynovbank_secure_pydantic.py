from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
import sqlite3
import subprocess
import os
import html
import re
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, validator

# Chargement des variables d'environnement
load_dotenv()

app = Flask(__name__)
# Récupération de la clé secrète depuis le .env
app.secret_key = os.getenv("SECRET_KEY", "prod-super-secret-key-123")

# ============================================================
# MODÈLES DE VALIDATION PYDANTIC (BONUS)
# ============================================================

class LoginSchema(BaseModel):
    username: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=50)

class CommentSchema(BaseModel):
    author: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=500)

class SearchSchema(BaseModel):
    name: str = Field(min_length=1, max_length=30)

    @validator('name')
    def name_must_be_alphanumeric(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Le nom doit être alphanumérique (lettres, chiffres, _, -)')
        return v

# ============================================================
# CONFIGURATION BASE DE DONNÉES & CSS
# ============================================================

def get_db():
    conn = sqlite3.connect('bank.db')
    conn.row_factory = sqlite3.Row
    return conn

CSS = '''
<style>
    body { font-family: 'Segoe UI', sans-serif; background-color: #0f1117; color: #e8e8f0; padding: 20px; }
    .header { background: linear-gradient(135deg, #1a0533, #0d1b2a); padding: 20px; border-radius: 8px; border-bottom: 2px solid #6c3fc5; }
    nav { background: #1e1e2e; padding: 15px; border-radius: 8px; margin: 20px 0; display: flex; gap: 20px; }
    nav a { color: #a78bfa; text-decoration: none; font-weight: bold; }
    .card { background: #1e1e2e; border: 1px solid #2d2d44; border-radius: 8px; padding: 20px; }
    input, textarea { background: #0f1117; border: 1px solid #2d2d44; color: white; padding: 10px; width: 100%; margin: 5px 0; }
    button { background: #6c3fc5; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
    pre { background: #000; padding: 15px; color: #10b981; }
    .error { color: #ef4444; font-weight: bold; }
</style>
'''

LAYOUT = f'''
<!DOCTYPE html>
<html>
<head>{CSS}</head>
<body>
    <div class="header"><h1>🏦 YnovBank (Secured Version)</h1></div>
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

# ============================================================
# ROUTES SÉCURISÉES
# ============================================================

@app.route('/')
def index():
    return render_template_string(LAYOUT, content="<h2>Bienvenue</h2><p>Interface bancaire sécurisée contre le Top 10 OWASP.</p>")

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        try:
            # Validation Pydantic
            data = LoginSchema(username=request.form.get('username'), password=request.form.get('password'))
            conn = get_db()
            # Correction SQLi : Requête paramétrée
            user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (data.username, data.password)).fetchone()
            conn.close()
            if user:
                session['user'] = user['username']
                return redirect(url_for('index'))
            error = "Identifiants invalides"
        except ValidationError as e:
            error = f"Erreur de format : {e.errors()[0]['msg']}"
    
    content = f'''<h2>Connexion</h2><form method="post">
        <input name="username" placeholder="Username"><br>
        <input type="password" name="password" placeholder="Password"><br>
        <button type="submit">Se connecter</button></form>
        {"<p class='error'>"+error+"</p>" if error else ""}'''
    return render_template_string(LAYOUT, content=content)

@app.route('/search')
def search():
    name = request.args.get('name', '')
    results_html = "<h2>Recherche</h2><form><input name='name' placeholder='Nom...'><button>Chercher</button></form>"
    if name:
        try:
            # Validation Pydantic (Bonus)
            valid_search = SearchSchema(name=name)
            conn = get_db()
            rows = conn.execute("SELECT username, role, balance FROM users WHERE username=?", (valid_search.name,)).fetchall()
            conn.close()
            results_html += "<ul>" + "".join([f"<li>{r['username']} - {r['role']} ({r['balance']}€)</li>" for r in rows]) + "</ul>"
        except ValidationError as e:
            results_html += f"<p class='error'>Validation échouée : {e.errors()[0]['msg']}</p>"
    return render_template_string(LAYOUT, content=results_html)

@app.route('/comments')
def view_comments():
    conn = get_db()
    rows = conn.execute("SELECT author, content FROM comments ORDER BY id DESC").fetchall()
    conn.close()
    comments_list = "".join([f"<div style='border-bottom:1px solid #2d2d44'><b>{r['author']}</b>: {r['content']}</div>" for r in rows])
    content = f'''<h2>Commentaires</h2><div>{comments_list}</div><hr>
        <input id="a" placeholder="Nom"><textarea id="c" placeholder="Message"></textarea>
        <button onclick="send()">Envoyer</button>
        <script>
            function send() {{
                fetch('/comment', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{author: document.getElementById('a').value, content: document.getElementById('c').value}})
                }}).then(res => res.ok ? location.reload() : alert("Erreur Pydantic/XSS"));
            }}
        </script>'''
    return render_template_string(LAYOUT, content=content)

@app.route('/comment', methods=['POST'])
def add_comment():
    try:
        # Validation Pydantic
        data = CommentSchema(**request.json)
        # Correction XSS : Echappement HTML
        author = html.escape(data.author)
        content = html.escape(data.content)
        conn = get_db()
        conn.execute("INSERT INTO comments (author, content) VALUES (?, ?)", (author, content))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except ValidationError as e:
        return jsonify({"status": "error"}), 400

@app.route('/ping')
def ping():
    host = request.args.get('host', '')
    output = ""
    if host:
        # Validation stricte Regex
        if not re.match(r'^[a-zA-Z0-9.-]+$', host):
            output = "Caractères interdits détectés."
        else:
            try:
                # Correction OS Injection : shell=False + Liste d'arguments
                res = subprocess.run(["ping", "-c", "2", host], shell=False, capture_output=True, text=True, timeout=5)
                output = res.stdout + res.stderr
            except Exception as e:
                output = str(e)
    content = f'<h2>Ping</h2><form><input name="host" placeholder="8.8.8.8"><button>Lancer</button></form><pre>{output}</pre>'
    return render_template_string(LAYOUT, content=content)

if __name__ == '__main__':
    # Correction Debug : Désactivation du mode debug
    app.run(debug=False, host='0.0.0.0', port=5000)