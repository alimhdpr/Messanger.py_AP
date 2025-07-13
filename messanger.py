import sys
import os
import sqlite3
import socket
import threading
from datetime import datetime
from PyQt6.QtWidgets import QListWidgetItem, QWidget, QLabel, QHBoxLayout
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QFileDialog
import shutil
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFileDialog, QListWidget,
    QTextEdit, QListWidgetItem, QDialog
)
from PyQt6.QtGui import QIcon,QPixmap
from PyQt6.QtCore import Qt, pyqtSignal, QObject

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "messenger.db")

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                profile_picture TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                contact_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) R EFERENCES users (id),
                FOREIGN KEY (contact_id) REFERENCES users (id),
                UNIQUE (user_id, contact_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (receiver_id) REFERENCES users (id)
            )
        """)
        self.conn.commit()

    def add_user(self, username, phone, password, profile_picture=None):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, phone, password, profile_picture) VALUES (?, ?, ?, ?)",
                (username, phone, password, profile_picture)
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def get_user(self, username=None, phone=None, user_id=None):
        cursor = self.conn.cursor()
        if username:
            cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        elif phone:
            cursor.execute("SELECT * FROM users WHERE phone=?", (phone,))
        elif user_id:
            cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
        else:
            return None
        return cursor.fetchone()

    def add_contact(self, user_id, contact_username):
        contact = self.get_user(username=contact_username)
        if not contact:
            return False
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO contacts (user_id, contact_id) VALUES (?, ?)",
                (user_id, contact[0])
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_contacts(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.profile_picture 
            FROM users u JOIN contacts c ON u.id = c.contact_id 
            WHERE c.user_id=?
        """, (user_id,))
        return cursor.fetchall()

    def add_message(self, sender_id, receiver_id, message):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO messages (sender_id, receiver_id, message) VALUES (?, ?, ?)",
            (sender_id, receiver_id, message)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_messages(self, user1_id, user2_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages 
            WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
            ORDER BY timestamp
        """, (user1_id, user2_id, user2_id, user1_id))
        return cursor.fetchall()

    def update_user(self, user_id, username=None, phone=None, password=None, profile_picture=None):
        cursor = self.conn.cursor()
        updates, params = [], []
        if username:
            updates.append("username=?")
            params.append(username)
        if phone:
            updates.append("phone=?")
            params.append(phone)
        if password:
            updates.append("password=?")
            params.append(password)
        if profile_picture:
            updates.append("profile_picture=?")
            params.append(profile_picture)
        if updates:
            query = "UPDATE users SET " + ", ".join(updates) + " WHERE id=?"
            params.append(user_id)
            cursor.execute(query, tuple(params))
            self.conn.commit()
            return True
        return False

class ClientSocket(QObject):
    message_received = pyqtSignal(str, str)

    def __init__(self, host, port):
        super().__init__()
        self.host, self.port = host, port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = True

    def connect_to_server(self):
        try:
            self.socket.connect((self.host, self.port))
            threading.Thread(target=self.receive_messages, daemon=True).start()
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def receive_messages(self):
        while self.running:
            try:
                data = self.socket.recv(1024).decode('utf-8')
                if data:
                    username, message = data.split(':', 1)
                    self.message_received.emit(username, message)
            except Exception:
                break

    def send_message(self, username, message):
        try:
            self.socket.send(f"{username}:{message}".encode('utf-8'))
        except Exception as e:
            print(f"Send error: {e}")

    def close(self):
        self.running = False
        try:
            self.socket.close()
        except Exception:
            pass

class SignInWidget(QWidget):
    def __init__(self, db, on_sign_in_success):
        super().__init__()
        self.db = db
        self.on_sign_in_success = on_sign_in_success
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Log in")
        self.setFixedSize(700, 600)


        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(40)

        title2 = QLabel("Sign in")
        title2.setStyleSheet("color: #28363D;")
        title2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title2)

        title = QLabel("Messenger")
        title.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Username")
        self.username_edit.setStyleSheet("background-color: #99AEAD; color: white;")
        self.username_edit.setFixedWidth(400)
        layout.addWidget(self.username_edit, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setStyleSheet("background-color: #99AEAD; color: white;")
        self.password_edit.setFixedWidth(400)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_edit, alignment=Qt.AlignmentFlag.AlignHCenter)


        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.sign_in_btn = QPushButton("Sign In")
        self.sign_in_btn.setStyleSheet("background-color: #658B6F; color: #2F575D;")
        self.sign_in_btn.setFixedSize(150,50)
        self.sign_in_btn.clicked.connect(self.sign_in)
        btn_layout.addWidget(self.sign_in_btn)

        self.sign_up_btn = QPushButton("Sign Up")
        self.sign_up_btn.setStyleSheet("background-color: #658B6F; color: #2F575D;")
        self.sign_up_btn.setFixedSize(150,50)
        self.sign_up_btn.clicked.connect(self.show_sign_up)
        btn_layout.addWidget(self.sign_up_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def sign_in(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        user = self.db.get_user(username=username)
        if user and user[3] == password:
            self.on_sign_in_success(user)
        else:
            QMessageBox.warning(self, "Error", "Invalid username or password")

    def show_sign_up(self):
        self.parentWidget().setCurrentIndex(1)

class SignUpWidget(QWidget):
    def __init__(self, db, on_sign_up_success):
        super().__init__()
        self.db = db
        self.on_sign_up_success = on_sign_up_success
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("sign up")
        self.setFixedSize(700, 600)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(40)

        title = QLabel("Messenger")
        title2 = QLabel("Sign up")
        title.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        title2.setStyleSheet("color: #28363D;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title2)
        layout.addWidget(title)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Username")
        self.username_edit.setStyleSheet("background-color: #99AEAD; color: white;")
        self.username_edit.setFixedWidth(400)
        layout.addWidget(self.username_edit)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Phone")
        self.phone_edit.setStyleSheet("background-color: #99AEAD; color: white;")
        self.phone_edit.setFixedWidth(400)
        layout.addWidget(self.phone_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setStyleSheet("background-color: #99AEAD; color: white;")
        self.password_edit.setFixedWidth(400)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_edit)

        self.passwordconfirm_edit = QLineEdit()
        self.passwordconfirm_edit.setPlaceholderText("Confirm Password")
        self.passwordconfirm_edit.setStyleSheet("background-color: #99AEAD; color: white;")
        self.passwordconfirm_edit.setFixedWidth(400)
        self.passwordconfirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.passwordconfirm_edit)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.sign_in_btn = QPushButton("Sign In")
        self.sign_in_btn.setStyleSheet("background-color: #658B6F; color: #2F575D;")
        self.sign_in_btn.setFixedSize(150, 50)
        self.sign_in_btn.clicked.connect(self.show_sign_in)
        btn_layout.addWidget(self.sign_in_btn)

        self.sign_up_btn = QPushButton("Sign Up")
        self.sign_up_btn.setStyleSheet("background-color: #658B6F; color: #2F575D;")
        self.sign_up_btn.setFixedSize(150, 50)
        self.sign_up_btn.clicked.connect(self.sign_up)
        btn_layout.addWidget(self.sign_up_btn)
        layout.addLayout(btn_layout)

        self.profile_pic_path = None
        self.setLayout(layout)


    def sign_up(self):
        username = self.username_edit.text().strip()
        phone = self.phone_edit.text().strip()
        password = self.password_edit.text().strip()
        passwordConfirm = self.passwordconfirm_edit.text().strip()

        if not username or not phone or not password or not passwordConfirm:
            QMessageBox.warning(self, "Error", "information missing!")
            return

        user_id = self.db.add_user(username, phone, password, self.profile_pic_path)
        if user_id and passwordConfirm == password:
            user = self.db.get_user(user_id=user_id)
            self.on_sign_up_success(user)
        else:
            QMessageBox.warning(self, "Error", "Username or phone already taken")

    def show_sign_in(self):
        self.parentWidget().setCurrentIndex(0)

class MainWindow(QMainWindow):
    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.user = user
        self.user_id = user[0]
        self.username = user[1]
        self.phone = user[2]
        self.profile_pic_path = self.user[4]
        self.client_socket = ClientSocket("localhost", 12345)
        self.client_socket.message_received.connect(self.receive_message)
        self.client_socket.connect_to_server()
        self.init_ui()

    def init_ui(self):
        self.setFixedSize(700, 600)


        self.setWindowTitle(f"Messenger - {self.username}")
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #C4CDC1;")
        main_layout = QHBoxLayout()
        layout = QVBoxLayout()

        setting_and_profile_and_addcontact_layout = QHBoxLayout()


        add_contact_btn = QPushButton()
        pixmap = QPixmap("C:/Users/AliMhd_Pr/Downloads/Screenshot 2025-07-11 145818.png")
        add_contact_btn.setIcon(QIcon(pixmap))
        add_contact_btn.setIconSize(add_contact_btn.size())
        add_contact_btn.setStyleSheet("background-color: #2F575D;")
        add_contact_btn.setFixedSize(115,100)
        add_contact_btn.clicked.connect(self.add_contact_dialog)
        setting_and_profile_and_addcontact_layout.addWidget(add_contact_btn)

        setting_btn = QPushButton()
        pixmap = QPixmap("C:/Users/AliMhd_Pr/Downloads/Screenshot 2025-07-11 145023.png")
        setting_btn.setIcon(QIcon(pixmap))
        setting_btn.setIconSize(setting_btn.size())
        setting_btn.setStyleSheet("background-color: #2F575D;")
        setting_btn.setFixedSize(115, 100)
        setting_btn.clicked.connect(self.setting_dialog)
        setting_and_profile_and_addcontact_layout.addWidget(setting_btn)

        Profile_btn = QPushButton()
        pixmap = QPixmap(self.profile_pic_path)
        Profile_btn.setIcon(QIcon(pixmap))
        Profile_btn.setIconSize(Profile_btn.size())

        Profile_btn.setStyleSheet("background-color: #2F575D;")
        Profile_btn.setFixedSize(115, 100)
        Profile_btn.clicked.connect(self.Profile_dialog)
        setting_and_profile_and_addcontact_layout.addWidget(Profile_btn)
        layout.addLayout(setting_and_profile_and_addcontact_layout)

        self.contacts_list = QListWidget()
        self.contacts_list.itemClicked.connect(self.load_messages)
        layout.addWidget(self.contacts_list)

        main_layout.addLayout(layout)

        chat_layout = QVBoxLayout()

        self.chat_display = QTextEdit()
        self.chat_display.setStyleSheet("background-color: #DEE1DD; color: #2F575D;")
        self.chat_display.setReadOnly(True)
        chat_layout.addWidget(self.chat_display)

        msg_input_layout = QHBoxLayout()
        self.message_edit = QLineEdit()
        self.message_edit.setStyleSheet("background-color: white; color: #2F575D;")
        msg_input_layout.addWidget(self.message_edit)

        send_btn = QPushButton("Send")
        send_btn.setStyleSheet("background-color: #2F575D; color: white;")
        send_btn.clicked.connect(self.send_message)
        msg_input_layout.addWidget(send_btn)

        chat_layout.addLayout(msg_input_layout)

        main_layout.addLayout(chat_layout)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.load_contacts()

    def load_contacts(self):
        self.contacts_list.clear()
        contacts = self.db.get_contacts(self.user_id)

        for contact in contacts:
            contact_id = contact[0]
            username = contact[1]
            profile_pic_path = contact[2]

            size = 48
            pixmap = QPixmap(profile_pic_path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                      Qt.TransformationMode.SmoothTransformation)


            rounded = QPixmap(size, size)
            rounded.fill(Qt.GlobalColor.transparent)

            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addEllipse(0, 0, size, size)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()


            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(10, 5, 10, 5)
            layout.setSpacing(12)


            image_label = QLabel()
            image_label.setPixmap(rounded)
            image_label.setFixedSize(size, size)
            layout.addWidget(image_label)


            name_label = QLabel(username)
            name_label.setStyleSheet("color: white; font-size: 16px;")
            layout.addWidget(name_label)


            layout.addStretch()


            widget.setStyleSheet("""
                background-color: qlineargradient(
                    spread:pad, x1:0, y1:0, x2:1, y2:0, 
                    stop:0 rgba(0, 84, 153, 180), stop:1 rgba(0, 110, 200, 180)
                );
                border-radius: 8px;
            """)


            item = QListWidgetItem()
            item.setSizeHint(QSize(200, 60))
            item.setData(Qt.ItemDataRole.UserRole, contact_id)
            self.contacts_list.addItem(item)
            self.contacts_list.setItemWidget(item, widget)

    def load_messages(self, item):
        contact_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_contact_id = contact_id

        contact = self.db.get_user(user_id=contact_id)
        if contact:
            contact_username = contact[1]
        else:
            contact_username = "Unknown"

        messages = self.db.get_messages(self.user_id, contact_id)
        self.chat_display.clear()

        for msg in messages:
        #     if msg[1]==self.user_id:
        #         sender = "Me"
        #     else:
        #         sender = contact_username
            sender = "Me" if msg[1] == self.user_id else contact_username
            self.chat_display.append(f"{sender}: {msg[3]}")



    def send_message(self):
        text = self.message_edit.text().strip()
        if text and hasattr(self, 'current_contact_id'):
            self.db.add_message(self.user_id, self.current_contact_id, text)
            self.client_socket.send_message(self.username, text)
            self.chat_display.append(f"Me: {text}")
            self.message_edit.clear()

    def receive_message(self, username, message):
        self.chat_display.append(f"{username}: {message}")

    def add_contact_dialog(self):
        dialog = QDialog(self)
        dialog.setStyleSheet("background-color: #1B4079; color: white;")
        dialog.setWindowTitle("Add Contact")
        dlg_layout = QVBoxLayout()
        contact_edit = QLineEdit()
        contact_edit.setStyleSheet("background-color: #CBDF90; color: #1B4079;")
        dlg_layout.addWidget(QLabel("Contact username:"))
        dlg_layout.addWidget(contact_edit)
        add_btn = QPushButton("Add")
        add_btn.setStyleSheet("background-color: #8FAD88; color: #CBDF90;")
        dlg_layout.addWidget(add_btn)

        def add():
            contact_username = contact_edit.text().strip()
            if contact_username:
                if self.db.add_contact(self.user_id, contact_username):
                    QMessageBox.information(self, "Success", "Contact added!")
                    self.load_contacts()
                    dialog.accept()
                else:
                    QMessageBox.warning(self, "Error", "User not found or already added")

        add_btn.clicked.connect(add)
        dialog.setLayout(dlg_layout)
        dialog.exec()

    def setting_dialog(self):
        dialog = QDialog(self)
        dialog.setFixedSize(400, 600)
        dialog.setWindowTitle("Settings")
        dlg_layout = QVBoxLayout()


        fields_layout = QVBoxLayout()

        usrname_title = QLabel("Username:")
        fields_layout.addWidget(usrname_title)
        self.username_edit = QLineEdit()
        self.username_edit.setText(self.username)
        self.username_edit.setFixedWidth(400)
        fields_layout.addWidget(self.username_edit, alignment=Qt.AlignmentFlag.AlignHCenter)

        phone_title = QLabel("Phone Number:")
        fields_layout.addWidget(phone_title)
        self.phone_edit = QLineEdit()
        self.phone_edit.setText(self.phone)
        self.phone_edit.setFixedWidth(400)
        fields_layout.addWidget(self.phone_edit, alignment=Qt.AlignmentFlag.AlignHCenter)

        new_password_title = QLabel("New Password:")
        fields_layout.addWidget(new_password_title)
        self.new_password_edit = QLineEdit()
        self.new_password_edit.setFixedWidth(400)
        self.new_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        fields_layout.addWidget(self.new_password_edit, alignment=Qt.AlignmentFlag.AlignHCenter)

        confirm_password_title = QLabel("Confirm Password:")
        fields_layout.addWidget(confirm_password_title)
        self.confirm_password_edit = QLineEdit()
        self.confirm_password_edit.setFixedWidth(400)
        self.confirm_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        fields_layout.addWidget(self.confirm_password_edit, alignment=Qt.AlignmentFlag.AlignHCenter)

        dlg_layout.addLayout(fields_layout)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        change_profile_pic_btn = QPushButton("Change Profile Picture")
        change_profile_pic_btn.setFixedSize(300, 50)

        def change_profile_pic():
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Profile Picture",
                "",
                "Image Files (*.png *.jpg *.jpeg *.bmp)"
            )

            if file_path:
                profile_pics_dir = os.path.join(os.getcwd(), "profile_pics")
                if not os.path.exists(profile_pics_dir):
                    os.makedirs(profile_pics_dir)


                filename = os.path.basename(file_path)
                dest_path = os.path.join(profile_pics_dir, f"user_{self.user_id}_{filename}")
                shutil.copyfile(file_path, dest_path)

                relative_path = os.path.relpath(dest_path, os.getcwd())

                success = self.db.update_user(self.user_id, profile_picture=relative_path)
                if success:
                    QMessageBox.information(self, "Profile Picture", "Profile picture updated successfully!")
                else:
                    QMessageBox.warning(self, "Error", "Failed to update profile picture.")

        change_profile_pic_btn.clicked.connect(change_profile_pic)
        btn_layout.addWidget(change_profile_pic_btn)

        save_changes_btn = QPushButton("Save Changes")
        save_changes_btn.setFixedSize(300, 50)

        def save_changes():
            username = self.username_edit.text().strip()
            phone = self.phone_edit.text().strip()
            password = self.new_password_edit.text().strip()
            passwordConfirm = self.confirm_password_edit.text().strip()

            if password != passwordConfirm:
                QMessageBox.warning(self, "Error", "Passwords do not match")
                return

            success = self.db.update_user(
                self.user_id,
                username=username,
                phone=phone,
                password=password if password else None
            )

            if success:
                QMessageBox.information(self, "Success", "Profile updated")
                self.username = username
            else:
                QMessageBox.warning(self, "Error", "Failed to update profile. Username or phone may be taken.")

        save_changes_btn.clicked.connect(save_changes)
        btn_layout.addWidget(save_changes_btn)

        dlg_layout.addLayout(btn_layout)

        dialog.setLayout(dlg_layout)
        dialog.exec()

    def Profile_dialog(self):
        dialog = QDialog(self)
        dialog.setFixedSize(400, 600)
        dialog.setWindowTitle("Profile")
        dlg_layout = QVBoxLayout()

        self.profile_pic_path = self.user[4]
        profile_pic_label = QLabel()
        if self.profile_pic_path:
            pixmap = QPixmap(self.profile_pic_path)
            pixmap = pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            profile_pic_label.setPixmap(pixmap)
        else:
            profile_pic_label.setText("No Profile Picture")
            profile_pic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dlg_layout.addWidget(profile_pic_label, alignment=Qt.AlignmentFlag.AlignCenter)


        username_label = QLabel(f"Username: {self.username}")
        username_label.setStyleSheet("color: #4D7C8A; font-size: 32px; font-weight: bold;")
        username_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dlg_layout.addWidget(username_label)

        phone_label = QLabel(f"phone: {self.phone}")
        phone_label.setStyleSheet("color: #4D7C8A; font-size: 32px; font-weight: bold;")
        phone_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dlg_layout.addWidget(phone_label)


        close_btn = QPushButton("Close")
        dlg_layout.addWidget(close_btn)

        def close():
            dialog.accept()
        close_btn.clicked.connect(close)
        dialog.setLayout(dlg_layout)
        dialog.exec()

    def closeEvent(self, event):
        self.client_socket.close()
        event.accept()

class MessengerApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.db = Database()
        self.init_ui()

    def init_ui(self):
        self.stacked_widget = QStackedWidget()
        self.sign_in_widget = SignInWidget(self.db, self.on_sign_in_success)
        self.sign_up_widget = SignUpWidget(self.db, self.on_sign_up_success)
        self.stacked_widget.addWidget(self.sign_in_widget)
        self.stacked_widget.addWidget(self.sign_up_widget)
        self.main_window = None
        self.stacked_widget.show()

    def on_sign_in_success(self, user):
        self.main_window = MainWindow(self.db, user)
        self.main_window.show()
        self.stacked_widget.close()

    def on_sign_up_success(self, user):
        self.on_sign_in_success(user)



if __name__ == "__main__":
    app = MessengerApp(sys.argv)
    sys.exit(app.exec())
