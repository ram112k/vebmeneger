from flask import Flask, render_template, request, jsonify, session
import sqlite3
import hashlib
from datetime import datetime
import os
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-12345')
app.config['DATABASE'] = 'messenger.db'

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
                message_type TEXT DEFAULT 'private', -- 'private', 'group'
                group_id INTEGER DEFAULT NULL,
                is_read INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (receiver_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица групп
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                creator_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица участников групп
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(group_id, user_id)
            )
        ''')
        
        # Создаем тестовых пользователей если их нет
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            test_users = [
                ('alex', '+79161234567', hash_password('password123')),
                ('maria', '+79269876543', hash_password('password123')),
                ('ivan', '+79031112233', hash_password('password123')),
                ('sophia', '+79051112233', hash_password('password123')),
                ('maxim', '+79061112233', hash_password('password123'))
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
            
            # Создаем тестовую группу
            cursor.execute(
                "INSERT INTO groups (name, description, creator_id) VALUES (?, ?, ?)",
                ('Общая группа', 'Группа для обсуждения общих вопросов', 1)
            )
            group_id = cursor.lastrowid
            
            # Добавляем всех пользователей в группу
            for user_id in [1, 2, 3, 4, 5]:
                cursor.execute(
                    "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                    (group_id, user_id)
                )
        
        db.commit()
        db.close()
        print("✅ База данных успешно инициализирована")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

def is_group_member(group_id, user_id):
    """Проверяет, является ли пользователь участником группы"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id)
    )
    is_member = cursor.fetchone() is not None
    
    db.close()
    return is_member

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
        return jsonify({'success': True, 'users': users_data})
        
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            init_db()
            return jsonify({'success': True, 'users': []})
        return jsonify({'success': False, 'error': f'Ошибка базы данных: {str(e)}'})

@app.route('/api/groups')
def api_groups():
    """API для получения списка групп"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute('''
            SELECT g.id, g.name, g.description, g.creator_id, u.username as creator_name,
                   (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count
            FROM groups g
            JOIN users u ON g.creator_id = u.id
            JOIN group_members gm ON g.id = gm.group_id
            WHERE gm.user_id = ?
            ORDER BY g.name
        ''', (session['user_id'],))
        
        groups = cursor.fetchall()
        db.close()
        
        groups_data = [dict(group) for group in groups]
        return jsonify({'success': True, 'groups': groups_data})
        
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            init_db()
            return jsonify({'success': True, 'groups': []})
        return jsonify({'success': False, 'error': f'Ошибка базы данных: {str(e)}'})

@app.route('/api/create_group', methods=['POST'])
def api_create_group():
    """API для создания группы"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        data = request.get_json()
        name = data.get('name')
        description = data.get('description', '')
        member_ids = data.get('member_ids', [])
        
        if not name:
            return jsonify({'success': False, 'error': 'Введите название группы'})
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            # Создаем группу
            cursor.execute(
                "INSERT INTO groups (name, description, creator_id) VALUES (?, ?, ?)",
                (name, description, session['user_id'])
            )
            group_id = cursor.lastrowid
            
            # Добавляем создателя в группу
            cursor.execute(
                "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                (group_id, session['user_id'])
            )
            
            # Добавляем выбранных участников
            for user_id in member_ids:
                if user_id != session['user_id']:  # Не добавляем себя повторно
                    try:
                        cursor.execute(
                            "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                            (group_id, user_id)
                        )
                    except sqlite3.IntegrityError:
                        # Пропускаем если пользователь уже в группе
                        pass
            
            db.commit()
            db.close()
            return jsonify({'success': True, 'message': 'Группа создана успешно', 'group_id': group_id})
        
        except Exception as e:
            db.close()
            return jsonify({'success': False, 'error': f'Ошибка создания группы: {str(e)}'}), 500
            
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            init_db()
            return jsonify({'success': False, 'error': 'База данных переинициализирована, попробуйте снова'})
        return jsonify({'success': False, 'error': f'Ошибка базы данных: {str(e)}'})

@app.route('/api/messages')
def api_messages():
    """API для получения сообщений"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        chat_type = request.args.get('type', 'private')  # 'private', 'group'
        chat_id = request.args.get('id')
        
        if not chat_id:
            return jsonify({'success': False, 'error': 'Укажите ID чата'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        if chat_type == 'private':
            cursor.execute('''
                SELECT m.id, m.sender_id, m.receiver_id, m.message_text, m.created_at, 
                       u.username as sender_name
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE (m.sender_id = ? AND m.receiver_id = ?) 
                   OR (m.sender_id = ? AND m.receiver_id = ?)
                ORDER BY m.created_at
            ''', (session['user_id'], chat_id, chat_id, session['user_id']))
        else:  # group
            # Проверяем, что пользователь состоит в группе
            cursor.execute(
                "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
                (chat_id, session['user_id'])
            )
            if not cursor.fetchone():
                db.close()
                return jsonify({'success': False, 'error': 'Вы не состоите в этой группе'}), 403
            
            cursor.execute('''
                SELECT m.id, m.sender_id, m.group_id, m.message_text, m.created_at, 
                       u.username as sender_name
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.group_id = ? AND m.message_type = 'group'
                ORDER BY m.created_at
            ''', (chat_id,))
        
        messages = cursor.fetchall()
        db.close()
        
        messages_data = []
        for msg in messages:
            message_data = {
                'id': msg['id'],
                'sender_id': msg['sender_id'],
                'message_text': msg['message_text'],
                'created_at': msg['created_at'],
                'sender_name': msg['sender_name'],
                'is_own': msg['sender_id'] == session['user_id'],
                'type': chat_type
            }
            if chat_type == 'private':
                message_data['receiver_id'] = msg['receiver_id']
            else:
                message_data['group_id'] = msg['group_id']
            
            messages_data.append(message_data)
        
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
        message_type = data.get('type', 'private')  # 'private', 'group'
        receiver_id = data.get('receiver_id')
        group_id = data.get('group_id')
        message_text = data.get('message_text', '').strip()
        
        if not message_text:
            return jsonify({'success': False, 'error': 'Введите текст сообщения'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            if message_type == 'private':
                if not receiver_id:
                    return jsonify({'success': False, 'error': 'Укажите получателя'}), 400
                
                cursor.execute(
                    "INSERT INTO messages (sender_id, receiver_id, message_text, message_type) VALUES (?, ?, ?, 'private')",
                    (session['user_id'], receiver_id, message_text)
                )
            else:  # group
                if not group_id:
                    return jsonify({'success': False, 'error': 'Укажите группу'}), 400
                
                # Проверяем, что пользователь состоит в группе
                if not is_group_member(group_id, session['user_id']):
                    db.close()
                    return jsonify({'success': False, 'error': 'Вы не состоите в этой группе'}), 403
                
                cursor.execute(
                    "INSERT INTO messages (sender_id, receiver_id, message_text, message_type, group_id) VALUES (?, NULL, ?, 'group', ?)",
                    (session['user_id'], message_text, group_id)
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

# HTML шаблон
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Messenger App</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            overflow: hidden;
            min-height: 80vh;
        }

        /* Аутентификация */
        .auth-container {
            padding: 40px;
            text-align: center;
        }

        .auth-form {
            max-width: 400px;
            margin: 0 auto;
            background: #f8f9fa;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }

        .auth-tabs {
            display: flex;
            margin-bottom: 20px;
            border-radius: 8px;
            overflow: hidden;
        }

        .auth-tab {
            flex: 1;
            padding: 15px;
            background: #e9ecef;
            border: none;
            cursor: pointer;
            font-weight: 500;
            transition: background 0.3s;
            color: #000;
        }

        .auth-tab.active {
            background: #8B5FBF;
            color: white;
        }

        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }

        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
            color: #333;
        }

        .form-control {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 16px;
            transition: border-color 0.3s;
        }

        .form-control:focus {
            outline: none;
            border-color: #8B5FBF;
        }

        .btn {
            width: 100%;
            padding: 12px;
            background: #8B5FBF;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            transition: background 0.3s;
        }

        .btn:hover {
            background: #6A4A9C;
        }

        .btn-secondary {
            background: #9370DB;
        }

        .btn-secondary:hover {
            background: #7B68EE;
        }

        .error-message {
            color: #dc3545;
            margin-top: 10px;
            padding: 10px;
            background: #f8d7da;
            border-radius: 5px;
            border: 1px solid #f5c6cb;
        }

        .success-message {
            color: #155724;
            margin-top: 10px;
            padding: 10px;
            background: #d4edda;
            border-radius: 5px;
            border: 1px solid #c3e6cb;
        }

        /* Основной интерфейс */
        .messenger-container {
            display: flex;
            height: 80vh;
        }

        .sidebar {
            width: 300px;
            background: #f8f9fa;
            border-right: 1px solid #dee2e6;
            padding: 20px;
            overflow-y: auto;
        }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .chat-header {
            padding: 20px;
            background: white;
            border-bottom: 1px solid #dee2e6;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .chat-messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #f8f9fa;
        }

        .message-input {
            padding: 20px;
            background: white;
            border-top: 1px solid #dee2e6;
        }

        .chat-list {
            list-style: none;
        }

        .chat-item {
            padding: 15px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            transition: background 0.3s;
            border-radius: 8px;
            margin-bottom: 5px;
        }

        .chat-item:hover {
            background: #e9ecef;
        }

        .chat-item.active {
            background: #8B5FBF;
            color: white;
        }

        .message {
            margin-bottom: 15px;
            max-width: 70%;
        }

        .message.own {
            margin-left: auto;
        }

        .message-content {
            padding: 12px;
            border-radius: 12px;
            background: white;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }

        .message.own .message-content {
            background: #8B5FBF;
            color: white;
        }

        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            font-size: 12px;
            color: #666;
        }

        .message.own .message-header {
            color: rgba(255, 255, 255, 0.8);
        }

        /* Адаптивность */
        @media (max-width: 768px) {
            .container {
                margin: 10px;
                border-radius: 10px;
            }

            .auth-container {
                padding: 20px;
            }

            .auth-form {
                padding: 20px;
            }

            .messenger-container {
                flex-direction: column;
                height: auto;
            }

            .sidebar {
                width: 100%;
                border-right: none;
                border-bottom: 1px solid #dee2e6;
                max-height: 300px;
            }

            .chat-messages {
                min-height: 400px;
            }

            .message {
                max-width: 85%;
            }
        }

        @media (max-width: 480px) {
            body {
                padding: 10px;
            }

            .container {
                margin: 5px;
                border-radius: 8px;
            }

            .auth-tabs {
                flex-direction: column;
            }

            .message {
                max-width: 95%;
            }

            .form-control, .btn {
                padding: 10px;
            }
        }

        /* Улучшенная анимация */
        .fade-in {
            animation: fadeIn 0.3s ease-in;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
        }

        .create-buttons {
            margin-bottom: 20px;
        }

        .create-buttons button {
            margin-right: 10px;
            margin-bottom: 10px;
        }

        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
        }

        .modal-content {
            background-color: white;
            margin: 10% auto;
            padding: 20px;
            border-radius: 10px;
            width: 90%;
            max-width: 500px;
            max-height: 80vh;
            overflow-y: auto;
        }

        .close {
            float: right;
            font-size: 24px;
            font-weight: bold;
            cursor: pointer;
        }

        .user-select {
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 10px;
            margin-top: 10px;
        }

        .user-select-item {
            padding: 8px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
        }

        .user-select-item:hover {
            background: #f0f0f0;
        }

        .user-select-item.selected {
            background: #8B5FBF;
            color: white;
        }
    </style>
</head>
<body>
    <div class="container">
        <div id="auth-container" class="auth-container">
            <div class="auth-form">
                <div class="auth-tabs">
                    <button class="auth-tab active" onclick="showTab('login')">Вход</button>
                    <button class="auth-tab" onclick="showTab('register')">Регистрация</button>
                </div>
                
                <div id="login-form">
                    <div class="form-group">
                        <label for="login-username">Логин:</label>
                        <input type="text" id="login-username" class="form-control" placeholder="Введите ваш логин">
                    </div>
                    <div class="form-group">
                        <label for="login-password">Пароль:</label>
                        <input type="password" id="login-password" class="form-control" placeholder="Введите ваш пароль">
                    </div>
                    <button class="btn" onclick="login()">Войти</button>
                    <div id="login-error" class="error-message" style="display: none;"></div>
                </div>
                
                <div id="register-form" style="display: none;">
                    <div class="form-group">
                        <label for="register-username">Логин:</label>
                        <input type="text" id="register-username" class="form-control" placeholder="Придумайте логин">
                    </div>
                    <div class="form-group">
                        <label for="register-phone">Телефон:</label>
                        <input type="tel" id="register-phone" class="form-control" placeholder="+79161234567">
                    </div>
                    <div class="form-group">
                        <label for="register-password">Пароль:</label>
                        <input type="password" id="register-password" class="form-control" placeholder="Придумайте пароль">
                    </div>
                    <div class="form-group">
                        <label for="register-confirm">Подтверждение пароля:</label>
                        <input type="password" id="register-confirm" class="form-control" placeholder="Повторите пароль">
                    </div>
                    <button class="btn" onclick="register()">Зарегистрироваться</button>
                    <div id="register-error" class="error-message" style="display: none;"></div>
                    <div id="register-success" class="success-message" style="display: none;"></div>
                </div>
            </div>
        </div>
        
        <div id="messenger-container" class="messenger-container" style="display: none;">
            <div class="sidebar">
                <div style="margin-bottom: 20px;">
                    <h3>Добро пожаловать, <span id="username-display"></span>!</h3>
                    <button class="btn btn-secondary" onclick="logout()" style="margin-top: 10px;">Выйти</button>
                </div>
                
                <div class="create-buttons">
                    <button class="btn" onclick="showCreateGroupModal()">Создать группу</button>
                </div>
                
                <h4>Пользователи</h4>
                <ul id="users-list" class="chat-list"></ul>
                
                <h4>Группы</h4>
                <ul id="groups-list" class="chat-list"></ul>
            </div>
            
            <div class="main-content">
                <div id="chat-header" class="chat-header">
                    <h4 id="current-chat">Выберите чат</h4>
                </div>
                
                <div id="chat-messages" class="chat-messages"></div>
                
                <div id="message-input" class="message-input" style="display: none;">
                    <div class="form-group">
                        <input type="text" id="message-text" class="form-control" placeholder="Введите сообщение..." onkeypress="handleKeyPress(event)">
                    </div>
                    <button class="btn" onclick="sendMessage()">Отправить</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Модальное окно создания группы -->
    <div id="create-group-modal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal('create-group-modal')">&times;</span>
            <h3>ЗАКРЫТО</h3>
            <div class="form-group">
                <label>Название группы:</label>
                <input type="text" id="group-name" class="form-control">
            </div>
            <div class="form-group">
                <label>Описание:</label>
                <textarea id="group-description" class="form-control" rows="3"></textarea>
            </div>
            <div class="form-group">
                <label>Участники:</label>
                <div id="group-users-select" class="user-select"></div>
            </div>
            <button class="btn" onclick="createGroup()">Создать группу</button>
        </div>
    </div>

    <script>
        let currentChat = null;
        let currentChatType = null;
        let selectedUsers = [];
        let currentUser = null;

        // Проверка авторизации при загрузке
        async function checkAuth() {
            try {
                const response = await fetch('/api/check_auth');
                const data = await response.json();
                
                if (data.success) {
                    currentUser = data.username;
                    showMessengerInterface(data.username);
                    loadChatLists();
                } else {
                    showAuthInterface();
                }
            } catch (error) {
                console.error('Ошибка проверки авторизации:', error);
                showAuthInterface();
            }
        }

        // Показать интерфейс аутентификации
        function showAuthInterface() {
            document.getElementById('auth-container').style.display = 'block';
            document.getElementById('messenger-container').style.display = 'none';
        }

        // Показать интерфейс мессенджера
        function showMessengerInterface(username) {
            document.getElementById('auth-container').style.display = 'none';
            document.getElementById('messenger-container').style.display = 'flex';
            document.getElementById('username-display').textContent = username;
        }

        // Переключение между вкладками входа/регистрации
        function showTab(tabName) {
            document.getElementById('login-form').style.display = tabName === 'login' ? 'block' : 'none';
            document.getElementById('register-form').style.display = tabName === 'register' ? 'block' : 'none';
            
            const tabs = document.querySelectorAll('.auth-tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            
            // Активируем правильную вкладку
            if (tabName === 'login') {
                document.querySelector('.auth-tab:first-child').classList.add('active');
            } else {
                document.querySelector('.auth-tab:last-child').classList.add('active');
            }
        }

        // Вход
        async function login() {
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;
            
            if (!username || !password) {
                showError('login-error', 'Заполните все поля');
                return;
            }
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ username, password })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    currentUser = data.username;
                    showMessengerInterface(data.username);
                    loadChatLists();
                } else {
                    showError('login-error', data.error || 'Ошибка входа');
                }
            } catch (error) {
                showError('login-error', 'Ошибка сети');
            }
        }

        // Регистрация
        async function register() {
            const username = document.getElementById('register-username').value;
            const phone = document.getElementById('register-phone').value;
            const password = document.getElementById('register-password').value;
            const confirm = document.getElementById('register-confirm').value;
            
            if (!username || !phone || !password || !confirm) {
                showError('register-error', 'Заполните все поля');
                return;
            }
            
            if (password !== confirm) {
                showError('register-error', 'Пароли не совпадают');
                return;
            }
            
            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ username, phone, password, confirm })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSuccess('register-success', data.message || 'Регистрация успешна!');
                    document.getElementById('register-error').style.display = 'none';
                    // Очищаем форму
                    document.getElementById('register-username').value = '';
                    document.getElementById('register-phone').value = '';
                    document.getElementById('register-password').value = '';
                    document.getElementById('register-confirm').value = '';
                    
                    // Переключаем на вкладку входа через 2 секунды
                    setTimeout(() => showTab('login'), 2000);
                } else {
                    showError('register-error', data.error || 'Ошибка регистрации');
                }
            } catch (error) {
                showError('register-error', 'Ошибка сети');
            }
        }

        // Выход
        async function logout() {
            try {
                await fetch('/api/logout');
                currentUser = null;
                currentChat = null;
                showAuthInterface();
            } catch (error) {
                console.error('Ошибка выхода:', error);
            }
        }

        // Загрузка списков чатов
        async function loadChatLists() {
            await loadUsers();
            await loadGroups();
        }

        // Загрузка списка пользователей
        async function loadUsers() {
            try {
                const response = await fetch('/api/users');
                const data = await response.json();
                
                if (data.success) {
                    const usersList = document.getElementById('users-list');
                    usersList.innerHTML = '';
                    
                    data.users.forEach(user => {
                        const li = document.createElement('li');
                        li.className = 'chat-item';
                        li.innerHTML = `
                            <strong>${user.username}</strong><br>
                            <small>${user.phone}</small>
                        `;
                        li.onclick = () => selectChat('private', user.id, user.username);
                        usersList.appendChild(li);
                    });
                }
            } catch (error) {
                console.error('Ошибка загрузки пользователей:', error);
            }
        }

        // Загрузка списка групп
        async function loadGroups() {
            try {
                const response = await fetch('/api/groups');
                const data = await response.json();
                
                if (data.success) {
                    const groupsList = document.getElementById('groups-list');
                    groupsList.innerHTML = '';
                    
                    data.groups.forEach(group => {
                        const li = document.createElement('li');
                        li.className = 'chat-item';
                        li.innerHTML = `
                            <strong>${group.name}</strong><br>
                            <small>Участников: ${group.member_count}</small>
                        `;
                        li.onclick = () => selectChat('group', group.id, group.name);
                        groupsList.appendChild(li);
                    });
                }
            } catch (error) {
                console.error('Ошибка загрузки групп:', error);
            }
        }

        // Выбор чата
        function selectChat(type, id, name) {
            currentChat = id;
            currentChatType = type;
            
            // Обновляем UI
            document.getElementById('current-chat').textContent = name;
            document.getElementById('message-input').style.display = 'block';
            
            // Загружаем сообщения
            loadMessages();
            
            // Периодическое обновление сообщений
            clearInterval(window.messageInterval);
            window.messageInterval = setInterval(loadMessages, 3000);
        }

        // Загрузка сообщений
        async function loadMessages() {
            if (!currentChat) return;
            
            try {
                const response = await fetch(`/api/messages?type=${currentChatType}&id=${currentChat}`);
                const data = await response.json();
                
                if (data.success) {
                    const messagesContainer = document.getElementById('chat-messages');
                    messagesContainer.innerHTML = '';
                    
                    data.messages.forEach(msg => {
                        const messageDiv = document.createElement('div');
                        messageDiv.className = `message ${msg.is_own ? 'own' : ''} fade-in`;
                        
                        const time = new Date(msg.created_at).toLocaleTimeString();
                        
                        messageDiv.innerHTML = `
                            <div class="message-header">
                                <span>${msg.sender_name}</span>
                                <span>${time}</span>
                            </div>
                            <div class="message-content">${msg.message_text}</div>
                        `;
                        
                        messagesContainer.appendChild(messageDiv);
                    });
                    
                    // Прокрутка вниз
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }
            } catch (error) {
                console.error('Ошибка загрузки сообщений:', error);
            }
        }

        // Отправка сообщения
        async function sendMessage() {
            if (!currentChat || !currentChatType) return;
            
            const messageText = document.getElementById('message-text').value.trim();
            if (!messageText) return;
            
            try {
                const requestData = {
                    message_text: messageText,
                    type: currentChatType
                };
                
                if (currentChatType === 'private') {
                    requestData.receiver_id = currentChat;
                } else {
                    requestData.group_id = currentChat;
                }
                
                const response = await fetch('/api/send_message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestData)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('message-text').value = '';
                    loadMessages(); // Обновляем сообщения
                } else {
                    alert('Ошибка отправки: ' + data.error);
                }
            } catch (error) {
                console.error('Ошибка отправки сообщения:', error);
            }
        }

        // Отправка по Enter
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }

        // Показать модальное окно создания группы
        async function showCreateGroupModal() {
            await loadUsersForGroup();
            document.getElementById('create-group-modal').style.display = 'block';
        }

        // Закрыть модальное окно
        function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
            selectedUsers = [];
        }

        // Загрузка пользователей для выбора в группу
        async function loadUsersForGroup() {
            try {
                const response = await fetch('/api/users');
                const data = await response.json();
                
                if (data.success) {
                    const container = document.getElementById('group-users-select');
                    container.innerHTML = '';
                    
                    data.users.forEach(user => {
                        const div = document.createElement('div');
                        div.className = 'user-select-item';
                        div.textContent = user.username;
                        div.onclick = () => toggleUserSelection(user.id, div);
                        container.appendChild(div);
                    });
                }
            } catch (error) {
                console.error('Ошибка загрузки пользователей:', error);
            }
        }

        // Переключение выбора пользователя
        function toggleUserSelection(userId, element) {
            const index = selectedUsers.indexOf(userId);
            
            if (index === -1) {
                selectedUsers.push(userId);
                element.classList.add('selected');
            } else {
                selectedUsers.splice(index, 1);
                element.classList.remove('selected');
            }
        }

        // Создание группы
        async function createGroup() {
            const name = document.getElementById('group-name').value.trim();
            const description = document.getElementById('group-description').value.trim();
            
            if (!name) {
                alert('Введите название группы');
                return;
            }
            
            try {
                const response = await fetch('/api/create_group', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name,
                        description,
                        member_ids: selectedUsers
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Группа создана успешно!');
                    closeModal('create-group-modal');
                    loadGroups(); // Обновляем список групп
                    
                    // Очищаем форму
                    document.getElementById('group-name').value = '';
                    document.getElementById('group-description').value = '';
                    selectedUsers = [];
                } else {
                    alert('Ошибка создания группы: ' + data.error);
                }
            } catch (error) {
                console.error('Ошибка создания группы:', error);
                alert('Ошибка сети');
            }
        }

        // Вспомогательные функции
        function showError(elementId, message) {
            const element = document.getElementById(elementId);
            element.textContent = message;
            element.style.display = 'block';
        }

        function showSuccess(elementId, message) {
            const element = document.getElementById(elementId);
            element.textContent = message;
            element.style.display = 'block';
        }

        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', function() {
            checkAuth();
            
            // Обработка нажатия вне модального окна
            window.onclick = function(event) {
                const modal = document.getElementById('create-group-modal');
                if (event.target === modal) {
                    closeModal('create-group-modal');
                }
            }
        });
    </script>
</body>
</html>
''')

if __name__ == '__main__':
    # Инициализация базы данных
    try:
        init_db()
        print("🚀 Сервер запускается...")
        print("📧 Мессенджер доступен по адресу: http://localhost:5000")
        print("👤 Тестовые пользователи: alex, maria, ivan, sophia, maxim")
        print("🔑 Пароль для всех: password123")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
