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
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QComboBox, QDateEdit,
    QCheckBox, QGridLayout, QFileDialog, QInputDialog, QTabWidget, QSpacerItem, QSizePolicy,
    QScrollArea, QGroupBox
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QColor
from fpdf import FPDF
import datetime
import random
import pulp

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
        login_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; border: none; border-radius: 4px;")
        login_btn.clicked.connect(self.login)
        layout.addWidget(login_btn)
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.setLayout(layout)

    def login(self):
        email = self.email.text()
        password = self.password.text()
        db = Database()
        cursor = db.conn.cursor()
        cursor.execute('SELECT id, role, department_id FROM users WHERE email=? AND password=?', (email, password))
        user = cursor.fetchone()
        if user:
            self.parent.user = {'id': user[0], 'role': user[1], 'department_id': user[2]}
            self.parent.show_main_window()
        else:
            QMessageBox.warning(self, 'Hata', 'Geçersiz kimlik bilgileri')
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
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("QTabWidget::tab { background: #e0e0e0; padding: 10px; }")

        if self.user['role'] == 'Admin':
            self.tab_widget.addTab(self.admin_tab(), 'Admin İşlemleri')

        classroom_tab = self.classroom_tab()
        self.tab_widget.addTab(classroom_tab, 'Derslik Girişi')

        dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else None
        has_classrooms = self.db.has_classrooms(dep_id) if dep_id else True

        if has_classrooms:
            course_upload_tab = self.course_upload_tab()
            self.tab_widget.addTab(course_upload_tab, 'Ders Listesi Yükle')
            student_upload_tab = self.student_upload_tab()
            self.tab_widget.addTab(student_upload_tab, 'Öğrenci Listesi Yükle')

            has_courses = self.db.has_courses(dep_id) if dep_id else True
            if has_courses:
                self.tab_widget.addTab(self.student_list_tab(), 'Öğrenci Listesi')
                self.tab_widget.addTab(self.course_list_tab(), 'Ders Listesi')

            has_students = self.db.has_students(dep_id) if dep_id else True
            if has_students and has_courses:
                self.tab_widget.addTab(self.exam_schedule_tab(), 'Sınav Programı Oluştur')
                self.tab_widget.addTab(self.seating_plan_tab(), 'Oturma Planı')
            elif has_courses and not has_students:
                note = QLabel('Öğrenci listesi yüklenmeden sınav programı oluşturulamaz.')
                note.setStyleSheet("color: red; font-weight: bold;")
                layout.addWidget(note)
        else:
            note = QLabel('Derslik bilgileri girilmeden diğer işlemler yapılamaz.')
            note.setStyleSheet("color: red; font-weight: bold;")
            layout.addWidget(note)

        layout.addWidget(self.tab_widget)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def refresh_tabs(self):
        self.show_main_window()

    def admin_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        add_user_btn = QPushButton('Yeni Kullanıcı Ekle')
        add_user_btn.clicked.connect(self.add_user)
        layout.addWidget(add_user_btn)
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        widget.setLayout(layout)
        return widget

    def add_user(self):
        email, ok = QInputDialog.getText(self, 'Yeni Kullanıcı', 'E-posta:')
        if not ok: return
        password, ok = QInputDialog.getText(self, 'Yeni Kullanıcı', 'Şifre:')
        if not ok: return
        role = 'Bölüm Koordinatörü'
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT id, name FROM departments')
        deps = cursor.fetchall()
        dep_names = [d[1] for d in deps]
        dep_name, ok = QInputDialog.getItem(self, 'Bölüm Seç', 'Bölüm:', dep_names, 0, False)
        if not ok: return
        dep_id = next(d[0] for d in deps if d[1] == dep_name)
        try:
            cursor.execute('INSERT INTO users (email, password, role, department_id) VALUES (?, ?, ?, ?)',
                           (email, password, role, dep_id))
            self.db.conn.commit()
            QMessageBox.information(self, 'Başarılı', 'Kullanıcı eklendi')
        except:
            QMessageBox.warning(self, 'Hata', 'E-posta zaten kayıtlı')

    def classroom_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        if self.user['role'] != 'Bölüm Koordinatörü':
            label = QLabel('Yetkiniz yok')
            layout.addWidget(label)
            widget.setLayout(layout)
            return widget

        form_group = QGroupBox('Derslik Ekle/Düzenle')
        form_layout = QGridLayout()
        self.class_code = QLineEdit(); form_layout.addWidget(QLabel('Derslik Kodu'), 0, 0); form_layout.addWidget(self.class_code, 0, 1)
        self.class_name = QLineEdit(); form_layout.addWidget(QLabel('Derslik Adı'), 1, 0); form_layout.addWidget(self.class_name, 1, 1)
        self.class_capacity = QLineEdit(); form_layout.addWidget(QLabel('Kapasite'), 2, 0); form_layout.addWidget(self.class_capacity, 2, 1)
        self.class_rows = QLineEdit(); form_layout.addWidget(QLabel('Satır Sayısı'), 3, 0); form_layout.addWidget(self.class_rows, 3, 1)
        self.class_columns = QLineEdit(); form_layout.addWidget(QLabel('Sütun Sayısı'), 4, 0); form_layout.addWidget(self.class_columns, 4, 1)
        self.class_seat_group = QComboBox(); self.class_seat_group.addItems(['2', '3']); form_layout.addWidget(QLabel('Sıra Yapısı'), 5, 0); form_layout.addWidget(self.class_seat_group, 5, 1)

        add_btn = QPushButton('Ekle')
        add_btn.clicked.connect(self.add_classroom)
        form_layout.addWidget(add_btn, 6, 0)
        edit_btn = QPushButton('Düzenle')
        edit_btn.clicked.connect(self.edit_classroom)
        form_layout.addWidget(edit_btn, 6, 1)
        delete_btn = QPushButton('Sil')
        delete_btn.clicked.connect(self.delete_classroom)
        form_layout.addWidget(delete_btn, 6, 2)
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        search_layout = QHBoxLayout()
        self.search_class_id = QLineEdit(); search_layout.addWidget(QLabel('Arama (ID)')); search_layout.addWidget(self.search_class_id)
        search_btn = QPushButton('Ara')
        search_btn.clicked.connect(self.search_classroom)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)

        self.classroom_table = QTableWidget()
        self.classroom_table.setHorizontalHeaderLabels(['ID', 'Kod', 'Ad', 'Kapasite', 'Satır', 'Sütun', 'Grup'])
        self.load_classrooms()
        self.classroom_table.cellClicked.connect(self.load_classroom_for_edit)
        layout.addWidget(self.classroom_table)

        self.classroom_view = QGridLayout()
        view_group = QGroupBox('Oturma Düzeni Görselleştirme')
        view_group.setLayout(self.classroom_view)
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_widget.setLayout(self.classroom_view)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        widget.setLayout(layout)
        return widget

    def load_classrooms(self):
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id']
        cursor.execute('SELECT id, code, name, capacity, rows, columns, seat_group FROM classrooms WHERE department_id=?', (dep_id,))
        classrooms = cursor.fetchall()
        self.classroom_table.setRowCount(len(classrooms))
        for i, row in enumerate(classrooms):
            for j, val in enumerate(row):
                self.classroom_table.setItem(i, j, QTableWidgetItem(str(val)))

    def add_classroom(self):
        self.modify_classroom('add')

    def edit_classroom(self):
        self.modify_classroom('edit')

    def modify_classroom(self, mode):
        code = self.class_code.text()
        name = self.class_name.text()
        capacity = self.class_capacity.text()
        rows = self.class_rows.text()
        columns = self.class_columns.text()
        seat_group = self.class_seat_group.currentText()
        if not all([code, name, capacity, rows, columns]):
            QMessageBox.warning(self, 'Hata', 'Tüm alanları doldurun')
            return
        try:
            capacity = int(capacity)
            rows = int(rows)
            columns = int(columns)
            seat_group = int(seat_group)
        except ValueError:
            QMessageBox.warning(self, 'Hata', 'Sayısal değerler girin')
            return
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id']
        if mode == 'add':
            try:
                cursor.execute('INSERT INTO classrooms (department_id, code, name, capacity, rows, columns, seat_group) VALUES (?, ?, ?, ?, ?, ?, ?)',
                               (dep_id, code, name, capacity, rows, columns, seat_group))
                QMessageBox.information(self, 'Başarılı', 'Derslik eklendi')
            except:
                QMessageBox.warning(self, 'Hata', 'Derslik kodu benzersiz olmalı')
        elif mode == 'edit':
            class_id = self.search_class_id.text()
            if not class_id:
                QMessageBox.warning(self, 'Hata', 'Düzenlemek için ID girin veya tablodan seçin')
                return
            cursor.execute('UPDATE classrooms SET code=?, name=?, capacity=?, rows=?, columns=?, seat_group=? WHERE id=? AND department_id=?',
                           (code, name, capacity, rows, columns, seat_group, class_id, dep_id))
            QMessageBox.information(self, 'Başarılı', 'Derslik güncellendi')
        self.db.conn.commit()
        self.load_classrooms()
        self.clear_class_form()
        self.refresh_tabs()

    def delete_classroom(self):
        class_id = self.search_class_id.text()
        if not class_id:
            QMessageBox.warning(self, 'Hata', 'Silmek için ID girin')
            return
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id']
        cursor.execute('DELETE FROM classrooms WHERE id=? AND department_id=?', (class_id, dep_id))
        self.db.conn.commit()
        QMessageBox.information(self, 'Başarılı', 'Derslik silindi')
        self.load_classrooms()
        self.clear_class_form()
        self.refresh_tabs()

    def load_classroom_for_edit(self, row, col):
        class_id = self.classroom_table.item(row, 0).text()
        self.search_class_id.setText(class_id)
        self.search_classroom()

    def search_classroom(self):
        class_id = self.search_class_id.text()
        if not class_id:
            return
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id']
        cursor.execute('SELECT code, name, capacity, rows, columns, seat_group FROM classrooms WHERE id=? AND department_id=?', (class_id, dep_id))
        classroom = cursor.fetchone()
        if classroom:
            self.class_code.setText(classroom[0])
            self.class_name.setText(classroom[1])
            self.class_capacity.setText(str(classroom[2]))
            self.class_rows.setText(str(classroom[3]))
            self.class_columns.setText(str(classroom[4]))
            self.class_seat_group.setCurrentText(str(classroom[5]))
            self.clear_view(self.classroom_view)
            for r in range(classroom[3]):
                for c in range(classroom[4]):
                    btn = QPushButton(f'{r+1}-{c+1}')
                    btn.setStyleSheet("background-color: #90CAF9; border: 1px solid #2196F3; border-radius: 4px;")
                    btn.setFixedSize(50, 30)
                    self.classroom_view.addWidget(btn, r, c)
        else:
            QMessageBox.warning(self, 'Hata', 'Bulunamadı')

    def clear_class_form(self):
        self.class_code.clear()
        self.class_name.clear()
        self.class_capacity.clear()
        self.class_rows.clear()
        self.class_columns.clear()
        self.search_class_id.clear()
        self.clear_view(self.classroom_view)

    def clear_view(self, view_layout):
        for i in reversed(range(view_layout.count())):
            view_layout.itemAt(i).widget().setParent(None)

    def course_upload_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        upload_btn = QPushButton('Excel Yükle')
        upload_btn.clicked.connect(self.upload_courses)
        layout.addWidget(upload_btn)
        self.course_status = QLabel('Dersler yüklenmedi.')
        self.course_status.setStyleSheet("color: #333;")
        layout.addWidget(self.course_status)
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        widget.setLayout(layout)
        return widget

    def upload_courses(self):
        file, _ = QFileDialog.getOpenFileName(self, 'Excel Seç')
        if not file: return
        try:
            df = pd.read_excel(file)
            cursor = self.db.conn.cursor()
            dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else 1
            errors = []
            current_year = None
            inserted_courses = 0
            for idx, row in df.iterrows():
                if pd.isna(row.get('DERS KODU')) and str(row.get('DERSİN ADI', '')).startswith(tuple(str(i) for i in range(1, 6)) + ('SEÇMELİ', 'SEÇİMLİK')):
                    current_year = int(str(row['DERSİN ADI']).split('.')[0]) if '.' in str(row['DERSİN ADI']) else None
                elif pd.notna(row.get('DERS KODU')):
                    required_cols = ['DERS KODU', 'DERSİN ADI', 'DERSİ VEREN ÖĞR. ELEMANI']
                    if not all(col in df.columns for col in required_cols):
                        errors.append(f'Satır {idx+1}: Gerekli sütunlar eksik - {", ".join(required_cols)}')
                        continue
                    code = str(row['DERS KODU']).strip()
                    name = row['DERSİN ADI']
                    instructor = row.get('DERSİ VEREN ÖĞR. ELEMANI', '')
                    year = current_year if current_year else 1
                    course_type = 'Zorunlu' if pd.notna(current_year) and current_year is not None else 'Seçmeli'
                    cursor.execute('INSERT OR IGNORE INTO courses (department_id, code, name, instructor, year, type) VALUES (?, ?, ?, ?, ?, ?)',
                                   (dep_id, code, name, instructor, year, course_type))
                    inserted_courses += cursor.rowcount
            self.db.conn.commit()
            if errors:
                QMessageBox.warning(self, 'Hata', '\n'.join(errors))
            else:
                self.course_status.setText(f'{inserted_courses} ders başarıyla yüklendi.')
                QMessageBox.information(self, 'Başarılı', f'{inserted_courses} ders yüklendi')
            self.refresh_tabs()  # Automatically add Ders Listesi tab
        except Exception as e:
            QMessageBox.warning(self, 'Hata', str(e))
            self.course_status.setText('Ders yükleme başarısız.')

    def student_upload_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        self.course_select = QComboBox()
        self.load_course_options()
        layout.addWidget(QLabel('Ders Seç'))
        layout.addWidget(self.course_select)
        upload_btn = QPushButton('Excel Yükle')
        upload_btn.clicked.connect(self.upload_students)
        layout.addWidget(upload_btn)
        self.student_status = QLabel('Öğrenciler yüklenmedi.')
        self.student_status.setStyleSheet("color: #333;")
        layout.addWidget(self.student_status)
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        widget.setLayout(layout)
        return widget

    def load_course_options(self):
        self.course_select.clear()
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else '%'
        cursor.execute('SELECT code, name FROM courses WHERE department_id LIKE ?', (dep_id,))
        courses = cursor.fetchall()
        self.course_select.addItems([f"{code} - {name}" for code, name in courses])
        self.course_select.setEnabled(bool(courses))

    def upload_students(self):
        dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else 1
        if not self.db.has_courses(dep_id):
            QMessageBox.warning(self, 'Uyarı', 'Önce ders listesini yükleyin.')
            self.student_status.setText('Ders listesi yüklenmedi.')
            return
        if not self.course_select.currentText():
            QMessageBox.warning(self, 'Uyarı', 'Lütfen bir ders seçin.')
            self.student_status.setText('Ders seçilmedi.')
            return
        course_code = self.course_select.currentText().split(' - ')[0]
        file, _ = QFileDialog.getOpenFileName(self, 'Excel Seç')
        if not file: return
        try:
            df = pd.read_excel(file)
            cursor = self.db.conn.cursor()
            missing_courses = set()
            errors = []
            required_cols = ['Öğrenci No', 'Ad Soyad', 'Sınıf', 'Ders']
            if not all(col in df.columns for col in required_cols):
                errors.append('Excel dosyasının başlıkları doğru değil. Gereken sütunlar: Öğrenci No, Ad Soyad, Sınıf, Ders')
                QMessageBox.warning(self, 'Hata', '\n'.join(errors))
                return
            cursor.execute('SELECT id FROM courses WHERE code = ? AND department_id = ?', (course_code, dep_id))
            course = cursor.fetchone()
            if not course:
                QMessageBox.warning(self, 'Hata', f'Ders {course_code} bulunamadı.')
                return
            course_id = course[0]
            inserted_students = 0
            for idx, row in df.iterrows():
                try:
                    number = str(row['Öğrenci No']).strip()
                    name = row['Ad Soyad']
                    year_str = row['Sınıf']
                    year = int(year_str.split('.')[0]) if isinstance(year_str, str) and '.' in year_str else int(year_str or 0)
                    ders = row['Ders']
                    if ders != course_code:
                        errors.append(f'Satır {idx+2}: Seçilen ders ({course_code}) ile Excel dosyasındaki ders ({ders}) uyuşmuyor.')
                        continue
                    cursor.execute('INSERT OR IGNORE INTO students (department_id, number, name, year) VALUES (?, ?, ?, ?)',
                                   (dep_id, number, name, year))
                    cursor.execute('SELECT id FROM students WHERE number = ? AND department_id = ?', (number, dep_id))
                    student_id = cursor.fetchone()[0]
                    cursor.execute('INSERT OR IGNORE INTO student_courses (student_id, course_id) VALUES (?, ?)',
                                   (student_id, course_id))
                    inserted_students += cursor.rowcount
                except KeyError as e:
                    errors.append(f'Satır {idx+2}: Sütun eksik - {e}')
                except ValueError as e:
                    errors.append(f'Satır {idx+2}: Değer hatası - {e}')
                except Exception as e:
                    errors.append(f'Satır {idx+2}: Hata - {e}')
            self.db.conn.commit()
            if errors:
                QMessageBox.warning(self, 'Hata', '\n'.join(errors))
            else:
                self.student_status.setText(f'{inserted_students} öğrenci başarıyla eklendi.')
                QMessageBox.information(self, 'Başarılı', f'{inserted_students} öğrenci {course_code} dersine eklendi')
            self.refresh_tabs()  # Automatically add Öğrenci Listesi tab
        except Exception as e:
            QMessageBox.warning(self, 'Hata', str(e))
            self.student_status.setText('Öğrenci yükleme başarısız.')

    def student_list_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        search_layout = QHBoxLayout()
        self.student_search = QLineEdit(); search_layout.addWidget(QLabel('Öğrenci No Ara')); search_layout.addWidget(self.student_search)
        search_btn = QPushButton('Ara')
        search_btn.clicked.connect(self.search_student)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        self.student_info = QLabel()
        self.student_info.setStyleSheet("background-color: white; border: 1px solid #ddd; padding: 10px;")
        layout.addWidget(self.student_info)
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        widget.setLayout(layout)
        return widget

    def search_student(self):
        number = self.student_search.text()
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else '%'
        cursor.execute('''
            SELECT s.name, GROUP_CONCAT(c.code || ' - ' || c.name, '<br>') FROM students s
            JOIN student_courses sc ON s.id = sc.student_id
            JOIN courses c ON sc.course_id = c.id
            WHERE s.number=? AND s.department_id LIKE ?
            GROUP BY s.id
        ''', (number, dep_id))
        result = cursor.fetchone()
        if result:
            info = f'<b>Öğrenci:</b> {result[0]}<br><b>Aldığı Dersler:</b><br>{result[1]}'
            self.student_info.setText(info)
        else:
            self.student_info.setText('Bulunamadı')

    def course_list_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        self.course_table = QTableWidget()
        self.course_table.setHorizontalHeaderLabels(['Kod', 'Ad'])
        self.load_courses()
        self.course_table.cellClicked.connect(self.show_course_students)
        layout.addWidget(self.course_table)
        self.course_students_info = QLabel()
        self.course_students_info.setStyleSheet("background-color: white; border: 1px solid #ddd; padding: 10px;")
        layout.addWidget(self.course_students_info)
        widget.setLayout(layout)
        return widget

    def load_courses(self):
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else '%'
        cursor.execute('SELECT code, name FROM courses WHERE department_id LIKE ?', (dep_id,))
        courses = cursor.fetchall()
        self.course_table.setRowCount(len(courses))
        for i, (code, name) in enumerate(courses):
            self.course_table.setItem(i, 0, QTableWidgetItem(code))
            self.course_table.setItem(i, 1, QTableWidgetItem(name))

    def show_course_students(self, row, col):
        code = self.course_table.item(row, 0).text()
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT s.number, s.name FROM students s
            JOIN student_courses sc ON s.id = sc.student_id
            JOIN courses c ON sc.course_id = c.id
            WHERE c.code=?
        ''', (code,))
        students = cursor.fetchall()
        info = '<b>Dersi Alan Öğrenciler:</b><br>' + '<br>'.join([f'{num} - {name}' for num, name in students])
        self.course_students_info.setText(info)

    def exam_schedule_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        form_group = QGroupBox('Kısıtlar')
        form_layout = QGridLayout()
        self.exam_type = QComboBox(); self.exam_type.addItems(['Vize', 'Final', 'Bütünleme'])
        form_layout.addWidget(QLabel('Sınav Türü'), 0, 0); form_layout.addWidget(self.exam_type, 0, 1)
        self.start_date = QDateEdit(); self.start_date.setDate(QDate.currentDate())
        form_layout.addWidget(QLabel('Başlangıç Tarihi'), 1, 0); form_layout.addWidget(self.start_date, 1, 1)
        self.end_date = QDateEdit(); self.end_date.setDate(QDate.currentDate().addDays(7))
        form_layout.addWidget(QLabel('Bitiş Tarihi'), 2, 0); form_layout.addWidget(self.end_date, 2, 1)
        self.default_duration = QLineEdit('75'); form_layout.addWidget(QLabel('Varsayılan Süre (dk)'), 3, 0); form_layout.addWidget(self.default_duration, 3, 1)
        self.break_time = QLineEdit('15'); form_layout.addWidget(QLabel('Bekleme Süresi (dk)'), 4, 0); form_layout.addWidget(self.break_time, 4, 1)

        # Exclude days
        exclude_days_group = QGroupBox('Dahil Olmayan Günler')
        exclude_layout = QHBoxLayout()
        self.exclude_days = {}
        days = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
        for i, day in enumerate(days):
            cb = QCheckBox(day)
            if i >= 5: cb.setChecked(True)
            exclude_layout.addWidget(cb)
            self.exclude_days[i+1] = cb
        exclude_days_group.setLayout(exclude_layout)
        layout.addWidget(exclude_days_group)

        # Course selection/exclusion
        course_select_group = QGroupBox('Ders Seçimi (Dahil Etme)')
        course_select_layout = QVBoxLayout()
        self.course_include_table = QTableWidget()
        self.course_include_table.setHorizontalHeaderLabels(['Dahil', 'Kod', 'Ad'])
        self.load_courses_for_schedule()
        course_select_layout.addWidget(self.course_include_table)
        course_select_group.setLayout(course_select_layout)
        layout.addWidget(course_select_group)

        # Exception durations
        exception_group = QGroupBox('İstisna Sınav Süreleri')
        exception_layout = QVBoxLayout()
        self.exception_table = QTableWidget(0, 3)
        self.exception_table.setHorizontalHeaderLabels(['Ders Kod', 'Süre (dk)', 'Sil'])
        add_exception_btn = QPushButton('İstisna Ekle')
        add_exception_btn.clicked.connect(self.add_exception_row)
        exception_layout.addWidget(self.exception_table)
        exception_layout.addWidget(add_exception_btn)
        exception_group.setLayout(exception_layout)
        layout.addWidget(exception_group)

        create_btn = QPushButton('Program Oluştur')
        create_btn.clicked.connect(self.create_schedule)
        form_layout.addWidget(create_btn, 5, 1)
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        self.schedule_table = QTableWidget()
        self.schedule_table.setHorizontalHeaderLabels(['Tarih', 'Saat', 'Ders Kodu', 'Ders Adı', 'Derslik'])
        layout.addWidget(self.schedule_table)

        export_btn = QPushButton('Excel İndir')
        export_btn.clicked.connect(self.export_schedule)
        layout.addWidget(export_btn)

        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        widget.setLayout(layout)
        return widget

    def load_courses_for_schedule(self):
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else '%'
        cursor.execute('SELECT id, code, name FROM courses WHERE department_id LIKE ?', (dep_id,))
        courses = cursor.fetchall()
        self.course_include_table.setRowCount(len(courses))
        self.course_include_ids = [cid for cid, _, _ in courses]
        for i, (cid, code, name) in enumerate(courses):
            cb = QCheckBox()
            cb.setChecked(True)
            self.course_include_table.setCellWidget(i, 0, cb)
            self.course_include_table.setItem(i, 1, QTableWidgetItem(code))
            self.course_include_table.setItem(i, 2, QTableWidgetItem(name))

    def add_exception_row(self):
        row = self.exception_table.rowCount()
        self.exception_table.insertRow(row)
        code_edit = QLineEdit()
        duration_edit = QLineEdit('75')
        delete_btn = QPushButton('Sil')
        delete_btn.clicked.connect(lambda: self.exception_table.removeRow(self.exception_table.currentRow()))
        self.exception_table.setCellWidget(row, 0, code_edit)
        self.exception_table.setCellWidget(row, 1, duration_edit)
        self.exception_table.setCellWidget(row, 2, delete_btn)

    def create_schedule(self):
        exam_type = self.exam_type.currentText()
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        default_duration = int(self.default_duration.text() or 75)
        break_time = int(self.break_time.text() or 15)

        excluded_weekdays = [day for day, cb in self.exclude_days.items() if cb.isChecked()]
        dates = [d for d in (start_date + datetime.timedelta(days=x) for x in range((end_date - start_date).days + 1))
                 if d.weekday() + 1 not in excluded_weekdays]
        if not dates:
            QMessageBox.warning(self, 'Hata', 'Seçilen tarih aralığı sınavları barındırmıyor!')
            return

        included_courses = [self.course_include_ids[i] for i in range(self.course_include_table.rowCount())
                           if self.course_include_table.cellWidget(i, 0).isChecked()]
        if not included_courses:
            QMessageBox.warning(self, 'Hata', 'En az bir ders seçin')
            return

        exceptions = {self.exception_table.cellWidget(i, 0).text(): int(self.exception_table.cellWidget(i, 1).text() or 75)
                      for i in range(self.exception_table.rowCount()) if self.exception_table.cellWidget(i, 0).text()}

        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else '%'
        placeholders = ','.join('?' for _ in included_courses)
        cursor.execute(f'SELECT id, year, code FROM courses WHERE id IN ({placeholders}) AND department_id LIKE ?', included_courses + [dep_id])
        courses = cursor.fetchall()
        course_dict = {cid: {'year': year, 'code': code} for cid, year, code in courses}

        course_student_count = {cid: cursor.execute('SELECT COUNT(*) FROM student_courses WHERE course_id=?', (cid,)).fetchone()[0]
                               for cid in included_courses}

        cursor.execute('SELECT id, capacity FROM classrooms WHERE department_id LIKE ?', (dep_id,))
        classrooms = sorted(cursor.fetchall(), key=lambda x: -x[1])

        student_courses = {}
        cursor.execute(f'SELECT student_id, course_id FROM student_courses WHERE course_id IN ({placeholders})', included_courses)
        for sid, cid in cursor.fetchall():
            if sid not in student_courses:
                student_courses[sid] = []
            student_courses[sid].append(cid)

        durations = {cid: exceptions.get(course_dict[cid]['code'], default_duration) for cid in included_courses}

        slot_start = 9 * 60
        slot_end = 17 * 60
        step = 15
        slots = [slot_start + i * step for i in range((slot_end - slot_start) // step) if slot_start + i * step + max(durations.values()) <= slot_end]

        prob = pulp.LpProblem("Exam_Scheduling", pulp.LpMinimize)
        assign = pulp.LpVariable.dicts("assign", ((c, d_idx, s_idx, cl_idx) for c in included_courses for d_idx in range(len(dates)) for s_idx in range(len(slots)) for cl_idx in range(len(classrooms))), cat='Binary')

        prob += 0
        for c in included_courses:
            prob += pulp.lpSum(assign[(c, d_idx, s_idx, cl_idx)] for d_idx in range(len(dates)) for s_idx in range(len(slots)) for cl_idx in range(len(classrooms))) == 1

        for d_idx in range(len(dates)):
            for s_idx in range(len(slots)):
                for cl_idx in range(len(classrooms)):
                    capacity = classrooms[cl_idx][1]
                    prob += pulp.lpSum(assign[(c, d_idx, s_idx, cl_idx)] * course_student_count.get(c, 0) for c in included_courses) <= capacity

        for sid in student_courses:
            for d_idx in range(len(dates)):
                for s_idx in range(len(slots)):
                    prob += pulp.lpSum(assign[(c, d_idx, s_idx, cl_idx)] for c in student_courses[sid] for cl_idx in range(len(classrooms))) <= 1

        for d_idx in range(len(dates)):
            for s_idx in range(len(slots)):
                for cl_idx in range(len(classrooms)):
                    for c in included_courses:
                        duration = durations[c]
                        next_slot = s_idx + (duration // step)
                        if next_slot < len(slots):
                            prob += assign[(c, d_idx, s_idx, cl_idx)] + pulp.lpSum(assign[(c2, d_idx, s2, cl_idx)] for s2 in range(s_idx + 1, next_slot + 1) for c2 in included_courses if c2 != c) <= 1

        # Year-based distribution
        year_courses = {}
        for c in included_courses:
            year = course_dict[c]['year']
            if year not in year_courses:
                year_courses[year] = []
            year_courses[year].append(c)
        for year, courses in year_courses.items():
            prob += pulp.lpSum(assign[(c, d_idx, s_idx, cl_idx)] for c in courses for d_idx in range(len(dates)) for s_idx in range(len(slots)) for cl_idx in range(len(classrooms))) <= len(dates) * 2  # Max 2 exams per day

        prob.solve()

        self.schedule_table.setRowCount(0)
        errors = []
        for c in included_courses:
            assigned = False
            for d_idx in range(len(dates)):
                for s_idx in range(len(slots)):
                    for cl_idx in range(len(classrooms)):
                        if pulp.value(assign[(c, d_idx, s_idx, cl_idx)]) == 1:
                            date = dates[d_idx].strftime('%Y-%m-%d')
                            hour = slot_start // 60 + s_idx * (step // 60)
                            time = f"{hour:02d}:00"
                            code = course_dict[c]['code']
                            name = course_dict[c]['name']
                            classroom_id = classrooms[cl_idx][0]
                            capacity = classrooms[cl_idx][1]
                            if course_student_count[c] > capacity:
                                errors.append(f'Ders {code} için kapasite yetersiz!')
                                continue
                            self.schedule_table.insertRow(self.schedule_table.rowCount())
                            self.schedule_table.setItem(self.schedule_table.rowCount() - 1, 0, QTableWidgetItem(date))
                            self.schedule_table.setItem(self.schedule_table.rowCount() - 1, 1, QTableWidgetItem(time))
                            self.schedule_table.setItem(self.schedule_table.rowCount() - 1, 2, QTableWidgetItem(code))
                            self.schedule_table.setItem(self.schedule_table.rowCount() - 1, 3, QTableWidgetItem(name))
                            self.schedule_table.setItem(self.schedule_table.rowCount() - 1, 4, QTableWidgetItem(str(classroom_id)))
                            cursor.execute('INSERT INTO exams (course_id, date, time, duration, type, classroom_id) VALUES (?, ?, ?, ?, ?, ?)',
                                           (c, date, time, durations[c], exam_type, classroom_id))
                            assigned = True
            if not assigned:
                errors.append(f'Ders {course_dict[c]["code"]} için derslik bulunamadı!')

        self.db.conn.commit()
        if errors:
            QMessageBox.warning(self, 'Hata', '\n'.join(errors))
        elif pulp.LpStatus[prob.status] != 'Optimal':
            QMessageBox.warning(self, 'Hata', 'Program oluşturulamadı, kısıtları kontrol edin')
        else:
            QMessageBox.information(self, 'Başarılı', 'Sınav programı oluşturuldu')

    def export_schedule(self):
        df = pd.DataFrame(columns=['Tarih', 'Saat', 'Ders Kodu', 'Ders Adı', 'Derslik'])
        for i in range(self.schedule_table.rowCount()):
            row = [self.schedule_table.item(i, j).text() for j in range(5)]
            df.loc[i] = row
        file, _ = QFileDialog.getSaveFileName(self, 'Kaydet', '', 'Excel Files (*.xlsx)')
        if file:
            df.to_excel(file, index=False)
            QMessageBox.information(self, 'Başarılı', 'Program Excel olarak kaydedildi')

    def seating_plan_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        self.seating_table = QTableWidget()
        self.seating_table.setHorizontalHeaderLabels(['Sınav', 'Tarih', 'Saat', 'Derslik', 'Oturma Planı'])
        self.load_exams()
        layout.addWidget(self.seating_table)
        generate_btn = QPushButton('Oturma Planı Oluştur')
        generate_btn.clicked.connect(self.generate_seating)
        layout.addWidget(generate_btn)
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        widget.setLayout(layout)
        return widget

    def load_exams(self):
        cursor = self.db.conn.cursor()
        dep_id = self.user['department_id'] if self.user['role'] == 'Bölüm Koordinatörü' else '%'
        cursor.execute('''
            SELECT e.id, c.code, c.name, e.date, e.time, e.classroom_id
            FROM exams e
            JOIN courses c ON e.course_id = c.id
            WHERE c.department_id LIKE ?
        ''', (dep_id,))
        exams = cursor.fetchall()
        self.seating_table.setRowCount(len(exams))
        for i, (exam_id, code, name, date, time, classroom_id) in enumerate(exams):
            self.seating_table.setItem(i, 0, QTableWidgetItem(f'{code} - {name}'))
            self.seating_table.setItem(i, 1, QTableWidgetItem(date))
            self.seating_table.setItem(i, 2, QTableWidgetItem(time))
            self.seating_table.setItem(i, 3, QTableWidgetItem(str(classroom_id)))

    def generate_seating(self):
        row = self.seating_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, 'Hata', 'Lütfen bir sınav seçin')
            return
        exam_id = int(self.seating_table.item(row, 0).text().split('-')[0].strip())
        cursor = self.db.conn.cursor()
        cursor.execute('SELECT c.id, c.code, e.classroom_id, e.date, e.time FROM exams e JOIN courses c ON e.course_id = c.id WHERE e.id = ?', (exam_id,))
        exam = cursor.fetchone()
        if not exam:
            QMessageBox.warning(self, 'Hata', 'Sınav bulunamadı')
            return
        course_id, code, classroom_id, date, time = exam
        cursor.execute('SELECT rows, columns FROM classrooms WHERE id = ?', (classroom_id,))
        rows, cols = cursor.fetchone()
        cursor.execute('SELECT s.id, s.number, s.name FROM students s JOIN student_courses sc ON s.id = sc.student_id WHERE sc.course_id = ?', (course_id,))
        students = cursor.fetchall()
        if len(students) > rows * cols:
            QMessageBox.warning(self, 'Hata', f'Ders {code} için belirtilen öğrenci ön sıraya yerleştirilemedi (kapasite dolu)!')
            return

        self.clear_seating_row(row)
        layout = QGridLayout()
        student_list = [f"{num} - {name}" for _, num, name in students]
        random.shuffle(student_list)
        seating = {}
        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                if idx < len(student_list):
                    btn = QPushButton(student_list[idx])
                    btn.setStyleSheet("background-color: #90CAF9; border: 1px solid #2196F3; border-radius: 4px;")
                    btn.setFixedSize(80, 30)
                    layout.addWidget(btn, r, c)
                    number, name = student_list[idx].split(' - ')
                    student_id = next(s[0] for s in students if s[1] == number and s[2] == name)
                    seating[(r, c)] = (student_id, number, name)
                    cursor.execute('INSERT INTO seating (exam_id, student_id, classroom_id, row, col) VALUES (?, ?, ?, ?, ?)',
                                   (exam_id, student_id, classroom_id, r, c))
        self.db.conn.commit()
        widget = QWidget()
        widget.setLayout(layout)
        self.seating_table.setCellWidget(row, 4, widget)

        # PDF Export
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(40, 10, f'Sınav: {code} - {date} {time}')
        pdf.ln(10)
        pdf.set_font('Arial', '', 12)
        for (r, c), (student_id, number, name) in seating.items():
            pdf.cell(40, 10, f'Öğrenci: {number} - {name}, Sıra: {r + 1}, Sütun: {c + 1}')
            pdf.ln()
        file, _ = QFileDialog.getSaveFileName(self, 'PDF Kaydet', '', 'PDF Files (*.pdf)')
        if file:
            pdf.output(file)
            QMessageBox.information(self, 'Başarılı', 'Oturma planı PDF olarak kaydedildi')

    def clear_seating_row(self, row):
        if self.seating_table.cellWidget(row, 4):
            self.seating_table.cellWidget(row, 4).setParent(None)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())