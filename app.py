
from flask import Flask, render_template, request, jsonify, session
import sqlite3
import hashlib
from datetime import datetime
import os
import requests
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-12345')
app.config['DATABASE'] = 'messenger.db'

# Настройки ИИ-бота (можно использовать OpenAI API или другой сервис)
AI_BOT_ENABLED = True
AI_BOT_NAME = "Ассистент"
AI_BOT_ID = 0  # Специальный ID для бота

def get_db():
    """Подключение к базе данных"""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных"""
    try:
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
                    print(f"Создан тестовый пользователь: {username}")
                except sqlite3.IntegrityError:
                    print(f"Пользователь {username} уже существует")
                    pass
        
        db.commit()
        db.close()
        print("✅ База данных успешно инициализирована")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

def ai_bot_response(message):
    """Функция для генерации ответа ИИ-бота"""
    try:
        # Простая реализация без внешнего API
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['привет', 'здравствуй', 'hello', 'hi']):
            return "Привет! Я ваш виртуальный помощник. Чем могу помочь?"
        
        elif any(word in message_lower for word in ['как дела', 'как ты']):
            return "У меня всё отлично! Готов помочь вам с любыми вопросами."
        
        elif any(word in message_lower for word in ['помощь', 'help']):
            return "Я могу ответить на ваши вопросы, поддержать беседу или просто поболтать. Попробуйте спросить о погоде, времени или просто рассказать что-нибудь!"
        
        elif any(word in message_lower for word in ['погода', 'weather']):
            return "К сожалению, я не имею доступа к данным о погоде в реальном времени. Но могу предположить, что сегодня отличный день для общения!"
        
        elif any(word in message_lower for word in ['время', 'time']):
            current_time = datetime.now().strftime("%H:%M:%S")
            return f"Сейчас {current_time}. Не теряйте время зря - общайтесь с друзьями!"
        
        elif any(word in message_lower for word in ['спасибо', 'благодарю']):
            return "Всегда пожалуйста! Рад быть полезным."
        
        elif any(word in message_lower for word in ['пока', 'до свидания']):
            return "До свидания! Жду нашего следующего общения."
        
        else:
            # Стандартный ответ для неизвестных запросов
            responses = [
                "Интересно! Расскажите подробнее.",
                "Понятно. Что вы думаете об этом?",
                "Я еще учусь понимать людей. Можете перефразировать?",
                "Не уверен, что правильно понял. Можете объяснить иначе?",
                "Записываю эту информацию. Что еще хотели бы обсудить?"
            ]
            import random
            return random.choice(responses)
            
    except Exception as e:
        return "Извините, произошла ошибка при обработке вашего сообщения."

@app.route('/')
def index():
    """Главная страница - SPA"""
    return render_template('index.html')

# API endpoints
@app.route('/api/login', methods=['POST'])
def api_login():
    """API для входа"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Заполните все поля'})
        
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
            return jsonify({'success': True, 'username': user['username']})
        else:
            db.close()
            return jsonify({'success': False, 'error': 'Неверный логин или пароль'})
            
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            # Попытка переинициализировать БД при ошибке
            try:
                init_db()
                return jsonify({'success': False, 'error': 'База данных переинициализирована, попробуйте снова'})
            except:
                return jsonify({'success': False, 'error': 'Ошибка базы данных. Попробуйте позже.'})
        return jsonify({'success': False, 'error': f'Ошибка базы данных: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'})

@app.route('/api/register', methods=['POST'])
def api_register():
    """API для регистрации"""
    try:
        data = request.get_json()
        username = data.get('username')
        phone = data.get('phone')
        password = data.get('password')
        confirm = data.get('confirm')
        
        if not all([username, phone, password, confirm]):
            return jsonify({'success': False, 'error': 'Заполните все поля'})
        
        if password != confirm:
            return jsonify({'success': False, 'error': 'Пароли не совпадают'})
        
        if len(password) < 4:
            return jsonify({'success': False, 'error': 'Пароль слишком короткий (мин. 4 символа)'})
        
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
            return jsonify({'success': True, 'message': 'Регистрация успешна! Теперь войдите.'})
        
        except sqlite3.IntegrityError:
            db.close()
            return jsonify({'success': False, 'error': 'Логин или телефон уже заняты'})
        except Exception as e:
            db.close()
            return jsonify({'success': False, 'error': f'Ошибка: {str(e)}'})
            
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            try:
                init_db()
                return jsonify({'success': False, 'error': 'База данных переинициализирована, попробуйте снова'})
            except:
                return jsonify({'success': False, 'error': 'Ошибка базы данных. Попробуйте позже.'})
        return jsonify({'success': False, 'error': f'Ошибка базы данных: {str(e)}'})

