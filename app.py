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
                message_type TEXT DEFAULT 'private', -- 'private', 'group', 'channel'
                group_id INTEGER DEFAULT NULL,
                channel_id INTEGER DEFAULT NULL,
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
        
        # Таблица каналов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                creator_id INTEGER NOT NULL,
                is_public BOOLEAN DEFAULT 1,
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
        
        # Таблица подписчиков каналов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(channel_id, user_id)
            )
        ''')
        
        # Новая таблица: администраторы каналов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                added_by INTEGER NOT NULL,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (added_by) REFERENCES users (id),
                UNIQUE(channel_id, user_id)
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
            for user_id in [1, 2, 3]:
                cursor.execute(
                    "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                    (group_id, user_id)
                )
            
            # Создаем тестовые каналы
            test_channels = [
                ('Новости проекта', 'Последние новости нашего проекта', 1, 1),
                ('Технические обсуждения', 'Обсуждение технических вопросов', 2, 1),
                ('Оффтоп', 'Несерьезные обсуждения', 3, 1)
            ]
            
            for name, description, creator_id, is_public in test_channels:
                cursor.execute(
                    "INSERT INTO channels (name, description, creator_id, is_public) VALUES (?, ?, ?, ?)",
                    (name, description, creator_id, is_public)
                )
                channel_id = cursor.lastrowid
                
                # Добавляем подписчиков в каналы
                subscribers = [1, 2, 3, 4] if channel_id == 1 else [1, 2, 3] if channel_id == 2 else [1, 3, 5]
                for user_id in subscribers:
                    cursor.execute(
                        "INSERT INTO channel_subscribers (channel_id, user_id) VALUES (?, ?)",
                        (channel_id, user_id)
                    )
                
                # Добавляем администраторов для тестовых каналов
                if channel_id == 1:  # Для первого канала добавляем админов
                    cursor.execute(
                        "INSERT INTO channel_admins (channel_id, user_id, added_by) VALUES (?, ?, ?)",
                        (channel_id, 2, 1)  # maria как админ
                    )
                    cursor.execute(
                        "INSERT INTO channel_admins (channel_id, user_id, added_by) VALUES (?, ?, ?)",
                        (channel_id, 3, 1)  # ivan как админ
                    )
        
        db.commit()
        db.close()
        print("✅ База данных успешно инициализирована")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

def is_channel_admin(channel_id, user_id):
    """Проверяет, является ли пользователь администратором канала"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute(
        "SELECT 1 FROM channel_admins WHERE channel_id = ? AND user_id = ?",
        (channel_id, user_id)
    )
    is_admin = cursor.fetchone() is not None
    
    cursor.execute(
        "SELECT creator_id FROM channels WHERE id = ?",
        (channel_id,)
    )
    channel = cursor.fetchone()
    is_creator = channel and channel['creator_id'] == user_id
    
    db.close()
    return is_creator or is_admin

def get_channel_admins(channel_id):
    """Получает список администраторов канала"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT u.id, u.username, ca.added_at, adder.username as added_by_name
        FROM channel_admins ca
        JOIN users u ON ca.user_id = u.id
        JOIN users adder ON ca.added_by = adder.id
        WHERE ca.channel_id = ?
        ORDER BY ca.added_at
    ''', (channel_id,))
    
    admins = cursor.fetchall()
    db.close()
    return [dict(admin) for admin in admins]

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

@app.route('/api/channels')
def api_channels():
    """API для получения списка каналов"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        db = get_db()
        cursor = db.cursor()
        
        # Получаем каналы, на которые подписан пользователь + публичные каналы
        cursor.execute('''
            SELECT c.id, c.name, c.description, c.creator_id, c.is_public,
                   u.username as creator_name,
                   (SELECT COUNT(*) FROM channel_subscribers WHERE channel_id = c.id) as subscriber_count,
                   EXISTS(SELECT 1 FROM channel_subscribers WHERE channel_id = c.id AND user_id = ?) as is_subscribed,
                   (c.creator_id = ? OR EXISTS(SELECT 1 FROM channel_admins WHERE channel_id = c.id AND user_id = ?)) as is_admin
            FROM channels c
            JOIN users u ON c.creator_id = u.id
            WHERE c.is_public = 1 OR EXISTS(SELECT 1 FROM channel_subscribers WHERE channel_id = c.id AND user_id = ?)
            ORDER BY c.name
        ''', (session['user_id'], session['user_id'], session['user_id'], session['user_id']))
        
        channels = cursor.fetchall()
        db.close()
        
        channels_data = [dict(channel) for channel in channels]
        return jsonify({'success': True, 'channels': channels_data})
        
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            init_db()
            return jsonify({'success': True, 'channels': []})
        return jsonify({'success': False, 'error': f'Ошибка базы данных: {str(e)}'})

@app.route('/api/channel_admins/<int:channel_id>')
def api_channel_admins(channel_id):
    """API для получения списка администраторов канала"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        # Проверяем, что пользователь является создателем канала
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            "SELECT creator_id FROM channels WHERE id = ?",
            (channel_id,)
        )
        channel = cursor.fetchone()
        
        if not channel or channel['creator_id'] != session['user_id']:
            db.close()
            return jsonify({'success': False, 'error': 'Только создатель канала может просматривать администраторов'}), 403
        
        admins = get_channel_admins(channel_id)
        db.close()
        
        return jsonify({'success': True, 'admins': admins})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка: {str(e)}'})

