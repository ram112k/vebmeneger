
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
                message = 'Подпика оформлена'
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
            color: #000; /* Черный текст */
        }

        .auth-tab.active {
            background: #007bff;
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
            border-color: #007bff;
        }

        .btn {
            width: 100%;
            padding: 12px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            transition: background 0.3s;
        }

        .btn:hover {
            background: #0056b3;
        }

        .btn-secondary {
            background: #6c757d;
        }

        .btn-secondary:hover {
            background: #545b62;
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
            background: #007bff;
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
            background: #007bff;
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

        .channel-admin-badge {
            background: #ffc107;
            color: #000;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            margin-left: 5px;
        }

        .admin-panel {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            border: 1px solid #dee2e6;
        }

        .admin-list {
            list-style: none;
            margin-top: 10px;
        }

        .admin-item {
            padding: 10px;
            background: white;
            border-radius: 6px;
            margin-bottom: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid #dee2e6;
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
            background: #007bff;
            color: white;
        }

        .channel-actions {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }

        .channel-actions button {
            flex: 1;
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
                    <button class="btn" onclick="showCreateChannelModal()">Создать канал</button>
                </div>
                
                <h4>Пользователи</h4>
                <ul id="users-list" class="chat-list"></ul>
                
                <h4>Группы</h4>
                <ul id="groups-list" class="chat-list"></ul>
                
                <h4>Каналы</h4>
                <ul id="channels-list" class="chat-list"></ul>
            </div>
            
            <div class="main-content">
                <div id="chat-header" class="chat-header">
                    <h4 id="current-chat">Выберите чат</h4>
                    <div id="channel-actions" style="display: none;">
                        <button class="btn" onclick="showAdminPanel()">Управление админами</button>
                    </div>
                </div>
                
                <div id="chat-messages" class="chat-messages"></div>
                
                <div id="message-input" class="message-input" style="display: none;">
                    <div class="form-group">
                        <input type="text" id="message-text" class="form-control" placeholder="Введите сообщение..." onkeypress="handleKeyPress(event)">
                    </div>
                    <button class="btn" onclick="sendMessage()">Отправить</button>
                </div>

                <div id="admin-panel" class="admin-panel" style="display: none;">
                    <h5>Управление администраторами канала</h5>
                    <div class="form-group">
                        <select id="admin-user-select" class="form-control">
                            <option value="">Выберите пользователя</option>
                        </select>
                    </div>
                    <button class="btn" onclick="addChannelAdmin()">Добавить администратора</button>
                    <ul id="admin-list" class="admin-list"></ul>
                </div>
            </div>
        </div>
    </div>

    <!-- Модальные окна -->
    <div id="create-group-modal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal('create-group-modal')">&times;</span>
            <h3>Создать группу</h3>
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

    <div id="create-channel-modal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal('create-channel-modal')">&times;</span>
            <h3>Создать канал</h3>
            <div class="form-group">
                <label>Название канала:</label>
                <input type="text" id="channel-name" class="form-control">
            </div>
            <div class="form-group">
                <label>Описание:</label>
                <textarea id="channel-description" class="form-control" rows="3"></textarea>
            </div>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="channel-public" checked> Публичный канал
                </label>
            </div>
            <button class="btn" onclick="createChannel()">Создать канал</button>
        </div>
    </div>

    <script>
        let currentChat = null;
        let currentChatType = null;
        let selectedUsers = [];
        let currentChannelId = null;

        // Проверка авторизации при загрузке
        async function checkAuth() {
            try {
                const response = await fetch('/api/check_auth');
                const data = await response.json();
                
                if (data.success) {
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
            event.target.classList.add('active');
        }

        // Вход
        async function login() {
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;
            
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
                    showMessengerInterface(data.username);
                    loadChatLists();
                } else {
                    showError('login-error', data.error);
                }
            } catch (error) {
                showError('login-error', 'Ошибка соединения');
            }
        }

        // Регистрация
        async function register() {
            const username = document.getElementById('register-username').value;
            const phone = document.getElementById('register-phone').value;
            const password = document.getElementById('register-password').value;
            const confirm = document.getElementById('register-confirm').value;
            
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
                    showSuccess('register-success', data.message);
                    // Очищаем форму
                    document.getElementById('register-username').value = '';
                    document.getElementById('register-phone').value = '';
                    document.getElementById('register-password').value = '';
                    document.getElementById('register-confirm').value = '';
                } else {
                    showError('register-error', data.error);
                }
            } catch (error) {
                showError('register-error', 'Ошибка соединения');
            }
        }

        // Выход
        async function logout() {
            try {
                await fetch('/api/logout');
                showAuthInterface();
            } catch (error) {
                console.error('Ошибка выхода:', error);
            }
        }

        // Загрузка списков чатов
        async function loadChatLists() {
            await loadUsers();
            await loadGroups();
            await loadChannels();
        }

        // Загрузка пользователей
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
                        li.onclick = () => openChat('private', user.id, user.username);
                        usersList.appendChild(li);
                    });
                }
            } catch (error) {
                console.error('Ошибка загрузки пользователей:', error);
            }
        }

        // Загрузка групп
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
                        li.onclick = () => openChat('group', group.id, group.name);
                        groupsList.appendChild(li);
                    });
                }
            } catch (error) {
                console.error('Ошибка загрузки групп:', error);
            }
        }

        // Загрузка каналов
        async function loadChannels() {
            try {
                const response = await fetch('/api/channels');
                const data = await response.json();
                
                if (data.success) {
                    const channelsList = document.getElementById('channels-list');
                    channelsList.innerHTML = '';
                    
                    data.channels.forEach(channel => {
                        const li = document.createElement('li');
                        li.className = 'chat-item';
                        li.innerHTML = `
                            <strong>${channel.name}</strong><br>
                            <small>Подписчиков: ${channel.subscriber_count}</small>
                            ${channel.is_admin ? '<span class="channel-admin-badge">Админ</span>' : ''}
                        `;
                        li.onclick = () => openChat('channel', channel.id, channel.name);
                        channelsList.appendChild(li);
                    });
                }
            } catch (error) {
                console.error('Ошибка загрузки каналов:', error);
            }
        }

        // Открыть чат
        async function openChat(chatType, chatId, chatName) {
            currentChat = chatId;
            currentChatType = chatType;
            currentChannelId = chatType === 'channel' ? chatId : null;
            
            document.getElementById('current-chat').textContent = chatName;
            document.getElementById('message-input').style.display = 'block';
            document.getElementById('admin-panel').style.display = 'none';
            
            // Показываем кнопки управления только для администраторов каналов
            if (chatType === 'channel') {
                const channel = await getChannelInfo(chatId);
                if (channel.is_admin) {
                    document.getElementById('channel-actions').style.display = 'block';
                } else {
                    document.getElementById('channel-actions').style.display = 'none';
                }
            } else {
                document.getElementById('channel-actions').style.display = 'none';
            }
            
            await loadMessages();
            
            // Прокручиваем вниз к новым сообщениям
            setTimeout(() => {
                const messagesContainer = document.getElementById('chat-messages');
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }, 100);
        }

        // Получить информацию о канале
        async function getChannelInfo(channelId) {
            try {
                const response = await fetch('/api/channels');
                const data = await response.json();
                
                if (data.success) {
                    return data.channels.find(ch => ch.id === channelId);
                }
            } catch (error) {
                console.error('Ошибка получения информации о канале:', error);
            }
            return null;
        }

        // Загрузка сообщений
        async function loadMessages() {
            try {
                const response = await fetch(`/api/messages?type=${currentChatType}&id=${currentChat}`);
                const data = await response.json();
                
                const messagesContainer = document.getElementById('chat-messages');
                messagesContainer.innerHTML = '';
                
                if (data.success && data.messages.length > 0) {
                    data.messages.forEach(message => {
                        const messageDiv = document.createElement('div');
                        messageDiv.className = `message ${message.is_own ? 'own' : ''} fade-in`;
                        
                        const date = new Date(message.created_at);
                        const time = date.toLocaleTimeString('ru-RU', { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                        });
                        
                        messageDiv.innerHTML = `
                            <div class="message-header">
                                <span>${message.sender_name}</span>
                                <span>${time}</span>
                            </div>
                            <div class="message-content">
                                ${escapeHtml(message.message_text)}
                            </div>
                        `;
                        
                        messagesContainer.appendChild(messageDiv);
                    });
                } else {
                    messagesContainer.innerHTML = '<div class="loading">Сообщений пока нет</div>';
                }
            } catch (error) {
                console.error('Ошибка загрузки сообщений:', error);
            }
        }

        // Отправка сообщения
        async function sendMessage() {
            const messageText = document.getElementById('message-text').value.trim();
            
            if (!messageText) return;
            
            try {
                const messageData = {
                    type: currentChatType,
                    message_text: messageText
                };
                
                if (currentChatType === 'private') {
                    messageData.receiver_id = currentChat;
                } else if (currentChatType === 'group') {
                    messageData.group_id = currentChat;
                } else if (currentChatType === 'channel') {
                    messageData.channel_id = currentChat;
                }
                
                const response = await fetch('/api/send_message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(messageData)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('message-text').value = '';
                    await loadMessages();
                    
                    // Прокручиваем к новому сообщению
                    const messagesContainer = document.getElementById('chat-messages');
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                } else {
                    alert('Ошибка: ' + data.error);
                }
            } catch (error) {
                console.error('Ошибка отправки сообщения:', error);
                alert('Ошибка отправки сообщения');
            }
        }

        // Обработка нажатия Enter для отправки сообщения
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }

        // Показать модальное окно создания группы
        async function showCreateGroupModal() {
            await loadUsersForSelection();
            document.getElementById('create-group-modal').style.display = 'block';
        }

        // Показать модальное окно создания канала
        function showCreateChannelModal() {
            document.getElementById('create-channel-modal').style.display = 'block';
        }

        // Закрыть модальное окно
        function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }

        // Загрузка пользователей для выбора в группу
        async function loadUsersForSelection() {
            try {
                const response = await fetch('/api/users');
                const data = await response.json();
                
                if (data.success) {
                    const container = document.getElementById('group-users-select');
                    container.innerHTML = '';
                    selectedUsers = [];
                    
                    data.users.forEach(user => {
                        const div = document.createElement('div');
                        div.className = 'user-select-item';
                        div.innerHTML = user.username;
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
                    closeModal('create-group-modal');
                    alert('Группа создана успешно!');
                    await loadGroups();
                    
                    // Очищаем форму
                    document.getElementById('group-name').value = '';
                    document.getElementById('group-description').value = '';
                } else {
                    alert('Ошибка: ' + data.error);
                }
            } catch (error) {
                console.error('Ошибка создания группы:', error);
                alert('Ошибка создания группы');
            }
        }

        // Создание канала
        async function createChannel() {
            const name = document.getElementById('channel-name').value.trim();
            const description = document.getElementById('channel-description').value.trim();
            const isPublic = document.getElementById('channel-public').checked;
            
            if (!name) {
                alert('Введите название канала');
                return;
            }
            
            try {
                const response = await fetch('/api/create_channel', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
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
                    alert('Канал создан успешно!');
                    await loadChannels();
                    
                    // Очищаем форму
                    document.getElementById('channel-name').value = '';
                    document.getElementById('channel-description').value = '';
                } else {
                    alert('Ошибка: ' + data.error);
                }
            } catch (error) {
                console.error('Ошибка создания канала:', error);
                alert('Ошибка создания канала');
            }
        }

        // Показать панель управления администраторами
        async function showAdminPanel() {
            if (!currentChannelId) return;
            
            document.getElementById('admin-panel').style.display = 'block';
            document.getElementById('message-input').style.display = 'none';
            
            await loadChannelAdmins();
            await loadUsersForAdminSelection();
        }

        // Загрузка администраторов канала
        async function loadChannelAdmins() {
            try {
                const response = await fetch(`/api/channel_admins/${currentChannelId}`);
                const data = await response.json();
                
                const adminList = document.getElementById('admin-list');
                adminList.innerHTML = '';
                
                if (data.success) {
                    data.admins.forEach(admin => {
                        const li = document.createElement('li');
                        li.className = 'admin-item';
                        li.innerHTML = `
                            <span>${admin.username}</span>
                            <small>Добавлен: ${new Date(admin.added_at).toLocaleDateString()}</small>
                            <button class="btn btn-secondary" onclick="removeChannelAdmin(${admin.id})">Удалить</button>
                        `;
                        adminList.appendChild(li);
                    });
                }
            } catch (error) {
                console.error('Ошибка загрузки администраторов:', error);
            }
        }

        // Загрузка пользователей для выбора администраторов
        async function loadUsersForAdminSelection() {
            try {
                const response = await fetch('/api/users');
                const data = await response.json();
                
                const select = document.getElementById('admin-user-select');
                select.innerHTML = '<option value="">Выберите пользователя</option>';
                
                if (data.success) {
                    data.users.forEach(user => {
                        const option = document.createElement('option');
                        option.value = user.id;
                        option.textContent = user.username;
                        select.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('Ошибка загрузки пользователей:', error);
            }
        }

        // Добавление администратора канала
        async function addChannelAdmin() {
            const userId = document.getElementById('admin-user-select').value;
            
            if (!userId) {
                alert('Выберите пользователя');
                return;
            }
            
            try {
                const response = await fetch('/api/add_channel_admin', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        channel_id: currentChannelId,
                        user_id: userId
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Администратор добавлен');
                    await loadChannelAdmins();
                } else {
                    alert('Ошибка: ' + data.error);
                }
            } catch (error) {
                console.error('Ошибка добавления администратора:', error);
                alert('Ошибка добавления администратора');
            }
        }

        // Удаление администратора канала
        async function removeChannelAdmin(userId) {
            if (!confirm('Вы уверены, что хотите удалить этого администратора?')) {
                return;
            }
            
            try {
                const response = await fetch('/api/remove_channel_admin', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        channel_id: currentChannelId,
                        user_id: userId
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Администратор удален');
                    await loadChannelAdmins();
                } else {
                    alert('Ошибка: ' + data.error);
                }
            } catch (error) {
                console.error('Ошибка удаления администратора:', error);
                alert('Ошибка удаления администратора');
            }
        }

        // Вспомогательные функции
        function showError(elementId, message) {
            const element = document.getElementById(elementId);
            element.textContent = message;
            element.style.display = 'block';
            
            // Скрываем ошибку через 5 секунд
            setTimeout(() => {
                element.style.display = 'none';
            }, 5000);
        }

        function showSuccess(elementId, message) {
            const element = document.getElementById(elementId);
            element.textContent = message;
            element.style.display = 'block';
            
            // Скрываем успех через 5 секунд
            setTimeout(() => {
                element.style.display = 'none';
            }, 5000);
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', function() {
            checkAuth();
            
            // Закрытие модальных окон при клике вне их
            window.onclick = function(event) {
                const modals = document.getElementsByClassName('modal');
                for (let modal of modals) {
                    if (event.target === modal) {
                        modal.style.display = 'none';
                    }
                }
            }
            
            // Автообновление сообщений каждые 5 секунд
            setInterval(async () => {
                if (currentChat) {
                    await loadMessages();
                }
            }, 5000);
        });
    </script>
</body>
</html>
''')

if __name__ == '__main__':
    # Инициализация базы данных
    init_db()
    
    # Запуск приложения
    print("🚀 Messenger App запущен на http://localhost:5000")
    print("📱 Приложение адаптировано для телефонов и ПК")
    print("⚡ Для остановки нажмите Ctrl+C")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