@app.route('/api/users')
def api_users():
    """API для получения списка пользователей"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            "SELECT id, username, phone FROM users WHERE id != ? ORDER BY username",
            (session['user_id'],)
        )
        users = cursor.fetchall()
        db.close()
        
        users_data = [dict(user) for user in users]
        
        # Добавляем ИИ-бота в список пользователей, если включен
        if AI_BOT_ENABLED:
            users_data.insert(0, {
                'id': AI_BOT_ID,
                'username': AI_BOT_NAME,
                'phone': 'Искусственный интеллект'
            })
        
        return jsonify({'success': True, 'users': users_data})
        
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            init_db()
            return jsonify({'success': True, 'users': []})
        return jsonify({'success': False, 'error': f'Ошибка базы данных: {str(e)}'})

@app.route('/api/messages')
def api_messages():
    """API для получения сообщений"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        other_user_id = request.args.get('user_id')
        if not other_user_id:
            return jsonify({'success': False, 'error': 'Укажите user_id'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        # Для чата с ботом возвращаем пустой список (сообщения не сохраняются в БД)
        if int(other_user_id) == AI_BOT_ID:
            return jsonify({'success': True, 'messages': []})
        
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
        
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            init_db()
            return jsonify({'success': True, 'messages': []})
        return jsonify({'success': False, 'error': f'Ошибка базы данных: {str(e)}'})

@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    """API для отправки сообщения"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        data = request.get_json()
        receiver_id = data.get('receiver_id')
        message_text = data.get('message_text', '').strip()
        
        if not receiver_id or not message_text:
            return jsonify({'success': False, 'error': 'Заполните все поля'}), 400
        
        # Обработка сообщений для ИИ-бота
        if int(receiver_id) == AI_BOT_ID:
            # Генерируем ответ от бота
            bot_response = ai_bot_response(message_text)
            return jsonify({
                'success': True, 
                'message': 'Сообщение отправлено',
                'bot_response': bot_response
            })
        
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
            
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            init_db()
            return jsonify({'success': False, 'error': 'База данных переинициализирована, попробуйте снова'})
        return jsonify({'success': False, 'error': f'Ошибка базы данных: {str(e)}'})

@app.route('/api/logout')
def api_logout():
    """API для выхода"""
    session.clear()
    return jsonify({'success': True})

@app.route('/api/check_auth')
def api_check_auth():
    """API для проверки авторизации"""
    try:
        if 'user_id' in session:
            return jsonify({'success': True, 'username': session['username']})
        return jsonify({'success': False})
    except:
        return jsonify({'success': False})

@app.route('/api/health')
def api_health():
    """API для проверки здоровья приложения"""
    try:
        # Проверяем подключение к БД
        db = get_db()
        db.execute("SELECT 1")
        db.close()
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'database': 'disconnected', 'error': str(e)})

# Создаем папку templates если ее нет
if not os.path.exists('templates'):
    os.makedirs('templates')

# HTML шаблон для SPA с адаптивным дизайном и ИИ-ботом
spa_html = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>💬 Web Messenger</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --primary-color: #667eea;
            --secondary-color: #764ba2;
            --light-bg: #f8f9fa;
            --dark-text: #333;
            --light-text: #fff;
            --border-color: #ddd;
            --error-color: #e74c3c;
            --success-color: #27ae60;
        }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%); 
            min-height: 100vh;
            color: var(--dark-text);
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px; 
            height: 100vh;
        }
        
        /* Аутентификация */
        .auth-container { 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
            padding: 20px;
        }
        .auth-box { 
            background: white; 
            padding: 30px; 
            border-radius: 15px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.2); 
            width: 100%; 
            max-width: 400px; 
        }
        .auth-tabs { 
            display: flex; 
            margin-bottom: 20px; 
            border-bottom: 2px solid var(--border-color); 
        }
        .auth-tab { 
            flex: 1; 
            padding: 15px; 
            text-align: center; 
            cursor: pointer; 
            border-bottom: 3px solid transparent; 
            transition: all 0.3s;
        }
        .auth-tab.active { 
            border-bottom-color: var(--primary-color); 
            color: var(--primary-color); 
            font-weight: bold; 
        }
        .auth-form { 
            display: none; 
        }
        .auth-form.active { 
            display: block; 
        }
        input { 
            width: 100%; 
            padding: 12px; 
            margin: 10px 0; 
            border: 2px solid var(--border-color); 
            border-radius: 8px; 
            font-size: 16px; 
            transition: border-color 0.3s;
        }
        input:focus { 
            outline: none; 
            border-color: var(--primary-color); 
        }
        button { 
            width: 100%; 
            padding: 12px; 
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%); 
            color: white; 
            border: none; 
            border-radius: 8px; 
            font-size: 16px; 
            cursor: pointer; 
            margin: 10px 0; 
            transition: opacity 0.3s;
        }
        button:hover { 
            opacity: 0.9; 
        }
        .error { 
            color: var(--error-color); 
            text-align: center; 
            margin: 10px 0; 
            padding: 10px; 
            background: #f8d7da; 
            border-radius: 5px; 
            display: none;
        }
        .success { 
            color: var(--success-color); 
            text-align: center; 
            margin: 10px 0; 
            padding: 10px; 
            background: #d4edda; 
            border-radius: 5px; 
            display: none;
        }
        
        /* Чат */
        .chat-container { 
            display: none; 
            background: white; 
            border-radius: 15px; 
            overflow: hidden; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.2); 
            height: calc(100vh - 40px);
            flex-direction: column;
        }
        .header { 
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%); 
            color: white; 
            padding: 15px 20px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            flex-shrink: 0;
        }
        .chat-layout { 
            display: flex; 
            height: 100%; 
            overflow: hidden;
        }
        .sidebar { 
            width: 250px; 
            background: var(--light-bg); 
            border-right: 1px solid var(--border-color); 
            overflow-y: auto; 
            display: flex;
            flex-direction: column;
        }
        .sidebar-header { 
            padding: 15px; 
            border-bottom: 1px solid var(--border-color); 
            background: white;
        }
        .user-list { 
            padding: 10px; 
            overflow-y: auto;
            flex-grow: 1;
        }
        .user-item { 
            padding: 12px; 
            margin: 5px 0; 
            background: white; 
            border-radius: 8px; 
            cursor: pointer; 
            transition: all 0.3s;
            display: flex;
            align-items: center;
        }
        .user-item:hover { 
            background: var(--primary-color); 
            color: white; 
        }
        .user-item.active { 
            background: var(--primary-color); 
            color: white; 
        }
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 10px;
            color: white;
            font-weight: bold;
        }
        .ai-bot {
            background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%);
        }
        .user-info {
            flex-grow: 1;
        }
        .user-name {
            font-weight: bold;
        }
        .user-phone {
            font-size: 0.8em;
            opacity: 0.7;
        }
        .chat-main { 
            flex: 1; 
            display: flex; 
            flex-direction: column; 
            height: 100%;
        }
        .chat-header { 
            padding: 15px; 
            background: white; 
            border-bottom: 1px solid var(--border-color); 
            flex-shrink: 0;
        }
        .messages-container { 
            flex: 1; 
            padding: 20px; 
            overflow-y: auto; 
            background: var(--light-bg);
            display: flex;
            flex-direction: column;
        }
        .message { 
            max-width: 70%; 
            margin: 10px 0; 
            padding: 12px 16px; 
            border-radius: 18px; 
            position: relative;
            animation: fadeIn 0.3s;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message-own { 
            background: var(--primary-color); 
            color: white; 
            margin-left: auto; 
            border-bottom-right-radius: 5px; 
        }
        .message-other { 
            background: white; 
            color: var(--dark-text); 
            margin-right: auto; 
            border-bottom-left-radius: 5px; 
            border: 1px solid var(--border-color); 
        }
        .message-bot {
            background: #4CAF50;
            color: white;
        }
        .message-sender {
            font-weight: bold;
            margin-bottom: 5px;
            font-size: 0.9em;
        }
        .message-time {
            font-size: 0.7em;
            opacity: 0.7;
            text-align: right;
            margin-top: 5px;
        }
        .message-input { 
            display: flex; 
            padding: 15px; 
            background: white; 
            border-top: 1px solid var(--border-color); 
            flex-shrink: 0;
        }
        .message-input input { 
            flex: 1; 
            margin-right: 10px; 
        }
        .logout-btn { 
            background: var(--error-color); 
            padding: 8px 15px; 
            border-radius: 5px; 
            border: none;
            color: white;
            cursor: pointer;
        }
        
        /* Мобильная адаптация */
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            .auth-box {
                padding: 20px;
            }
            .chat-container {
                height: calc(100vh - 20px);
                border-radius: 10px;
            }
            .chat-layout {
                flex-direction: column;
            }
            .sidebar {
                width: 100%;
                height: 30%;
                border-right: none;
                border-bottom: 1px solid var(--border-color);
            }
            .user-list {
                padding: 5px;
            }
            .user-item {
                padding: 8px;
            }
            .header h2 {
                font-size: 1.2em;
            }
            .message {
                max-width: 85%;
            }
        }
        
        @media (max-width: 480px) {
            .auth-tab {
                padding: 10px;
                font-size: 0.9em;
            }
            input, button {
                padding: 10px;
                font-size: 14px;
            }
            .user-avatar {
                width: 35px;
                height: 35px;
                font-size: 0.9em;
            }
            .user-name {
                font-size: 0.9em;
            }
            .user-phone {
                font-size: 0.7em;
            }
            .message {
                max-width: 90%;
                padding: 10px 12px;
            }
        }
        
        /* Индикатор загрузки */
        .loader {
            display: none;
            text-align: center;
            padding: 10px;
            color: var(--primary-color);
        }
        .typing-indicator {
            display: none;
            background: white;
            padding: 10px 15px;
            border-radius: 18px;
            margin: 5px 0;
            align-self: flex-start;
            border: 1px solid var(--border-color);
            font-style: italic;
            color: #666;
        }
        
        /* Изначально скрываем поле ввода */
        #messageInput {
            display: none !important;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="auth-container" id="authSection">
            <div class="auth-box">
                <div class="auth-tabs">
                    <div class="auth-tab active" onclick="showTab('login')">Вход</div>
                    <div class="auth-tab" onclick="showTab('register')">Регистрация</div>
                </div>
                
                <div class="auth-form active" id="loginForm">
                    <h2>🔐 Вход</h2>
                    <div id="loginError" class="error"></div>
                    <input type="text" id="loginUsername" placeholder="Логин" value="alex">
                    <input type="password" id="loginPassword" placeholder="Пароль" value="password123">
                    <button onclick="login()">Войти</button>
                </div>
                
                <div class="auth-form" id="registerForm">
                    <h2>📝 Регистрация</h2>
                    <div id="registerError" class="error"></div>
                    <input type="text" id="regUsername" placeholder="Логин">
                    <input type="text" id="regPhone" placeholder="Телефон">
                    <input type="password" id="regPassword" placeholder="Пароль">
                    <input type="password" id="regConfirm" placeholder="Подтверждение пароля">
                    <button onclick="register()">Зарегистрироваться</button>
                </div>
            </div>
        </div>

        <div class="chat-container" id="chatSection">
            <div class="header">
                <h2>💬 Web Messenger - <span id="currentUsername"></span></h2>
                <button class="logout-btn" onclick="logout()">🚪 Выйти</button>
            </div>
            
            <div class="chat-layout">
                <div class="sidebar">
                    <div class="sidebar-header">
                        <h3>👥 Пользователи</h3>
                    </div>
                    <div class="user-list" id="userList">
                        <div class="loader" id="usersLoader">Загрузка...</div>
                    </div>
                </div>
                
                <div class="chat-main">
                    <div class="chat-header">
                        <h3 id="chatTitle">Выберите пользователя для чата</h3>
                    </div>
                    
                    <div class="messages-container" id="messagesContainer">
                        <div class="loader" id="messagesLoader">Загрузка сообщений...</div>
                    </div>
                    
                    <div class="typing-indicator" id="typingIndicator">Ассистент печатает...</div>
                    
                    <div class="message-input" id="messageInput">
                        <input type="text" id="messageText" placeholder="Введите сообщение..." onkeypress="if(event.key === 'Enter') sendMessage()">
                        <button onclick="sendMessage()">📤</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;
        let selectedUserId = null;
        let selectedUserName = null;
        let refreshInterval = null;
        let isMobile = window.innerWidth <= 768;
        
        // Определяем мобильное устройство
        window.addEventListener('resize', () => {
            isMobile = window.innerWidth <= 768;
        });
        
        async function checkAuth() {
            try {
                const response = await fetch('/api/check_auth');
                const data = await response.json();
                
                if (data.success) {
                    currentUser = data.username;
                    showChat();
                    loadUsers();
                } else {
                    showAuth();
                }
            } catch (error) {
                showAuth();
            }
        }
        
        function showTab(tabName) {
            document.querySelectorAll('.auth-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
            
            document.querySelector(`.auth-tab:nth-child(${tabName === 'login' ? 1 : 2})`).classList.add('active');
            document.getElementById(tabName + 'Form').classList.add('active');
        }
        
        function showAuth() {
            document.getElementById('authSection').style.display = 'flex';
            document.getElementById('chatSection').style.display = 'none';
            if (refreshInterval) clearInterval(refreshInterval);
        }
        
        function showChat() {
            document.getElementById('authSection').style.display = 'none';
            document.getElementById('chatSection').style.display = 'block';
            document.getElementById('currentUsername').textContent = currentUser;
        }
        
        async function login() {
            const username = document.getElementById('loginUsername').value;
            const password = document.getElementById('loginPassword').value;
            
            if (!username || !password) {
                showError('loginError', 'Заполните все поля');
                return;
            }
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username, password })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    currentUser = data.username;
                    showChat();
                    loadUsers();
                } else {
                    showError('loginError', data.error);
                }
            } catch (error) {
                showError('loginError', 'Ошибка соединения');
            }
        }
        
        async function register() {
            const username = document.getElementById('regUsername').value;
            const phone = document.getElementById('regPhone').value;
            const password = document.getElementById('regPassword').value;
            const confirm = document.getElementById('regConfirm').value;
            
            if (!username || !phone || !password || !confirm) {
                showError('registerError', 'Заполните все поля');
                return;
            }
            
            if (password !== confirm) {
                showError('registerError', 'Пароли не совпадают');
                return;
            }
            
            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username, phone, password, confirm })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showTab('login');
                    alert(data.message);
                } else {
                    showError('registerError', data.error);
                }
            } catch (error) {
                showError('registerError', 'Ошибка соединения');
            }
        }
        
        async function logout() {
            await fetch('/api/logout');
            currentUser = null;
            selectedUserId = null;
            showAuth();
        }
        
        async function loadUsers() {
            showLoader('usersLoader', true);
            
            try {
                const response = await fetch('/api/users');
                const data = await response.json();
                
                if (data.success) {
                    const userList = document.getElementById('userList');
                    userList.innerHTML = '';
                    
                    data.users.forEach(user => {
                        const userElement = document.createElement('div');
                        userElement.className = 'user-item';
                        if (user.id === 0) {
                            userElement.classList.add('ai-bot');
                        }
                        
                        const firstLetter = user.username.charAt(0).toUpperCase();
                        userElement.innerHTML = `
                            <div class="user-avatar">${firstLetter}</div>
                            <div class="user-info">
                                <div class="user-name">${user.username}</div>
                                <div class="user-phone">${user.phone}</div>
                            </div>
                        `;
                        
                        userElement.onclick = () => selectUser(user.id, user.username);
                        userList.appendChild(userElement);
                    });
                }
            } catch (error) {
                console.error('Failed to load users:', error);
            } finally {
                showLoader('usersLoader', false);
            }
        }
        
        async function selectUser(userId, username) {
            // Сброс предыдущего выбора
            document.querySelectorAll('.user-item').forEach(item => item.classList.remove('active'));
            event.currentTarget.classList.add('active');
            
            selectedUserId = userId;
            selectedUserName = username;
            
            document.getElementById('chatTitle').textContent = `💬 Чат с ${username}`;
            document.getElementById('messageInput').style.display = 'flex';
            
            await loadMessages();
            
            // На мобильных устройствах скрываем sidebar после выбора пользователя
            if (isMobile) {
                document.querySelector('.sidebar').style.display = 'none';
                document.querySelector('.chat-main').style.width = '100%';
            }
            
            if (refreshInterval) clearInterval(refreshInterval);
            refreshInterval = setInterval(loadMessages, 2000);
        }
        
        async function loadMessages() {
            if (!selectedUserId) return;
            
            showLoader('messagesLoader', true);
            
            try {
                const response = await fetch(`/api/messages?user_id=${selectedUserId}`);
                const data = await response.json();
                
                if (data.success) {
                    const messagesContainer = document.getElementById('messagesContainer');
                    messagesContainer.innerHTML = '';
                    
                    if (data.messages.length === 0 && selectedUserId == 0) {
                        const welcomeMsg = document.createElement('div');
                        welcomeMsg.className = 'message message-bot';
                        welcomeMsg.innerHTML = `
                            <div class="message-sender">Ассистент</div>
                            <div>Привет! Я ваш виртуальный помощник. Задайте мне любой вопрос!</div>
                            <div class="message-time">${new Date().toLocaleTimeString()}</div>
                        `;
                        messagesContainer.appendChild(welcomeMsg);
                    } else {
                        data.messages.forEach(msg => {
                            const messageElement = document.createElement('div');
                            messageElement.className = `message ${msg.is_own ? 'message-own' : 'message-other'}`;
                            
                            const time = new Date(msg.created_at).toLocaleTimeString();
                            messageElement.innerHTML = `
                                ${!msg.is_own ? `<div class="message-sender">${msg.sender_name}</div>` : ''}
                                <div>${msg.message_text}</div>
                                <div class="message-time">${time}</div>
                            `;
                            
                            messagesContainer.appendChild(messageElement);
                        });
                    }
                    
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }
            } catch (error) {
                console.error('Failed to load messages:', error);
            } finally {
                showLoader('messagesLoader', false);
            }
        }
        
        async function sendMessage() {
            const messageText = document.getElementById('messageText').value.trim();
            if (!messageText || !selectedUserId) return;
            
            // Добавляем сообщение сразу в интерфейс для мгновенного отображения
            const messagesContainer = document.getElementById('messagesContainer');
            const messageElement = document.createElement('div');
            messageElement.className = 'message message-own';
            
            const time = new Date().toLocaleTimeString();
            messageElement.innerHTML = `
                <div>${messageText}</div>
                <div class="message-time">${time}</div>
            `;
            
            messagesContainer.appendChild(messageElement);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            
            // Очищаем поле ввода
            document.getElementById('messageText').value = '';
            
            try {
                const response = await fetch('/api/send_message', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ receiver_id: selectedUserId, message_text: messageText })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Если это сообщение боту и есть ответ
                    if (data.bot_response) {
                        // Показываем индикатор набора сообщения
                        document.getElementById('typingIndicator').style.display = 'block';
                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                        
                        // Имитируем задержку ответа бота
                        setTimeout(() => {
                            document.getElementById('typingIndicator').style.display = 'none';
                            
                            const botMessageElement = document.createElement('div');
                            botMessageElement.className = 'message message-bot';
                            
                            const time = new Date().toLocaleTimeString();
                            botMessageElement.innerHTML = `
                                <div class="message-sender">Ассистент</div>
                                <div>${data.bot_response}</div>
                                <div class="message-time">${time}</div>
                            `;
                            
                            messagesContainer.appendChild(botMessageElement);
                            messagesContainer.scrollTop = messagesContainer.scrollHeight;
                        }, 1500);
                    } else {
                        // Для обычных пользователей просто обновляем сообщения
                        loadMessages();
                    }
                } else {
                    alert('Ошибка: ' + data.error);
                }
            } catch (error) {
                alert('Ошибка отправки сообщения');
            }
        }
        
        function showError(elementId, message) {
            const element = document.getElementById(elementId);
            element.textContent = message;
            element.style.display = 'block';
            setTimeout(() => element.style.display = 'none', 5000);
        }
        
        function showLoader(loaderId, show) {
            const loader = document.getElementById(loaderId);
            loader.style.display = show ? 'block' : 'none';
        }
        
        // Функция для показа/скрытия sidebar на мобильных устройствах
        function toggleSidebar() {
            const sidebar = document.querySelector('.sidebar');
            if (sidebar.style.display === 'none') {
                sidebar.style.display = 'block';
                document.querySelector('.chat-main').style.width = '0';
            } else {
                sidebar.style.display = 'none';
                document.querySelector('.chat-main').style.width = '100%';
            }
        }
        
        // Добавляем кнопку для мобильной навигации
        function addMobileNav() {
            if (isMobile) {
                const header = document.querySelector('.header');
                const backButton = document.createElement('button');
                backButton.className = 'logout-btn';
                backButton.innerHTML = '← Назад';
                backButton.onclick = toggleSidebar;
                backButton.style.marginRight = '10px';
                header.insertBefore(backButton, header.childNodes[0]);
                
                // Изначально скрываем sidebar на мобильных
                document.querySelector('.sidebar').style.display = 'block';
                document.querySelector('.chat-main').style.width = '100%';
            }
        }
        
        // Инициализация при загрузке
        window.onload = function() {
            checkAuth();
            addMobileNav();
        };
    </script>
</body>
</html>
'''

# Создаем файл шаблона
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(spa_html)

# Инициализируем базу данных при запуске
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Web Messenger запущен!")
    print("✅ База данных инициализирована")
    print("🔑 Тестовые пользователи: alex/password123, maria/password123, ivan/password123")
    print("🤖 ИИ-бот активирован")
    app.run(host='0.0.0.0', port=port, debug=False)
