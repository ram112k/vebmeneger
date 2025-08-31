from flask import Flask, render_template_string, request, redirect, url_for, flash, session
import sqlite3
import hashlib
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'secret-key-12345'  # Секретный ключ для сессий

# HTML шаблоны в виде строк
LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>🔐 Вход в Мессенджер</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="password"] { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .alert { padding: 10px; margin: 10px 0; border-radius: 4px; }
        .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .tabs { display: flex; margin-bottom: 20px; }
        .tab { padding: 10px 20px; cursor: pointer; border: 1px solid #ddd; }
        .tab.active { background: #007bff; color: white; }
    </style>
</head>
<body>
    <h2>🔐 Вход в Мессенджер</h2>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    <div class="tabs">
        <div class="tab {% if not register %}active{% endif %}" onclick="showLogin()">Вход</div>
        <div class="tab {% if register %}active{% endif %}" onclick="showRegister()">Регистрация</div>
    </div>

    <div id="login-form" style="display: {% if not register %}block{% else %}none{% endif %}">
        <form method="POST" action="{{ url_for('auth') }}?action=login">
            <div class="form-group">
                <label>Логин:</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>Пароль:</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">Войти</button>
        </form>
    </div>

    <div id="register-form" style="display: {% if register %}block{% else %}none{% endif %}">
        <form method="POST" action="{{ url_for('auth') }}?action=register">
            <div class="form-group">
                <label>Логин:</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>Телефон:</label>
                <input type="text" name="phone" required>
            </div>
            <div class="form-group">
                <label>Пароль:</label>
                <input type="password" name="password" required>
            </div>
            <div class="form-group">
                <label>Подтверждение пароля:</label>
                <input type="password" name="confirm" required>
            </div>
            <button type="submit">Зарегистрироваться</button>
        </form>
    </div>

    <script>
        function showLogin() {
            document.getElementById('login-form').style.display = 'block';
            document.getElementById('register-form').style.display = 'none';
            document.querySelectorAll('.tab')[0].classList.add('active');
            document.querySelectorAll('.tab')[1].classList.remove('active');
        }
        
        function showRegister() {
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('register-form').style.display = 'block';
            document.querySelectorAll('.tab')[0].classList.remove('active');
            document.querySelectorAll('.tab')[1].classList.add('active');
        }
    </script>
</body>
</html>
'''

CHAT_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>📱 Мессенджер - {{ user.username }}</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; }
        .header { background: #007bff; color: white; padding: 15px; display: flex; justify-content: space-between; }
        .container { display: flex; height: calc(100vh - 60px); }
        .users-panel { width: 300px; border-right: 1px solid #ddd; padding: 15px; overflow-y: auto; }
        .chat-panel { flex: 1; display: flex; flex-direction: column; }
        .messages { flex: 1; padding: 15px; overflow-y: auto; border-bottom: 1px solid #ddd; }
        .message-input { padding: 15px; }
        textarea { width: 100%; height: 60px; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px; }
        button:hover { background: #0056b3; }
        .user-item { padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; }
        .user-item:hover { background: #f5f5f5; }
        .user-item.selected { background: #e3f2fd; }
        .message { margin-bottom: 15px; padding: 10px; border-radius: 8px; }
        .my-message { background: #007bff; color: white; margin-left: 50px; }
        .their-message { background: #e9ecef; margin-right: 50px; }
        .message-time { font-size: 12px; opacity: 0.7; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <div>👤 {{ user.username }} ({{ user.phone }})</div>
        <div>
            <a href="{{ url_for('logout') }}" style="color: white; text-decoration: none;">🚪 Выйти</a>
        </div>
    </div>

    <div class="container">
        <div class="users-panel">
            <h3>👥 Пользователи</h3>
            {% for u in users %}
                <div class="user-item {% if u.id == selected_user_id %}selected{% endif %}" 
                     onclick="selectUser({{ u.id }})">
                    <strong>{{ u.username }}</strong><br>
                    <small>{{ u.phone }}</small>
                </div>
            {% endfor %}
        </div>

        <div class="chat-panel">
            {% if selected_user %}
            <div class="messages" id="messages">
                {% for msg in messages %}
                <div class="message {% if msg.sender_id == user.id %}my-message{% else %}their-message{% endif %}">
                    <div>{{ msg.message_text }}</div>
                    <div class="message-time">
                        {{ msg.created_at.strftime('%H:%M') }} | 
                        {% if msg.sender_id == user.id %}Вы{% else %}{{ selected_user.username }}{% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>

            <div class="message-input">
                <form method="POST" action="{{ url_for('send_message') }}">
                    <input type="hidden" name="receiver_id" value="{{ selected_user.id }}">
                    <textarea name="message" placeholder="Введите сообщение..." required></textarea>
                    <button type="submit">📤 Отправить</button>
                </form>
            </div>
            {% else %}
            <div style="padding: 20px; text-align: center; color: #666;">
                Выберите пользователя для начала общения
            </div>
            {% endif %}
        </div>
    </div>

    <script>
        function selectUser(userId) {
            window.location.href = "{{ url_for('index') }}?selected_user=" + userId;
        }

        // Автопрокрутка вниз сообщений
        window.onload = function() {
            const messagesDiv = document.getElementById('messages');
            if (messagesDiv) {
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        }
    </script>
</body>
</html>
'''

def get_db_connection():
    """Создание подключения к БД"""
    conn = sqlite3.connect('messenger.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def index():
    """Главная страница чата"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    users = conn.execute('SELECT * FROM users WHERE id != ?', (session['user_id'],)).fetchall()
    
    selected_user_id = request.args.get('selected_user', type=int)
    selected_user = None
    messages = []
    
    if selected_user_id:
        selected_user = conn.execute('SELECT * FROM users WHERE id = ?', (selected_user_id,)).fetchone()
        if selected_user:
            messages = conn.execute('''
                SELECT m.*, u.username as sender_name 
                FROM messages m 
                JOIN users u ON m.sender_id = u.id 
                WHERE (m.sender_id = ? AND m.receiver_id = ?) 
                   OR (m.sender_id = ? AND m.receiver_id = ?)
                ORDER BY m.created_at
            ''', (session['user_id'], selected_user_id, selected_user_id, session['user_id'])).fetchall()
    
    conn.close()
    
    return render_template_string(CHAT_HTML, 
                                user=user, 
                                users=users, 
                                selected_user=selected_user,
                                selected_user_id=selected_user_id,
                                messages=messages)

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    """Аутентификация (вход/регистрация)"""
    if request.method == 'POST':
        action = request.args.get('action', 'login')
        
        if action == 'login':
            username = request.form['username']
            password = request.form['password']
            
            conn = get_db_connection()
            user = conn.execute(
                'SELECT * FROM users WHERE username = ? AND password_hash = ?',
                (username, hash_password(password))
            ).fetchone()
            conn.close()
            
            if user:
                session['user_id'] = user['id']
                return redirect(url_for('index'))
            else:
                flash('Неверный логин или пароль', 'error')
                return render_template_string(LOGIN_HTML, register=False)
        
        elif action == 'register':
            username = request.form['username']
            phone = request.form['phone']
            password = request.form['password']
            confirm = request.form['confirm']
            
            if password != confirm:
                flash('Пароли не совпадают', 'error')
                return render_template_string(LOGIN_HTML, register=True)
            
            if len(password) < 4:
                flash('Пароль слишком короткий (мин. 4 символа)', 'error')
                return render_template_string(LOGIN_HTML, register=True)
            
            try:
                conn = get_db_connection()
                conn.execute(
                    'INSERT INTO users (username, phone, password_hash) VALUES (?, ?, ?)',
                    (username, phone, hash_password(password))
                )
                conn.commit()
                conn.close()
                
                flash('Регистрация успешна! Теперь войдите.', 'success')
                return render_template_string(LOGIN_HTML, register=False)
                
            except sqlite3.IntegrityError:
                flash('Логин или телефон уже заняты', 'error')
                return render_template_string(LOGIN_HTML, register=True)
    
    return render_template_string(LOGIN_HTML, register=False)

@app.route('/send_message', methods=['POST'])
def send_message():
    """Отправка сообщения"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    receiver_id = request.form['receiver_id']
    message_text = request.form['message'].strip()
    
    if message_text:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO messages (sender_id, receiver_id, message_text) VALUES (?, ?, ?)',
            (session['user_id'], receiver_id, message_text)
        )
        conn.commit()
        conn.close()
    
    return redirect(url_for('index', selected_user=receiver_id))

@app.route('/logout')
def logout():
    """Выход из системы"""
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/login')
def login():
    """Страница входа"""
    return render_template_string(LOGIN_HTML, register=False)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
