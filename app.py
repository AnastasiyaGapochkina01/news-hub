from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import requests
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# MariaDB connection с .env
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'newshub'),
        password=os.getenv('DB_PASSWORD', 'SecurePass123!'),
        database=os.getenv('DB_NAME', 'news_hub')
    )

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'])
    return None

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (username, password_hash) VALUES (%s, %s)',
                (username, generate_password_hash(password))
            )
            conn.commit()
            flash('Регистрация успешна! Можете войти.')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Пользователь с таким именем уже существует.')
        finally:
            cursor.close()
            conn.close()
    
    return render_template('login.html', action='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], user_data['username'])
            login_user(user)
            return redirect(url_for('feeds'))
        flash('Неверное имя пользователя или пароль.')
    
    return render_template('login.html')

@app.route('/feeds')
@login_required
def feeds():
    try:
        # Crypto news API с .env
        url = f"{os.getenv('NEWS_API_URL', 'https://cryptonews-api.com/api/v1')}/category"
        params = {
            'token': os.getenv('NEWS_API_TOKEN', 'demo'),
            'section': 'general',
            'items': 5
        }
        response = requests.get(url, params=params, timeout=10)
        news = response.json().get('data', [])
    except:
        # Fallback новости
        news = [
            {"title": "Bitcoin достигает нового максимума", "description": "BTC цена выросла на 10%", "url": "https://example.com/btc"},
            {"title": "Ethereum обновление Shapella", "description": "Успешный хардфорк", "url": "https://example.com/eth"},
            {"title": "Solana показывает рост", "description": "TPS достигает 65k", "url": "https://example.com/sol"},
            {"title": "DeFi протоколы бьют рекорды", "description": "TVL превысил $100B", "url": "https://example.com/defi"},
            {"title": "NFT рынок восстанавливается", "description": "Объем торгов растет", "url": "https://example.com/nft"}
        ]
    
    return render_template('feeds.html', news=news)

@app.route('/tofavorite', methods=['POST'])
@login_required
def tofavorite():
    data = request.json
    title = data['title']
    description = data['description']
    url = data['url']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO favorites (user_id, title, description, url) VALUES (%s, %s, %s, %s)',
        (current_user.id, title, description, url)
    )
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success'})

@app.route('/list')
@login_required
def list_favorites():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM favorites WHERE user_id = %s ORDER BY created_at DESC', (current_user.id,))
    favorites = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('favorites.html', favorites=favorites)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)

