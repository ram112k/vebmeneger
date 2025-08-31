from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import hashlib
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-12345')
app.config['DATABASE'] = os.environ.get('DATABASE_URL', 'messenger.db').replace('postgresql://', 'sqlite:///', 1)

def get_db():
    """Подключение к базе данных"""
    if app.config['DATABASE'].startswith('sqlite:///'):
        db_path = app.config['DATABASE'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
    else:
        # Для PostgreSQL (если захотите перейти)
        import psycopg2
        conn = psycopg2.connect(app.config['DATABASE'])
    
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных"""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица сообщений
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
        
        # Создаем тестовых пользователей если их нет
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            test_users = [
                ('alex', '+79161234567', hash_password('password123')),
                ('maria', '+79269876543', hash_password('password123')),
                ('ivan', '+79031112233', hash_password('password123'))
            ]
            
            for username, phone, pwd_hash in test_users:
                try:
                    cursor.execute(
                        "INSERT INTO users (username, phone, password_hash) VALUES (?, ?, ?)",
                        (username, phone, pwd_hash)
                    )
                except:
                    pass
        
        db.commit()
        db.close()

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def index():
    """Главная страница"""
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", 
            (username,)
        )
        user = cursor.fetchone()
        
        if user and user['password_hash'] == hash_password(password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            db.close()
            return redirect(url_for('chat'))
        else:
            db.close()
            return render_template('login.html', error='Неверный логин или пароль')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации"""
    if request.method == 'POST':
        username = request.form.get('username')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm = request.form.get('confirm')
        
        if not all([username, phone, password, confirm]):
            return render_template('register.html', error='Заполните все поля')
        
        if password != confirm:
            return render_template('register.html', error='Пароли не совпадают')
        
        if len(password) < 4:
            return render_template('register.html', error='Пароль слишком короткий (мин. 4 символа)')
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            password_hash = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, phone, password_hash) VALUES (?, ?, ?)",
                (username, phone, password_hash)
            )
            db.commit()
            db.close()
            return redirect(url_for('login', success='Регистрация успешна! Теперь войдите.'))
        
        except sqlite3.IntegrityError:
            db.close()
            return render_template('register.html', error='Логин или телефон уже заняты')
        except Exception as e:
            db.close()
            return render_template('register.html', error=f'Ошибка: {str(e)}')
    
    return render_template('register.html')