@app.route('/api/add_channel_admin', methods=['POST'])
def api_add_channel_admin():
    """API для добавления администратора канала"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        data = request.get_json()
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        
        if not channel_id or not user_id:
            return jsonify({'success': False, 'error': 'Укажите канал и пользователя'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        # Проверяем, что пользователь является создателем канала
        cursor.execute(
            "SELECT creator_id FROM channels WHERE id = ?",
            (channel_id,)
        )
        channel = cursor.fetchone()
        
        if not channel or channel['creator_id'] != session['user_id']:
            db.close()
            return jsonify({'success': False, 'error': 'Только создатель канала может добавлять администраторов'}), 403
        
        # Проверяем, что пользователь существует
        cursor.execute(
            "SELECT 1 FROM users WHERE id = ?",
            (user_id,)
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
        
        # Проверяем, что пользователь не является создателем
        if user_id == channel['creator_id']:
            db.close()
            return jsonify({'success': False, 'error': 'Создатель канала уже является администратором'}), 400
        
        # Добавляем администратора
        try:
            cursor.execute(
                "INSERT INTO channel_admins (channel_id, user_id, added_by) VALUES (?, ?, ?)",
                (channel_id, user_id, session['user_id'])
            )
            db.commit()
            db.close()
            return jsonify({'success': True, 'message': 'Администратор добавлен'})
        except sqlite3.IntegrityError:
            db.close()
            return jsonify({'success': False, 'error': 'Пользователь уже является администратором'}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка: {str(e)}'})

@app.route('/api/remove_channel_admin', methods=['POST'])
def api_remove_channel_admin():
    """API для удаления администратора канала"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        data = request.get_json()
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        
        if not channel_id or not user_id:
            return jsonify({'success': False, 'error': 'Укажите канал и пользователя'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        # Проверяем, что пользователь является создателем канала
        cursor.execute(
            "SELECT creator_id FROM channels WHERE id = ?",
            (channel_id,)
        )
        channel = cursor.fetchone()
        
        if not channel or channel['creator_id'] != session['user_id']:
            db.close()
            return jsonify({'success': False, 'error': 'Только создатель канала может удалять администраторов'}), 403
        
        # Удаляем администратора
        cursor.execute(
            "DELETE FROM channel_admins WHERE channel_id = ? AND user_id = ?",
            (channel_id, user_id)
        )
        
        if cursor.rowcount == 0:
            db.close()
            return jsonify({'success': False, 'error': 'Администратор не найден'}), 404
        
        db.commit()
        db.close()
        return jsonify({'success': True, 'message': 'Администратор удален'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка: {str(e)}'})

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

@app.route('/api/create_channel', methods=['POST'])
def api_create_channel():
    """API для создания канала"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        data = request.get_json()
        name = data.get('name')
        description = data.get('description', '')
        is_public = data.get('is_public', True)
        
        if not name:
            return jsonify({'success': False, 'error': 'Введите название канала'})
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            # Создаем канал
            cursor.execute(
                "INSERT INTO channels (name, description, creator_id, is_public) VALUES (?, ?, ?, ?)",
                (name, description, session['user_id'], is_public)
            )
            channel_id = cursor.lastrowid
            
            # Автоматически подписываем создателя на канал
            cursor.execute(
                "INSERT INTO channel_subscribers (channel_id, user_id) VALUES (?, ?)",
                (channel_id, session['user_id'])
            )
            
            db.commit()
            db.close()
            return jsonify({'success': True, 'message': 'Канал создан успешно', 'channel_id': channel_id})
        
        except Exception as e:
            db.close()
            return jsonify({'success': False, 'error': f'Ошибка создания канала: {str(e)}'}), 500
            
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            init_db()
            return jsonify({'success': False, 'error': 'База данных переинициализирована, попробуйте снова'})
        return jsonify({'success': False, 'error': f'Ошибка базы данных: {str(e)}'})

@app.route('/api/subscribe_channel', methods=['POST'])
def api_subscribe_channel():
    """API для подписки/отписки от канала"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
        
        data = request.get_json()
        channel_id = data.get('channel_id')
        action = data.get('action', 'subscribe')  # 'subscribe' или 'unsubscribe'
        
        if not channel_id:
            return jsonify({'success': False, 'error': 'Укажите канал'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            if action == 'subscribe':
                cursor.execute(
                    "INSERT OR IGNORE INTO channel_subscribers (channel_id, user_id) VALUES (?, ?)",
                    (channel_id, session['user_id'])
                )
                message = 'Подписка оформлена'
            else:
                cursor.execute(
                    "DELETE FROM channel_subscribers WHERE channel_id = ? AND user_id = ?",
                    (channel_id, session['user_id'])
                )
                message = 'Подписка отменена'
            
            db.commit()
            
            # Получаем обновленное количество подписчиков
            cursor.execute(
                "SELECT COUNT(*) as count FROM channel_subscribers WHERE channel_id = ?",
                (channel_id,)
            )
            subscriber_count = cursor.fetchone()['count']
            
            db.close()
            return jsonify({'success': True, 'message': message, 'subscriber_count': subscriber_count})
        
        except Exception as e:
            db.close()
            return jsonify({'success': False, 'error': f'Ошибка: {str(e)}'}), 500
            
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
        
        chat_type = request.args.get('type', 'private')  # 'private', 'group', 'channel'
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
        elif chat_type == 'group':
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
        else:  # channel
            # Проверяем, что пользователь подписан на канал
            cursor.execute(
                "SELECT 1 FROM channel_subscribers WHERE channel_id = ? AND user_id = ?",
                (chat_id, session['user_id'])
            )
            if not cursor.fetchone():
                db.close()
                return jsonify({'success': False, 'error': 'Вы не подписаны на этот канал'}), 403
            
            cursor.execute('''
                SELECT m.id, m.sender_id, m.channel_id, m.message_text, m.created_at, 
                       u.username as sender_name
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.channel_id = ? AND m.message_type = 'channel'
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
            elif chat_type == 'group':
                message_data['group_id'] = msg['group_id']
            else:
                message_data['channel_id'] = msg['channel_id']
            
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
        message_type = data.get('type', 'private')  # 'private', 'group', 'channel'
        receiver_id = data.get('receiver_id')
        group_id = data.get('group_id')
        channel_id = data.get('channel_id')
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
            elif message_type == 'group':
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
            else:  # channel
                if not channel_id:
                    return jsonify({'success': False, 'error': 'Укажите канал'}), 400
                
                # Проверяем, что пользователь является администратором канала
                if not is_channel_admin(channel_id, session['user_id']):
                    db.close()
                    return jsonify({'success': False, 'error': 'Только администраторы могут отправлять сообщения в канал'}), 403
                
                cursor.execute(
                    "INSERT INTO messages (sender_id, receiver_id, message_text, message_type, channel_id) VALUES (?, NULL, ?, 'channel', ?)",
                    (session['user_id'], message_text, channel_id)
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
    <title>Мессенджер</title>
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
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
            min-height: 90vh;
        }
        
        .auth-container {
            padding: 40px;
            text-align: center;
        }
        
        .tabs {
            display: flex;
            margin-bottom: 30px;
        }
        
        .tab {
            flex: 1;
            padding: 15px;
            background: #f8f9fa;
            border: none;
            cursor: pointer;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        
        .tab.active {
            background: white;
            border-bottom: 3px solid #667eea;
            font-weight: 500;
        }
        
        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }
        
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
            color: #333;
        }
        
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s ease;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        button {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            transition: transform 0.2s ease;
        }
        
        button:hover {
            transform: translateY(-2px);
        }
        
        .error {
            color: #dc3545;
            margin-top: 10px;
            padding: 10px;
            background: #f8d7da;
            border-radius: 5px;
        }
        
        .success {
            color: #155724;
            margin-top: 10px;
            padding: 10px;
            background: #d4edda;
            border-radius: 5px;
        }
        
        .app-container {
            display: flex;
            height: 90vh;
        }
        
        .sidebar {
            width: 300px;
            background: #f8f9fa;
            border-right: 1px solid #dee2e6;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            padding: 20px;
            background: white;
            border-bottom: 1px solid #dee2e6;
        }
        
        .user-info {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .search {
            padding: 15px;
            border-bottom: 1px solid #dee2e6;
        }
        
        .search input {
            border-radius: 20px;
        }
        
        .chats {
            flex: 1;
            overflow-y: auto;
        }
        
        .chat-list {
            list-style: none;
        }
        
        .chat-item {
            padding: 15px;
            border-bottom: 1px solid #e9ecef;
            cursor: pointer;
            transition: background 0.2s ease;
        }
        
        .chat-item:hover {
            background: #e9ecef;
        }
        
        .chat-item.active {
            background: #667eea;
            color: white;
        }
        
        .chat-name {
            font-weight: 500;
            margin-bottom: 5px;
        }
        
        .chat-preview {
            font-size: 14px;
            color: #666;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .chat-item.active .chat-preview {
            color: rgba(255,255,255,0.8);
        }
        
        .chat-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .chat-header {
            padding: 20px;
            background: white;
            border-bottom: 1px solid #dee2e6;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #f8f9fa;
        }
        
        .message {
            max-width: 70%;
            margin-bottom: 15px;
            padding: 12px 16px;
            border-radius: 18px;
            position: relative;
        }
        
        .message.own {
            background: #667eea;
            color: white;
            margin-left: auto;
            border-bottom-right-radius: 5px;
        }
        
        .message.other {
            background: white;
            border: 1px solid #dee2e6;
            margin-right: auto;
            border-bottom-left-radius: 5px;
        }
        
        .message-sender {
            font-weight: 500;
            margin-bottom: 5px;
            font-size: 14px;
        }
        
        .message-time {
            font-size: 12px;
            opacity: 0.7;
            margin-top: 5px;
            text-align: right;
        }
        
        .message-input {
            padding: 20px;
            background: white;
            border-top: 1px solid #dee2e6;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
        }
        
        .input-group input {
            flex: 1;
            border-radius: 25px;
        }
        
        .input-group button {
            width: auto;
            padding: 12px 24px;
            border-radius: 25px;
        }
        
        .create-buttons {
            padding: 15px;
            display: flex;
            gap: 10px;
        }
        
        .create-buttons button {
            flex: 1;
            padding: 10px;
            font-size: 14px;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
        }
        
        .modal-content {
            background: white;
            margin: 10% auto;
            padding: 30px;
            border-radius: 15px;
            max-width: 500px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .close {
            font-size: 24px;
            cursor: pointer;
        }
        
        .user-select {
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            margin-bottom: 15px;
        }
        
        .user-option {
            padding: 10px;
            border-bottom: 1px solid #e9ecef;
            cursor: pointer;
        }
        
        .user-option:hover {
            background: #f8f9fa;
        }
        
        .user-option.selected {
            background: #667eea;
            color: white;
        }
        
        .channel-info {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .admin-badge {
            background: #28a745;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 10px;
        }
        
        .creator-badge {
            background: #dc3545;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 10px;
        }
        
        .admin-panel {
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        
        .admin-list {
            margin-top: 10px;
        }
        
        .admin-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px;
            border-bottom: 1px solid #dee2e6;
        }
        
        .admin-actions {
            display: flex;
            gap: 10px;
        }
        
        .admin-actions button {
            padding: 5px 10px;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div id="auth-container" class="auth-container">
            <div class="tabs">
                <button class="tab active" onclick="showTab('login')">Вход</button>
                <button class="tab" onclick="showTab('register')">Регистрация</button>
            </div>
            
            <div id="login-form">
                <div class="form-group">
                    <label for="login-username">Логин:</label>
                    <input type="text" id="login-username" placeholder="Введите ваш логин">
                </div>
                <div class="form-group">
                    <label for="login-password">Пароль:</label>
                    <input type="password" id="login-password" placeholder="Введите ваш пароль">
                </div>
                <button onclick="login()">Войти</button>
                <div id="login-error" class="error" style="display: none;"></div>
            </div>
            
            <div id="register-form" style="display: none;">
                <div class="form-group">
                    <label for="reg-username">Логин:</label>
                    <input type="text" id="reg-username" placeholder="Придумайте логин">
                </div>
                <div class="form-group">
                    <label for="reg-phone">Телефон:</label>
                    <input type="tel" id="reg-phone" placeholder="+7XXXXXXXXXX">
                </div>
                <div class="form-group">
                    <label for="reg-password">Пароль:</label>
                    <input type="password" id="reg-password" placeholder="Придумайте пароль">
                </div>
                <div class="form-group">
                    <label for="reg-confirm">Подтвердите пароль:</label>
                    <input type="password" id="reg-confirm" placeholder="Повторите пароль">
                </div>
                <button onclick="register()">Зарегистрироваться</button>
                <div id="register-error" class="error" style="display: none;"></div>
                <div id="register-success" class="success" style="display: none;"></div>
            </div>
        </div>
        
        <div id="app-container" class="app-container" style="display: none;">
            <div class="sidebar">
                <div class="header">
                    <div class="user-info">
                        <span id="current-user">Пользователь</span>
                        <button onclick="logout()" style="width: auto; padding: 5px 10px;">Выйти</button>
                    </div>
                </div>
                
                <div class="search">
                    <input type="text" placeholder="Поиск..." oninput="searchChats(this.value)">
                </div>
                
                <div class="create-buttons">
                    <button onclick="showCreateGroupModal()">Создать группу</button>
                    <button onclick="showCreateChannelModal()">Создать канал</button>
                </div>
                
                <div class="chats">
                    <ul class="chat-list" id="chat-list">
                        <!-- Список чатов будет здесь -->
                    </ul>
                </div>
            </div>
            
            <div class="chat-content">
                <div class="chat-header">
                    <span id="current-chat-name">Выберите чат</span>
                    <div id="channel-admin-panel" style="display: none;">
                        <button onclick="showAdminPanel()" style="width: auto; padding: 5px 10px;">
                            Управление админами
                        </button>
                    </div>
                </div>
                
                <div class="messages" id="messages">
                    <!-- Сообщения будут здесь -->
                </div>
                
                <div class="message-input">
                    <div class="input-group">
                        <input type="text" id="message-input" placeholder="Введите сообщение..." onkeypress="handleKeyPress(event)">
                        <button onclick="sendMessage()">Отправить</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Модальное окно создания группы -->
    <div id="create-group-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Создать группу</h3>
                <span class="close" onclick="closeModal('create-group-modal')">&times;</span>
            </div>
            <div class="form-group">
                <label>Название группы:</label>
                <input type="text" id="group-name" placeholder="Введите название группы">
            </div>
            <div class="form-group">
                <label>Описание:</label>
                <input type="text" id="group-description" placeholder="Описание группы (необязательно)">
            </div>
            <div class="form-group">
                <label>Участники:</label>
                <div class="user-select" id="group-members-select">
                    <!-- Список пользователей -->
                </div>
            </div>
            <button onclick="createGroup()">Создать группу</button>
            <div id="group-error" class="error" style="display: none;"></div>
        </div>
    </div>

    <!-- Модальное окно создания канала -->
    <div id="create-channel-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Создать канал</h3>
                <span class="close" onclick="closeModal('create-channel-modal')">&times;</span>
            </div>
            <div class="form-group">
                <label>Название канала:</label>
                <input type="text" id="channel-name" placeholder="Введите название канала">
            </div>
            <div class="form-group">
                <label>Описание:</label>
                <input type="text" id="channel-description" placeholder="Описание канала (необязательно)">
            </div>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="channel-public" checked> Публичный канал
                </label>
            </div>
            <button onclick="createChannel()">Создать канал</button>
            <div id="channel-error" class="error" style="display: none;"></div>
        </div>
    </div>

    <!-- Модальное окно управления администраторами -->
    <div id="admin-panel-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Управление администраторами</h3>
                <span class="close" onclick="closeModal('admin-panel-modal')">&times;</span>
            </div>
            <div class="form-group">
                <label>Добавить администратора:</label>
                <select id="admin-user-select">
                    <!-- Список пользователей -->
                </select>
                <button onclick="addChannelAdmin()" style="margin-top: 10px;">Добавить</button>
            </div>
            <div class="admin-list" id="admin-list">
                <!-- Список администраторов -->
            </div>
            <div id="admin-error" class="error" style="display: none;"></div>
        </div>
    </div>

    <script>
        let currentUser = null;
        let currentChat = null;
        let users = [];
        let groups = [];
        let channels = [];
        let selectedUsers = new Set();
        let currentChannelAdmins = [];

        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('register-form').style.display = 'none';
            
            if (tabName === 'login') {
                document.querySelector('.tab:first-child').classList.add('active');
                document.getElementById('login-form').style.display = 'block';
            } else {
                document.querySelector('.tab:last-child').classList.add('active');
                document.getElementById('register-form').style.display = 'block';
            }
        }

        async function login() {
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;
            const errorDiv = document.getElementById('login-error');

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password })
                });

                const data = await response.json();

                if (data.success) {
                    currentUser = data.username;
                    document.getElementById('current-user').textContent = currentUser;
                    document.getElementById('auth-container').style.display = 'none';
                    document.getElementById('app-container').style.display = 'flex';
                    loadAppData();
                    startPolling();
                } else {
                    errorDiv.textContent = data.error;
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = 'Ошибка подключения к серверу';
                errorDiv.style.display = 'block';
            }
        }

        async function register() {
            const username = document.getElementById('reg-username').value;
            const phone = document.getElementById('reg-phone').value;
            const password = document.getElementById('reg-password').value;
            const confirm = document.getElementById('reg-confirm').value;
            const errorDiv = document.getElementById('register-error');
            const successDiv = document.getElementById('register-success');

            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, phone, password, confirm })
                });

                const data = await response.json();

                if (data.success) {
                    successDiv.textContent = data.message;
                    successDiv.style.display = 'block';
                    errorDiv.style.display = 'none';
                    
                    // Очищаем форму
                    document.getElementById('reg-username').value = '';
                    document.getElementById('reg-phone').value = '';
                    document.getElementById('reg-password').value = '';
                    document.getElementById('reg-confirm').value = '';
                    
                    // Переключаем на вкладку входа
                    setTimeout(() => showTab('login'), 2000);
                } else {
                    errorDiv.textContent = data.error;
                    errorDiv.style.display = 'block';
                    successDiv.style.display = 'none';
                }
            } catch (error) {
                errorDiv.textContent = 'Ошибка подключения к серверу';
                errorDiv.style.display = 'block';
            }
        }

        async function logout() {
            await fetch('/api/logout');
            currentUser = null;
            currentChat = null;
            document.getElementById('app-container').style.display = 'none';
            document.getElementById('auth-container').style.display = 'block';
            document.getElementById('login-username').value = '';
            document.getElementById('login-password').value = '';
            stopPolling();
        }

        async function loadAppData() {
            await Promise.all([
                loadUsers(),
                loadGroups(),
                loadChannels()
            ]);
            renderChatList();
        }

        async function loadUsers() {
            try {
                const response = await fetch('/api/users');
                const data = await response.json();
                if (data.success) {
                    users = data.users;
                }
            } catch (error) {
                console.error('Ошибка загрузки пользователей:', error);
            }
        }

        async function loadGroups() {
            try {
                const response = await fetch('/api/groups');
                const data = await response.json();
                if (data.success) {
                    groups = data.groups;
                }
            } catch (error) {
                console.error('Ошибка загрузки групп:', error);
            }
        }

        async function loadChannels() {
            try {
                const response = await fetch('/api/channels');
                const data = await response.json();
                if (data.success) {
                    channels = data.channels;
                }
            } catch (error) {
                console.error('Ошибка загрузки каналов:', error);
            }
        }

        function renderChatList() {
            const chatList = document.getElementById('chat-list');
            chatList.innerHTML = '';

            // Пользователи
            users.forEach(user => {
                const li = document.createElement('li');
                li.className = 'chat-item';
                li.onclick = () => selectChat('private', user.id, user.username);
                li.innerHTML = `
                    <div class="chat-name">${user.username}</div>
                    <div class="chat-preview">Личный чат</div>
                `;
                chatList.appendChild(li);
            });

            // Группы
            groups.forEach(group => {
                const li = document.createElement('li');
                li.className = 'chat-item';
                li.onclick = () => selectChat('group', group.id, group.name);
                li.innerHTML = `
                    <div class="chat-name">${group.name}</div>
                    <div class="chat-preview">Группа · ${group.member_count} участников</div>
                `;
                chatList.appendChild(li);
            });

            // Каналы
            channels.forEach(channel => {
                const li = document.createElement('li');
                li.className = 'chat-item';
                li.onclick = () => selectChat('channel', channel.id, channel.name);
                li.innerHTML = `
                    <div class="chat-name">
                        ${channel.name}
                        ${channel.is_admin ? '<span class="admin-badge">Админ</span>' : ''}
                    </div>
                    <div class="chat-preview">Канал · ${channel.subscriber_count} подписчиков</div>
                `;
                chatList.appendChild(li);
            });
        }

        async function selectChat(type, id, name) {
            currentChat = { type, id, name };
            
            // Обновляем активный элемент в списке
            document.querySelectorAll('.chat-item').forEach(item => {
                item.classList.remove('active');
            });
            event.currentTarget.classList.add('active');
            
            // Обновляем заголовок чата
            document.getElementById('current-chat-name').textContent = name;
            
            // Показываем/скрываем панель администратора
            const adminPanel = document.getElementById('channel-admin-panel');
            if (type === 'channel') {
                const channel = channels.find(c => c.id === id);
                if (channel && channel.is_admin) {
                    adminPanel.style.display = 'block';
                } else {
                    adminPanel.style.display = 'none';
                }
            } else {
                adminPanel.style.display = 'none';
            }
            
            // Загружаем сообщения
            await loadMessages();
        }

        async function loadMessages() {
            if (!currentChat) return;

            try {
                const response = await fetch(`/api/messages?type=${currentChat.type}&id=${currentChat.id}`);
                const data = await response.json();
                
                const messagesContainer = document.getElementById('messages');
                messagesContainer.innerHTML = '';
                
                if (data.success && data.messages) {
                    data.messages.forEach(msg => {
                        const messageDiv = document.createElement('div');
                        messageDiv.className = `message ${msg.is_own ? 'own' : 'other'}`;
                        
                        const time = new Date(msg.created_at).toLocaleTimeString();
                        
                        messageDiv.innerHTML = `
                            ${!msg.is_own && msg.type !== 'private' ? 
                                `<div class="message-sender">${msg.sender_name}</div>` : ''}
                            <div>${msg.message_text}</div>
                            <div class="message-time">${time}</div>
                        `;
                        
                        messagesContainer.appendChild(messageDiv);
                    });
                    
                    // Прокручиваем вниз
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }
            } catch (error) {
                console.error('Ошибка загрузки сообщений:', error);
            }
        }

        async function sendMessage() {
            if (!currentChat) {
                alert('Выберите чат для отправки сообщения');
                return;
            }

            const messageInput = document.getElementById('message-input');
            const messageText = messageInput.value.trim();
            
            if (!messageText) return;

            try {
                const payload = {
                    message_text: messageText,
                    type: currentChat.type
                };

                if (currentChat.type === 'private') {
                    payload.receiver_id = currentChat.id;
                } else if (currentChat.type === 'group') {
                    payload.group_id = currentChat.id;
                } else {
                    payload.channel_id = currentChat.id;
                }

                const response = await fetch('/api/send_message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();

                if (data.success) {
                    messageInput.value = '';
                    await loadMessages();
                } else {
                    alert(data.error);
                }
            } catch (error) {
                console.error('Ошибка отправки сообщения:', error);
                alert('Ошибка отправки сообщения');
            }
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }

        function showCreateGroupModal() {
            const modal = document.getElementById('create-group-modal');
            const userSelect = document.getElementById('group-members-select');
            
            userSelect.innerHTML = '';
            selectedUsers.clear();
            
            users.forEach(user => {
                const div = document.createElement('div');
                div.className = 'user-option';
                div.textContent = user.username;
                div.onclick = () => {
                    if (selectedUsers.has(user.id)) {
                        selectedUsers.delete(user.id);
                        div.classList.remove('selected');
                    } else {
                        selectedUsers.add(user.id);
                        div.classList.add('selected');
                    }
                };
                userSelect.appendChild(div);
            });
            
            modal.style.display = 'block';
        }

        async function createGroup() {
            const name = document.getElementById('group-name').value.trim();
            const description = document.getElementById('group-description').value.trim();
            const errorDiv = document.getElementById('group-error');

            if (!name) {
                errorDiv.textContent = 'Введите название группы';
                errorDiv.style.display = 'block';
                return;
            }

            try {
                const response = await fetch('/api/create_group', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        name,
                        description,
                        member_ids: Array.from(selectedUsers)
                    })
                });

                const data = await response.json();

                if (data.success) {
                    closeModal('create-group-modal');
                    await loadGroups();
                    renderChatList();
                    // Очищаем форму
                    document.getElementById('group-name').value = '';
                    document.getElementById('group-description').value = '';
                    errorDiv.style.display = 'none';
                } else {
                    errorDiv.textContent = data.error;
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = 'Ошибка создания группы';
                errorDiv.style.display = 'block';
            }
        }

        function showCreateChannelModal() {
            const modal = document.getElementById('create-channel-modal');
            modal.style.display = 'block';
        }

        async function createChannel() {
            const name = document.getElementById('channel-name').value.trim();
            const description = document.getElementById('channel-description').value.trim();
            const isPublic = document.getElementById('channel-public').checked;
            const errorDiv = document.getElementById('channel-error');

            if (!name) {
                errorDiv.textContent = 'Введите название канала';
                errorDiv.style.display = 'block';
                return;
            }

            try {
                const response = await fetch('/api/create_channel', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        name,
                        description,
                        is_public: isPublic
                    })
                });

                const data = await response.json();

                if (data.success) {
                    closeModal('create-channel-modal');
                    await loadChannels();
                    renderChatList();
                    // Очищаем форму
                    document.getElementById('channel-name').value = '';
                    document.getElementById('channel-description').value = '';
                    errorDiv.style.display = 'none';
                } else {
                    errorDiv.textContent = data.error;
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = 'Ошибка создания канала';
                errorDiv.style.display = 'block';
            }
        }

        async function showAdminPanel() {
            if (!currentChat || currentChat.type !== 'channel') return;

            const modal = document.getElementById('admin-panel-modal');
            const userSelect = document.getElementById('admin-user-select');
            const adminList = document.getElementById('admin-list');

            // Загружаем список администраторов
            try {
                const response = await fetch(`/api/channel_admins/${currentChat.id}`);
                const data = await response.json();
                
                if (data.success) {
                    currentChannelAdmins = data.admins;
                    renderAdminList();
                }
            } catch (error) {
                console.error('Ошибка загрузки администраторов:', error);
            }

            // Заполняем выпадающий список пользователей
            userSelect.innerHTML = '';
            users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.id;
                option.textContent = user.username;
                userSelect.appendChild(option);
            });

            modal.style.display = 'block';
        }

        function renderAdminList() {
            const adminList = document.getElementById('admin-list');
            adminList.innerHTML = '';

            currentChannelAdmins.forEach(admin => {
                const div = document.createElement('div');
                div.className = 'admin-item';
                div.innerHTML = `
                    <span>${admin.username} (добавлен: ${new Date(admin.added_at).toLocaleDateString()})</span>
                    <div class="admin-actions">
                        <button onclick="removeAdmin(${admin.id})">Удалить</button>
                    </div>
                `;
                adminList.appendChild(div);
            });
        }

        async function addChannelAdmin() {
            const userSelect = document.getElementById('admin-user-select');
            const userId = userSelect.value;
            const errorDiv = document.getElementById('admin-error');

            if (!userId) {
                errorDiv.textContent = 'Выберите пользователя';
                errorDiv.style.display = 'block';
                return;
            }

            try {
                const response = await fetch('/api/add_channel_admin', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        channel_id: currentChat.id,
                        user_id: userId
                    })
                });

                const data = await response.json();

                if (data.success) {
                    errorDiv.style.display = 'none';
                    // Обновляем список администраторов
                    const adminsResponse = await fetch(`/api/channel_admins/${currentChat.id}`);
                    const adminsData = await adminsResponse.json();
                    
                    if (adminsData.success) {
                        currentChannelAdmins = adminsData.admins;
                        renderAdminList();
                    }
                } else {
                    errorDiv.textContent = data.error;
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = 'Ошибка добавления администратора';
                errorDiv.style.display = 'block';
            }
        }

        async function removeAdmin(userId) {
            const errorDiv = document.getElementById('admin-error');

            try {
                const response = await fetch('/api/remove_channel_admin', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        channel_id: currentChat.id,
                        user_id: userId
                    })
                });

                const data = await response.json();

                if (data.success) {
                    errorDiv.style.display = 'none';
                    // Обновляем список администраторов
                    const adminsResponse = await fetch(`/api/channel_admins/${currentChat.id}`);
                    const adminsData = await adminsResponse.json();
                    
                    if (adminsData.success) {
                        currentChannelAdmins = adminsData.admins;
                        renderAdminList();
                    }
                } else {
                    errorDiv.textContent = data.error;
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = 'Ошибка удаления администратора';
                errorDiv.style.display = 'block';
            }
        }

        function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }

        function searchChats(query) {
            const chatItems = document.querySelectorAll('.chat-item');
            chatItems.forEach(item => {
                const chatName = item.querySelector('.chat-name').textContent;
                if (chatName.toLowerCase().includes(query.toLowerCase())) {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
        }

        let pollingInterval;
        function startPolling() {
            pollingInterval = setInterval(async () => {
                if (currentChat) {
                    await loadMessages();
                }
                await loadAppData();
            }, 3000); // Обновление каждые 3 секунды
        }

        function stopPolling() {
            clearInterval(pollingInterval);
        }

        // Проверяем авторизацию при загрузке
        async function checkAuth() {
            try {
                const response = await fetch('/api/check_auth');
                const data = await response.json();
                
                if (data.success) {
                    currentUser = data.username;
                    document.getElementById('current-user').textContent = currentUser;
                    document.getElementById('auth-container').style.display = 'none';
                    document.getElementById('app-container').style.display = 'flex';
                    loadAppData();
                    startPolling();
                }
            } catch (error) {
                console.error('Ошибка проверки авторизации:', error);
            }
        }

        // Закрытие модальных окон при клике вне их
        window.onclick = function(event) {
            const modals = document.querySelectorAll('.modal');
            modals.forEach(modal => {
                if (event.target === modal) {
                    modal.style.display = 'none';
                }
            });
        }

        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', function() {
            checkAuth();
            showTab('login');
        });
    </script>
</body>
</html>
''')

# Инициализация базы данных при запуске
init_db()

if __name__ == '__main__':
    print("🚀 Запуск мессенджера...")
    print("📧 Доступные тестовые пользователи:")
    print("   👤 alex / password123")
    print("   👤 maria / password123") 
    print("   👤 ivan / password123")
    print("   👤 sophia / password123")
    print("   👤 maxim / password123")
    print("🌐 Откройте: http://localhost:5000")
    app.run(host='0.0.0.0', port=port, debug=False)
