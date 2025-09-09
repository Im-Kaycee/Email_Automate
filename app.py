import sys
import os
import smtplib
import pandas as pd
import time
import csv
from datetime import datetime
from threading import Thread
from urllib.parse import urljoin
import re
import requests
from bs4 import BeautifulSoup

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QPlainTextEdit, 
                               QProgressBar, QTabWidget, QFileDialog, QSpinBox,
                               QLineEdit, QFormLayout, QGroupBox, QCheckBox,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QComboBox, QFrame, QScrollArea, QSplitter)
from PySide6.QtCore import Qt, QThread, QTimer, Signal, QSettings
from PySide6.QtGui import QFont, QPalette, QColor, QIcon
from PySide6.QtWebEngineWidgets import QWebEngineView  
try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    print("Warning: ddgs library not found. Please install with: pip install duckduckgo-search")

class ScrapingThread(QThread):
    progress_updated = Signal(int, str)
    data_scraped = Signal(list)
    finished = Signal()
    
    def __init__(self, query, max_results):
        super().__init__()
        self.query = query
        self.max_results = max_results
        
    def run(self):
        if not DDGS:
            self.progress_updated.emit(0, "Error: ddgs library not installed. Please install with: pip install duckduckgo-search")
            self.finished.emit()
            return
            
        agencies = []
        try:
            with DDGS() as ddgs:
                results = ddgs.text(self.query, max_results=self.max_results)
                total = len(list(results))
                
                with DDGS() as ddgs2:  # New instance for actual processing
                    results = ddgs2.text(self.query, max_results=self.max_results)
                    for i, r in enumerate(results):
                        url = r.get("href")
                        title = r.get("title", "")
                        
                        self.progress_updated.emit(int((i/total)*100), f"Scraping: {title[:50]}...")
                        
                        emails, links = self.scrape_website(url, deep=True)
                        agencies.append({
                            "title": title,
                            "url": url,
                            "emails": emails,
                            "links": links
                        })
                        
            self.data_scraped.emit(agencies)
        except Exception as e:
            self.progress_updated.emit(0, f"Error: {str(e)}")
        finally:
            self.finished.emit()
    
    def scrape_website(self, url, deep=False):
        emails, links = [], []
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text()
            emails = list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)))
            links = [a["href"] for a in soup.find_all("a", href=True)]
            
            if deep:
                important_links = [
                    l for l in links 
                    if any(word in l.lower() for word in ["contact", "about", "team", "support"])
                ]
                
                for l in important_links[:3]:
                    full_url = urljoin(url, l)
                    sub_emails, _ = self.scrape_website(full_url, deep=False)
                    emails.extend(sub_emails)
        except Exception as e:
            pass
        
        return list(set(emails)), links

class EmailSenderThread(QThread):
    progress_updated = Signal(int, str)
    email_sent = Signal(str, bool, str)
    finished = Signal(int, int)
    
    def __init__(self, emails, smtp_config, sender_email, subject, plain_text):
        super().__init__()
        self.emails = emails
        self.smtp_config = smtp_config
        self.sender_email = sender_email
        self.subject = subject
        self.plain_text = plain_text
        
    def run(self):
        successful = 0
        failed = 0
        
        # Import MIME libraries here to avoid import issues
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        
        for i, email in enumerate(self.emails):
            try:
                # Create MIME multipart message for text emails
                msg = MIMEMultipart()
                msg['Subject'] = self.subject
                msg['From'] = self.sender_email
                msg['To'] = email
                
                # Add  plain text 
                msg.attach(MIMEText(self.plain_text, 'plain'))
               
                
                with smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port']) as server:
                    server.starttls()
                    server.login(self.smtp_config['username'], self.smtp_config['password'])
                    server.sendmail(self.sender_email, email, msg.as_string())
                
                successful += 1
                self.email_sent.emit(email, True, "Success")
                self.progress_updated.emit(int((i+1)/len(self.emails)*100), f"Sent to {email}")
                time.sleep(3)  # Rate limiting
                
            except Exception as e:
                failed += 1
                self.email_sent.emit(email, False, str(e))
                time.sleep(5)
        
        self.finished.emit(successful, failed)
