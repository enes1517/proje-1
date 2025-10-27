# Full project code for Dynamic Exam Schedule Creation System (Updated with new Excel data compatibility)
# This is a complete Python implementation using PyQt5 for GUI, sqlite3 for database, pandas for Excel parsing,
# fpdf for PDF generation, and PuLP for optimized scheduling.
# Updates:
# - Compatible with ogrenci_listesi.xlsx and Ders Listesi.xlsx structures.
# - Handles year extraction from Sınıf column and course type detection.
# - Enhanced error handling for duplicate students and missing courses.
# - To run: Install dependencies: pip install pyqt5 pandas fpdf openpyxl pulp
# Run the main.py file in PyCharm or via python main.py


import sys
import sqlite3
import pandas as pd
import unicodedata
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QComboBox, QDateEdit,
    QCheckBox, QGridLayout, QFileDialog, QInputDialog, QTabWidget, QSpacerItem, QSizePolicy,
    QScrollArea, QGroupBox , QHeaderView
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QColor
from fpdf import FPDF
import datetime
import random
import pulp



def turkish_to_ascii(text):
    """Türkçe karakterleri ASCII'ye çevir"""
    replacements = {
        'ş': 's', 'Ş': 'S',
        'ğ': 'g', 'Ğ': 'G',
        'ü': 'u', 'Ü': 'U',
        'ö': 'o', 'Ö': 'O',
        'ç': 'c', 'Ç': 'C',
        'ı': 'i', 'İ': 'I'
    }
    for tr, en in replacements.items():
        text = text.replace(tr, en)
    return text

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('exam_scheduler.db')
        self.create_tables()
        self.init_default_data()

    def create_tables(self):
        cursor = self.conn.cursor()
        # Users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                email TEXT UNIQUE,
                password TEXT,
                role TEXT,
                department_id INTEGER
            )
        ''')
        # Departments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE
            )
        ''')
        # Classrooms
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS classrooms (
                id INTEGER PRIMARY KEY,
                department_id INTEGER,
                code TEXT,
                name TEXT,
                capacity INTEGER,
                rows INTEGER,
                columns INTEGER,
                seat_group INTEGER
            )
        ''')
        # Courses
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY,
                department_id INTEGER,
                code TEXT,
                name TEXT,
                instructor TEXT,
                year INTEGER,
                type TEXT
            )
        ''')
        # Students
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                department_id INTEGER,
                number TEXT UNIQUE,
                name TEXT,
                year INTEGER
            )
        ''')
        # StudentCourses
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_courses (
                student_id INTEGER,
                course_id INTEGER,
                PRIMARY KEY (student_id, course_id)
            )
        ''')
        # Exams
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY,
                course_id INTEGER,
                date DATE,
                time TIME,
                duration INTEGER,
                type TEXT,
                classroom_id INTEGER
            )
        ''')
        # Seating
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seating (
                id INTEGER PRIMARY KEY,
                exam_id INTEGER,
                student_id INTEGER,
                classroom_id INTEGER,
                row INTEGER,
                col INTEGER
            )
        ''')
        self.conn.commit()

    def init_default_data(self):
        cursor = self.conn.cursor()
        departments = ['Bilgisayar Müh.', 'Yazılım Müh.', 'Elektrik Müh.', 'Elektronik Müh.', 'İnşaat Müh.']
        for dep in departments:
            cursor.execute('INSERT OR IGNORE INTO departments (name) VALUES (?)', (dep,))
        cursor.execute('INSERT OR IGNORE INTO users (email, password, role) VALUES (?, ?, ?)', ('admin@example.com', 'admin', 'Admin'))
        self.conn.commit()

    def has_classrooms(self, dep_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM classrooms WHERE department_id = ?', (dep_id,))
        return cursor.fetchone()[0] > 0

    def has_courses(self, dep_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM courses WHERE department_id = ?', (dep_id,))
        return cursor.fetchone()[0] > 0

    def has_students(self, dep_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM students WHERE department_id = ?', (dep_id,))
        return cursor.fetchone()[0] > 0

    def close(self):
        self.conn.close()

class LoginWindow(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        layout = QVBoxLayout()
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        title = QLabel('Dinamik Sınav Takvimi Sistemi')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18pt; font-weight: bold; color: #333;")
        layout.addWidget(title)
        self.email = QLineEdit(self)
        self.email.setPlaceholderText('E-posta')
        self.email.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        layout.addWidget(self.email)
        self.password = QLineEdit(self)
        self.password.setPlaceholderText('Şifre')
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        layout.addWidget(self.password)
        login_btn = QPushButton('Giriş Yap')
        login_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; padding: 10px; border: none; border-radius: 4px;")
        login_btn.clicked.connect(self.login)
        layout.addWidget(login_btn)
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.setLayout(layout)

    def login(self):
        email = self.email.text().strip()
        password = self.password.text().strip()

        if not email or not password:
            QMessageBox.warning(self, 'Hata', 'E-posta ve şifre gereklidir.')
            return

        db = Database()
        try:
            cursor = db.conn.cursor()
            cursor.execute('SELECT id, email, role, department_id FROM users WHERE email=? AND password=?',
                           (email, password))
            user = cursor.fetchone()

            if user:
                self.parent.user = {
                    'id': user[0],
                    'email': user[1],  # EMAIL EKLENDI
                    'role': user[2],
                    'department_id': user[3]
                }
                self.parent.show_main_window()
            else:
                QMessageBox.warning(self, 'Hata', 'Geçersiz kimlik bilgileri')
        except Exception as e:
            QMessageBox.critical(self, 'Hata', f'Giriş işlemi başarısız:\n{str(e)}')
        finally:
            db.close()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Dinamik Sınav Takvimi Oluşturma Sistemi')
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f0f0; }
            QLabel { color: #333; }
            QLineEdit { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
            QPushButton { background-color: #2196F3; color: white; padding: 8px; border: none; border-radius: 4px; }
            QPushButton:hover { background-color: #1976D2; }
            QTableWidget { background-color: white; border: 1px solid #ddd; }
            QTabWidget::pane { border: 1px solid #ddd; background: white; }
            QTabWidget::tab-bar { alignment: left; }
            QComboBox { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
            QCheckBox { color: #333; }
        """)
        self.user = None
        self.db = Database()
        self.login_window = LoginWindow(self)
        self.setCentralWidget(self.login_window)
        self.resize(1000, 700)

    def show_main_window(self):
        central_widget = QWidget()
        layout = QVBoxLayout()

        # TOOLBAR
        toolbar_layout = QHBoxLayout()

        # Kullanıcı bilgisi
        user_info = QLabel(f"👤 {self.user['email']} ({self.user['role']})")
        user_info.setStyleSheet("font-weight: bold; padding: 5px;")
        toolbar_layout.addWidget(user_info)

        # Boşluk
        toolbar_layout.addStretch()

        # Çıkış butonu
        logout_btn = QPushButton('Çıkış')
        logout_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; padding: 8px 15px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #d32f2f; }"
        )
        logout_btn.clicked.connect(self.logout)
        toolbar_layout.addWidget(logout_btn)

        # Toolbar grubu
        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)
        toolbar_widget.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #ddd; padding: 5px;")
        layout.addWidget(toolbar_widget)

        # TAB WIDGET
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("QTabWidget::tab { background: #e0e0e0; padding: 10px; }")

        # Admin sekmesi - sadece Admin için
        if self.user['role'] == 'Admin':
            self.tab_widget.addTab(self.admin_tab(), 'Admin İşlemleri')

        # Tüm diğer sekmeler - Admin ve Bölüm Koordinatörü için direkt açılsın
        self.tab_widget.addTab(self.classroom_tab(), 'Derslik Girişi')
        self.tab_widget.addTab(self.course_upload_tab(), 'Ders Listesi Yükle')
        self.tab_widget.addTab(self.student_upload_tab(), 'Öğrenci Listesi Yükle')
        self.tab_widget.addTab(self.student_list_tab(), 'Öğrenci Listesi')
        self.tab_widget.addTab(self.course_list_tab(), 'Ders Listesi')
        self.tab_widget.addTab(self.exam_schedule_tab(), 'Sınav Programı Oluştur')
        self.tab_widget.addTab(self.seating_plan_tab(), 'Oturma Planı')

        layout.addWidget(self.tab_widget)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def logout(self):
        """Çıkış işlemi"""
        reply = QMessageBox.question(
            self, 'Çıkış Onayı',
            f'{self.user["email"]} hesabından çıkış yapılacak.\n\nEmin misiniz?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.tab_widget = None
            self.user = None

            # Login ekranına geri dön
            login_window = LoginWindow(self)
            self.setCentralWidget(login_window)
            self.setWindowTitle('Dinamik Sınav Takvimi Oluşturma Sistemi')

    def closeEvent(self, event):
        """Pencere kapanırken"""
        try:
            self.db.close()
        except:
            pass
        event.accept()


    def admin_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # Başlık
        title = QLabel('Admin Yönetim Paneli')
        title.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px; background-color: #FFEBEE;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Kullanıcı Yönetimi Grubu
        user_group = QGroupBox('Kullanıcı Yönetimi')
        user_layout = QVBoxLayout()

        # Butonlar
        button_layout = QHBoxLayout()

        add_user_btn = QPushButton('➕ Yeni Kullanıcı Ekle')
        add_user_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; padding: 10px; "
            "font-size: 11pt; font-weight: bold; border-radius: 5px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        add_user_btn.clicked.connect(self.add_user)
        button_layout.addWidget(add_user_btn)

        view_users_btn = QPushButton('👥 Kullanıcıları Görüntüle')
        view_users_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; padding: 10px; "
            "font-size: 11pt; font-weight: bold; border-radius: 5px; }"
            "QPushButton:hover { background-color: #0b7dda; }"
        )
        view_users_btn.clicked.connect(self.view_users)
        button_layout.addWidget(view_users_btn)

        button_layout.addStretch()
        user_layout.addLayout(button_layout)

        # Kullanıcı Listesi Tablosu
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(5)
        self.users_table.setHorizontalHeaderLabels(['ID', 'E-posta', 'Rol', 'Bölüm', 'İşlemler'])
        self.users_table.horizontalHeader().setStretchLastSection(True)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.users_table.setMinimumHeight(300)
        self.load_users_table()

        user_layout.addWidget(self.users_table)
        user_group.setLayout(user_layout)
        layout.addWidget(user_group)

        # İstatistikler Grubu
        stats_group = QGroupBox('Sistem İstatistikleri')
        stats_layout = QGridLayout()

        # İstatistikleri yükle
        cursor = self.db.conn.cursor()

        # Toplam kullanıcı
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]

        # Toplam departman
        cursor.execute('SELECT COUNT(*) FROM departments')
        total_depts = cursor.fetchone()[0]

        # Toplam ders
        cursor.execute('SELECT COUNT(*) FROM courses')
        total_courses = cursor.fetchone()[0]

        # Toplam öğrenci
        cursor.execute('SELECT COUNT(*) FROM students')
        total_students = cursor.fetchone()[0]

        # İstatistik kartları
        stats_data = [
            ('Toplam Kullanıcı', str(total_users), '#4CAF50'),
            ('Toplam Departman', str(total_depts), '#2196F3'),
            ('Toplam Ders', str(total_courses), '#FF9800'),
            ('Toplam Öğrenci', str(total_students), '#9C27B0')
        ]

        for idx, (label, value, color) in enumerate(stats_data):
            stat_card = QLabel(f'<b>{label}</b><br><font size="5">{value}</font>')
            stat_card.setStyleSheet(
                f"background-color: {color}; color: white; padding: 15px; "
                f"border-radius: 8px; text-align: center; font-weight: bold;"
            )
            stat_card.setAlignment(Qt.AlignCenter)
            stat_card.setMinimumHeight(80)
            stats_layout.addWidget(stat_card, idx // 2, idx % 2)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Alt Boşluk
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def load_users_table(self):
        """Kullanıcı tablosunu yükle"""
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT u.id, u.email, u.role, d.name 
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            ORDER BY u.id
        ''')

        users = cursor.fetchall()
        self.users_table.setRowCount(len(users))

        for i, (user_id, email, role, dept_name) in enumerate(users):
            # ID
            self.users_table.setItem(i, 0, QTableWidgetItem(str(user_id)))

            # E-posta
            self.users_table.setItem(i, 1, QTableWidgetItem(email))

            # Rol (renkli)
            role_item = QTableWidgetItem(role)
            if role == 'Admin':
                role_item.setBackground(QColor('#FFCDD2'))
            elif role == 'Bölüm Koordinatörü':
                role_item.setBackground(QColor('#C8E6C9'))
            self.users_table.setItem(i, 2, role_item)

            # Bölüm
            self.users_table.setItem(i, 3, QTableWidgetItem(dept_name or 'N/A'))

            # İşlemler Butonu
            delete_btn = QPushButton('🗑️ Sil')
            delete_btn.setStyleSheet("background-color: #f44336; color: white; padding: 5px;")
            delete_btn.clicked.connect(lambda checked, uid=user_id: self.delete_user(uid))
            self.users_table.setCellWidget(i, 4, delete_btn)

    def view_users(self):
        """Kullanıcı tablosunu yenile"""
        self.load_users_table()
        QMessageBox.information(self, 'Başarılı', 'Kullanıcı listesi güncellendi.')

    def add_user(self):
        """Yeni kullanıcı ekle - Dialog Tabanlı"""
        # E-posta girişi
        email, ok = QInputDialog.getText(
            self, 'Yeni Kullanıcı',
            'E-posta adresini girin:',
            text='example@university.edu'
        )
        if not ok or not email:
            return

        # E-posta validasyonu
        if '@' not in email:
            QMessageBox.warning(self, 'Hata', 'Geçerli bir e-posta adresi girin.')
            return

        # Şifre girişi
        password, ok = QInputDialog.getText(
            self, 'Yeni Kullanıcı',
            'Şifre belirleyin:',
            text='password123'
        )
        if not ok or not password:
            return

        if len(password) < 6:
            QMessageBox.warning(self, 'Hata', 'Şifre en az 6 karakter olmalıdır.')
            return

        # Rol seçimi
        roles = ['Bölüm Koordinatörü', 'Admin']
        role, ok = QInputDialog.getItem(
            self, 'Rol Seçimi',
            'Kullanıcı rolünü seçin:',
            roles, 0, False
        )
        if not ok:
            return

        # Bölüm seçimi (Admin değilse)
        cursor = self.db.conn.cursor()

        if role == 'Bölüm Koordinatörü':
            cursor.execute('SELECT id, name FROM departments ORDER BY name')
            deps = cursor.fetchall()

            if not deps:
                QMessageBox.warning(self, 'Hata', 'Sistemde departman bulunmamaktadır.')
                return

            dep_names = [d[1] for d in deps]
            dep_name, ok = QInputDialog.getItem(
                self, 'Bölüm Seçimi',
                'Kullanıcının bölümünü seçin:',
                dep_names, 0, False
            )
            if not ok:
                return

            dep_id = next(d[0] for d in deps if d[1] == dep_name)
        else:
            dep_id = None  # Admin için departman gerekli değil

        # Veritabanına ekle
        try:
            cursor.execute(
                'INSERT INTO users (email, password, role, department_id) VALUES (?, ?, ?, ?)',
                (email, password, role, dep_id)
            )
            self.db.conn.commit()

            QMessageBox.information(
                self, 'Başarılı',
                f'Kullanıcı başarıyla eklendi.\n\n'
                f'E-posta: {email}\n'
                f'Rol: {role}'
            )

            # Tabloyu yenile
            self.load_users_table()

        except Exception as e:
            if 'UNIQUE constraint failed' in str(e):
                QMessageBox.warning(self, 'Hata', 'Bu e-posta adresi zaten kayıtlıdır.')
            else:
                QMessageBox.warning(self, 'Hata', f'Kullanıcı eklenemedi:\n{str(e)}')

    def delete_user(self, user_id):
        """Kullanıcı sil"""
        # Kendi kendini silemesin
        if user_id == self.user['id']:
            QMessageBox.warning(self, 'Hata', 'Kendi hesabınızı silemezsiniz.')
            return

        # Onay al
        reply = QMessageBox.question(
            self, 'Silme Onayı',
            f'ID={user_id} olan kullanıcıyı silmek istediğinizden emin misiniz?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        try:
            cursor = self.db.conn.cursor()
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            self.db.conn.commit()

            QMessageBox.information(self, 'Başarılı', 'Kullanıcı silindi.')
            self.load_users_table()

        except Exception as e:
            QMessageBox.critical(self, 'Hata', f'Kullanıcı silinemedi:\n{str(e)}')

    def classroom_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # Yetki kontrolü - Admin ve Bölüm Koordinatörü
        if self.user['role'] not in ['Admin', 'Bölüm Koordinatörü']:
            label = QLabel('Bu sayfayı görüntüleme yetkiniz yok.')
            label.setStyleSheet("color: red; font-size: 12pt; padding: 20px;")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            widget.setLayout(layout)
            return widget

        # Başlık
        title = QLabel('Derslik Yönetimi')
        title.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px; background-color: #E3F2FD;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Form grubu
        form_group = QGroupBox('Derslik Ekle/Düzenle')
        form_layout = QGridLayout()

        form_layout.addWidget(QLabel('Derslik Kodu:'), 0, 0)
        self.class_code = QLineEdit()
        self.class_code.setPlaceholderText('Örn: A101')
        form_layout.addWidget(self.class_code, 0, 1)

        form_layout.addWidget(QLabel('Derslik Adı:'), 1, 0)
        self.class_name = QLineEdit()
        self.class_name.setPlaceholderText('Örn: Amfi A')
        form_layout.addWidget(self.class_name, 1, 1)

        form_layout.addWidget(QLabel('Kapasite:'), 2, 0)
        self.class_capacity = QLineEdit()
        self.class_capacity.setPlaceholderText('Sınav kapasitesi')
        form_layout.addWidget(self.class_capacity, 2, 1)

        form_layout.addWidget(QLabel('Satır Sayısı:'), 3, 0)
        self.class_rows = QLineEdit()
        self.class_rows.setPlaceholderText('Boyuna sıra sayısı')
        form_layout.addWidget(self.class_rows, 3, 1)

        form_layout.addWidget(QLabel('Sütun Sayısı:'), 4, 0)
        self.class_columns = QLineEdit()
        self.class_columns.setPlaceholderText('Enine sıra sayısı')
        form_layout.addWidget(self.class_columns, 4, 1)

        form_layout.addWidget(QLabel('Sıra Yapısı:'), 5, 0)
        self.class_seat_group = QComboBox()
        self.class_seat_group.addItems(['2', '3', '4'])
        form_layout.addWidget(self.class_seat_group, 5, 1)

        # Departman seçimi (Admin için)
        if self.user['role'] == 'Admin':
            form_layout.addWidget(QLabel('Departman ID:'), 6, 0)
            self.class_department = QLineEdit()
            self.class_department.setPlaceholderText('Departman ID')
            self.class_department.setText('1')
            form_layout.addWidget(self.class_department, 6, 1)
            button_row = 7
        else:
            button_row = 6

        # Butonlar
        button_layout = QHBoxLayout()

        add_btn = QPushButton('➕ Ekle')
        add_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; font-weight: bold;")
        add_btn.clicked.connect(self.add_classroom)
        button_layout.addWidget(add_btn)

        edit_btn = QPushButton('✏️ Düzenle')
        edit_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px; font-weight: bold;")
        edit_btn.clicked.connect(self.edit_classroom)
        button_layout.addWidget(edit_btn)

        delete_btn = QPushButton('🗑️ Sil')
        delete_btn.setStyleSheet("background-color: #f44336; color: white; padding: 8px; font-weight: bold;")
        delete_btn.clicked.connect(self.delete_classroom)
        button_layout.addWidget(delete_btn)

        clear_btn = QPushButton('🔄 Temizle')
        clear_btn.setStyleSheet("background-color: #9E9E9E; color: white; padding: 8px; font-weight: bold;")
        clear_btn.clicked.connect(self.clear_class_form)
        button_layout.addWidget(clear_btn)

        form_layout.addLayout(button_layout, button_row, 0, 1, 2)
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Arama bölümü
        search_group = QGroupBox('Derslik Ara')
        search_layout = QHBoxLayout()

        search_layout.addWidget(QLabel('Derslik ID:'))
        self.search_class_id = QLineEdit()
        self.search_class_id.setPlaceholderText('ID ile arama yapın')
        search_layout.addWidget(self.search_class_id)

        search_btn = QPushButton('🔍 Ara ve Görselleştir')
        search_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 8px; font-weight: bold;")
        search_btn.clicked.connect(self.search_classroom)
        search_layout.addWidget(search_btn)

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # Derslik tablosu
        table_group = QGroupBox('Kayıtlı Derslikler')
        table_layout = QVBoxLayout()

        self.classroom_table = QTableWidget()
        self.classroom_table.setColumnCount(8)
        self.classroom_table.setHorizontalHeaderLabels(
            ['ID', 'Kod', 'Ad', 'Kapasite', 'Satır', 'Sütun', 'Yapı', 'Departman'])
        self.classroom_table.horizontalHeader().setStretchLastSection(True)
        self.classroom_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.classroom_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.classroom_table.cellClicked.connect(self.load_classroom_for_edit)

        self.load_classrooms()
        table_layout.addWidget(self.classroom_table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Görselleştirme bölümü
        self.classroom_view_toggle = QPushButton('▼ Oturma Düzeni Görselleştirmesi')
        self.classroom_view_toggle.setStyleSheet(
            "QPushButton { text-align: left; padding: 8px; background-color: #E3F2FD; border: 1px solid #2196F3; }"
            "QPushButton:hover { background-color: #BBDEFB; }"
        )
        self.classroom_view_toggle.clicked.connect(self.toggle_classroom_view)
        self.classroom_view_toggle.setVisible(False)
        layout.addWidget(self.classroom_view_toggle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)

        view_widget = QWidget()
        self.classroom_view = QGridLayout()
        self.classroom_view.setSpacing(5)
        view_widget.setLayout(self.classroom_view)

        scroll.setWidget(view_widget)
        scroll.setVisible(False)
        scroll.setStyleSheet("background-color: white; border: 1px solid #ddd;")
        self.classroom_view_scroll = scroll
        layout.addWidget(scroll)

        widget.setLayout(layout)
        return widget

    def toggle_classroom_view(self):
        is_visible = self.classroom_view_scroll.isVisible()
        self.classroom_view_scroll.setVisible(not is_visible)

        if is_visible:
            self.classroom_view_toggle.setText('▼ Oturma Düzeni Görselleştirmesi')
        else:
            self.classroom_view_toggle.setText('▲ Oturma Düzeni Görselleştirmesi')

    def load_classrooms(self):
        try:
            cursor = self.db.conn.cursor()

            # Admin: tüm derslikleri, Bölüm Koor: sadece kendi departmanı
            if self.user['role'] == 'Admin':
                cursor.execute(
                    'SELECT id, code, name, capacity, rows, columns, seat_group, department_id FROM classrooms ORDER BY code'
                )
            else:
                dep_id = self.user['department_id']
                cursor.execute(
                    'SELECT id, code, name, capacity, rows, columns, seat_group, department_id FROM classrooms WHERE department_id=? ORDER BY code',
                    (dep_id,)
                )

            classrooms = cursor.fetchall()

            self.classroom_table.setRowCount(len(classrooms))

            for i, row in enumerate(classrooms):
                for j, val in enumerate(row):
                    item = QTableWidgetItem(str(val))
                    if j == 0:
                        item.setForeground(QColor('#2196F3'))
                    self.classroom_table.setItem(i, j, item)

        except Exception as e:
            QMessageBox.critical(self, 'Hata', f'Derslikler yüklenirken hata: {str(e)}')

    def add_classroom(self):
        self.modify_classroom('add')

    def edit_classroom(self):
        self.modify_classroom('edit')

    def modify_classroom(self, mode):
        code = self.class_code.text().strip()
        name = self.class_name.text().strip()
        capacity = self.class_capacity.text().strip()
        rows = self.class_rows.text().strip()
        columns = self.class_columns.text().strip()
        seat_group = self.class_seat_group.currentText()

        if not all([code, name, capacity, rows, columns]):
            QMessageBox.warning(self, 'Eksik Bilgi', 'Lütfen tüm alanları doldurun.')
            return

        try:
            capacity = int(capacity)
            rows = int(rows)
            columns = int(columns)
            seat_group = int(seat_group)

            if capacity <= 0 or rows <= 0 or columns <= 0:
                raise ValueError("Pozitif değer girilmeli")

        except ValueError:
            QMessageBox.warning(self, 'Hata', 'Kapasite, satır ve sütun pozitif tam sayı olmalıdır.')
            return

        try:
            cursor = self.db.conn.cursor()

            # Departman ID'sini belirle
            if self.user['role'] == 'Admin':
                try:
                    dep_id = int(self.class_department.text().strip())
                except ValueError:
                    QMessageBox.warning(self, 'Hata', 'Geçerli bir Departman ID girin.')
                    return
            else:
                dep_id = self.user['department_id']

            if mode == 'add':
                cursor.execute(
                    'INSERT INTO classrooms (department_id, code, name, capacity, rows, columns, seat_group) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (dep_id, code, name, capacity, rows, columns, seat_group)
                )
                self.db.conn.commit()
                QMessageBox.information(self, 'Başarılı', f'Derslik "{code}" başarıyla eklendi.')
                self.clear_class_form()

            elif mode == 'edit':
                class_id = self.search_class_id.text().strip()
                if not class_id:
                    QMessageBox.warning(self, 'Hata',
                                        'Düzenlemek için önce tablodan bir derslik seçin veya ID ile arama yapın.')
                    return

                cursor.execute(
                    'UPDATE classrooms SET code=?, name=?, capacity=?, rows=?, columns=?, seat_group=? WHERE id=? AND department_id=?',
                    (code, name, capacity, rows, columns, seat_group, class_id, dep_id)
                )
                self.db.conn.commit()

                if cursor.rowcount > 0:
                    QMessageBox.information(self, 'Başarılı', f'Derslik "{code}" güncellendi.')
                    self.clear_class_form()
                else:
                    QMessageBox.warning(self, 'Hata', 'Güncellenecek derslik bulunamadı.')

            # Tabloyu güncelle
            self.load_classrooms()



        except Exception as e:
            self.db.conn.rollback()  # Hata durumunda rollback
            QMessageBox.critical(self, 'Hata', f'İşlem sırasında hata oluştu:\n{str(e)}')

    def delete_classroom(self):
        class_id = self.search_class_id.text().strip()

        if not class_id:
            QMessageBox.warning(self, 'Hata', 'Silmek için önce tablodan bir derslik seçin veya ID ile arama yapın.')
            return

        reply = QMessageBox.question(
            self, 'Silme Onayı',
            f'ID={class_id} olan derslik silinecek. Emin misiniz?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        try:
            cursor = self.db.conn.cursor()

            # Departman kontrol
            if self.user['role'] == 'Admin':
                cursor.execute('DELETE FROM classrooms WHERE id=?', (class_id,))
            else:
                dep_id = self.user['department_id']
                cursor.execute('DELETE FROM classrooms WHERE id=? AND department_id=?', (class_id, dep_id))

            self.db.conn.commit()

            if cursor.rowcount > 0:
                QMessageBox.information(self, 'Başarılı', 'Derslik silindi.')
                self.clear_class_form()
                self.load_classrooms()

        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(self, 'Hata', f'Silme işlemi sırasında hata:\n{str(e)}')

    def load_classroom_for_edit(self, row, col):
        try:
            class_id = self.classroom_table.item(row, 0).text()
            self.search_class_id.setText(class_id)
            self.search_classroom()
        except Exception as e:
            QMessageBox.warning(self, 'Hata', f'Derslik yüklenirken hata: {str(e)}')

    def search_classroom(self):
        class_id = self.search_class_id.text().strip()

        if not class_id:
            QMessageBox.warning(self, 'Uyarı', 'Lütfen arama yapmak için bir ID girin.')
            return

        try:
            cursor = self.db.conn.cursor()

            if self.user['role'] == 'Admin':
                cursor.execute(
                    'SELECT code, name, capacity, rows, columns, seat_group, department_id FROM classrooms WHERE id=?',
                    (class_id,)
                )
            else:
                dep_id = self.user['department_id']
                cursor.execute(
                    'SELECT code, name, capacity, rows, columns, seat_group, department_id FROM classrooms WHERE id=? AND department_id=?',
                    (class_id, dep_id)
                )

            classroom = cursor.fetchone()

            if classroom:
                code, name, capacity, rows, columns, seat_group, dept_id = classroom

                self.class_code.setText(code)
                self.class_name.setText(name)
                self.class_capacity.setText(str(capacity))
                self.class_rows.setText(str(rows))
                self.class_columns.setText(str(columns))
                self.class_seat_group.setCurrentText(str(seat_group))

                # Admin ise departman ID'sini de göster
                if self.user['role'] == 'Admin':
                    self.class_department.setText(str(dept_id))

                self.visualize_classroom(code, name, rows, columns, seat_group)

            else:
                QMessageBox.warning(self, 'Hata', f'ID={class_id} olan derslik bulunamadı.')

        except Exception as e:
            QMessageBox.critical(self, 'Hata', f'Arama sırasında hata:\n{str(e)}')

    def visualize_classroom(self, code, name, rows, columns, seat_group):
        try:
            self.clear_view(self.classroom_view)

            # Toplam sütun sayısı hesapla: her grup seat_group koltuk + gruplar arası spacer (columns-1 kadar)
            total_cols = columns * seat_group + max(0, columns - 1)

            title_label = QLabel(f'<b>{code} - {name}</b><br>Satır: {rows} | Sütun: {columns} | Yapı: {seat_group}\'li')
            title_label.setStyleSheet("background-color: #E3F2FD; padding: 10px; border-radius: 5px; font-size: 11pt;")
            title_label.setAlignment(Qt.AlignCenter)
            self.classroom_view.addWidget(title_label, 0, 0, 1, total_cols)

            for r in range(rows):
                col_idx = 0
                for c in range(columns):
                    if c > 0:
                        spacer = QLabel()
                        spacer.setFixedWidth(20)
                        self.classroom_view.addWidget(spacer, r + 1, col_idx)
                        col_idx += 1

                    for s in range(seat_group):
                        # Numaralandırma: her satırda sıralı koltuk numarası (1'den başlayarak)
                        seat_num = c * seat_group + s + 1
                        seat_label = f'{r + 1}-{seat_num}'
                        btn = QPushButton(seat_label)
                        btn.setStyleSheet(
                            "QPushButton { background-color: #90CAF9; color: #0D47A1; border: 2px solid #2196F3; "
                            "border-radius: 4px; font-weight: bold; }"
                            "QPushButton:hover { background-color: #64B5F6; }"
                        )
                        btn.setFixedSize(60, 35)
                        btn.setToolTip(f'Sıra {r + 1}, Grup {c + 1}, Koltuk {s + 1}')
                        self.classroom_view.addWidget(btn, r + 1, col_idx)
                        col_idx += 1

            self.classroom_view_toggle.setVisible(True)
            self.classroom_view_toggle.setText('▼ Oturma Düzeni Görselleştirmesi')
            self.classroom_view_scroll.setVisible(True)

        except Exception as e:
            QMessageBox.warning(self, 'Hata', f'Görselleştirme hatası: {str(e)}')

    def clear_class_form(self):
        try:
            self.class_code.clear()
            self.class_name.clear()
            self.class_capacity.clear()
            self.class_rows.clear()
            self.class_columns.clear()
            self.class_seat_group.setCurrentIndex(0)
            self.search_class_id.clear()

            if self.user['role'] == 'Admin' and hasattr(self, 'class_department'):
                self.class_department.setText('1')

            self.clear_view(self.classroom_view)
            self.classroom_view_toggle.setVisible(False)
            self.classroom_view_scroll.setVisible(False)

        except Exception as e:
            print(f"Form temizleme hatası: {str(e)}")

    def clear_view(self, view_layout):
        try:
            while view_layout.count():
                item = view_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        except Exception as e:
            print(f"View temizleme hatası: {str(e)}")



    def course_upload_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # Başlık
        title = QLabel('Ders Listesi Yükleme')
        title.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 10px; background-color: #E3F2FD;")
        layout.addWidget(title)

        # Yetki kontrolü
        if self.user['role'] not in ['Admin', 'Bölüm Koordinatörü']:
            label = QLabel('Bu işlemi yapma yetkiniz yok.')
            label.setStyleSheet("color: red; font-size: 11pt; padding: 20px;")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            widget.setLayout(layout)
            return widget

        upload_btn = QPushButton('📁 Excel Yükle')
        upload_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px; font-weight: bold;")
        upload_btn.clicked.connect(self.upload_courses)
        layout.addWidget(upload_btn)

        self.course_status = QLabel('Dersler yüklenmedi.')
        self.course_status.setStyleSheet("color: #333;")
        layout.addWidget(self.course_status)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def upload_courses(self):
        # Yetki kontrolü
        if self.user['role'] not in ['Admin', 'Bölüm Koordinatörü']:
            QMessageBox.warning(self, 'Yetkisiz Erişim', 'Bu işlemi yapma yetkiniz yok.')
            return

        file, _ = QFileDialog.getOpenFileName(self, 'Excel Seç', '', 'Excel Files (*.xlsx *.xls)')
        if not file:
            return

        try:
            df = pd.read_excel(file, header=None)
            cursor = self.db.conn.cursor()

            # Admin: departman seçimi yapabilir, Bölüm Koordinatörü: kendi departmanı
            if self.user['role'] == 'Admin':
                # Admin için departman seçim dialogu
                dep_id, ok = QInputDialog.getInt(
                    self, 'Departman Seçimi',
                    'Departman ID girin:',
                    value=1, min=1, max=999
                )
                if not ok:
                    return
            else:
                dep_id = self.user['department_id']

            errors = []
            current_year = None
            current_type = 'Zorunlu'
            inserted_courses = 0
            updated_courses = 0

            for idx, row in df.iterrows():
                joined = " ".join(str(x).strip() for x in row if pd.notna(x))

                if not joined:
                    continue

                upper_text = joined.upper()

                # Sınıf başlığı algılama
                if "SINIF" in upper_text and any(ch.isdigit() for ch in upper_text):
                    for i in range(1, 7):
                        if f"{i}" in upper_text:
                            current_year = i
                            current_type = 'Zorunlu'
                            break
                    continue

                # Seçmeli başlık algılama
                if "SEÇMELİ" in upper_text or "SEÇİMLİK" in upper_text:
                    current_type = "Seçmeli"
                    continue

                # Sahte başlık satırlarını atla
                if "DERS" in upper_text and ("KOD" in upper_text or "ADI" in upper_text):
                    continue

                # Gerçek ders satırı
                ders_kodu = str(row[0]).strip() if pd.notna(row[0]) else ""
                ders_adi = str(row[1]).strip() if pd.notna(row[1]) else ""
                instructor = str(row[2]).strip() if len(row) > 2 and pd.notna(row[2]) else ""

                if not ders_kodu or not ders_adi:
                    continue

                year = current_year if current_year else 1
                course_type = current_type

                # Aynı kod varsa güncelle
                cursor.execute(
                    'SELECT id FROM courses WHERE code = ? AND department_id = ?',
                    (ders_kodu, dep_id)
                )
                existing = cursor.fetchone()

                if existing:
                    cursor.execute('''
                        UPDATE courses
                        SET name = ?, instructor = ?, year = ?, type = ?
                        WHERE code = ? AND department_id = ?
                    ''', (ders_adi, instructor, year, course_type, ders_kodu, dep_id))
                    updated_courses += 1
                else:
                    cursor.execute('''
                        INSERT INTO courses (department_id, code, name, instructor, year, type)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (dep_id, ders_kodu, ders_adi, instructor, year, course_type))
                    inserted_courses += 1

            self.db.conn.commit()

            result_msg = f'{inserted_courses} yeni ders eklendi'
            if updated_courses > 0:
                result_msg += f', {updated_courses} ders güncellendi'

            if errors:
                error_msg = '\n'.join(errors[:10])
                if len(errors) > 10:
                    error_msg += f'\n... ve {len(errors) - 10} hata daha'
                QMessageBox.warning(self, 'Tamamlandı (Hatalarla)', f'{result_msg}\n\nHatalar:\n{error_msg}')
            else:
                QMessageBox.information(self, 'Başarılı', f'✓ {result_msg}')

            self.course_status.setText(result_msg)


        except Exception as e:
            QMessageBox.critical(self, 'Hata', f'Excel okunamadı:\n{e}')
            self.course_status.setText('Ders yükleme başarısız.')

        if hasattr(self, 'course_table'):
            self.load_courses()

            # Ders seçim tablosunu da yenile (sınav programı sekmesinde)
        if hasattr(self, 'course_include_table'):
            self.load_courses_for_schedule()




    def student_upload_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # Başlık
        title = QLabel('Öğrenci Listesi Yükleme')
        title.setStyleSheet("font-size: 12pt; font-weight: bold; padding: 10px; background-color: #E8F5E9;")
        layout.addWidget(title)

        # Yetki kontrolü
        if self.user['role'] not in ['Admin', 'Bölüm Koordinatörü']:
            label = QLabel('Bu işlemi yapma yetkiniz yok.')
            label.setStyleSheet("color: red; font-size: 11pt; padding: 20px;")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            widget.setLayout(layout)
            return widget

        upload_btn = QPushButton('📁 Excel Yükle')
        upload_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; font-weight: bold;")
        upload_btn.clicked.connect(self.upload_students)
        layout.addWidget(upload_btn)

        self.student_status = QLabel('Öğrenciler yüklenmedi.')
        self.student_status.setStyleSheet("color: #333;")
        layout.addWidget(self.student_status)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def upload_students(self):
        # Yetki kontrolü
        if self.user['role'] not in ['Admin', 'Bölüm Koordinatörü']:
            QMessageBox.warning(self, 'Yetkisiz Erişim', 'Bu işlemi yapma yetkiniz yok.')
            return

        # Admin için departman seçimi, Bölüm Koordinatörü için otomatik
        if self.user['role'] == 'Admin':
            dep_id, ok = QInputDialog.getInt(
                self, 'Departman Seçimi',
                'Departman ID girin:',
                value=1, min=1, max=999
            )
            if not ok:
                return
        else:
            dep_id = self.user['department_id']

        cursor = self.db.conn.cursor()

        # Ders kontrolü
        cursor.execute('SELECT COUNT(*) FROM courses WHERE department_id = ?', (dep_id,))
        if cursor.fetchone()[0] == 0:
            QMessageBox.warning(self, 'Uyarı', 'Önce ders listesini yükleyin.')
            self.student_status.setText('Ders listesi yüklenmedi.')
            return

        # Onay al
        reply = QMessageBox.question(
            self, 'Onay',
            'Departmanın mevcut öğrenci listesi silinecek ve yeni liste yüklenecek.\n\nDevam edilsin mi?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        file, _ = QFileDialog.getOpenFileName(self, 'Excel Seç', '', 'Excel Files (*.xlsx *.xls)')
        if not file:
            return

        try:
            # Mevcut öğrencileri sil
            cursor.execute(
                'DELETE FROM student_courses WHERE student_id IN (SELECT id FROM students WHERE department_id = ?)',
                (dep_id,)
            )
            cursor.execute('DELETE FROM students WHERE department_id = ?', (dep_id,))
            self.db.conn.commit()

            df = pd.read_excel(file, header=0)

            # Sütun kontrolü
            required_cols = ['Öğrenci No', 'Ad Soyad', 'Sınıf', 'Ders']
            missing_cols = [col for col in required_cols if col not in df.columns]

            if missing_cols:
                QMessageBox.warning(
                    self, 'Hata',
                    f'Excel dosyasında eksik sütunlar: {", ".join(missing_cols)}\n'
                    f'Gerekli: {", ".join(required_cols)}'
                )
                return

            cursor.execute('BEGIN TRANSACTION')

            errors = []
            new_students = 0
            course_enrollments = 0
            student_data = {}

            for idx, row in df.iterrows():
                try:
                    number = str(row['Öğrenci No']).strip()
                    name = str(row['Ad Soyad']).strip()
                    course_code = str(row['Ders']).strip()

                    if not number or number == 'nan':
                        continue

                    try:
                        year_str = str(row['Sınıf']).strip()
                        year = int(year_str.split('.')[0])
                        if year < 1 or year > 6:
                            year = 1
                    except:
                        year = 1

                    if number not in student_data:
                        student_data[number] = {
                            'name': name,
                            'year': year,
                            'courses': []
                        }

                    student_data[number]['courses'].append(course_code)

                except Exception as e:
                    errors.append(f"Satır {idx + 2}: {str(e)}")

            # Öğrencileri ekle
            student_cache = {}

            for number, data in student_data.items():
                try:
                    cursor.execute(
                        'INSERT INTO students (department_id, number, name, year) VALUES (?, ?, ?, ?)',
                        (dep_id, number, data['name'], data['year'])
                    )
                    student_id = cursor.lastrowid
                    student_cache[number] = student_id
                    new_students += 1

                except Exception as e:
                    errors.append(f"Öğrenci {number} ({data['name']}): {str(e)}")
                    continue

            # Ders kayıtları
            for number, data in student_data.items():
                if number not in student_cache:
                    continue

                student_id = student_cache[number]

                for course_code in data['courses']:
                    try:
                        cursor.execute(
                            'SELECT id FROM courses WHERE code = ? AND department_id = ?',
                            (course_code, dep_id)
                        )
                        course = cursor.fetchone()

                        if not course:
                            errors.append(f"Ders '{course_code}' bulunamadı")
                            continue

                        course_id = course[0]

                        cursor.execute(
                            'INSERT INTO student_courses (student_id, course_id) VALUES (?, ?)',
                            (student_id, course_id)
                        )
                        course_enrollments += 1

                    except Exception as e:
                        errors.append(f"{number} - {course_code}: {str(e)}")

            self.db.conn.commit()

            success_msg = f'{new_students} öğrenci, {course_enrollments} ders kaydı eklendi'

            if errors:
                error_msg = '\n'.join(errors[:10])
                if len(errors) > 10:
                    error_msg += f'\n... ve {len(errors) - 10} hata daha'
                QMessageBox.warning(self, 'Tamamlandı', f'{success_msg}\n\nHatalar:\n{error_msg}')
            else:
                QMessageBox.information(self, 'Başarılı', f'✓ {success_msg}')

            self.student_status.setText(success_msg)

        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(self, 'Hata', f'İşlem başarısız:\n{str(e)}')
            self.student_status.setText('Yükleme başarısız.')

        if hasattr(self, 'course_table'):
            self.load_courses()


    def student_list_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        # Arama kutusu
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel('Öğrenci No Ara:'))
        self.student_search = QLineEdit()
        self.student_search.setPlaceholderText('Öğrenci numarasını girin...')
        search_layout.addWidget(self.student_search)

        search_btn = QPushButton('Ara')
        search_btn.clicked.connect(self.search_student)
        search_layout.addWidget(search_btn)

        layout.addLayout(search_layout)

        # Toggle buton
        self.student_info_toggle = QPushButton('▼ Öğrenci Bilgileri')
        self.student_info_toggle.setStyleSheet(
            "QPushButton { text-align: left; padding: 8px; background-color: #f0f0f0; border: 1px solid #ddd; }"
            "QPushButton:hover { background-color: #e0e0e0; }"
        )
        self.student_info_toggle.clicked.connect(self.toggle_student_info)
        self.student_info_toggle.setVisible(False)
        layout.addWidget(self.student_info_toggle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(250)

        self.student_info = QLabel('Aramak için öğrenci numarası girin.')
        self.student_info.setStyleSheet(
            "background-color: white; border: 1px solid #ddd; padding: 15px; "
            "border-radius: 5px; font-size: 11pt;"
        )
        self.student_info.setWordWrap(True)
        self.student_info.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll.setWidget(self.student_info)
        scroll.setVisible(False)
        self.student_info_scroll = scroll
        layout.addWidget(scroll)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def toggle_student_info(self):
        is_visible = self.student_info_scroll.isVisible()
        self.student_info_scroll.setVisible(not is_visible)

        if is_visible:
            self.student_info_toggle.setText('▼ Öğrenci Bilgileri')
        else:
            self.student_info_toggle.setText('▲ Öğrenci Bilgileri')

    def search_student(self):
        number = self.student_search.text().strip()

        if not number:
            self.student_info.setText('Lütfen öğrenci numarası girin.')
            self.student_info_toggle.setVisible(False)
            self.student_info_scroll.setVisible(False)
            return

        cursor = self.db.conn.cursor()

        # Admin: tüm departmanları görebilir, Bölüm Koor: sadece kendi departmanını
        if self.user['role'] == 'Admin':
            dep_id = '%'
        else:
            dep_id = self.user['department_id']

        cursor.execute('''
            SELECT s.name, s.year FROM students s
            WHERE s.number = ? AND s.department_id LIKE ?
        ''', (number, dep_id))

        student = cursor.fetchone()

        if not student:
            self.student_info.setText(f'<span style="color: red;">Öğrenci bulunamadı: {number}</span>')
            self.student_info_toggle.setVisible(True)
            self.student_info_toggle.setText('▼ Öğrenci Bilgileri')
            self.student_info_scroll.setVisible(True)
            return

        student_name, student_year = student

        cursor.execute('''
            SELECT c.code, c.name FROM courses c
            JOIN student_courses sc ON c.id = sc.course_id
            JOIN students s ON sc.student_id = s.id
            WHERE s.number = ? AND s.department_id LIKE ?
            ORDER BY c.code
        ''', (number, dep_id))

        courses = cursor.fetchall()

        info_html = f'''
        <div style="font-family: Arial, sans-serif;">
            <p style="font-size: 13pt; margin-bottom: 10px;">
                <b>Öğrenci:</b> {student_name}
            </p>
            <p style="margin-bottom: 15px;">
                <b>Öğrenci No:</b> {number}
            </p>
            <p style="font-size: 12pt; margin-bottom: 8px;">
                <b>Aldığı Dersler:</b>
            </p>
        '''

        if courses:
            for code, name in courses:
                info_html += f'<p style="margin-left: 15px; margin-bottom: 5px;">- {code} - {name}</p>'
        else:
            info_html += '<p style="margin-left: 15px; color: #666;"><i>Henüz ders kaydı yok</i></p>'

        info_html += '</div>'

        self.student_info.setText(info_html)

        self.student_info_toggle.setVisible(True)
        self.student_info_toggle.setText('▼ Öğrenci Bilgileri')
        self.student_info_scroll.setVisible(True)

    def course_list_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        self.course_table = QTableWidget()
        self.course_table.setColumnCount(2)
        self.course_table.setHorizontalHeaderLabels(['Ders Kodu', 'Ders Adı'])
        self.course_table.horizontalHeader().setStretchLastSection(True)
        self.course_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.course_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.course_table.cellClicked.connect(self.show_course_students)

        self.load_courses()
        layout.addWidget(self.course_table)

        self.course_info_toggle = QPushButton('▼ Dersi Alan Öğrenciler')
        self.course_info_toggle.setStyleSheet(
            "QPushButton { text-align: left; padding: 8px; background-color: #f0f0f0; border: 1px solid #ddd; }"
            "QPushButton:hover { background-color: #e0e0e0; }"
        )
        self.course_info_toggle.clicked.connect(self.toggle_course_info)
        self.course_info_toggle.setVisible(False)
        layout.addWidget(self.course_info_toggle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(250)

        self.course_students_info = QLabel('Dersi alan öğrencileri görmek için listeden bir ders seçin.')
        self.course_students_info.setStyleSheet(
            "background-color: white; border: 1px solid #ddd; padding: 15px; "
            "border-radius: 5px; font-size: 11pt;"
        )
        self.course_students_info.setWordWrap(True)
        self.course_students_info.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll.setWidget(self.course_students_info)
        scroll.setVisible(False)
        self.course_students_scroll = scroll
        layout.addWidget(scroll)

        widget.setLayout(layout)
        return widget

    def toggle_course_info(self):
        is_visible = self.course_students_scroll.isVisible()
        self.course_students_scroll.setVisible(not is_visible)

        if is_visible:
            self.course_info_toggle.setText('▼ Dersi Alan Öğrenciler')
        else:
            self.course_info_toggle.setText('▲ Dersi Alan Öğrenciler')

    def load_courses(self):
        cursor = self.db.conn.cursor()

        # Admin: tüm dersler, Bölüm Koor: sadece kendi dersler
        if self.user['role'] == 'Admin':
            dep_id = '%'
        else:
            dep_id = self.user['department_id']

        cursor.execute(
            'SELECT code, name FROM courses WHERE department_id LIKE ? ORDER BY code',
            (dep_id,)
        )
        courses = cursor.fetchall()

        self.course_table.setRowCount(len(courses))

        for i, (code, name) in enumerate(courses):
            self.course_table.setItem(i, 0, QTableWidgetItem(code))
            self.course_table.setItem(i, 1, QTableWidgetItem(name))

    def show_course_students(self, row, col):
        code = self.course_table.item(row, 0).text()
        name = self.course_table.item(row, 1).text()

        cursor = self.db.conn.cursor()

        cursor.execute('''
            SELECT s.number, s.name FROM students s
            JOIN student_courses sc ON s.id = sc.student_id
            JOIN courses c ON sc.course_id = c.id
            WHERE c.code = ?
            ORDER BY s.number
        ''', (code,))

        students = cursor.fetchall()

        info_html = f'''
        <div style="font-family: Arial, sans-serif;">
            <p style="font-size: 13pt; margin-bottom: 10px;">
                <b>Ders:</b> {code} - {name}
            </p>
            <p style="font-size: 12pt; margin-bottom: 8px;">
                <b>Dersi Alan Öğrenciler:</b>
            </p>
        '''

        if students:
            for number, student_name in students:
                info_html += f'<p style="margin-left: 15px; margin-bottom: 5px;">• {number} - {student_name}</p>'
            info_html += f'<p style="margin-top: 10px; color: #666;"><i>Toplam: {len(students)} öğrenci</i></p>'
        else:
            info_html += '<p style="margin-left: 15px; color: #666;"><i>Bu dersi alan öğrenci yok</i></p>'

        info_html += '</div>'

        self.course_students_info.setText(info_html)

        self.course_info_toggle.setVisible(True)
        self.course_info_toggle.setText('▼ Dersi Alan Öğrenciler')
        self.course_students_scroll.setVisible(True)











    def exam_schedule_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()


        # Başlık
        title = QLabel('Sınav Programı Oluşturma')
        title.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px; background-color: #E3F2FD;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # KISITLAR BÖLÜMÜ
        constraints_group = QGroupBox('Kısıtlar ve Ayarlar')
        constraints_layout = QVBoxLayout()

        # 1. Sınav Türü ve Tarih
        basic_form = QGridLayout()

        basic_form.addWidget(QLabel('Sınav Türü:'), 0, 0)
        self.exam_type = QComboBox()
        self.exam_type.addItems(['Vize', 'Final', 'Bütünleme'])
        basic_form.addWidget(self.exam_type, 0, 1)

        basic_form.addWidget(QLabel('Başlangıç Tarihi:'), 1, 0)
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        basic_form.addWidget(self.start_date, 1, 1)

        basic_form.addWidget(QLabel('Bitiş Tarihi:'), 2, 0)
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate().addDays(14))
        self.end_date.setCalendarPopup(True)
        basic_form.addWidget(self.end_date, 2, 1)

        basic_form.addWidget(QLabel('Varsayılan Sınav Süresi (dk):'), 3, 0)
        self.default_duration = QLineEdit('75')
        self.default_duration.setPlaceholderText('Örn: 75')
        basic_form.addWidget(self.default_duration, 3, 1)

        basic_form.addWidget(QLabel('Bekleme Süresi (dk):'), 4, 0)
        self.break_time = QLineEdit('15')
        self.break_time.setPlaceholderText('Sınavlar arası bekleme')
        basic_form.addWidget(self.break_time, 4, 1)

        # Aynı zamana denk gelme kontrolü
        self.no_overlap_check = QCheckBox('Hiçbir sınav aynı anda başlamasın (Tüm sınavlar sıralı)')
        self.no_overlap_check.setChecked(False)
        self.no_overlap_check.setToolTip('Aktif olduğunda bir sınav bitene kadar başka sınav başlamaz')
        basic_form.addWidget(self.no_overlap_check, 5, 0, 1, 2)

        constraints_layout.addLayout(basic_form)

        # 2. Dahil Olmayan Günler
        exclude_days_group = QGroupBox('Sınav Programına Dahil Olmayan Günler')
        exclude_layout = QHBoxLayout()
        self.exclude_days = {}
        days = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
        for i, day in enumerate(days):
            cb = QCheckBox(day)
            if i >= 5:  # Cumartesi, Pazar
                cb.setChecked(True)
            exclude_layout.addWidget(cb)
            self.exclude_days[i + 1] = cb
        exclude_days_group.setLayout(exclude_layout)
        constraints_layout.addWidget(exclude_days_group)

        # 3. Ders Seçimi
        course_select_group = QGroupBox('Programa Dahil Edilecek Dersler')
        course_select_layout = QVBoxLayout()

        course_buttons = QHBoxLayout()
        select_all_btn = QPushButton('Tümünü Seç')
        select_all_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 5px;")
        select_all_btn.clicked.connect(lambda: self.toggle_all_courses(True))
        deselect_all_btn = QPushButton('Tümünü Kaldır')
        deselect_all_btn.setStyleSheet("background-color: #FF5722; color: white; padding: 5px;")
        deselect_all_btn.clicked.connect(lambda: self.toggle_all_courses(False))
        course_buttons.addWidget(select_all_btn)
        course_buttons.addWidget(deselect_all_btn)
        course_buttons.addStretch()
        course_select_layout.addLayout(course_buttons)

        self.course_include_table = QTableWidget()
        self.course_include_table.setColumnCount(4)
        self.course_include_table.setHorizontalHeaderLabels(['Dahil Et', 'Kod', 'Ders Adı', 'Sınıf'])

        # Sütun genişliklerini ayarla
        self.course_include_table.setColumnWidth(0, 80)  # Dahil Et
        self.course_include_table.setColumnWidth(1, 120)  # Kod
        self.course_include_table.setColumnWidth(2, 400)  # Ders Adı (geniş)
        self.course_include_table.setColumnWidth(3, 100)  # Sınıf

        # Tablo ayarları
        self.course_include_table.horizontalHeader().setStretchLastSection(False)
        self.course_include_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # Ders Adı esnek
        self.course_include_table.setMinimumHeight(250)  # Minimum yükseklik artırıldı
        self.course_include_table.setMaximumHeight(350)  # Maksimum yükseklik artırıldı
        self.course_include_table.setAlternatingRowColors(True)
        self.course_include_table.setSelectionBehavior(QTableWidget.SelectRows)

        self.load_courses_for_schedule()
        course_select_layout.addWidget(self.course_include_table)

        course_select_group.setLayout(course_select_layout)
        constraints_layout.addWidget(course_select_group)

        # 4. İstisna Sınav Süreleri
        exception_group = QGroupBox('İstisna Sınav Süreleri (Farklı Süre Gereken Dersler)')
        exception_layout = QVBoxLayout()

        exception_info = QLabel('Varsayılan süreden farklı süre gereken dersleri buraya ekleyin.')
        exception_info.setStyleSheet("color: #666; font-style: italic;")
        exception_layout.addWidget(exception_info)

        self.exception_table = QTableWidget(0, 3)
        self.exception_table.setHorizontalHeaderLabels(['Ders Kodu', 'Süre (dk)', 'Sil'])
        self.exception_table.setMaximumHeight(150)
        exception_layout.addWidget(self.exception_table)

        add_exception_btn = QPushButton('+ İstisna Ekle')
        add_exception_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px;")
        add_exception_btn.clicked.connect(self.add_exception_row)
        exception_layout.addWidget(add_exception_btn)

        exception_group.setLayout(exception_layout)
        constraints_layout.addWidget(exception_group)

        constraints_group.setLayout(constraints_layout)
        layout.addWidget(constraints_group)

        # Program Oluştur Butonu
        create_btn = QPushButton('🗓️ Sınav Programını Oluştur')
        create_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; padding: 12px; "
            "font-size: 12pt; font-weight: bold; border-radius: 5px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        create_btn.clicked.connect(self.create_schedule)
        layout.addWidget(create_btn)

        # Oluşturulan Program Tablosu
        schedule_group = QGroupBox('Oluşturulan Sınav Programı')
        schedule_layout = QVBoxLayout()

        self.schedule_table = QTableWidget()
        self.schedule_table.setColumnCount(6)
        self.schedule_table.setHorizontalHeaderLabels(['Tarih', 'Gün', 'Saat', 'Ders Kodu', 'Ders Adı', 'Derslik'])
        self.schedule_table.horizontalHeader().setStretchLastSection(True)
        self.schedule_table.setEditTriggers(QTableWidget.NoEditTriggers)
        schedule_layout.addWidget(self.schedule_table)

        export_btn = QPushButton('📥 Excel Olarak İndir')
        export_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; font-weight: bold;")
        export_btn.clicked.connect(self.export_schedule)
        schedule_layout.addWidget(export_btn)

        schedule_group.setLayout(schedule_layout)
        layout.addWidget(schedule_group)

        widget.setLayout(layout)
        return widget

    def toggle_all_courses(self, checked):
        """Tüm dersleri seç/kaldır"""
        for i in range(self.course_include_table.rowCount()):
            widget = self.course_include_table.cellWidget(i, 0)
            if widget:
                # Widget içindeki checkbox'ı bul
                checkbox = widget.layout().itemAt(0).widget()
                if checkbox and isinstance(checkbox, QCheckBox):
                    checkbox.setChecked(checked)

    def load_courses_for_schedule(self):
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else '%'
        cursor.execute('SELECT id, code, name, year FROM courses WHERE department_id LIKE ? ORDER BY year, code',
                       (dep_id,))
        courses = cursor.fetchall()

        self.course_include_table.setRowCount(len(courses))
        self.course_include_ids = {}
        self.course_checkboxes = []  # CHECKBOX'LARI SAKLAMAK İÇİN LİSTE

        for i, (cid, code, name, year) in enumerate(courses):
            # Checkbox - basit yöntem
            cb = QCheckBox()
            cb.setChecked(True)
            self.course_checkboxes.append(cb)  # LİSTEYE EKLE

            # Ortalamak için widget kullan
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(cb)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.course_include_table.setCellWidget(i, 0, checkbox_widget)

            # Kod
            code_item = QTableWidgetItem(code)
            code_item.setTextAlignment(Qt.AlignCenter)
            self.course_include_table.setItem(i, 1, code_item)

            # Ders adı
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.course_include_table.setItem(i, 2, name_item)

            # Sınıf
            year_item = QTableWidgetItem(f'{year}. Sınıf')
            year_item.setTextAlignment(Qt.AlignCenter)
            self.course_include_table.setItem(i, 3, year_item)

            self.course_include_ids[i] = cid

        # Satır yüksekliğini ayarla
        for i in range(len(courses)):
            self.course_include_table.setRowHeight(i, 35)

    def toggle_all_courses(self, checked):
        """Tüm dersleri seç/kaldır - LİSTEDEN KULLAN"""
        for cb in self.course_checkboxes:
            cb.setChecked(checked)

    def add_exception_row(self):
        row = self.exception_table.rowCount()
        self.exception_table.insertRow(row)

        code_edit = QLineEdit()
        code_edit.setPlaceholderText('Ders kodu girin')

        duration_edit = QLineEdit('90')
        duration_edit.setPlaceholderText('Süre (dk)')

        delete_btn = QPushButton('🗑️')
        delete_btn.setStyleSheet("background-color: #f44336; color: white;")
        delete_btn.clicked.connect(lambda: self.exception_table.removeRow(self.exception_table.currentRow()))

        self.exception_table.setCellWidget(row, 0, code_edit)
        self.exception_table.setCellWidget(row, 1, duration_edit)
        self.exception_table.setCellWidget(row, 2, delete_btn)

    def create_schedule(self):
        try:
            # Kısıtları al
            exam_type = self.exam_type.currentText()
            start_date = self.start_date.date().toPyDate()
            end_date = self.end_date.date().toPyDate()

            try:
                default_duration = int(self.default_duration.text() or 75)
                break_time = int(self.break_time.text() or 15)
            except ValueError:
                QMessageBox.warning(self, 'Hata', 'Sınav süresi ve bekleme süresi sayısal olmalıdır.')
                return

            no_overlap = self.no_overlap_check.isChecked()

            # Tarih kontrolü
            if end_date < start_date:
                QMessageBox.warning(self, 'Hata', 'Bitiş tarihi başlangıç tarihinden önce olamaz!')
                return

            # Dahil olmayan günleri al
            excluded_weekdays = [day for day, cb in self.exclude_days.items() if cb.isChecked()]

            # Geçerli tarihleri oluştur
            dates = []
            current = start_date
            while current <= end_date:
                if (current.weekday() + 1) not in excluded_weekdays:
                    dates.append(current)
                current += datetime.timedelta(days=1)

            if not dates:
                QMessageBox.warning(self, 'Hata',
                                    'Seçilen tarih aralığı sınavları barındırmıyor!\nTüm günler hariç tutulmuş.')
                return

            # Dahil edilen dersleri al
            included_courses = []
            for i in range(self.course_include_table.rowCount()):
                # LİSTEDEN CHECKBOX AL
                if i < len(self.course_checkboxes) and self.course_checkboxes[i].isChecked():
                    included_courses.append(self.course_include_ids[i])

            if not included_courses:
                QMessageBox.warning(self, 'Hata', 'En az bir ders seçmelisiniz!')
                return

            # İstisna süreleri al
            exceptions = {}
            for i in range(self.exception_table.rowCount()):
                code_widget = self.exception_table.cellWidget(i, 0)
                duration_widget = self.exception_table.cellWidget(i, 1)
                if code_widget and duration_widget:
                    code = code_widget.text().strip()
                    if code:
                        try:
                            exceptions[code] = int(duration_widget.text() or default_duration)
                        except ValueError:
                            pass

            # Veritabanından ders bilgilerini çek
            cursor = self.db.conn.cursor()
            dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else '%'

            placeholders = ','.join('?' for _ in included_courses)
            cursor.execute(
                f'SELECT id, year, code, name FROM courses WHERE id IN ({placeholders}) AND department_id LIKE ?',
                included_courses + [dep_id]
            )
            courses = cursor.fetchall()

            if not courses:
                QMessageBox.warning(self, 'Hata', 'Seçilen derslere ait bilgi bulunamadı!')
                return

            course_dict = {cid: {'year': year, 'code': code, 'name': name} for cid, year, code, name in courses}

            # Her dersin öğrenci sayısını çek
            course_student_count = {}
            for cid in included_courses:
                cursor.execute('SELECT COUNT(*) FROM student_courses WHERE course_id=?', (cid,))
                count = cursor.fetchone()[0]
                course_student_count[cid] = count

            # Derslikleri çek
            cursor.execute(
                'SELECT id, code, capacity FROM classrooms WHERE department_id LIKE ? ORDER BY capacity DESC',
                (dep_id,))
            classrooms = cursor.fetchall()

            if not classrooms:
                QMessageBox.warning(self, 'Hata', 'Derslik bulunamadı!\nÖnce derslik ekleyin.')
                return

            # Öğrenci-ders ilişkilerini çek
            student_courses = {}
            cursor.execute(
                f'SELECT student_id, course_id FROM student_courses WHERE course_id IN ({placeholders})',
                included_courses
            )
            for sid, cid in cursor.fetchall():
                if sid not in student_courses:
                    student_courses[sid] = []
                student_courses[sid].append(cid)

            # Ders sürelerini belirle
            durations = {}
            for cid in included_courses:
                code = course_dict[cid]['code']
                durations[cid] = exceptions.get(code, default_duration)

            # Sınav programını oluştur
            schedule, errors = self.generate_schedule(
                included_courses, course_dict, course_student_count, classrooms,
                student_courses, durations, dates, break_time, no_overlap
            )

            if errors:
                error_msg = '\n'.join(errors[:15])
                if len(errors) > 15:
                    error_msg += f'\n\n... ve {len(errors) - 15} hata daha'
                QMessageBox.warning(self, 'Program Oluşturulamadı', f'Aşağıdaki hatalar oluştu:\n\n{error_msg}')
                return

            if not schedule:
                QMessageBox.warning(self, 'Hata', 'Program oluşturulamadı!\nKısıtları gevşetmeyi deneyin.')
                return

            # Önce eski sınav kayıtlarını sil (aynı tür için)
            cursor.execute('DELETE FROM exams WHERE type=?', (exam_type,))
            # Eski oturma planlarını sil
            cursor.execute('DELETE FROM seating WHERE exam_id IN (SELECT id FROM exams WHERE type=?)', (exam_type,))

            # Tabloyu temizle ve programı göster
            self.schedule_table.setRowCount(0)

            days_tr = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']

            for item in sorted(schedule, key=lambda x: (x['date'], x['time'])):
                row = self.schedule_table.rowCount()
                self.schedule_table.insertRow(row)

                date_obj = datetime.datetime.strptime(item['date'], '%Y-%m-%d')
                day_name = days_tr[date_obj.weekday()]

                self.schedule_table.setItem(row, 0, QTableWidgetItem(item['date']))
                self.schedule_table.setItem(row, 1, QTableWidgetItem(day_name))
                self.schedule_table.setItem(row, 2, QTableWidgetItem(item['time']))
                self.schedule_table.setItem(row, 3, QTableWidgetItem(item['code']))
                self.schedule_table.setItem(row, 4, QTableWidgetItem(item['name']))
                self.schedule_table.setItem(row, 5, QTableWidgetItem(item['classroom']))

                # Veritabanına kaydet
                cursor.execute(
                    'INSERT INTO exams (course_id, date, time, duration, type, classroom_id) VALUES (?, ?, ?, ?, ?, ?)',
                    (item['course_id'], item['date'], item['time'], item['duration'], exam_type, item['classroom_id'])
                )

            self.db.conn.commit()
            # Oturma planı sekmesini yenile
            self.seating_table.setRowCount(0)  # Tabloyu sıfırla
            self.load_exams()
            self.refresh_seating_tab()

            QMessageBox.information(
                self, 'Başarılı',
                f'Sınav programı oluşturuldu!\n\n'
                f'Toplam {len(schedule)} sınav planlandı.\n'
                f'{len(dates)} gün kullanıldı.'
            )

        except Exception as e:
            QMessageBox.critical(self, 'Hata', f'Program oluşturulurken hata oluştu:\n{str(e)}')

    def refresh_seating_tab(self):
        if hasattr(self, 'seating_table'):
            self.seating_table.setRowCount(0)
            self.clear_seating_view()
            self.load_exams()


    def generate_schedule(self, courses, course_dict, course_student_count, classrooms,
                          student_courses, durations, dates, break_time, no_overlap):
        """Geliştirilmiş sınav programı oluşturma - Düzeltilmiş saat hesaplama"""

        schedule = []
        errors = []

        # Derslik kullanımı takibi - Her tarih ve derslik için kullanılan zaman aralıkları
        classroom_schedule = {(date, cl[0]): [] for date in dates for cl in classrooms}

        # Öğrenci sınav takibi (çakışma önleme)
        student_exam_times = {sid: [] for sid in student_courses.keys()}

        # Sınıf bazlı dağılım (günde max 2 sınav)
        year_daily_count = {(year, date): 0 for year in range(1, 7) for date in dates}

        # Dersleri sınıf ve öğrenci sayısına göre sırala
        sorted_courses = sorted(
            courses,
            key=lambda c: (course_dict[c]['year'], -course_student_count[c])
        )

        def time_to_minutes(time_str):
            """Saat string'ini dakikaya çevir (09:00 -> 540)"""
            h, m = map(int, time_str.split(':'))
            return h * 60 + m

        def minutes_to_time(minutes):
            """Dakikayı saat string'ine çevir (540 -> 09:00)"""
            h = minutes // 60
            m = minutes % 60
            return f'{h:02d}:{m:02d}'

        def check_time_overlap(start1, end1, start2, end2):
            """İki zaman aralığı çakışıyor mu?"""
            return start1 < end2 and start2 < end1

        def find_available_time_slot(date, selected_classrooms, duration, break_time):
            """Verilen dersliklerde boş bir zaman dilimi bul"""
            start_time = 9 * 60  # 09:00
            end_time = 17 * 60  # 17:00
            exam_duration_with_break = duration + break_time

            # Her 15 dakikalık aralıkta dene
            current = start_time
            while current + duration <= end_time:
                exam_end = current + exam_duration_with_break

                # Tüm seçili dersliklerde bu zaman müsait mi?
                all_available = True
                for cl_id in selected_classrooms:
                    # Bu dersliğin programını kontrol et
                    for occupied_start, occupied_end in classroom_schedule[(date, cl_id)]:
                        if check_time_overlap(current, exam_end, occupied_start, occupied_end):
                            all_available = False
                            break
                    if not all_available:
                        break

                if all_available:
                    return current

                current += 15  # 15 dakika ilerle

            return None

        for course_id in sorted_courses:
            code = course_dict[course_id]['code']
            name = course_dict[course_id]['name']
            year = course_dict[course_id]['year']
            student_count = course_student_count[course_id]
            duration = durations[course_id]

            assigned = False

            # Uygun tarih bul
            for date in dates:
                # Sınıf için günlük kotayı kontrol et
                if year_daily_count[(year, date)] >= 2:
                    continue

                # Öğrenci çakışması kontrolü için bu tarihteki mevcut sınavları kontrol et
                student_conflict_times = []
                for sid in student_courses:
                    if course_id in student_courses[sid]:
                        student_conflict_times.extend([
                            (exam_date, exam_start, exam_end)
                            for exam_date, exam_start, exam_end in student_exam_times[sid]
                            if exam_date == date
                        ])

                # Müsait derslikleri bul
                available_classrooms = classrooms.copy()

                if not available_classrooms:
                    continue

                # Toplam kapasiteyi hesapla
                total_capacity = sum(cl[2] for cl in available_classrooms)

                if total_capacity < student_count:
                    continue

                # Öğrencileri dersliklere dağıt
                remaining_students = student_count
                selected_classrooms_info = []

                # Derslikleri kapasiteye göre sırala (büyükten küçüğe)
                sorted_available = sorted(available_classrooms, key=lambda x: -x[2])

                for classroom in sorted_available:
                    cl_id, cl_code, cl_capacity = classroom

                    if remaining_students > 0:
                        students_in_this_room = min(remaining_students, cl_capacity)

                        selected_classrooms_info.append({
                            'id': cl_id,
                            'code': cl_code,
                            'capacity': cl_capacity,
                            'students': students_in_this_room
                        })

                        remaining_students -= students_in_this_room

                    if remaining_students <= 0:
                        break

                if remaining_students > 0:
                    continue

                # Seçilen derslikler için uygun zaman dilimi bul
                selected_classroom_ids = [cl['id'] for cl in selected_classrooms_info]

                start_time_minutes = find_available_time_slot(
                    date, selected_classroom_ids, duration, break_time
                )

                if start_time_minutes is None:
                    continue

                # Öğrenci çakışma kontrolü
                end_time_minutes = start_time_minutes + duration + break_time
                has_student_conflict = False

                for conflict_date, conflict_start, conflict_end in student_conflict_times:
                    if check_time_overlap(start_time_minutes, end_time_minutes,
                                          conflict_start, conflict_end):
                        has_student_conflict = True
                        break

                if has_student_conflict:
                    continue

                # No overlap kontrolü
                if no_overlap:
                    # Bu tarihte başka sınav var mı ve çakışıyor mu?
                    has_overlap = False
                    for existing in schedule:
                        if existing['date'] == date.strftime('%Y-%m-%d'):
                            existing_start = time_to_minutes(existing['time'])
                            existing_end = existing_start + existing['duration'] + break_time

                            if check_time_overlap(start_time_minutes, end_time_minutes,
                                                  existing_start, existing_end):
                                has_overlap = True
                                break

                    if has_overlap:
                        continue

                # Atama yap
                start_time_str = minutes_to_time(start_time_minutes)

                for classroom_info in selected_classrooms_info:
                    schedule.append({
                        'course_id': course_id,
                        'date': date.strftime('%Y-%m-%d'),
                        'time': start_time_str,
                        'code': code,
                        'name': name,
                        'duration': duration,
                        'classroom_id': classroom_info['id'],
                        'classroom': classroom_info['code'],
                        'students_count': classroom_info['students'],
                        'total_students': student_count
                    })

                    # Derslik programına ekle
                    classroom_schedule[(date, classroom_info['id'])].append(
                        (start_time_minutes, end_time_minutes)
                    )

                # Sınıf günlük sayacını artır
                year_daily_count[(year, date)] += 1

                # Öğrenci sınav zamanlarını kaydet
                for sid in student_courses:
                    if course_id in student_courses[sid]:
                        student_exam_times[sid].append((date, start_time_minutes, end_time_minutes))

                assigned = True
                break

            if not assigned:
                # Toplam kapasite bilgisini ekle
                total_available_capacity = sum(cl[2] for cl in classrooms)
                errors.append(
                    f'Ders {code} ({name}) için uygun slot bulunamadı! '
                    f'Öğrenci: {student_count}, Mevcut toplam kapasite: {total_available_capacity}'
                )

        return schedule, errors

    def create_schedule(self):
        try:
            # Kısıtları al
            exam_type = self.exam_type.currentText()
            start_date = self.start_date.date().toPyDate()
            end_date = self.end_date.date().toPyDate()

            try:
                default_duration = int(self.default_duration.text() or 75)
                break_time = int(self.break_time.text() or 15)
            except ValueError:
                QMessageBox.warning(self, 'Hata', 'Sınav süresi ve bekleme süresi sayısal olmalıdır.')
                return

            no_overlap = self.no_overlap_check.isChecked()

            # Tarih kontrolü
            if end_date < start_date:
                QMessageBox.warning(self, 'Hata', 'Bitiş tarihi başlangıç tarihinden önce olamaz!')
                return

            # Dahil olmayan günleri al
            excluded_weekdays = [day for day, cb in self.exclude_days.items() if cb.isChecked()]

            # Geçerli tarihleri oluştur
            dates = []
            current = start_date
            while current <= end_date:
                if (current.weekday() + 1) not in excluded_weekdays:
                    dates.append(current)
                current += datetime.timedelta(days=1)

            if not dates:
                QMessageBox.warning(self, 'Hata',
                                    'Seçilen tarih aralığı sınavları barındırmıyor!\nTüm günler hariç tutulmuş.')
                return

            # Dahil edilen dersleri al
            included_courses = []
            for i in range(self.course_include_table.rowCount()):
                if i < len(self.course_checkboxes) and self.course_checkboxes[i].isChecked():
                    included_courses.append(self.course_include_ids[i])

            if not included_courses:
                QMessageBox.warning(self, 'Hata', 'En az bir ders seçmelisiniz!')
                return

            # İstisna süreleri al
            exceptions = {}
            for i in range(self.exception_table.rowCount()):
                code_widget = self.exception_table.cellWidget(i, 0)
                duration_widget = self.exception_table.cellWidget(i, 1)
                if code_widget and duration_widget:
                    code = code_widget.text().strip()
                    if code:
                        try:
                            exceptions[code] = int(duration_widget.text() or default_duration)
                        except ValueError:
                            pass

            # Veritabanından ders bilgilerini çek
            cursor = self.db.conn.cursor()
            dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else '%'

            placeholders = ','.join('?' for _ in included_courses)
            cursor.execute(
                f'SELECT id, year, code, name FROM courses WHERE id IN ({placeholders}) AND department_id LIKE ?',
                included_courses + [dep_id]
            )
            courses = cursor.fetchall()

            if not courses:
                QMessageBox.warning(self, 'Hata', 'Seçilen derslere ait bilgi bulunamadı!')
                return

            course_dict = {cid: {'year': year, 'code': code, 'name': name} for cid, year, code, name in courses}

            # Her dersin öğrenci sayısını çek
            course_student_count = {}
            for cid in included_courses:
                cursor.execute('SELECT COUNT(*) FROM student_courses WHERE course_id=?', (cid,))
                count = cursor.fetchone()[0]
                course_student_count[cid] = count

            # Derslikleri çek
            cursor.execute(
                'SELECT id, code, capacity FROM classrooms WHERE department_id LIKE ? ORDER BY capacity DESC',
                (dep_id,))
            classrooms = cursor.fetchall()

            if not classrooms:
                QMessageBox.warning(self, 'Hata', 'Derslik bulunamadı!\nÖnce derslik ekleyin.')
                return

            # Öğrenci-ders ilişkilerini çek
            student_courses = {}
            cursor.execute(
                f'SELECT student_id, course_id FROM student_courses WHERE course_id IN ({placeholders})',
                included_courses
            )
            for sid, cid in cursor.fetchall():
                if sid not in student_courses:
                    student_courses[sid] = []
                student_courses[sid].append(cid)

            # Ders sürelerini belirle
            durations = {}
            for cid in included_courses:
                code = course_dict[cid]['code']
                durations[cid] = exceptions.get(code, default_duration)

            # Sınav programını oluştur
            schedule, errors = self.generate_schedule(
                included_courses, course_dict, course_student_count, classrooms,
                student_courses, durations, dates, break_time, no_overlap
            )

            if errors:
                error_msg = '\n'.join(errors[:15])
                if len(errors) > 15:
                    error_msg += f'\n\n... ve {len(errors) - 15} hata daha'
                QMessageBox.warning(self, 'Program Oluşturulamadı', f'Aşağıdaki hatalar oluştu:\n\n{error_msg}')

                if not schedule:
                    return

            if not schedule:
                QMessageBox.warning(self, 'Hata', 'Program oluşturulamadı!\nKısıtları gevşetmeyi deneyin.')
                return

            # ÖNCESİ: Eski sınav kayıtlarını sil (aynı tür için)
            cursor.execute('DELETE FROM exams WHERE type=?', (exam_type,))

            # YENİ: Tüm oturma planlarını sil
            self.clear_all_seating_plans()

            # Tabloyu temizle ve programı göster
            self.schedule_table.setRowCount(0)

            days_tr = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']

            # Aynı sınav için birden fazla derslik varsa grupla
            exam_groups = {}
            for item in schedule:
                key = (item['course_id'], item['date'], item['time'])
                if key not in exam_groups:
                    exam_groups[key] = []
                exam_groups[key].append(item)

            for key, items in sorted(exam_groups.items(), key=lambda x: (x[0][1], x[0][2])):
                row = self.schedule_table.rowCount()
                self.schedule_table.insertRow(row)

                first_item = items[0]
                date_obj = datetime.datetime.strptime(first_item['date'], '%Y-%m-%d')
                day_name = days_tr[date_obj.weekday()]

                self.schedule_table.setItem(row, 0, QTableWidgetItem(first_item['date']))
                self.schedule_table.setItem(row, 1, QTableWidgetItem(day_name))
                self.schedule_table.setItem(row, 2, QTableWidgetItem(first_item['time']))
                self.schedule_table.setItem(row, 3, QTableWidgetItem(first_item['code']))
                self.schedule_table.setItem(row, 4, QTableWidgetItem(first_item['name']))

                # Birden fazla derslik varsa hepsini göster
                if len(items) > 1:
                    classroom_info = []
                    for item in items:
                        classroom_info.append(f"{item['classroom']} ({item['students_count']} öğr.)")
                    classroom_text = ' + '.join(classroom_info)
                    classroom_text += f"\n[Toplam: {first_item['total_students']} öğrenci]"
                else:
                    classroom_text = items[0]['classroom']

                classroom_item = QTableWidgetItem(classroom_text)
                if len(items) > 1:
                    classroom_item.setBackground(QColor('#FFF9C4'))
                    classroom_item.setToolTip(f"Bu sınav {len(items)} farklı derslikte yapılacak")
                self.schedule_table.setItem(row, 5, classroom_item)

                # Veritabanına kaydet
                for item in items:
                    cursor.execute(
                        'INSERT INTO exams (course_id, date, time, duration, type, classroom_id) VALUES (?, ?, ?, ?, ?, ?)',
                        (item['course_id'], item['date'], item['time'], item['duration'], exam_type,
                         item['classroom_id'])
                    )

            self.db.conn.commit()

            # İstatistikleri hesapla
            unique_exams = len(exam_groups)
            multi_classroom_exams = sum(1 for items in exam_groups.values() if len(items) > 1)

            info_msg = f'Sınav programı oluşturuldu!\n\n'
            info_msg += f'Toplam {unique_exams} sınav planlandı.\n'
            info_msg += f'{len(dates)} gün kullanıldı.\n'
            if multi_classroom_exams > 0:
                info_msg += f'\n⚠️ {multi_classroom_exams} sınav birden fazla derslikte yapılacak.'
            info_msg += f'\n\n✓ Tüm oturma planları temizlendi.'

            QMessageBox.information(self, 'Başarılı', info_msg)

            self.load_exams()

        except Exception as e:
            QMessageBox.critical(self, 'Hata', f'Program oluşturulurken hata oluştu:\n{str(e)}')
            import traceback
            traceback.print_exc()

    def clear_all_seating_plans(self):
        """Tüm oturma planlarını sil"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute('DELETE FROM seating')
            self.db.conn.commit()

            # Seating tab'ını temizle (varsa)
            if hasattr(self, 'seating_table'):
                self.seating_table.setRowCount(0)
            if hasattr(self, 'seating_view_layout'):
                self.clear_seating_view()
            if hasattr(self, 'seating_view_toggle'):
                self.seating_view_toggle.setVisible(False)
            if hasattr(self, 'seating_view_scroll'):
                self.seating_view_scroll.setVisible(False)

        except Exception as e:
            QMessageBox.warning(self, 'Hata', f'Oturma planları silinirken hata:\n{str(e)}')

    def export_schedule(self):
        if self.schedule_table.rowCount() == 0:
            QMessageBox.warning(self, 'Uyarı', 'Henüz program oluşturulmadı!')
            return

        # DataFrame oluştur
        data = []
        for i in range(self.schedule_table.rowCount()):
            row = []
            for j in range(6):
                item = self.schedule_table.item(i, j)
                row.append(item.text() if item else '')
            data.append(row)

        df = pd.DataFrame(data, columns=['Tarih', 'Gün', 'Saat', 'Ders Kodu', 'Ders Adı', 'Derslik'])

        # Dosya kaydetme dialogu
        file, _ = QFileDialog.getSaveFileName(
            self, 'Sınav Programını Kaydet',
            f'Sinav_Programi_{self.exam_type.currentText()}.xlsx',
            'Excel Files (*.xlsx)'
        )

        if file:
            try:
                # Excel writer ile formatlamayı ekle
                with pd.ExcelWriter(file, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sınav Programı')

                    # Worksheet'i al
                    worksheet = writer.sheets['Sınav Programı']

                    # Sütun genişliklerini ayarla
                    worksheet.column_dimensions['A'].width = 12
                    worksheet.column_dimensions['B'].width = 12
                    worksheet.column_dimensions['C'].width = 8
                    worksheet.column_dimensions['D'].width = 12
                    worksheet.column_dimensions['E'].width = 30
                    worksheet.column_dimensions['F'].width = 40

                QMessageBox.information(self, 'Başarılı', f'Program Excel olarak kaydedildi:\n{file}')
            except Exception as e:
                QMessageBox.critical(self, 'Hata', f'Dosya kaydedilemedi:\n{str(e)}')

    def seating_plan_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        clear_seating_btn = QPushButton('🗑️ Tüm Oturma Planlarını Sil')
        clear_seating_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; padding: 10px; "
            "font-size: 11pt; font-weight: bold; border-radius: 5px; }"
            "QPushButton:hover { background-color: #d32f2f; }"
        )
        clear_seating_btn.clicked.connect(self.clear_all_seating_plans)
        layout.addWidget(clear_seating_btn)

        # Başlık
        title = QLabel('Oturma Planı Oluşturma')
        title.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px; background-color: #E8F5E9;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Sınav listesi
        exams_group = QGroupBox('Planlanan Sınavlar')
        exams_layout = QVBoxLayout()

        info_label = QLabel('Oturma planı oluşturmak için listeden bir sınav seçin.')
        info_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        exams_layout.addWidget(info_label)

        self.seating_table = QTableWidget()
        self.seating_table.setColumnCount(6)
        self.seating_table.setHorizontalHeaderLabels(['Sınav', 'Tarih', 'Gün', 'Saat', 'Derslik', 'Durum'])
        self.seating_table.horizontalHeader().setStretchLastSection(True)
        self.seating_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.seating_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.load_exams()
        exams_layout.addWidget(self.seating_table)

        # Butonlar
        button_layout = QHBoxLayout()

        generate_btn = QPushButton('🪑 Oturma Planı Oluştur')
        generate_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; padding: 10px; "
            "font-size: 11pt; font-weight: bold; border-radius: 5px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        generate_btn.clicked.connect(self.generate_seating)
        button_layout.addWidget(generate_btn)

        view_btn = QPushButton('👁️ Planı Görüntüle')
        view_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; padding: 10px; "
            "font-size: 11pt; font-weight: bold; border-radius: 5px; }"
            "QPushButton:hover { background-color: #0b7dda; }"
        )
        view_btn.clicked.connect(self.view_seating_plan)
        button_layout.addWidget(view_btn)

        export_pdf_btn = QPushButton('📄 PDF İndir')
        export_pdf_btn.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; padding: 10px; "
            "font-size: 11pt; font-weight: bold; border-radius: 5px; }"
            "QPushButton:hover { background-color: #e68900; }"
        )
        export_pdf_btn.clicked.connect(self.export_seating_pdf)
        button_layout.addWidget(export_pdf_btn)

        exams_layout.addLayout(button_layout)
        exams_group.setLayout(exams_layout)
        layout.addWidget(exams_group)

        # Oturma planı görselleştirme alanı (açılır/kapanır)
        self.seating_view_toggle = QPushButton('▼ Oturma Düzeni Görselleştirmesi')
        self.seating_view_toggle.setStyleSheet(
            "QPushButton { text-align: left; padding: 8px; background-color: #E8F5E9; border: 1px solid #4CAF50; }"
            "QPushButton:hover { background-color: #C8E6C9; }"
        )
        self.seating_view_toggle.clicked.connect(self.toggle_seating_view)
        self.seating_view_toggle.setVisible(False)
        layout.addWidget(self.seating_view_toggle)

        # Görselleştirme scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(500)

        view_widget = QWidget()
        self.seating_view_layout = QVBoxLayout()
        view_widget.setLayout(self.seating_view_layout)

        scroll.setWidget(view_widget)
        scroll.setVisible(False)
        scroll.setStyleSheet("background-color: white; border: 1px solid #ddd;")
        self.seating_view_scroll = scroll
        layout.addWidget(scroll)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def clear_all_seating_plans(self):
        cursor = self.db.conn.cursor()
        cursor.execute('DELETE FROM seating')
        self.db.conn.commit()
        self.refresh_seating_tab()
        QMessageBox.information(self, 'Başarılı', 'Tüm oturma planları silindi.')

    def toggle_seating_view(self):
        is_visible = self.seating_view_scroll.isVisible()
        self.seating_view_scroll.setVisible(not is_visible)

        if is_visible:
            self.seating_view_toggle.setText('▼ Oturma Düzeni Görselleştirmesi')
        else:
            self.seating_view_toggle.setText('▲ Oturma Düzeni Görselleştirmesi')

    def load_exams(self):
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else '%'

        cursor.execute('''
            SELECT e.id, c.code, c.name, e.date, e.time, cl.code, cl.name, cl.capacity
            FROM exams e
            JOIN courses c ON e.course_id = c.id
            JOIN classrooms cl ON e.classroom_id = cl.id
            WHERE c.department_id LIKE ?
            ORDER BY e.date, e.time
        ''', (dep_id,))

        exams = cursor.fetchall()
        self.seating_table.setRowCount(len(exams))

        days_tr = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']

        for i, (exam_id, code, name, date, time, cl_code, cl_name, capacity) in enumerate(exams):
            # Sınav - Exam ID'yi gizli tut
            item = QTableWidgetItem(f'{code} - {name}')
            item.setData(Qt.UserRole, exam_id)  # Exam ID'yi sakla
            self.seating_table.setItem(i, 0, item)

            # Tarih
            self.seating_table.setItem(i, 1, QTableWidgetItem(date))

            # Gün
            try:
                date_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
                day_name = days_tr[date_obj.weekday()]
            except:
                day_name = ''
            self.seating_table.setItem(i, 2, QTableWidgetItem(day_name))

            # Saat
            self.seating_table.setItem(i, 3, QTableWidgetItem(time))

            # Derslik
            self.seating_table.setItem(i, 4, QTableWidgetItem(f'{cl_code} - {cl_name} (Kap: {capacity})'))

            # Durum kontrolü - Oturma planı var mı?
            cursor.execute('SELECT COUNT(*) FROM seating WHERE exam_id = ?', (exam_id,))
            seating_count = cursor.fetchone()[0]

            status_item = QTableWidgetItem('✓ Oluşturuldu' if seating_count > 0 else '✗ Henüz yok')
            status_item.setForeground(QColor('#4CAF50') if seating_count > 0 else QColor('#999'))
            self.seating_table.setItem(i, 5, status_item)

    def generate_seating(self):
        """Oturma planı oluşturma - Çoklu derslik destekli, RASTGELE yerleştirme"""
        row = self.seating_table.currentRow()

        if row < 0:
            QMessageBox.warning(self, 'Uyarı', 'Lütfen listeden bir sınav seçin!')
            return

        exam_id = self.seating_table.item(row, 0).data(Qt.UserRole)
        cursor = self.db.conn.cursor()

        # Seçilen sınav bilgilerini çek
        cursor.execute('''
            SELECT e.id, e.course_id, c.code, c.name, e.date, e.time, e.type, e.classroom_id
            FROM exams e
            JOIN courses c ON e.course_id = c.id
            WHERE e.id = ?
        ''', (exam_id,))

        exam = cursor.fetchone()

        if not exam:
            QMessageBox.warning(self, 'Hata', 'Sınav bulunamadı!')
            return

        selected_exam_id, course_id, code, name, date, time, exam_type, classroom_id = exam

        # Aynı ders, tarih ve saatte olan TÜM sınav kayıtlarını çek (birden fazla derslik)
        cursor.execute('''
            SELECT e.id, e.classroom_id, cl.code, cl.name, cl.rows, cl.columns, cl.capacity, cl.seat_group
            FROM exams e
            JOIN classrooms cl ON e.classroom_id = cl.id
            WHERE e.course_id = ? AND e.date = ? AND e.time = ?
            ORDER BY cl.code
        ''', (course_id, date, time))

        exam_classrooms = cursor.fetchall()

        if not exam_classrooms:
            QMessageBox.warning(self, 'Hata', 'Derslik bulunamadı!')
            return

        # Öğrencileri çek
        cursor.execute('''
            SELECT s.id, s.number, s.name
            FROM students s
            JOIN student_courses sc ON s.id = sc.student_id
            WHERE sc.course_id = ?
            ORDER BY s.number
        ''', (course_id,))

        students = cursor.fetchall()

        if not students:
            QMessageBox.warning(self, 'Hata', f'Ders {code} için öğrenci bulunamadı!')
            return

        # Toplam kapasite hesapla (capacity alanından)
        total_capacity = sum(capacity for _, _, _, _, _, _, capacity, _ in exam_classrooms)

        if len(students) > total_capacity:
            classroom_list = '\n'.join([
                f'  • {cl_code} - {cl_name} (Kapasite: {capacity})'
                for _, _, cl_code, cl_name, _, _, capacity, _ in exam_classrooms
            ])

            QMessageBox.warning(
                self, 'Kapasite Yetersiz',
                f'Toplam derslik kapasitesi yetersiz!\n\n'
                f'Öğrenci sayısı: {len(students)}\n'
                f'Toplam kapasite: {total_capacity}\n'
                f'Eksik: {len(students) - total_capacity} koltuk\n\n'
                f'Ders: {code} - {name}\n\n'
                f'Kullanılan derslikler:\n{classroom_list}'
            )
            return

        # Derslik bilgilerini göster
        classroom_info = '\n'.join([
            f'  • {cl_code} - {cl_name} (Kapasite: {capacity})'
            for _, _, cl_code, cl_name, _, _, capacity, _ in exam_classrooms
        ])

        reply = QMessageBox.question(
            self, 'Oturma Planı Oluştur',
            f'Sınav: {code} - {name}\n'
            f'Tarih: {date} {time}\n'
            f'Öğrenci: {len(students)}\n'
            f'Toplam Kapasite: {total_capacity}\n\n'
            f'Kullanılacak Derslikler ({len(exam_classrooms)} adet):\n{classroom_info}\n\n'
            f'⚠️ Öğrenciler RASTGELE yerleştirilecektir\n\n'
            f'Oturma planı oluşturulsun mu?\n'
            f'(Tüm dersliklerdeki mevcut planlar silinecek)',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        try:
            # Tüm ilgili sınav kayıtları için eski oturma planlarını sil
            exam_ids = [e_id for e_id, _, _, _, _, _, _, _ in exam_classrooms]
            cursor.executemany('DELETE FROM seating WHERE exam_id = ?', [(e_id,) for e_id in exam_ids])

            # Öğrencileri karıştır
            student_list = list(students)
            random.shuffle(student_list)

            # Öğrencileri dersliklere RASTGELE dağıt
            student_index = 0
            total_placed = 0
            placement_info = []

            for e_id, cl_id, cl_code, cl_name, rows, columns, capacity, seat_group in exam_classrooms:
                # Bu derslik için tüm koltuk pozisyonlarını oluştur
                all_seats = []
                for r in range(rows):
                    for c in range(columns):
                        available_positions = []
                        if seat_group == 2:
                            available_positions = [2]  # sıranın sağına
                        elif seat_group == 3:
                            available_positions = [1, 3]  # bir sağ bir sol
                        elif seat_group == 4:
                            available_positions = [1, 4]  # bir sağ bir sol, ortası boş
                        for s in available_positions:
                            seat_col = c * seat_group + s
                            all_seats.append((r + 1, seat_col))

                # Koltukları RASTGELE karıştır
                random.shuffle(all_seats)

                placed_in_classroom = 0

                # Bu derslikteki kapasiteye kadar öğrenci yerleştir
                for seat_row, seat_col in all_seats:
                    if student_index < len(student_list) and placed_in_classroom < capacity:
                        student_id, number, student_name = student_list[student_index]

                        # Veritabanına kaydet
                        cursor.execute(
                            'INSERT INTO seating (exam_id, student_id, classroom_id, row, col) VALUES (?, ?, ?, ?, ?)',
                            (e_id, student_id, cl_id, seat_row, seat_col)
                        )

                        student_index += 1
                        placed_in_classroom += 1
                        total_placed += 1
                    else:
                        break

                placement_info.append(f'{cl_code}: {placed_in_classroom} öğrenci')

            self.db.conn.commit()

            # Durum sütununu güncelle
            status_item = QTableWidgetItem('✓ Oluşturuldu')
            status_item.setForeground(QColor('#4CAF50'))
            self.seating_table.setItem(row, 5, status_item)

            # Diğer ilgili satırları da güncelle
            if len(exam_classrooms) > 1:
                for i in range(self.seating_table.rowCount()):
                    item_exam_id = self.seating_table.item(i, 0).data(Qt.UserRole)
                    if item_exam_id in exam_ids and i != row:
                        status_item2 = QTableWidgetItem('✓ Oluşturuldu')
                        status_item2.setForeground(QColor('#4CAF50'))
                        self.seating_table.setItem(i, 5, status_item2)

            QMessageBox.information(
                self, 'Başarılı',
                f'✅ Oturma planı RASTGELE oluşturuldu!\n\n'
                f'Sınav: {code} - {name}\n'
                f'Toplam: {total_placed} öğrenci yerleştirildi\n\n'
                f'Derslik Dağılımı:\n' + '\n'.join([f'  • {info}' for info in placement_info])
            )

            # Planı otomatik göster
            self.view_seating_plan()

        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(self, 'Hata', f'Oturma planı oluşturulamadı:\n{str(e)}')

    def view_seating_plan(self):
        """Oturma planını görselleştir - Çoklu derslik destekli"""
        row = self.seating_table.currentRow()

        if row < 0:
            QMessageBox.warning(self, 'Uyarı', 'Lütfen listeden bir sınav seçin!')
            return

        exam_id = self.seating_table.item(row, 0).data(Qt.UserRole)
        cursor = self.db.conn.cursor()

        # Seçilen sınav bilgilerini çek
        cursor.execute('''
            SELECT e.id, e.course_id, c.code, c.name, e.date, e.time
            FROM exams e
            JOIN courses c ON e.course_id = c.id
            WHERE e.id = ?
        ''', (exam_id,))

        exam = cursor.fetchone()

        if not exam:
            QMessageBox.warning(self, 'Hata', 'Sınav bulunamadı!')
            return

        exam_id, course_id, code, name, date, time = exam

        # Aynı ders, tarih ve saatte olan tüm sınav kayıtlarını bul
        cursor.execute('''
            SELECT e.id
            FROM exams e
            WHERE e.course_id = ? AND e.date = ? AND e.time = ?
        ''', (course_id, date, time))

        exam_ids = [e[0] for e in cursor.fetchall()]

        if not exam_ids:
            QMessageBox.information(
                self, 'Bilgi',
                'Bu sınav için henüz oturma planı oluşturulmamış.'
            )
            return

        # Bu sınav grubu için kullanılan tüm derslikleri çek
        placeholders = ','.join('?' * len(exam_ids))
        cursor.execute(f'''
            SELECT DISTINCT cl.id, cl.code, cl.name, cl.rows, cl.columns, st.exam_id, cl.seat_group
            FROM seating st
            JOIN classrooms cl ON st.classroom_id = cl.id
            WHERE st.exam_id IN ({placeholders})
            ORDER BY cl.code
        ''', exam_ids)

        classrooms_data = cursor.fetchall()

        if not classrooms_data:
            QMessageBox.information(
                self, 'Bilgi',
                'Bu sınav için henüz oturma planı oluşturulmamış.\n\n'
                '"Oturma Planı Oluştur" butonuna tıklayarak plan oluşturabilirsiniz.'
            )
            return

        # Görselleştirmeyi temizle
        self.clear_seating_view()

        # Ana başlık
        title_label = QLabel(
            f'<div style="text-align: center;">'
            f'<h2 style="margin: 5px;">{code} - {name}</h2>'
            f'<p style="margin: 3px;"><b>Tarih:</b> {date} | <b>Saat:</b> {time}</p>'
            f'<p style="margin: 3px; color: #666;"><i>{len(classrooms_data)} derslikte oturma planı</i></p>'
            f'</div>'
        )
        title_label.setStyleSheet(
            "background-color: #E8F5E9; padding: 15px; border-radius: 5px; "
            "border: 2px solid #4CAF50;"
        )
        self.seating_view_layout.addWidget(title_label)

        # Her derslik için ayrı görselleştirme
        total_students = 0

        for classroom_id, cl_code, cl_name, rows, columns, related_exam_id, seat_group in classrooms_data:
            # Derslik başlığı
            classroom_title = QLabel(
                f'<div style="text-align: center;">'
                f'<h3 style="margin: 8px;">{cl_code} - {cl_name}</h3>'
                f'<p style="margin: 3px; color: #666;">Düzen: {rows}x{columns} (Yapı: {seat_group}\'li)</p>'
                f'</div>'
            )
            classroom_title.setStyleSheet(
                "background-color: #E3F2FD; padding: 10px; border-radius: 5px; "
                "border: 1px solid #2196F3; margin-top: 15px;"
            )
            self.seating_view_layout.addWidget(classroom_title)

            # Bu derslik için oturma planını çek
            cursor.execute('''
                SELECT st.row, st.col, s.number, s.name
                FROM seating st
                JOIN students s ON st.student_id = s.id
                WHERE st.exam_id = ? AND st.classroom_id = ?
                ORDER BY st.row, st.col
            ''', (related_exam_id, classroom_id))

            seating_data = cursor.fetchall()
            total_students += len(seating_data)

            # Oturma düzeni grid
            seating_grid = QGridLayout()
            seating_grid.setSpacing(5)

            # Seating data'yı dict'e çevir
            seating_dict = {(r, c): (num, name) for r, c, num, name in seating_data}

            for r in range(rows):
                col_idx = 0
                for c in range(columns):
                    if c > 0:
                        spacer = QLabel()
                        spacer.setFixedWidth(20)
                        seating_grid.addWidget(spacer, r, col_idx)
                        col_idx += 1

                    for s in range(seat_group):
                        global_col = c * seat_group + s + 1
                        if (r + 1, global_col) in seating_dict:
                            number, student_name = seating_dict[(r + 1, global_col)]

                            # Öğrenci butonu
                            btn = QPushButton(f'{number}\n{student_name}')
                            btn.setStyleSheet(
                                "QPushButton { background-color: #81C784; color: white; "
                                "border: 2px solid #4CAF50; border-radius: 5px; "
                                "font-weight: bold; padding: 5px; font-size: 9pt; }"
                                "QPushButton:hover { background-color: #66BB6A; }"
                            )
                            btn.setFixedSize(120, 60)
                            btn.setToolTip(f'Sıra {r + 1}, Grup {c + 1}, Koltuk {s + 1}\n{number} - {student_name}')
                            seating_grid.addWidget(btn, r, col_idx)
                        else:
                            # Boş koltuk
                            empty_label = QLabel('Boş')
                            empty_label.setStyleSheet(
                                "background-color: #EEEEEE; border: 1px dashed #BDBDBD; "
                                "border-radius: 5px; color: #757575;"
                            )
                            empty_label.setAlignment(Qt.AlignCenter)
                            empty_label.setFixedSize(120, 60)
                            seating_grid.addWidget(empty_label, r, col_idx)

                        col_idx += 1

            grid_widget = QWidget()
            grid_widget.setLayout(seating_grid)
            self.seating_view_layout.addWidget(grid_widget)

            # Derslik istatistikleri
            classroom_stats = QLabel(
                f'<div style="text-align: center; padding: 8px;">'
                f'<i>{cl_code}: <b>{len(seating_data)}</b> öğrenci</i>'
                f'</div>'
            )
            classroom_stats.setStyleSheet(
                "color: #666; background-color: #f5f5f5; border-radius: 3px; margin-bottom: 10px;"
            )
            self.seating_view_layout.addWidget(classroom_stats)

        # Genel istatistikler
        total_stats_label = QLabel(
            f'<div style="text-align: center; padding: 12px;">'
            f'<b style="font-size: 11pt;">Toplam: {total_students} öğrenci, {len(classrooms_data)} derslik</b>'
            f'</div>'
        )
        total_stats_label.setStyleSheet(
            "color: #333; background-color: #FFF9C4; border-radius: 5px; "
            "border: 2px solid #FFC107; margin-top: 10px;"
        )
        self.seating_view_layout.addWidget(total_stats_label)

        # Görselleştirme alanını göster
        self.seating_view_toggle.setVisible(True)
        self.seating_view_toggle.setText('▲ Oturma Düzeni Görselleştirmesi')
        self.seating_view_scroll.setVisible(True)

    def clear_seating_view(self):
        """Oturma planı görselleştirme alanını temizle"""
        while self.seating_view_layout.count():
            item = self.seating_view_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # PDF export fonksiyonunu tamamen değiştirelim
    def export_seating_pdf(self):
        """Oturma planını PDF olarak kaydet - Türkçe karakter destekli"""
        row = self.seating_table.currentRow()

        if row < 0:
            QMessageBox.warning(self, 'Uyarı', 'Lütfen listeden bir sınav seçin!')
            return

        exam_id = self.seating_table.item(row, 0).data(Qt.UserRole)
        cursor = self.db.conn.cursor()

        # Sınav bilgilerini çek
        cursor.execute('''
            SELECT e.course_id, c.code, c.name, e.date, e.time, e.type
            FROM exams e
            JOIN courses c ON e.course_id = c.id
            WHERE e.id = ?
        ''', (exam_id,))

        exam = cursor.fetchone()

        if not exam:
            QMessageBox.warning(self, 'Hata', 'Sınav bulunamadı!')
            return

        course_id, code, name, date, time, exam_type = exam

        # Aynı ders için tüm derslik kayıtlarını bul
        cursor.execute('''
            SELECT e.id
            FROM exams e
            WHERE e.course_id = ? AND e.date = ? AND e.time = ?
        ''', (course_id, date, time))

        exam_ids = [e[0] for e in cursor.fetchall()]

        # Derslikleri çek
        placeholders = ','.join('?' * len(exam_ids))
        cursor.execute(f'''
            SELECT DISTINCT cl.id, cl.code, cl.name, cl.rows, cl.columns, st.exam_id
            FROM seating st
            JOIN classrooms cl ON st.classroom_id = cl.id
            WHERE st.exam_id IN ({placeholders})
            ORDER BY cl.code
        ''', exam_ids)

        classrooms_data = cursor.fetchall()

        if not classrooms_data:
            QMessageBox.warning(self, 'Uyarı', 'Bu sınav için oturma planı oluşturulmamış!')
            return

        # Dosya kaydetme dialogu
        file, _ = QFileDialog.getSaveFileName(
            self, 'PDF Kaydet',
            f'Oturma_Plani_{code}_{date}.pdf',
            'PDF Files (*.pdf)'
        )

        if not file:
            return

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import cm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            # DejaVu Sans fontunu kaydet (Türkçe karakter destekli)
            try:
                pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
                pdfmetrics.registerFont(TTFont('DejaVu-Bold', 'DejaVuSans-Bold.ttf'))
                font_name = 'DejaVu'
                font_bold = 'DejaVu-Bold'
            except:
                # Font bulunamazsa varsayılan Helvetica kullan
                font_name = 'Helvetica'
                font_bold = 'Helvetica-Bold'

            # PDF oluştur
            doc = SimpleDocTemplate(file, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
            elements = []
            styles = getSampleStyleSheet()

            # Özel stiller
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontName=font_bold,
                fontSize=18,
                textColor=colors.HexColor('#1976D2'),
                alignment=1  # Center
            )

            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontName=font_bold,
                fontSize=14,
                textColor=colors.HexColor('#424242')
            )

            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=10
            )

            total_students = 0

            # Ana başlık
            elements.append(Paragraph('OTURMA PLANI', title_style))
            elements.append(Spacer(1, 0.5 * cm))

            # Sınav bilgileri
            exam_info = [
                ['Sınav:', f'{code} - {name}'],
                ['Sınav Türü:', exam_type],
                ['Tarih:', date],
                ['Saat:', time]
            ]

            info_table = Table(exam_info, colWidths=[4 * cm, 12 * cm])
            info_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), font_bold),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E3F2FD')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')])
            ]))
            elements.append(info_table)
            elements.append(Spacer(1, 1 * cm))

            # Her derslik için
            for idx, (classroom_id, cl_code, cl_name, rows, cols, related_exam_id) in enumerate(classrooms_data):

                if idx > 0:
                    elements.append(PageBreak())

                # Derslik başlığı
                elements.append(Paragraph(f'Derslik: {cl_code} - {cl_name}', heading_style))
                elements.append(Paragraph(f'Düzeni: {rows} sıra × {cols} sütun', normal_style))
                elements.append(Spacer(1, 0.5 * cm))

                # Oturma planını çek
                cursor.execute('''
                    SELECT st.row, st.col, s.number, s.name
                    FROM seating st
                    JOIN students s ON st.student_id = s.id
                    WHERE st.exam_id = ? AND st.classroom_id = ?
                    ORDER BY st.row, st.col
                ''', (related_exam_id, classroom_id))

                seating_data = cursor.fetchall()
                total_students += len(seating_data)

                # Tablo verileri
                table_data = [['Sıra', 'Sütun', 'Öğrenci No', 'Ad Soyad']]

                for r, c, number, student_name in seating_data:
                    table_data.append([str(r), str(c), str(number), student_name])

                # Tablo oluştur
                seating_table = Table(table_data, colWidths=[2 * cm, 2 * cm, 4 * cm, 8 * cm])
                seating_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, 0), font_bold),
                    ('FONTNAME', (0, 1), (-1, -1), font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (2, -1), 'CENTER'),
                    ('ALIGN', (3, 0), (3, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F8E9')])
                ]))
                elements.append(seating_table)
                elements.append(Spacer(1, 0.5 * cm))

                # Derslik özeti
                classroom_summary = Paragraph(
                    f'<b>{cl_code}:</b> {len(seating_data)} öğrenci',
                    normal_style
                )
                elements.append(classroom_summary)

            # Genel özet
            elements.append(PageBreak())
            elements.append(Paragraph('GENEL ÖZET', heading_style))
            elements.append(Spacer(1, 0.5 * cm))

            summary_data = [['Toplam Öğrenci:', str(total_students)],
                            ['Toplam Derslik:', str(len(classrooms_data))]]

            summary_table = Table(summary_data, colWidths=[6 * cm, 10 * cm])
            summary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), font_bold),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FFF9C4')),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            elements.append(summary_table)

            # Alt bilgi
            elements.append(Spacer(1, 2 * cm))
            footer_text = f'Oluşturulma: {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}'
            elements.append(Paragraph(footer_text, normal_style))

            # PDF'i oluştur
            doc.build(elements)

            QMessageBox.information(
                self, 'Başarılı',
                f'Oturma planı PDF olarak kaydedildi:\n\n{file}\n\n'
                f'İçerik: {len(classrooms_data)} derslik, {total_students} öğrenci'
            )

        except ImportError:
            QMessageBox.critical(
                self, 'Hata',
                'ReportLab kütüphanesi bulunamadı!\n\n'
                'Lütfen şu komutu çalıştırın:\n'
                'pip install reportlab'
            )
        except Exception as e:
            QMessageBox.critical(self, 'Hata', f'PDF oluşturulamadı:\n\n{str(e)}')
            import traceback
            traceback.print_exc()





if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

