import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import hashlib

class MessengerWithAuth:
    def __init__(self, root):
        self.root = root
        self.root.title("📱 Мессенджер с Регистрацией")
        self.root.geometry("900x700")
        self.current_user = None
        
        # Создаем базу данных
        self.setup_database()
        
        # Показываем окно авторизации
        self.show_auth_window()
        
    def setup_database(self):
        """Создаем базу данных с таблицами"""
        self.conn = sqlite3.connect('messenger.db')
        self.cursor = self.conn.cursor()
        
        # Таблица пользователей
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица сообщений
        self.cursor.execute('''
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
        
        self.conn.commit()
    
    def hash_password(self, password):
        """Хеширование пароля"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def show_auth_window(self):
        """Окно авторизации/регистрации"""
        self.auth_window = tk.Toplevel(self.root)
        self.auth_window.title("Вход / Регистрация")
        self.auth_window.geometry("400x500")
        self.auth_window.resizable(False, False)
        
        # Центрируем окно
        self.auth_window.transient(self.root)
        self.auth_window.grab_set()
        
        # Стили
        title_font = ("Arial", 16, "bold")
        label_font = ("Arial", 10)
        
        # Заголовок
        tk.Label(self.auth_window, text="🔐 Вход в Мессенджер", 
                font=title_font, pady=20).pack()
        
        # Фрейм для формы
        form_frame = ttk.Frame(self.auth_window, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Поле логина
        tk.Label(form_frame, text="Логин:", font=label_font).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.login_entry = ttk.Entry(form_frame, width=30)
        self.login_entry.grid(row=0, column=1, pady=5, padx=5)
        
        # Поле телефона (для регистрации)
        tk.Label(form_frame, text="Телефон:", font=label_font).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.phone_entry = ttk.Entry(form_frame, width=30)
        self.phone_entry.grid(row=1, column=1, pady=5, padx=5)
        
        # Поле пароля
        tk.Label(form_frame, text="Пароль:", font=label_font).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.password_entry = ttk.Entry(form_frame, width=30, show="*")
        self.password_entry.grid(row=2, column=1, pady=5, padx=5)
        
        # Поле подтверждения пароля (для регистрации)
        tk.Label(form_frame, text="Подтверждение:", font=label_font).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.confirm_entry = ttk.Entry(form_frame, width=30, show="*")
        self.confirm_entry.grid(row=3, column=1, pady=5, padx=5)
        
        # Кнопки
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Войти", command=self.login).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Зарегистрироваться", command=self.register).pack(side=tk.LEFT, padx=10)
        
        # Статус
        self.auth_status = tk.StringVar()
        self.auth_status.set("Введите данные для входа или регистрации")
        tk.Label(self.auth_window, textvariable=self.auth_status, 
                fg="blue", font=("Arial", 9)).pack(pady=10)
        
        # Связываем Enter с входом
        self.password_entry.bind('<Return>', lambda e: self.login())
    
    def register(self):
        """Регистрация нового пользователя"""
        username = self.login_entry.get().strip()
        phone = self.phone_entry.get().strip()
        password = self.password_entry.get()
        confirm = self.confirm_entry.get()
        
        if not all([username, phone, password, confirm]):
            self.auth_status.set("Заполните все поля!")
            return
        
        if password != confirm:
            self.auth_status.set("Пароли не совпадают!")
            return
        
        if len(password) < 4:
            self.auth_status.set("Пароль слишком короткий (мин. 4 символа)!")
            return
        
        try:
            password_hash = self.hash_password(password)
            self.cursor.execute(
                "INSERT INTO users (username, phone, password_hash) VALUES (?, ?, ?)",
                (username, phone, password_hash)
            )
            self.conn.commit()
            
            self.auth_status.set("Регистрация успешна! Теперь войдите.")
            messagebox.showinfo("Успех", "Регистрация завершена! Теперь вы можете войти.")
            
            # Очищаем поля
            self.phone_entry.delete(0, tk.END)
            self.confirm_entry.delete(0, tk.END)
            
        except sqlite3.IntegrityError:
            self.auth_status.set("Логин или телефон уже заняты!")
        except Exception as e:
            self.auth_status.set(f"Ошибка: {str(e)}")
    
    def login(self):
        """Вход пользователя"""
        username = self.login_entry.get().strip()
        password = self.password_entry.get()
        
        if not username or not password:
            self.auth_status.set("Введите логин и пароль!")
            return
        
        try:
            password_hash = self.hash_password(password)
            self.cursor.execute(
                "SELECT id, username, phone FROM users WHERE username = ? AND password_hash = ?",
                (username, password_hash)
            )
            user = self.cursor.fetchone()
            
            if user:
                self.current_user = {
                    'id': user[0],
                    'username': user[1],
                    'phone': user[2]
                }
                self.auth_window.destroy()
                self.create_main_window()
                self.load_messages()
            else:
                self.auth_status.set("Неверный логин или пароль!")
                
        except Exception as e:
            self.auth_status.set(f"Ошибка входа: {str(e)}")
    
    def create_main_window(self):
        """Создаем главное окно мессенджера"""
        # Очищаем root window
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.root.title(f"📱 Мессенджер - {self.current_user['username']}")
        
        # Главный фрейм
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок с информацией о пользователе
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        user_info = f"👤 {self.current_user['username']} ({self.current_user['phone']})"
        tk.Label(header_frame, text=user_info, font=("Arial", 14, "bold")).pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="🚪 Выйти", command=self.logout).pack(side=tk.RIGHT)
        
        # Разделение на две части
        paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Левая часть - список пользователей
        left_frame = ttk.Frame(paned_window, padding="5")
        paned_window.add(left_frame, weight=1)
        
        tk.Label(left_frame, text="👥 Пользователи", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Список пользователей
        users_frame = ttk.Frame(left_frame)
        users_frame.pack(fill=tk.BOTH, expand=True)
        
        self.users_tree = ttk.Treeview(users_frame, columns=("username", "phone"), show="headings", height=15)
        self.users_tree.heading("username", text="Имя")
        self.users_tree.heading("phone", text="Телефон")
        self.users_tree.column("username", width=120)
        self.users_tree.column("phone", width=100)
        
        users_scrollbar = ttk.Scrollbar(users_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=users_scrollbar.set)
        
        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        users_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Правая часть - сообщения
        right_frame = ttk.Frame(paned_window, padding="5")
        paned_window.add(right_frame, weight=2)
        
        tk.Label(right_frame, text="💬 Сообщения", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Сообщения
        messages_frame = ttk.Frame(right_frame)
        messages_frame.pack(fill=tk.BOTH, expand=True)
        
        self.messages_text = scrolledtext.ScrolledText(messages_frame, wrap=tk.WORD, height=20)
        self.messages_text.pack(fill=tk.BOTH, expand=True)
        self.messages_text.config(state=tk.DISABLED)
        
        # Форма отправки сообщения
        send_frame = ttk.Frame(right_frame)
        send_frame.pack(fill=tk.X, pady=(10, 0))
        
        tk.Label(send_frame, text="Новое сообщение:").pack(anchor=tk.W)
        
        self.message_entry = tk.Text(send_frame, height=3, width=50)
        self.message_entry.pack(fill=tk.X, pady=5)
        
        ttk.Button(send_frame, text="📤 Отправить", command=self.send_message).pack()
        
        # Загружаем список пользователей
        self.load_users()
        
        # Привязываем выбор пользователя
        self.users_tree.bind('<<TreeviewSelect>>', self.on_user_select)
    
    def load_users(self):
        """Загружаем список пользователей"""
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        
        self.cursor.execute("SELECT id, username, phone FROM users WHERE id != ?", 
                          (self.current_user['id'],))
        users = self.cursor.fetchall()
        
        for user in users:
            self.users_tree.insert("", "end", values=(user[1], user[2]), tags=(user[0],))
    
    def on_user_select(self, event):
        """Обработчик выбора пользователя"""
        selection = self.users_tree.selection()
        if selection:
            item = self.users_tree.item(selection[0])
            self.selected_user_id = self.users_tree.item(selection[0], "tags")[0]
            self.load_messages()
    
    def load_messages(self):
        """Загружаем сообщения с выбранным пользователем"""
        if not hasattr(self, 'selected_user_id'):
            return
        
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.delete(1.0, tk.END)
        
        # Загружаем историю сообщений
        self.cursor.execute('''
            SELECT u.username, m.message_text, m.created_at 
            FROM messages m 
            JOIN users u ON m.sender_id = u.id 
            WHERE (m.sender_id = ? AND m.receiver_id = ?) 
               OR (m.sender_id = ? AND m.receiver_id = ?)
            ORDER BY m.created_at
        ''', (self.current_user['id'], self.selected_user_id, 
              self.selected_user_id, self.current_user['id']))
        
        messages = self.cursor.fetchall()
        
        for username, message, time in messages:
            time_str = datetime.strptime(time, "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
            prefix = "▶️ Вы: " if username == self.current_user['username'] else f"◀️ {username}: "
            self.messages_text.insert(tk.END, f"[{time_str}] {prefix}{message}\n\n")
        
        self.messages_text.config(state=tk.DISABLED)
        self.messages_text.see(tk.END)
    
    def send_message(self):
        """Отправляем сообщение"""
        if not hasattr(self, 'selected_user_id'):
            messagebox.showwarning("Внимание", "Выберите пользователя для отправки сообщения")
            return
        
        message_text = self.message_entry.get("1.0", tk.END).strip()
        if not message_text:
            return
        
        try:
            self.cursor.execute(
                "INSERT INTO messages (sender_id, receiver_id, message_text) VALUES (?, ?, ?)",
                (self.current_user['id'], self.selected_user_id, message_text)
            )
            self.conn.commit()
            
            self.message_entry.delete("1.0", tk.END)
            self.load_messages()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось отправить сообщение: {str(e)}")
    
    def logout(self):
        """Выход из системы"""
        self.current_user = None
        for widget in self.root.winfo_children():
            widget.destroy()
        self.show_auth_window()
    
    def run(self):
        """Запускаем приложение"""
        self.root.mainloop()

# Запуск приложения
if __name__ == "__main__":
    root = tk.Tk()
    app = MessengerWithAuth(root)
    app.run()