class ProfessionalButton(QPushButton):
    def __init__(self, text, primary=False):
        super().__init__(text)
        self.primary = primary
        self.setMinimumHeight(40)
        self.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.update_style()
        
    def update_style(self):
        if self.primary:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2B5CE6;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #1E4BD1;
                }
                QPushButton:pressed {
                    background-color: #1640B8;
                }
                QPushButton:disabled {
                    background-color: #6B7280;
                    color: #9CA3AF;
                }
            """)
        else:
            if hasattr(QApplication.instance(), 'dark_mode') and QApplication.instance().dark_mode:
                self.setStyleSheet("""
                    QPushButton {
                        background-color: #374151;
                        color: #F3F4F6;
                        border: 1px solid #4B5563;
                        border-radius: 8px;
                        padding: 8px 16px;
                    }
                    QPushButton:hover {
                        background-color: #4B5563;
                    }
                    QPushButton:pressed {
                        background-color: #6B7280;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QPushButton {
                        background-color: #F3F4F6;
                        color: #374151;
                        border: 1px solid #D1D5DB;
                        border-radius: 8px;
                        padding: 8px 16px;
                    }
                    QPushButton:hover {
                        background-color: #E5E7EB;
                    }
                    QPushButton:pressed {
                        background-color: #D1D5DB;
                    }
                """)

class AgencyOutreachApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('AgencyOutreach', 'Settings')
        self.dark_mode = self.settings.value('dark_mode', False, bool)
        self.scraped_data = []
        from PySide6.QtGui import QShortcut, QKeySequence
        self.shortcut_fullscreen = QShortcut(QKeySequence("F11"), self)
        self.shortcut_fullscreen.activated.connect(self.toggle_fullscreen)
        self.setWindowTitle("Professional Agency Outreach Tool")
        self.setup_ui()
        self.apply_theme()
    def setup_ui(self):
        # Create a central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Header (non-scrollable)
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Agency Outreach Tool")
        title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Theme toggle
        self.theme_toggle = ProfessionalButton("🌙 Dark Mode" if not self.dark_mode else "☀️ Light Mode")
        self.theme_toggle.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.theme_toggle)
        
        main_layout.addLayout(header_layout)
        
        # Tab widget inside a scroll area
        self.tab_widget = QTabWidget()
        
        # Apply styles to tab widget
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                margin-top: 8px;
            }
            QTabBar::tab {
                background-color: #F9FAFB;
                color: #374151;
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background-color: #2B5CE6;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #E5E7EB;
            }
        """)
        
        # Create tabs with scroll areas
        self.create_scraper_tab()
        self.create_email_tab()
        
        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)
        
    def create_scraper_tab(self):
        # Create scroll area for the scraper tab
        scraper_scroll = QScrollArea()
        scraper_scroll.setWidgetResizable(True)
        scraper_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scraper_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create container widget for scroll area
        scraper_container = QWidget()
        scraper_layout = QVBoxLayout(scraper_container)
        scraper_layout.setSpacing(20)
        scraper_layout.setContentsMargins(10, 10, 10, 10)
        
        # Search configuration
        config_group = QGroupBox("Search Configuration")
        config_layout = QFormLayout(config_group)
        config_layout.setContentsMargins(15, 20, 15, 15)
        config_layout.setSpacing(10)
        
        self.query_input = QLineEdit("landscaping agencies UK")
        self.query_input.setMinimumHeight(35)
        config_layout.addRow("Search Query:", self.query_input)
        
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(1, 100)
        self.max_results_spin.setValue(30)
        self.max_results_spin.setMinimumHeight(35)
        config_layout.addRow("Max Results:", self.max_results_spin)
        
        scraper_layout.addWidget(config_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.start_scraping_btn = ProfessionalButton("🔍 Start Scraping", primary=True)
        self.start_scraping_btn.clicked.connect(self.start_scraping)
        button_layout.addWidget(self.start_scraping_btn)
        
        self.export_csv_btn = ProfessionalButton("💾 Export to CSV")
        self.export_csv_btn.clicked.connect(self.export_to_csv)
        self.export_csv_btn.setEnabled(False)
        button_layout.addWidget(self.export_csv_btn)
        
        button_layout.addStretch()
        scraper_layout.addLayout(button_layout)
        
        # Progress
        self.scraping_progress = QProgressBar()
        self.scraping_progress.setVisible(False)
        self.scraping_progress.setMinimumHeight(25)
        scraper_layout.addWidget(self.scraping_progress)
        
        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        self.progress_label.setWordWrap(True)  # Allow text wrapping
        scraper_layout.addWidget(self.progress_label)
        
        # Results table with stretch
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Title", "URL", "Emails"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Make table expandable
        scraper_layout.addWidget(self.results_table, 1)  # The '1' makes it stretch
        
        # Set the container as the scroll area's widget
        scraper_scroll.setWidget(scraper_container)
        
        self.tab_widget.addTab(scraper_scroll, "🔍 Web Scraper")
        
    def create_email_tab(self):
        # Create scroll area for the email tab
        email_scroll = QScrollArea()
        email_scroll.setWidgetResizable(True)
        email_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        email_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create container widget for scroll area
        email_container = QWidget()
        email_layout = QVBoxLayout(email_container)
        email_layout.setSpacing(20)
        email_layout.setContentsMargins(10, 10, 10, 10)
        
        # SMTP Configuration
        smtp_group = QGroupBox("SMTP Configuration")
        smtp_layout = QFormLayout(smtp_group)
        smtp_layout.setContentsMargins(15, 20, 15, 15)
        smtp_layout.setSpacing(10)
        
        self.smtp_host = QLineEdit("sandbox.smtp.mailtrap.io")
        self.smtp_host.setMinimumHeight(35)
        smtp_layout.addRow("SMTP Host:", self.smtp_host)
        
        self.smtp_port = QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(2525)
        self.smtp_port.setMinimumHeight(35)
        smtp_layout.addRow("SMTP Port:", self.smtp_port)
        #something
        self.smtp_username = QLineEdit("username")
        self.smtp_username.setMinimumHeight(35)
        smtp_layout.addRow("Username:", self.smtp_username)
        
        self.smtp_password = QLineEdit("password")
        self.smtp_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.smtp_password.setMinimumHeight(35)
        smtp_layout.addRow("Password:", self.smtp_password)
        
        self.sender_email = QLineEdit("favourkaycee23@gmail.com")
        self.sender_email.setMinimumHeight(35)
        smtp_layout.addRow("Sender Email:", self.sender_email)
        
        email_layout.addWidget(smtp_group)
        
                # Email content
        content_group = QGroupBox("Email Content")
        content_layout = QVBoxLayout(content_group)
        content_layout.setContentsMargins(15, 20, 15, 15)
        content_layout.setSpacing(10)

        subject_layout = QHBoxLayout()
        subject_layout.addWidget(QLabel("Subject:"))
        self.email_subject = QLineEdit("Business Partnership Opportunity")
        self.email_subject.setMinimumHeight(35)
        subject_layout.addWidget(self.email_subject)
        content_layout.addLayout(subject_layout)

        # Add plain text editor for email body
        self.email_message = QPlainTextEdit()
        self.email_message.setPlaceholderText("Write your email message here...")
        self.email_message.setVisible(True)
        content_layout.addWidget(self.email_message)

        email_layout.addWidget(content_group)

        # Hide the old plain text editor (keep it for compatibility but hide it)
        #self.email_message = QTextEdit()
        #self.email_message.setVisible(True)
        
        # Email list management
        list_group = QGroupBox("Email List")
        list_layout = QVBoxLayout(list_group)
        list_layout.setContentsMargins(15, 20, 15, 15)
        list_layout.setSpacing(10)
        
        file_layout = QHBoxLayout()
        self.load_excel_btn = ProfessionalButton("📂 Load Excel File")
        self.load_excel_btn.clicked.connect(self.load_excel_file)
        file_layout.addWidget(self.load_excel_btn)
        
        self.use_scraped_btn = ProfessionalButton("📋 Use Scraped Emails")
        self.use_scraped_btn.clicked.connect(self.use_scraped_emails)
        self.use_scraped_btn.setEnabled(False)
        file_layout.addWidget(self.use_scraped_btn)
        
        file_layout.addStretch()
        list_layout.addLayout(file_layout)
        
        self.email_list = QPlainTextEdit()
        self.email_list.setPlaceholderText("Email addresses will appear here...")
        list_layout.addWidget(self.email_list)
        
        email_layout.addWidget(list_group)
        
        # Send controls
        send_layout = QHBoxLayout()
        self.send_emails_btn = ProfessionalButton("📧 Send Emails", primary=True)
        self.send_emails_btn.clicked.connect(self.send_emails)
        self.send_emails_btn.setEnabled(False)
        send_layout.addWidget(self.send_emails_btn)
        
        send_layout.addStretch()
        email_layout.addLayout(send_layout)
        
        # Email progress
        self.email_progress = QProgressBar()
        self.email_progress.setVisible(False)
        self.email_progress.setMinimumHeight(25)
        email_layout.addWidget(self.email_progress)
        
        self.email_status_label = QLabel()
        self.email_status_label.setVisible(False)
        self.email_status_label.setWordWrap(True)
        email_layout.addWidget(self.email_status_label)
        
        # REMOVED THE STRETCH: email_layout.addStretch()
        
        # Set the container as the scroll area's widget
        email_scroll.setWidget(email_container)
        
        self.tab_widget.addTab(email_scroll, "📧 Email Sender")
        
    def start_scraping(self):
        query = self.query_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Warning", "Please enter a search query.")
            return
            
        self.scraping_progress.setVisible(True)
        self.progress_label.setVisible(True)
        self.start_scraping_btn.setEnabled(False)
        self.results_table.setRowCount(0)
        
        self.scraping_thread = ScrapingThread(query, self.max_results_spin.value())
        self.scraping_thread.progress_updated.connect(self.update_scraping_progress)
        self.scraping_thread.data_scraped.connect(self.display_scraped_data)
        self.scraping_thread.finished.connect(self.scraping_finished)
        self.scraping_thread.start()
        
    def update_scraping_progress(self, value, message):
        self.scraping_progress.setValue(value)
        self.progress_label.setText(message)
        
    def display_scraped_data(self, data):
        self.scraped_data = data
        self.results_table.setRowCount(len(data))
        
        for i, agency in enumerate(data):
            self.results_table.setItem(i, 0, QTableWidgetItem(agency['title']))
            self.results_table.setItem(i, 1, QTableWidgetItem(agency['url']))
            emails_text = '\n'.join(agency['emails']) if agency['emails'] else 'None found'
            self.results_table.setItem(i, 2, QTableWidgetItem(emails_text))
        
        self.export_csv_btn.setEnabled(True)
        self.use_scraped_btn.setEnabled(True)
        
    def scraping_finished(self):
        self.scraping_progress.setVisible(False)
        self.progress_label.setVisible(False)
        self.start_scraping_btn.setEnabled(True)
        
    def export_to_csv(self):
        if not self.scraped_data:
            return
            
        filename, _ = QFileDialog.getSaveFileName(self, "Save CSV", "agencies.csv", "CSV files (*.csv)")
        if filename:
            with open(filename, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Title", "URL", "Emails"])
                for agency in self.scraped_data:
                    writer.writerow([
                        agency["title"],
                        agency["url"],
                        "\n".join(agency["emails"]) if agency["emails"] else "None found"
                    ])
            QMessageBox.information(self, "Success", f"Data exported to {filename}")
            
    def load_excel_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load File", "", 
                                                  "Excel/CSV files (*.xlsx *.xls *.csv)")
        if filename:
            try:
                if filename.lower().endswith('.csv'):
                    df = pd.read_csv(filename)
                else:
                    df = pd.read_excel(filename)
                # Try to find email column
                email_columns = [col for col in df.columns if 'email' in col.lower()]
                if not email_columns:
                    email_columns = [col for col in df.columns if '@' in str(df[col].iloc[0]) if not pd.isna(df[col].iloc[0])]
                if email_columns:
                    emails = [e for e in df[email_columns[0]].dropna().tolist() if str(e).strip().lower() != "none found"]
                    self.email_list.setPlainText('\n'.join(map(str, emails)))
                    self.send_emails_btn.setEnabled(bool(emails))
                else:
                    QMessageBox.warning(self, "Warning", "No email column found in the file.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")
                
    def use_scraped_emails(self):
        if not self.scraped_data:
            return
            
        all_emails = []
        for agency in self.scraped_data:
            all_emails.extend(agency['emails'])
        
        if all_emails:
            self.email_list.setPlainText('\n'.join(all_emails))
            self.send_emails_btn.setEnabled(True)
        else:
            QMessageBox.information(self, "Info", "No emails found in scraped data.")
            
    def send_emails(self):
        emails = [email.strip() for email in self.email_list.toPlainText().split('\n') if email.strip()]
        if not emails:
            QMessageBox.warning(self, "Warning", "No email addresses found.")
            return
            
        smtp_config = {
            'host': self.smtp_host.text(),
            'port': self.smtp_port.value(),
            'username': self.smtp_username.text(),
            'password': self.smtp_password.text()
        }
        
        subject = self.email_subject.text()
        plain_text = self.email_message.toPlainText()
        html_content = None  # Not used for text-based emails
        
        self.email_progress.setVisible(True)
        self.email_status_label.setVisible(True)
        self.send_emails_btn.setEnabled(False)
        
        self.email_thread = EmailSenderThread(
            emails, smtp_config, self.sender_email.text(),
            subject, plain_text  # Use plain text for both
        )
        self.email_thread.progress_updated.connect(self.update_email_progress)
        self.email_thread.email_sent.connect(self.email_sent_callback)
        self.email_thread.finished.connect(self.email_sending_finished)
        self.email_thread.start()
        
    def update_email_progress(self, value, message):
        self.email_progress.setValue(value)
        self.email_status_label.setText(message)
        
    def email_sent_callback(self, email, success, message):
        # You could add a log widget here to show individual email results
        pass
        
    def email_sending_finished(self, successful, failed):
        self.email_progress.setVisible(False)
        self.email_status_label.setVisible(False)
        self.send_emails_btn.setEnabled(True)
        
        QMessageBox.information(self, "Email Campaign Complete", 
                               f"Successfully sent: {successful}\nFailed: {failed}")
        
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.settings.setValue('dark_mode', self.dark_mode)
        self.apply_theme()
        
    def apply_theme(self):
        app = QApplication.instance()
        app.dark_mode = self.dark_mode
        
        if self.dark_mode:
            # Dark theme
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1F2937;
                    color: #F9FAFB;
                }
                QWidget {
                    background-color: #1F2937;
                    color: #F9FAFB;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #374151;
                    border-radius: 8px;
                    margin-top: 1ex;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QLineEdit, QTextEdit, QSpinBox {
                    background-color: #374151;
                    border: 1px solid #4B5563;
                    border-radius: 6px;
                    padding: 8px;
                    color: #F9FAFB;
                }
                QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
                    border-color: #2B5CE6;
                }
                QTableWidget {
                    background-color: #374151;
                    alternate-background-color: #4B5563;
                    gridline-color: #6B7280;
                    color: #F9FAFB;
                }
                QHeaderView::section {
                    background-color: #4B5563;
                    color: #F9FAFB;
                    padding: 8px;
                    border: none;
                    font-weight: bold;
                }
                QProgressBar {
                    border: 2px solid #4B5563;
                    border-radius: 8px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #2B5CE6;
                    border-radius: 6px;
                }
                QTabWidget::pane {
                    border: 1px solid #4B5563;
                    background-color: #374151;
                }
                QTabBar::tab {
                    background-color: #4B5563;
                    color: #F9FAFB;
                }
                QTabBar::tab:selected {
                    background-color: #2B5CE6;
                }
            """)
            self.theme_toggle.setText("☀️ Light Mode")
        else:
            # Light theme
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #FFFFFF;
                    color: #1F2937;
                }
                QWidget {
                    background-color: #FFFFFF;
                    color: #1F2937;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #E5E7EB;
                    border-radius: 8px;
                    margin-top: 1ex;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QLineEdit, QTextEdit, QSpinBox {
                    background-color: #F9FAFB;
                    border: 1px solid #D1D5DB;
                    border-radius: 6px;
                    padding: 8px;
                    color: #1F2937;
                }
                QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
                    border-color: #2B5CE6;
                }
                QTableWidget {
                    background-color: #FFFFFF;
                    alternate-background-color: #F9FAFB;
                    gridline-color: #E5E7EB;
                    color: #1F2937;
                }
                QHeaderView::section {
                    background-color: #F3F4F6;
                    color: #1F2937;
                    padding: 8px;
                    border: none;
                    font-weight: bold;
                }
                QProgressBar {
                    border: 2px solid #E5E7EB;
                    border-radius: 8px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #2B5CE6;
                    border-radius: 6px;
                }
            """)
            self.theme_toggle.setText("🌙 Dark Mode")
        
        # Update all professional buttons
        for button in self.findChildren(ProfessionalButton):
            button.update_style()
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.menuBar().show()  
        else:
            self.menuBar().hide()  
            self.showFullScreen()
    
    

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Agency Outreach Tool")
    app.setOrganizationName("Professional Tools")
    
    # Set application font
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    window = AgencyOutreachApp()
    
    # Start maximized but not fullscreen (better UX)
    window.show()
    
    # Optional: Start in fullscreen (press F11 to toggle)
    # window.showFullScreen()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()