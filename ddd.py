import sys
import os
import subprocess
import time
import platform
import webbrowser
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, 
                             QPushButton, QTextEdit, QLabel, QProgressBar, 
                             QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QFont

class WorkerThread(QThread):
    """Asosiy jarayonlarni bajaradigan thread"""
    log_signal = pyqtSignal(str)
    url_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.ngrok_url = None
        self.django_process = None
        self.ngrok_process = None
        
    def get_desktop_path(self):
        """Desktop papkasining yo'li"""
        if platform.system() == "Windows":
            return os.path.join(os.environ["USERPROFILE"], "Desktop")
        else:
            return os.path.join(os.environ["HOME"], "Desktop")
    
    def find_hozmag_system(self, desktop_path):
        """hozmag_system papkasini qidirish"""
        target = "hozmag_system"
        full_path = os.path.join(desktop_path, target)
        
        if os.path.exists(full_path) and os.path.isdir(full_path):
            return full_path
        else:
            # Desktop ichida recursive qidirish
            for root, dirs, files in os.walk(desktop_path):
                if target in dirs:
                    return os.path.join(root, target)
            raise Exception(f"'{target}' papkasi Desktopda topilmadi!")
    
    def run_django_server(self, project_path):
        """Django serverni backgroundda ishga tushirish (konsolsiz)"""
        self.log_signal.emit(f"Django serverni ishga tushirish: {project_path}")
        
        if platform.system() == "Windows":
            # Windows: konsolsiz ishga tushirish
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            cmd = f'cd /d "{project_path}" && python manage.py runserver'
            self.django_process = subprocess.Popen(
                cmd, 
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            # Linux/macOS: backgroundda ishga tushirish
            cmd = f'cd "{project_path}" && python3 manage.py runserver'
            self.django_process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                preexec_fn=os.setpgrp
            )
        
        time.sleep(3)
        self.log_signal.emit("Django server ishga tushdi (http://127.0.0.1:8000)")
    
    def run_ngrok(self):
        """Ngrok ni backgroundda ishga tushirish va URL olish"""
        self.log_signal.emit("Ngrok ni ishga tushirish...")
        
        if platform.system() == "Windows":
            # Windows: konsolsiz ishga tushirish
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            self.ngrok_process = subprocess.Popen(
                "ngrok http 8000",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            # Linux/macOS: backgroundda ishga tushirish
            self.ngrok_process = subprocess.Popen(
                "ngrok http 8000",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                preexec_fn=os.setpgrp
            )
        
        # Ngrok API dan URL olish
        time.sleep(5)
        ngrok_api = "http://127.0.0.1:4040/api/tunnels"
        
        for attempt in range(15):
            try:
                response = requests.get(ngrok_api, timeout=2)
                if response.status_code == 200:
                    tunnels = response.json().get("tunnels", [])
                    for tunnel in tunnels:
                        if tunnel.get("proto") == "https":
                            self.ngrok_url = tunnel.get("public_url")
                            break
                        elif tunnel.get("proto") == "http" and not self.ngrok_url:
                            self.ngrok_url = tunnel.get("public_url")
                    if self.ngrok_url:
                        break
            except:
                pass
            time.sleep(2)
        
        if self.ngrok_url:
            # URL ni faylga saqlash
            with open("ngrok_url.txt", "w") as f:
                f.write(self.ngrok_url)
            self.log_signal.emit(f"Ngrok URL: {self.ngrok_url}")
            self.log_signal.emit(f"URL faylga saqlandi: ngrok_url.txt")
            self.url_signal.emit(self.ngrok_url)
        else:
            self.log_signal.emit("Ngrok URL topilmadi! Ngrok to'g'ri ishlayotganini tekshiring.")
    
    def run(self):
        try:
            self.log_signal.emit("1. Desktop papkasini topish...")
            desktop = self.get_desktop_path()
            self.log_signal.emit(f"   Desktop: {desktop}")
            
            self.log_signal.emit("2. 'hozmag_system' papkasini qidirish...")
            project_path = self.find_hozmag_system(desktop)
            self.log_signal.emit(f"   Topildi: {project_path}")
            
            self.log_signal.emit("3. Django serverni ishga tushirish...")
            self.run_django_server(project_path)
            
            self.log_signal.emit("4. Ngrok ni ishga tushirish...")
            self.run_ngrok()
            
            self.finished_signal.emit(True, self.ngrok_url if self.ngrok_url else "")
        except Exception as e:
            self.log_signal.emit(f"Xatolik: {str(e)}")
            self.finished_signal.emit(False, str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker_thread = None
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Django Ngrok Launcher")
        self.setGeometry(100, 100, 700, 600)
        
        # Markaziy widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Sarlavha
        title_label = QLabel("Django & Ngrok Auto Launcher")
        title_font = QFont("Arial", 16, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50; padding: 10px;")
        layout.addWidget(title_label)
        
        # Tavsif
        desc_label = QLabel("Bu dastur Desktopdagi 'hozmag_system' papkasini topib,\n"
                           "Django serverni va Ngrok ni avtomatik ishga tushiradi.\n"
                           "Ngrok public URL avtomatik browserda ochiladi va saqlanadi.")
        desc_label.setStyleSheet("color: #7f8c8d; padding: 5px;")
        layout.addWidget(desc_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Log oynasi
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: 'Courier New';
                font-size: 12px;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.log_text)
        
        # URL ko'rsatish
        self.url_label = QLabel("Ngrok URL: -")
        self.url_label.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                color: #2c3e50;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        self.url_label.setWordWrap(True)
        layout.addWidget(self.url_label)
        
        # Tugmalar
        self.start_btn = QPushButton("Ishlatish")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.start_btn.clicked.connect(self.start_process)
        layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("To'xtatish")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_process)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        # Saqlangan URL ni ochish tugmasi
        self.open_url_btn = QPushButton("Saqlangan URL ni ochish")
        self.open_url_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px;
                border-radius: 5px;
            }
        """)
        self.open_url_btn.clicked.connect(self.open_saved_url)
        layout.addWidget(self.open_url_btn)
        
    def log_message(self, message):
        """Log oynasiga xabar qo'shish"""
        self.log_text.append(message)
        
    def update_url(self, url):
        """URL label ni yangilash va browserda ochish"""
        self.url_label.setText(f"Ngrok URL: {url}")
        # URL ni avtomatik browserda ochish
        webbrowser.open(url)
        self.log_message(f"URL browserda ochildi: {url}")
        
    def start_process(self):
        """Jarayonni boshlash"""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.log_text.clear()
        self.url_label.setText("Ngrok URL: -")
        
        self.worker_thread = WorkerThread()
        self.worker_thread.log_signal.connect(self.log_message)
        self.worker_thread.url_signal.connect(self.update_url)
        self.worker_thread.finished_signal.connect(self.process_finished)
        self.worker_thread.start()
        
    def process_finished(self, success, message):
        """Jarayon tugaganda"""
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        if success:
            if message:
                QMessageBox.information(self, "Muvaffaqiyatli", 
                                       f"Barcha jarayonlar ishga tushdi!\n\nURL: {message}")
            else:
                QMessageBox.warning(self, "Ogohlantirish", 
                                   "Jarayonlar ishga tushdi, lekin URL topilmadi!")
        else:
            QMessageBox.critical(self, "Xatolik", f"Xatolik yuz berdi:\n{message}")
    
    def stop_process(self):
        """Jarayonlarni to'xtatish"""
        if self.worker_thread and self.worker_thread.isRunning():
            # Jarayonlarni to'xtatish
            if self.worker_thread.django_process:
                self.worker_thread.django_process.terminate()
            if self.worker_thread.ngrok_process:
                self.worker_thread.ngrok_process.terminate()
            
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self.log_message("Jarayonlar to'xtatildi!")
            self.process_finished(False, "Foydalanuvchi tomonidan to'xtatildi")
    
    def open_saved_url(self):
        """Saqlangan URL faylini ochish"""
        if os.path.exists("ngrok_url.txt"):
            with open("ngrok_url.txt", "r") as f:
                url = f.read().strip()
            QMessageBox.information(self, "Saqlangan URL", f"Saqlangan URL:\n{url}")
            
            # URL ni clipboardga nusxalash so'rovi
            reply = QMessageBox.question(self, "Nusxalash", 
                                        "URL ni clipboardga nusxalaysizmi?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                clipboard = QApplication.clipboard()
                clipboard.setText(url)
                self.log_message("URL clipboardga nusxalandi!")
            
            # Browserda ochish so'rovi
            reply2 = QMessageBox.question(self, "Browserda ochish", 
                                         "URL ni browserda ochasizmi?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply2 == QMessageBox.Yes:
                webbrowser.open(url)
                self.log_message("URL browserda ochildi!")
        else:
            QMessageBox.warning(self, "Topilmadi", "ngrok_url.txt fayli topilmadi!")

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()