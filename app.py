from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import requests
import json
from datetime import datetime
import os
from dotenv import load_dotenv

import logging
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
import time

load_dotenv()

def setup_logging():
    log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO'))
    log_file = os.getenv('LOG_FILE', 'news-hub.log')
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # ✅ ПРОСТОЙ ТЕКСТОВЫЙ формат БЕЗ extra полей
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)8s] %(name)s:%(lineno)3d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.stream.reconfigure(encoding='utf-8')
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    ))
    
    logging.basicConfig(level=log_level, handlers=[file_handler, console_handler], force=True)
    return logging.getLogger('news-hub')


logger = setup_logging()

def log_with_context(message, level='info', extra=None):
    """Логирование с автоматическим контекстом"""
    default_extra = {
        'user_context': getattr(current_user, 'username', 'Anonymous') if current_user.is_authenticated else 'Anonymous',
        'ip_context': getattr(request, 'remote_addr', 'N/A')
    }
    if extra:
        default_extra.update(extra)
    
    getattr(logger, level)(message, extra=default_extra)

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
        logger.info(f"Пользователь загружен: {user_data['username']} (ID: {user_id})")
        return User(user_data['id'], user_data['username'])
    logger.warning(f"Пользователь не найден: ID {user_id}")
    return None


from flask import request
from flask_login import current_user

@app.before_request
def log_request():
    # ✅ Правильное добавление extra полей
    logger.info(
        f"{request.method} {request.path}",
        extra={
            'user_context': getattr(current_user, 'username', 'Anonymous'),
            'ip_context': request.remote_addr
        }
    )


@app.route('/')
def index():
    logger.info("Главная страница просмотрена")
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        logger.info(f"Регистрация пользователя: {username}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (username, password_hash) VALUES (%s, %s)',
                (username, generate_password_hash(password))
            )
            conn.commit()
            logger.info(f"Пользователь зарегистрирован: {username}")
            flash('Регистрация успешна! Можете войти.')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            logger.warning(f"Пользователь уже существует: {username}")
            flash('Пользователь с таким именем уже существует.')
        except Exception as e:
            logger.error(f"Ошибка регистрации {username}: {e}")
            flash('Ошибка регистрации.')
        finally:
            cursor.close()
            conn.close()
    
    return render_template('login.html', action='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        logger.info(f"Попытка входа: {username}")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], user_data['username'])
            login_user(user)
            logger.info(f"Успешный вход: {username}")
            return redirect(url_for('feeds'))
        logger.warning(f"Неудачная попытка входа: {username}")
        flash('Неверное имя пользователя или пароль.')
        logger.error(f"Ошибка входа {username}: {e}")
        flash('Ошибка входа.')
    
    return render_template('login.html')

@app.route('/feeds')
@login_required
def feeds():
    logger.info(f"Просмотр новостей пользователем: {current_user.username}")
    try:
        # Crypto news API с .env
        url = f"{os.getenv('NEWS_API_URL', 'https://cryptonews-api.com/api/v1')}/category"
        params = {
            'token': os.getenv('NEWS_API_TOKEN', 'demo'),
            'section': 'general',
            'items': 5
        }
        response = requests.get(url, params=params, timeout=10)
        logger.info(f"Получены последние новости пользователем {current_user.username}") 
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
    logger.info(f"{current_user.username} добавляет в избранное: {data['title'][:50]}")
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
    logger.info(f"Добавлено в избранное (ID: {cursor.lastrowid}) пользователем {current_user.username}")
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
    logger.info(f"Найдено {len(favorites)} избранных для {current_user.username}")
    cursor.close()
    conn.close()
    
    return render_template('favorites.html', favorites=favorites)

@app.route('/logout')
@login_required
def logout():
    username = current_user.username
    logout_user()
    logger.info(f"Выход: {username}")
    return redirect(url_for('index'))

@app.after_request
def after_request(response):
    logger.debug(f"{request.method} {request.path} -> {response.status_code}")
    return response

@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404: {request.path}")
    return "Страница не найдена", 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500: {request.path} - {str(error)}")
    return "Внутренняя ошибка сервера", 500


if __name__ == '__main__':
    logger.info("🚀 News Hub запущен на http://0.0.0.0:5000")
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)

