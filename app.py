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
                message_type TEXT DEFAULT 'private', -- 'private' или 'group'
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
            
            # Создаем тестовую группу
            cursor.execute(
                "INSERT INTO groups (name, description, creator_id) VALUES (?, ?, ?)",
                ('Общая группа', 'Группа для обсуждения общих вопросов', 1)
            )
            group_id = cursor.lastrowid
            
            # Добавляем всех пользователей в группу
            for user_id in [1, 2, 3]:
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
            SELECT g.id, g.name, g.description, g.creator_id, u.username as creator_name
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
                    cursor.execute(
                        "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                        (group_id, user_id)
                    )
            
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
        
        chat_type = request.args.get('type', 'private')  # 'private' или 'group'
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
        message_type = data.get('type', 'private')  # 'private' или 'group'
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
                cursor.execute(
                    "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
                    (group_id, session['user_id'])
                )
                if not cursor.fetchone():
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

# HTML шаблон для SPA
spa_html = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>💬 Web Messenger</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        
        .auth-container { display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .auth-box { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); width: 100%; max-width: 400px; }
        .auth-tabs { display: flex; margin-bottom: 20px; border-bottom: 2px solid #eee; }
        .auth-tab { flex: 1; padding: 15px; text-align: center; cursor: pointer; border-bottom: 3px solid transparent; }
        .auth-tab.active { border-bottom-color: #667eea; color: #667eea; font-weight: bold; }
        .auth-form { display: none; }
        .auth-form.active { display: block; }
        input, textarea { width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; }
        input:focus, textarea:focus { outline: none; border-color: #667eea; }
        button { padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; margin: 10px 0; }
        button:hover { opacity: 0.9; }
        .btn-small { padding: 8px 15px; font-size: 14px; }
        .btn-danger { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); }
        .error { color: #e74c3c; text-align: center; margin: 10px 0; padding: 10px; background: #f8d7da; border-radius: 5px; }
        .success { color: #27ae60; text-align: center; margin: 10px 0; padding: 10px; background: #d4edda; border-radius: 5px; }
        
        .chat-container { display: none; background: white; border-radius: 15px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.2); height: 80vh; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
        .chat-layout { display: flex; height: calc(100% - 60px); }
        .sidebar { width: 300px; background: #f8f9fa; border-right: 1px solid #ddd; overflow-y: auto; display: flex; flex-direction: column; }
        .sidebar-header { padding: 15px; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; }
        .chat-list { flex: 1; overflow-y: auto; padding: 10px; }
        .chat-item { padding: 12px; margin: 5px 0; background: white; border-radius: 8px; cursor: pointer; transition: all 0.3s; display: flex; align-items: center; }
        .chat-item:hover { background: #667eea; color: white; }
        .chat-item.active { background: #667eea; color: white; }
        .chat-item-icon { margin-right: 10px; font-size: 18px; }
        .chat-main { flex: 1; display: flex; flex-direction: column; }
        .chat-header { padding: 15px; background: white; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; }
        .messages-container { flex: 1; padding: 20px; overflow-y: auto; background: #f8f9fa; display: flex; flex-direction: column; }
        .message { max-width: 70%; margin: 10px 0; padding: 12px; border-radius: 15px; position: relative; }
        .message-own { background: #667eea; color: white; margin-left: auto; border-bottom-right-radius: 5px; }
        .message-other { background: white; color: #333; margin-right: auto; border-bottom-left-radius: 5px; border: 1px solid #ddd; }
        .message-group { background: #e8f4f8; border-color: #b8e0f0; }
        .message-time { font-size: 0.8em; opacity: 0.7; margin-top: 5px; }
        .message-sender { font-weight: bold; margin-bottom: 5px; }
        .message-input-area { padding: 15px; background: white; border-top: 1px solid #ddd; }
        .message-input-container { display: flex; gap: 10px; }
        .message-input { flex: 1; }
        .message-actions { display: flex; gap: 5px; }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal-content { background: white; margin: 10% auto; padding: 20px; border-radius: 15px; width: 90%; max-width: 500px; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .close-modal { font-size: 24px; cursor: pointer; }
        .user-select-list { max-height: 200px; overflow-y: auto; margin: 10px 0; }
        .user-select-item { padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin: 5px 0; }
        .checkbox-container { display: flex; align-items: center; gap: 10px; }
        
        .tabs { display: flex; border-bottom: 2px solid #eee; margin-bottom: 15px; }
        .tab { padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; }
        .tab.active { border-bottom-color: #667eea; color: #667eea; font-weight: bold; }
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
                    <div id="loginError" class="error" style="display: none;"></div>
                    <input type="text" id="loginUsername" placeholder="Логин" value="alex">
                    <input type="password" id="loginPassword" placeholder="Пароль" value="password123">
                    <button onclick="login()">Войти</button>
                </div>
                
                <div class="auth-form" id="registerForm">
                    <h2>📝 Регистрация</h2>
                    <div id="registerError" class="error" style="display: none;"></div>
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
                <button class="btn-small btn-danger" onclick="logout()">🚪 Выйти</button>
            </div>
            
            <div class="chat-layout">
                <div class="sidebar">
                    <div class="sidebar-header">
                        <h3>💬 Чаты</h3>
                        <button class="btn-small" onclick="showCreateGroupModal()">➕ Группа</button>
                    </div>
                    
                    <div class="tabs">
                        <div class="tab active" onclick="showChatTab('users')">👥 Люди</div>
                        <div class="tab" onclick="showChatTab('groups')">👪 Группы</div>
                    </div>
                    
                    <div class="chat-list">
                        <div id="usersList" class="chat-tab active"></div>
                        <div id="groupsList" class="chat-tab" style="display: none;"></div>
                    </div>
                </div>
                
                <div class="chat-main">
                    <div class="chat-header">
                        <h3 id="chatTitle">Выберите чат для общения</h3>
                        <div id="chatInfo"></div>
                    </div>
                    
                    <div class="messages-container" id="messagesContainer"></div>
                    
                    <div class="message-input-area" id="messageInputArea" style="display: none;">
                        <div class="message-input-container">
                            <input type="text" id="messageText" class="message-input" placeholder="Введите сообщение..." onkeypress="if(event.key === 'Enter') sendMessage()">
                            <div class="message-actions">
                                <button onclick="sendMessage()">📤</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Модальное окно создания группы -->
    <div id="createGroupModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Создать новую группу</h3>
                <span class="close-modal" onclick="closeModal('createGroupModal')">&times;</span>
            </div>
            <div id="createGroupError" class="error" style="display: none;"></div>
            <input type="text" id="groupName" placeholder="Название группы">
            <textarea id="groupDescription" placeholder="Описание группы (необязательно)" rows="3"></textarea>
            <h4>Выберите участников:</h4>
            <div class="user-select-list" id="groupMembersList"></div>
            <button onclick="createGroup()">Создать группу</button>
        </div>
    </div>

    <script>
        let currentUser = null;
        let currentChat = null;
        let currentChatType = null;
        let refreshInterval = null;
        let allUsers = [];
        
        async function checkAuth() {
            try {
                const response = await fetch('/api/check_auth');
                const data = await response.json();
                
                if (data.success) {
                    currentUser = data.username;
                    showChat();
                    loadUsers();
                    loadGroups();
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
        
        function showChatTab(tabName) {
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.chat-tab').forEach(tab => tab.style.display = 'none');
            
            document.querySelector(`.tab:nth-child(${tabName === 'users' ? 1 : 2})`).classList.add('active');
            document.getElementById(tabName === 'users' ? 'usersList' : 'groupsList').style.display = 'block';
        }
        
        async function login() {
            const username = document.getElementById('loginUsername').value;
            const password = document.getElementById('loginPassword').value;
            
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
                    loadGroups();
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
            currentChat = null;
            showAuth();
        }
        
        async function loadUsers() {
            try {
                const response = await fetch('/api/users');
                const data = await response.json();
                
                if (data.success) {
                    allUsers = data.users;
                    const usersList = document.getElementById('usersList');
                    usersList.innerHTML = '';
                    
                    data.users.forEach(user => {
                        const userElement = document.createElement('div');
                        userElement.className = 'chat-item';
                        userElement.innerHTML = `
                            <span class="chat-item-icon">👤</span>
                            <div>${user.username} (${user.phone})</div>
                        `;
                        userElement.onclick = () => selectChat('private', user.id, user.username);
                        usersList.appendChild(userElement);
                    });
                }
            } catch (error) {
                console.error('Failed to load users:', error);
            }
        }
        
        async function loadGroups() {
            try {
                const response = await fetch('/api/groups');
                const data = await response.json();
                
                if (data.success) {
                    const groupsList = document.getElementById('groupsList');
                    groupsList.innerHTML = '';
                    
                    data.groups.forEach(group => {
                        const groupElement = document.createElement('div');
                        groupElement.className = 'chat-item';
                        groupElement.innerHTML = `
                            <span class="chat-item-icon">👪</span>
                            <div>
                                <strong>${group.name}</strong>
                                <div style="font-size: 0.9em; opacity: 0.7;">${group.description || 'Без описания'}</div>
                            </div>
                        `;
                        groupElement.onclick = () => selectChat('group', group.id, group.name);
                        groupsList.appendChild(groupElement);
                    });
                }
            } catch (error) {
                console.error('Failed to load groups:', error);
            }
        }
        
        async function selectChat(chatType, chatId, chatName) {
            currentChat = chatId;
            currentChatType = chatType;
            
            // Сбрасываем выделение
            document.querySelectorAll('.chat-item').forEach(item => item.classList.remove('active'));
            event.target.classList.add('active');
            
            document.getElementById('chatTitle').textContent = `💬 Чат с ${chatName}`;
            document.getElementById('messageInputArea').style.display = 'block';
            
            if (chatType === 'group') {
                document.getElementById('chatInfo').innerHTML = `<button class="btn-small" onclick="showGroupInfo(${chatId})">ℹ️ Инфо</button>`;
            } else {
                document.getElementById('chatInfo').innerHTML = '';
            }
            
            await loadMessages();
            
            if (refreshInterval) clearInterval(refreshInterval);
            refreshInterval = setInterval(loadMessages, 2000);
        }
        
        async function loadMessages() {
            if (!currentChat) return;
            
            try {
                const response = await fetch(`/api/messages?type=${currentChatType}&id=${currentChat}`);
                const data = await response.json();
                
                if (data.success) {
                    const messagesContainer = document.getElementById('messagesContainer');
                    messagesContainer.innerHTML = '';
                    
                    data.messages.forEach(msg => {
                        const messageElement = document.createElement('div');
                        messageElement.className = `message ${msg.is_own ? 'message-own' : 'message-other'} ${msg.type === 'group' ? 'message-group' : ''}`;
                        
                        const time = new Date(msg.created_at).toLocaleTimeString();
                        
                        let messageContent = '';
                        if (msg.type === 'group' && !msg.is_own) {
                            messageContent += `<div class="message-sender">${msg.sender_name}</div>`;
                        }
                        
                        messageContent += `
                            <div>${msg.message_text}</div>
                            <div class="message-time">${time}</div>
                        `;
                        
                        messageElement.innerHTML = messageContent;
                        messagesContainer.appendChild(messageElement);
                    });
                    
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }
            } catch (error) {
                console.error('Failed to load messages:', error);
            }
        }
        
        async function sendMessage() {
            const messageText = document.getElementById('messageText').value.trim();
            if (!messageText || !currentChat) return;
            
            try {
                const payload = {
                    message_text: messageText,
                    type: currentChatType
                };
                
                if (currentChatType === 'private') {
                    payload.receiver_id = currentChat;
                } else {
                    payload.group_id = currentChat;
                }
                
                const response = await fetch('/api/send_message', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('messageText').value = '';
                    loadMessages();
                } else {
                    alert('Ошибка: ' + data.error);
                }
            } catch (error) {
                alert('Ошибка отправки сообщения');
            }
        }
        
        function showCreateGroupModal() {
            const modal = document.getElementById('createGroupModal');
            const membersList = document.getElementById('groupMembersList');
            
            membersList.innerHTML = '';
            allUsers.forEach(user => {
                const userElement = document.createElement('div');
                userElement.className = 'user-select-item';
                userElement.innerHTML = `
                    <div class="checkbox-container">
                        <input type="checkbox" id="user-${user.id}" value="${user.id}">
                        <label for="user-${user.id}">${user.username} (${user.phone})</label>
                    </div>
                `;
                membersList.appendChild(userElement);
            });
            
            modal.style.display = 'block';
        }
        
        function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }
        
        async function createGroup() {
            const name = document.getElementById('groupName').value.trim();
            const description = document.getElementById('groupDescription').value.trim();
            
            if (!name) {
                showError('createGroupError', 'Введите название группы');
                return;
            }
            
            const memberCheckboxes = document.querySelectorAll('#groupMembersList input[type="checkbox"]:checked');
            const memberIds = Array.from(memberCheckboxes).map(cb => parseInt(cb.value));
            
            try {
                const response = await fetch('/api/create_group', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name, description, member_ids: memberIds })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    closeModal('createGroupModal');
                    alert('Группа создана успешно!');
                    loadGroups();
                    
                    // Очищаем форму
                    document.getElementById('groupName').value = '';
                    document.getElementById('groupDescription').value = '';
                    document.querySelectorAll('#groupMembersList input[type="checkbox"]').forEach(cb => cb.checked = false);
                } else {
                    showError('createGroupError', data.error);
                }
            } catch (error) {
                showError('createGroupError', 'Ошибка создания группы');
            }
        }
        
        function showGroupInfo(groupId) {
            alert('Информация о группе будет здесь. ID группы: ' + groupId);
            // В реальном приложении здесь можно показать детальную информацию о группе
        }
        
        function showError(elementId, message) {
            const element = document.getElementById(elementId);
            element.textContent = message;
            element.style.display = 'block';
            setTimeout(() => element.style.display = 'none', 5000);
        }
        
        // Закрытие модального окна при клике вне его
        window.onclick = function(event) {
            if (event.target.classList.contains('modal')) {
                event.target.style.display = 'none';
            }
        }
        
        checkAuth();
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
    print("👪 Тестовая группа: 'Общая группа' с участием всех пользователей")
    app.run(host='0.0.0.0', port=port, debug=False)
