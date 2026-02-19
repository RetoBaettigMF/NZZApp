#!/usr/bin/env python3
"""
Flask API Server mit Authentication für NZZ Reader.
"""
import os
import json
import bcrypt
import jwt
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Konfiguration
ARTICLES_DIR = Path(os.getenv('OUTPUT_DIR', './articles'))
USERS_FILE = Path(__file__).parent / 'users.json'
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
TOKEN_EXPIRY_HOURS = 24

# ==================== User Management ====================

def load_users():
    """Lädt User aus JSON-Datei."""
    if not USERS_FILE.exists():
        return {'users': []}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(data):
    """Speichert User in JSON-Datei."""
    with open(USERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def hash_password(password):
    """Hasht ein Passwort mit bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """Prüft ob Passwort mit Hash übereinstimmt."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_token(user):
    """Generiert JWT Token für User."""
    payload = {
        'user_id': user['id'],
        'email': user['email'],
        'is_admin': user.get('is_admin', False),
        'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def decode_token(token):
    """Dekodiert JWT Token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# ==================== Auth Middleware ====================

def token_required(f):
    """Decorator für geschützte Endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': 'Token fehlt'}), 401

        if token.startswith('Bearer '):
            token = token[7:]

        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Token ungültig oder abgelaufen'}), 401

        return f(payload, *args, **kwargs)

    return decorated

def admin_required(f):
    """Decorator für Admin-only Endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': 'Token fehlt'}), 401

        if token.startswith('Bearer '):
            token = token[7:]

        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Token ungültig oder abgelaufen'}), 401

        if not payload.get('is_admin'):
            return jsonify({'error': 'Admin-Rechte erforderlich'}), 403

        return f(payload, *args, **kwargs)

    return decorated

# ==================== Auth Endpoints ====================

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login Endpoint."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email und Passwort erforderlich'}), 400

    users_data = load_users()
    user = next((u for u in users_data['users'] if u['email'] == email), None)

    if not user or not check_password(password, user['password']):
        return jsonify({'error': 'Ungültige Anmeldedaten'}), 401

    token = generate_token(user)

    return jsonify({
        'token': token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'is_admin': user.get('is_admin', False)
        }
    })

@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_current_user(payload):
    """Gibt aktuellen User zurück."""
    return jsonify({
        'id': payload['user_id'],
        'email': payload['email'],
        'is_admin': payload.get('is_admin', False)
    })

@app.route('/api/auth/change-password', methods=['POST'])
@token_required
def change_password(payload):
    """User ändert eigenes Passwort."""
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return jsonify({'error': 'Altes und neues Passwort erforderlich'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'Passwort muss mindestens 6 Zeichen lang sein'}), 400

    users_data = load_users()
    user = next((u for u in users_data['users'] if u['id'] == payload['user_id']), None)

    if not user:
        return jsonify({'error': 'User nicht gefunden'}), 404

    if not check_password(old_password, user['password']):
        return jsonify({'error': 'Altes Passwort falsch'}), 401

    user['password'] = hash_password(new_password)
    save_users(users_data)

    return jsonify({'message': 'Passwort erfolgreich geändert'})

# ==================== User Management (Admin) ====================

@app.route('/api/users', methods=['GET'])
@admin_required
def list_users(payload):
    """Listet alle User (Admin only)."""
    users_data = load_users()
    users = [{
        'id': u['id'],
        'email': u['email'],
        'is_admin': u.get('is_admin', False),
        'created_at': u.get('created_at')
    } for u in users_data['users']]

    return jsonify({'users': users})

@app.route('/api/users', methods=['POST'])
@admin_required
def create_user(payload):
    """Erstellt neuen User (Admin only)."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email und Passwort erforderlich'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Passwort muss mindestens 6 Zeichen lang sein'}), 400

    users_data = load_users()

    # Prüfe ob Email bereits existiert
    if any(u['email'] == email for u in users_data['users']):
        return jsonify({'error': 'Email bereits vergeben'}), 400

    # Neue User-ID generieren
    max_id = max([int(u['id']) for u in users_data['users']], default=0)
    new_id = str(max_id + 1)

    new_user = {
        'id': new_id,
        'email': email,
        'password': hash_password(password),
        'is_admin': False,
        'created_at': datetime.utcnow().isoformat() + 'Z'
    }

    users_data['users'].append(new_user)
    save_users(users_data)

    return jsonify({
        'message': 'User erstellt',
        'user': {
            'id': new_user['id'],
            'email': new_user['email'],
            'is_admin': False
        }
    }), 201

@app.route('/api/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(payload, user_id):
    """Löscht User (Admin only)."""
    users_data = load_users()

    # Verhindere Löschen des eigenen Accounts
    if user_id == payload['user_id']:
        return jsonify({'error': 'Du kannst deinen eigenen Account nicht löschen'}), 400

    user = next((u for u in users_data['users'] if u['id'] == user_id), None)
    if not user:
        return jsonify({'error': 'User nicht gefunden'}), 404

    users_data['users'] = [u for u in users_data['users'] if u['id'] != user_id]
    save_users(users_data)

    return jsonify({'message': 'User gelöscht'})

@app.route('/api/users/<user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(payload, user_id):
    """Setzt User-Passwort zurück (Admin only)."""
    data = request.get_json()
    new_password = data.get('new_password')

    if not new_password:
        return jsonify({'error': 'Neues Passwort erforderlich'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'Passwort muss mindestens 6 Zeichen lang sein'}), 400

    users_data = load_users()
    user = next((u for u in users_data['users'] if u['id'] == user_id), None)

    if not user:
        return jsonify({'error': 'User nicht gefunden'}), 404

    user['password'] = hash_password(new_password)
    save_users(users_data)

    return jsonify({'message': 'Passwort zurückgesetzt'})

# ==================== Article Endpoints (Protected) ====================

@app.route('/api/latest', methods=['GET'])
@token_required
def get_latest(payload):
    """Gibt das neueste verfügbare Datum zurück."""
    try:
        zips = sorted(ARTICLES_DIR.glob('*.zip'), reverse=True)

        if not zips:
            return jsonify({'error': 'No archives found'}), 404

        latest = zips[0]
        date = latest.stem

        manifest_path = ARTICLES_DIR / date / 'manifest.json'
        manifest = {}
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

        response = {
            'date': date,
            'download_url': f'/api/download/{date}',
            'manifest': manifest
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/list', methods=['GET'])
@token_required
def get_list(payload):
    """Gibt eine Liste aller verfügbaren Archive zurück."""
    try:
        zips = sorted(ARTICLES_DIR.glob('*.zip'), reverse=True)
        archives = []

        for zip_file in zips:
            date = zip_file.stem
            manifest_path = ARTICLES_DIR / date / 'manifest.json'
            manifest = {}
            if manifest_path.exists():
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)

            archives.append({
                'date': date,
                'download_url': f'/api/download/{date}',
                'manifest': manifest
            })

        return jsonify({'archives': archives})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<date>', methods=['GET'])
@token_required
def download_zip(payload, date):
    """Serviert eine ZIP-Datei."""
    try:
        zip_path = ARTICLES_DIR / f"{date}.zip"

        if not zip_path.exists():
            return jsonify({'error': 'Archive not found'}), 404

        return send_file(
            zip_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{date}.zip"
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== Health Check ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health Check Endpoint (ungeschützt)."""
    return jsonify({'status': 'ok'})

# ==================== Server ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    print(f"✓ Flask API Server läuft auf http://localhost:{port}")
    print(f"  - /api/auth/login - Login")
    print(f"  - /api/latest     - Neuestes Archiv (geschützt)")
    print(f"  - /api/list       - Alle Archive (geschützt)")
    print(f"  - /api/users      - User-Verwaltung (Admin)")
    print("\nDrücke Ctrl+C zum Beenden")

    app.run(host='0.0.0.0', port=port, debug=True)