@app.route('/chat')
def chat():
    """Страница чата"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    cursor = db.cursor()
    
    # Получаем список пользователей
    cursor.execute(
        "SELECT id, username, phone FROM users WHERE id != ? ORDER BY username",
        (session['user_id'],)
    )
    users = cursor.fetchall()
    
    # Получаем сообщения если выбран пользователь
    selected_user_id = request.args.get('user_id')
    messages = []
    selected_user = None
    
    if selected_user_id:
        cursor.execute('''
            SELECT m.id, m.sender_id, m.receiver_id, m.message_text, m.created_at, 
                   u.username as sender_name
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE (m.sender_id = ? AND m.receiver_id = ?) 
               OR (m.sender_id = ? AND m.receiver_id = ?)
            ORDER BY m.created_at
        ''', (session['user_id'], selected_user_id, selected_user_id, session['user_id']))
        
        messages = cursor.fetchall()
        
        # Получаем информацию о выбранном пользователе
        cursor.execute(
            "SELECT username FROM users WHERE id = ?",
            (selected_user_id,)
        )
        selected_user = cursor.fetchone()
    
    db.close()
    
    return render_template('chat.html', 
                         users=users, 
                         messages=messages, 
                         selected_user_id=selected_user_id,
                         selected_user=selected_user,
                         username=session['username'])

@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    """API для отправки сообщения"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
    
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    message_text = data.get('message_text', '').strip()
    
    if not receiver_id or not message_text:
        return jsonify({'success': False, 'error': 'Заполните все поля'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO messages (sender_id, receiver_id, message_text) VALUES (?, ?, ?)",
            (session['user_id'], receiver_id, message_text)
        )
        db.commit()
        db.close()
        return jsonify({'success': True, 'message': 'Сообщение отправлено'})
    
    except Exception as e:
        db.close()
        return jsonify({'success': False, 'error': f'Ошибка отправки: {str(e)}'}), 500

@app.route('/api/messages')
def api_messages():
    """API для получения сообщений"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
    
    other_user_id = request.args.get('user_id')
    if not other_user_id:
        return jsonify({'success': False, 'error': 'Укажите user_id'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT m.id, m.sender_id, m.receiver_id, m.message_text, m.created_at, 
               u.username as sender_name
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE (m.sender_id = ? AND m.receiver_id = ?) 
           OR (m.sender_id = ? AND m.receiver_id = ?)
        ORDER BY m.created_at
    ''', (session['user_id'], other_user_id, other_user_id, session['user_id']))
    
    messages = cursor.fetchall()
    db.close()
    
    messages_data = [{
        'id': msg['id'],
        'sender_id': msg['sender_id'],
        'receiver_id': msg['receiver_id'],
        'message_text': msg['message_text'],
        'created_at': msg['created_at'],
        'sender_name': msg['sender_name'],
        'is_own': msg['sender_id'] == session['user_id']
    } for msg in messages]
    
    return jsonify({'success': True, 'messages': messages_data})

@app.route('/logout')
def logout():
    """Выход из системы"""
    session.clear()
    return redirect(url_for('index'))

# Создаем папку templates если ее нет
if not os.path.exists('templates'):
    os.makedirs('templates')

# HTML шаблоны
index_html = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web Messenger</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); text-align: center; max-width: 400px; width: 100%; }
        h1 { color: #333; margin-bottom: 30px; }
        .btn { display: inline-block; padding: 12px 30px; margin: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 8px; font-size: 16px; transition: transform 0.2s; }
        .btn:hover { transform: translateY(-2px); }
    </style>
</head>
<body>
    <div class="container">
        <h1>💬 Web Messenger</h1>
        <p>Добро пожаловать в современный мессенджер</p>
        <div>
            <a href="/login" class="btn">Войти</a>
            <a href="/register" class="btn">Регистрация</a>
        </div>
    </div>
</body>
</html>
'''

login_html = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход - Web Messenger</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); max-width: 400px; width: 100%; }
        h1 { color: #333; text-align: center; margin-bottom: 30px; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; }
        input:focus { outline: none; border-color: #667eea; }
        button { width: 100%; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; margin: 10px 0; }
        button:hover { opacity: 0.9; }
        .error { color: #e74c3c; text-align: center; margin: 10px 0; }
        .success { color: #27ae60; text-align: center; margin: 10px 0; }
        .link { text-align: center; margin-top: 20px; }
        a { color: #667eea; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 Вход</h1>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        {% if request.args.get('success') %}
        <div class="success">{{ request.args.get('success') }}</div>
        {% endif %}
        <form method="POST">
            <input type="text" name="username" placeholder="Логин" value="alex" required>
            <input type="password" name="password" placeholder="Пароль" value="password123" required>
            <button type="submit">Войти</button>
        </form>
        <div class="link">
            Нет аккаунта? <a href="/register">Зарегистрироваться</a>
        </div>
    </div>
</body>
</html>
'''

register_html = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Регистрация - Web Messenger</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); max-width: 400px; width: 100%; }
        h1 { color: #333; text-align: center; margin-bottom: 30px; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; }
        input:focus { outline: none; border-color: #667eea; }
        button { width: 100%; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; margin: 10px 0; }
        button:hover { opacity: 0.9; }
        .error { color: #e74c3c; text-align: center; margin: 10px 0; }
        .link { text-align: center; margin-top: 20px; }
        a { color: #667eea; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📝 Регистрация</h1>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST">
            <input type="text" name="username" placeholder="Логин" required>
            <input type="text" name="phone" placeholder="Телефон" required>
            <input type="password" name="password" placeholder="Пароль" required>
            <input type="password" name="confirm" placeholder="Подтверждение пароля" required>
            <button type="submit">Зарегистрироваться</button>
        </form>
        <div class="link">
            Уже есть аккаунт? <a href="/login">Войти</a>
        </div>
    </div>
</body>
</html>
'''

chat_html = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Чат - Web Messenger</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f0f2f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
        .chat-container { display: flex; height: calc(100vh - 60px); }
        .sidebar { width: 250px; background: white; border-right: 1px solid #ddd; overflow-y: auto; }
        .sidebar-header { padding: 15px; border-bottom: 1px solid #ddd; }
        .user-list { padding: 10px; }
        .user-item { padding: 10px; margin: 5px 0; background: #f8f9fa; border-radius: 5px; cursor: pointer; transition: background 0.3s; }
        .user-item:hover, .user-item.active { background: #667eea; color: white; }
        .chat-main { flex: 1; display: flex; flex-direction: column; }
        .chat-header { padding: 15px; background: white; border-bottom: 1px solid #ddd; }
        .messages-container { flex: 1; padding: 20px; overflow-y: auto; background: white; }
        .message { max-width: 70%; margin: 10px 0; padding: 12px; border-radius: 15px; }
        .message-own { background: #667eea; color: white; margin-left: auto; border-bottom-right-radius: 5px; }
        .message-other { background: #f0f2f5; color: #333; margin-right: auto; border-bottom-left-radius: 5px; }
        .message-input { display: flex; padding: 15px; background: white; border-top: 1px solid #ddd; }
        .message-input input { flex: 1; padding: 12px; border: 2px solid #ddd; border-radius: 25px; margin-right: 10px; }
        .message-input button { padding: 12px 20px; background: #667eea; color: white; border: none; border-radius: 25px; cursor: pointer; }
        .logout-btn { background: #e74c3c; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="header">
        <h2>💬 Web Messenger - {{ username }}</h2>
        <a href="/logout" class="logout-btn">Выйти</a>
    </div>

    <div class="chat-container">
        <div class="sidebar">
            <div class="sidebar-header">
                <h3>👥 Пользователи</h3>
            </div>
            <div class="user-list">
                {% for user in users %}
                <div class="user-item {% if user.id == selected_user_id|int %}active{% endif %}" 
                     onclick="selectUser({{ user.id }})">
                    {{ user.username }} ({{ user.phone }})
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="chat-main">
            <div class="chat-header">
                <h3>
                    {% if selected_user %}
                    💬 Чат с {{ selected_user.username }}
                    {% else %}
                    Выберите пользователя для чата
                    {% endif %}
                </h3>
            </div>

            <div class="messages-container" id="messages-container">
                {% for message in messages %}
                <div class="message {% if message.sender_id == session.user_id %}message-own{% else %}message-other{% endif %}">
                    <strong>{{ message.sender_name }}:</strong> {{ message.message_text }}
                    <div style="font-size: 0.8em; opacity: 0.7;">
                        {{ message.created_at }}
                    </div>
                </div>
                {% endfor %}
            </div>

            {% if selected_user_id %}
            <div class="message-input">
                <input type="text" id="message-text" placeholder="Введите сообщение..." 
                       onkeypress="if(event.key === 'Enter') sendMessage()">
                <button onclick="sendMessage()">📤 Отправить</button>
            </div>
            {% endif %}
        </div>
    </div>

    <script>
        function selectUser(userId) {
            window.location.href = `/chat?user_id=${userId}`;
        }

        async function sendMessage() {
            const messageText = document.getElementById('message-text').value.trim();
            if (!messageText) return;

            const response = await fetch('/api/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    receiver_id: {{ selected_user_id }},
                    message_text: messageText
                })
            });

            const result = await response.json();
            if (result.success) {
                document.getElementById('message-text').value = '';
                window.location.reload();
            } else {
                alert('Ошибка: ' + result.error);
            }
        }

        // Автообновление каждые 5 секунд
        setInterval(() => {
            if ({{ selected_user_id or 0 }}) {
                window.location.reload();
            }
        }, 5000);
    </script>
</body>
</html>
'''

# Создаем файлы шаблонов
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(index_html)

with open('templates/login.html', 'w', encoding='utf-8') as f:
    f.write(login_html)

with open('templates/register.html', 'w', encoding='utf-8') as f:
    f.write(register_html)

with open('templates/chat.html', 'w', encoding='utf-8') as f:
    f.write(chat_html)

if __name__ == '__main__':
    # Инициализируем базу данных
    init_db()
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
