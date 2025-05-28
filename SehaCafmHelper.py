# SehaCafmHelper.py
import sys
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTextEdit, QMessageBox, QLabel, QGroupBox)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont

# --- استيراد الوحدات المساعدة ---
try:
    from utils.browser_manager import BrowserManager 
    from utils.logger import Logger 
    # from utils.config_manager import ConfigManager # سنضيفه عند الحاجة لقراءة الإعدادات من ملف
except ImportError as e:
    initial_error_msg = f"خطأ حرج في استيراد الوحدات: {e}\n" \
                        f"يرجى التأكد من وجود مجلد 'utils' وبه الملفات المطلوبة."
    try:
        app_temp = QApplication.instance() or QApplication(sys.argv)
        error_box = QMessageBox()
        error_box.setIcon(QMessageBox.Critical)
        error_box.setWindowTitle("خطأ في بدء التشغيل")
        error_box.setText(initial_error_msg)
        error_box.exec()
    except Exception:
        print(initial_error_msg)
    sys.exit(1)

# --- مسارات ---
APP_BASE_DIR = Path(__file__).resolve().parent
SESSIONS_DIR = APP_BASE_DIR / 'sessions' # سيتم إنشاؤه إذا لم يكن موجودًا
BROWSER_SESSION_FILE = SESSIONS_DIR / "browser_session.json"

# --- الخيط الخاص بعمليات المتصفح ---
class BrowserLoginThread(QThread):
    log_signal = Signal(str)
    connection_status_signal = Signal(bool, str, bool) 
    login_check_status_signal = Signal(bool, str) 
    session_save_status_signal = Signal(bool, str) 

    def __init__(self, operation: str, browser_manager: BrowserManager, 
                 login_url: str | None = None, session_check_xpath: str | None = None,
                 logger_instance: Logger | None = None):
        super().__init__()
        self.operation = operation
        self.browser_manager = browser_manager
        self.login_url = login_url
        self.session_check_xpath = session_check_xpath
        self.logger = logger_instance if logger_instance else Logger(name=f"BrowserLoginThread-{operation}")
        self.setObjectName(f"BrowserLoginThread-{operation}")

    def run(self):
        try:
            if self.operation == "connect_and_navigate":
                self.log_signal.emit("بدء عملية الاتصال بالمتصفح والانتقال لصفحة تسجيل الدخول...")
                if not self.login_url:
                    self.log_signal.emit("خطأ: رابط تسجيل الدخول (login_url) غير محدد.")
                    self.connection_status_signal.emit(False, "رابط تسجيل الدخول غير محدد.", False)
                    return

                if self.browser_manager.connect_to_existing_cdp_browser():
                    self.log_signal.emit("تم الاتصال بالمتصفح بنجاح.")
                    if self.browser_manager.navigate_to_url(self.login_url):
                        msg = f"تم الانتقال إلى: {self.login_url}. يرجى تسجيل الدخول يدويًا في المتصفح."
                        self.log_signal.emit(msg)
                        self.connection_status_signal.emit(True, msg, True)
                    else:
                        msg = f"فشل الانتقال إلى صفحة تسجيل الدخول ({self.login_url})."
                        self.log_signal.emit(msg)
                        self.connection_status_signal.emit(True, msg, False) 
                else:
                    msg = "فشل الاتصال بالمتصفح. تأكد من تشغيله يدويًا مع العلامات الصحيحة (--remote-debugging-port و --user-data-dir)."
                    self.log_signal.emit(msg)
                    self.connection_status_signal.emit(False, msg, False)

            elif self.operation == "check_login_status":
                self.log_signal.emit("بدء عملية التحقق من تسجيل الدخول...")
                if not self.browser_manager.is_connected_to_persistent_cdp:
                    self.log_signal.emit("غير متصل بالمتصفح. لا يمكن التحقق.")
                    self.login_check_status_signal.emit(False, "غير متصل بالمتصفح.")
                    return
                if not self.session_check_xpath:
                    self.log_signal.emit("تحذير: محدد XPath للتحقق من تسجيل الدخول غير متوفر. لا يمكن التحقق.")
                    self.login_check_status_signal.emit(False, "محدد XPath للتحقق مفقود.")
                    return

                if self.browser_manager.check_element_exists(self.session_check_xpath):
                    msg = "تم التحقق من تسجيل الدخول بنجاح (العنصر المطلوب موجود)."
                    self.log_signal.emit(msg)
                    self.login_check_status_signal.emit(True, msg)
                else:
                    msg = "فشل التحقق من تسجيل الدخول (العنصر المطلوب غير موجود). تأكد من أنك على الصفحة الصحيحة بعد تسجيل الدخول."
                    self.log_signal.emit(msg)
                    self.login_check_status_signal.emit(False, msg)
            
            elif self.operation == "save_session":
                self.log_signal.emit("بدء عملية حفظ الجلسة...")
                if not self.browser_manager.is_connected_to_persistent_cdp:
                    self.log_signal.emit("غير متصل بالمتصفح. لا يمكن حفظ الجلسة.")
                    self.session_save_status_signal.emit(False, "غير متصل بالمتصفح.")
                    return

                SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
                if self.browser_manager.save_current_session_state(str(BROWSER_SESSION_FILE)):
                    msg = f"تم حفظ الجلسة بنجاح في: {BROWSER_SESSION_FILE}"
                    self.log_signal.emit(msg)
                    self.session_save_status_signal.emit(True, msg)
                else:
                    msg = "فشل حفظ الجلسة."
                    self.log_signal.emit(msg)
                    self.session_save_status_signal.emit(False, msg)
        except Exception as e:
            error_msg = f"حدث خطأ فادح في خيط عمليات المتصفح ({self.operation}): {e}"
            self.log_signal.emit(error_msg)
            self.logger.error(error_msg, exc_info=True)
            if self.operation == "connect_and_navigate":
                self.connection_status_signal.emit(False, f"خطأ فادح: {e}", False)
            elif self.operation == "check_login_status":
                self.login_check_status_signal.emit(False, f"خطأ فادح: {e}")
            elif self.operation == "save_session":
                self.session_save_status_signal.emit(False, f"خطأ فادح: {e}")
        finally:
            self.log_signal.emit(f"انتهى عمل الخيط لعملية: {self.operation}")


class MainApplicationWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SehaCafmHelper - مدير تسجيل الدخول") 
        self.setGeometry(200, 200, 750, 550)
        
        self.logger = Logger(name="SehaCafmGUI") 
        self.browser_manager = BrowserManager(logger_instance=self.logger)
        self.active_thread: BrowserLoginThread | None = None
        self.login_verified = False 

        # --- قيم مؤقتة للإعدادات (لاحقًا من config.json) ---
        self.login_url = "https://cafm.seha.ae/ADH/applogin.aspx" 
        self.session_check_xpath = "xpath=/html/body/form/div[2]/table/tbody/tr[2]/td/table/tbody/tr/td[1]/table/tbody/tr/td/a" # إضافة xpath=
        
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

        self.init_ui()
        self._update_button_states() 

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        login_actions_group = QGroupBox("خطوات تسجيل الدخول وحفظ الجلسة")
        login_actions_layout = QVBoxLayout(login_actions_group)

        self.connect_button = QPushButton("1. اتصل بالمتصفح واذهب لصفحة تسجيل الدخول")
        self.connect_button.setToolTip("تأكد من تشغيل المتصفح يدويًا مع العلامات المطلوبة.")
        self.connect_button.clicked.connect(self.action_connect_and_navigate)
        login_actions_layout.addWidget(self.connect_button)

        self.check_login_button = QPushButton("2. تحقق من أنك سجلت الدخول بنجاح")
        self.check_login_button.setToolTip("اضغط بعد إتمام تسجيل الدخول يدويًا في المتصفح.")
        self.check_login_button.clicked.connect(self.action_check_login_status)
        login_actions_layout.addWidget(self.check_login_button)
        
        self.save_session_button = QPushButton("3. احفظ الجلسة الحالية")
        self.save_session_button.setToolTip("يحفظ الكوكيز وبيانات الجلسة الحالية.")
        self.save_session_button.clicked.connect(self.action_save_session)
        login_actions_layout.addWidget(self.save_session_button)
        
        main_layout.addWidget(login_actions_group)

        self.status_label = QLabel("الحالة: جاهز. يرجى التأكد من تشغيل المتصفح يدويًا أولاً.")
        self.status_label.setAlignment(Qt.AlignCenter)
        font = self.status_label.font()
        font.setPointSize(10); font.setBold(True)
        self.status_label.setFont(font)
        main_layout.addWidget(self.status_label)

        log_display_group = QGroupBox("سجل العمليات")
        log_display_layout = QVBoxLayout(log_display_group)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 9))
        log_display_layout.addWidget(self.log_area)
        main_layout.addWidget(log_display_group, 1)

        self.setLayout(main_layout)

    def _update_button_states(self):
        is_thread_running = self.active_thread and self.active_thread.isRunning()
        is_connected = self.browser_manager.is_connected_to_persistent_cdp
        
        self.connect_button.setEnabled(not is_thread_running and not is_connected)
        self.check_login_button.setEnabled(not is_thread_running and is_connected)
        self.save_session_button.setEnabled(not is_thread_running and is_connected and self.login_verified) 

    def log_to_gui(self, message: str):
        self.logger.info(f"[FromThreadLOG]: {message}")
        current_thread_obj = QThread.currentThread()
        thread_name = "MainThread"
        if current_thread_obj:
            name_from_object = current_thread_obj.objectName()
            if name_from_object: thread_name = name_from_object
            else: thread_name = f"QtThread-{id(current_thread_obj)}"
        self.log_area.append(f"[{thread_name}] {message}")
        self.log_area.ensureCursorVisible()

    def handle_thread_start(self, operation_name: str):
        self.log_to_gui(f"بدء عملية: {operation_name}...")
        self._update_button_states() 

    def handle_thread_finish(self, operation_name: str, success: bool, message: str):
        self.log_to_gui(f"انتهاء عملية '{operation_name}': {message} (النجاح: {success})")
        if self.active_thread:
            self.active_thread.finished.connect(self.active_thread.deleteLater) 
            self.active_thread = None
        self._update_button_states()

    def action_connect_and_navigate(self):
        if self.active_thread and self.active_thread.isRunning():
            QMessageBox.warning(self, "عملية جارية", "هناك عملية اتصال جارية بالفعل."); return
        self.handle_thread_start("الاتصال والانتقال")
        self.status_label.setText("الحالة: جاري الاتصال بالمتصفح والانتقال...")
        self.login_verified = False 
        self.active_thread = BrowserLoginThread("connect_and_navigate", self.browser_manager, self.login_url, logger_instance=self.logger)
        self.active_thread.log_signal.connect(self.log_to_gui)
        self.active_thread.connection_status_signal.connect(self.on_connection_status_received)
        self.active_thread.start()

    def on_connection_status_received(self, success: bool, message: str, page_ready_for_login: bool):
        self.handle_thread_finish("الاتصال والانتقال", success, message)
        if success:
            if page_ready_for_login:
                self.status_label.setText("الحالة: متصل. يرجى تسجيل الدخول يدويًا ثم الضغط 'تحقق'.")
                QMessageBox.information(self, "نجاح الاتصال", "تم الاتصال بالمتصفح والانتقال لصفحة تسجيل الدخول.\nيرجى تسجيل الدخول يدويًا ثم الضغط '2. تحقق...'.")
            else:
                self.status_label.setText(f"الحالة: متصل لكن فشل الانتقال - {message}")
                QMessageBox.warning(self, "مشكلة في الانتقال", f"تم الاتصال، لكن فشل الانتقال: {message}")
        else:
            self.status_label.setText(f"الحالة: فشل الاتصال - {message}")
            QMessageBox.critical(self, "فشل الاتصال", message)
        self._update_button_states()

    def action_check_login_status(self):
        if self.active_thread and self.active_thread.isRunning():
            QMessageBox.warning(self, "عملية جارية", "هناك عملية أخرى جارية."); return
        if not self.browser_manager.is_connected_to_persistent_cdp:
            QMessageBox.warning(self, "غير متصل", "يجب الاتصال بالمتصفح أولاً."); return
        self.handle_thread_start("التحقق من تسجيل الدخول")
        self.status_label.setText("الحالة: جاري التحقق من تسجيل الدخول...")
        self.login_verified = False
        self.active_thread = BrowserLoginThread("check_login_status", self.browser_manager, session_check_xpath=self.session_check_xpath, logger_instance=self.logger)
        self.active_thread.log_signal.connect(self.log_to_gui)
        self.active_thread.login_check_status_signal.connect(self.on_login_check_status_received)
        self.active_thread.start()

    def on_login_check_status_received(self, success: bool, message: str):
        self.handle_thread_finish("التحقق من تسجيل الدخول", success, message)
        if success:
            self.status_label.setText("الحالة: تم التحقق من تسجيل الدخول. يمكنك الآن حفظ الجلسة.")
            QMessageBox.information(self, "نجاح التحقق", "تم التحقق من تسجيل الدخول بنجاح.\nيمكنك الآن الضغط '3. احفظ الجلسة...'.")
            self.login_verified = True
        else:
            self.status_label.setText(f"الحالة: فشل التحقق - {message}")
            QMessageBox.warning(self, "فشل التحقق", message)
            self.login_verified = False
        self._update_button_states()

    def action_save_session(self):
        if self.active_thread and self.active_thread.isRunning():
            QMessageBox.warning(self, "عملية جارية", "هناك عملية أخرى جارية."); return
        if not self.browser_manager.is_connected_to_persistent_cdp:
            QMessageBox.warning(self, "غير متصل", "يجب الاتصال بالمتصفح أولاً."); return
        if not self.login_verified:
            QMessageBox.warning(self, "لم يتم التحقق", "يرجى التحقق من تسجيل الدخول أولاً (الخطوة 2)."); return
        self.handle_thread_start("حفظ الجلسة")
        self.status_label.setText("الحالة: جاري حفظ الجلسة...")
        self.active_thread = BrowserLoginThread("save_session", self.browser_manager, logger_instance=self.logger)
        self.active_thread.log_signal.connect(self.log_to_gui)
        self.active_thread.session_save_status_signal.connect(self.on_session_save_status_received)
        self.active_thread.start()

    def on_session_save_status_received(self, success: bool, message: str):
        self.handle_thread_finish("حفظ الجلسة", success, message)
        if success:
            self.status_label.setText(f"الحالة: تم حفظ الجلسة بنجاح في {BROWSER_SESSION_FILE}")
            QMessageBox.information(self, "نجاح الحفظ", message)
            self.login_verified = False 
        else:
            self.status_label.setText(f"الحالة: فشل حفظ الجلسة - {message}")
            QMessageBox.critical(self, "فشل الحفظ", message)
        self._update_button_states()

    def closeEvent(self, event):
        self.logger.info("التعامل مع حدث إغلاق النافذة...")
        if self.active_thread and self.active_thread.isRunning():
            self.logger.warning("محاولة إغلاق الواجهة بينما لا يزال هناك خيط يعمل.")
            reply = QMessageBox.question(self, "تأكيد الإغلاق", 
                                         "هناك عملية متصفح جارية. هل أنت متأكد أنك تريد الإغلاق؟\n(قد يؤدي هذا إلى إنهاء العملية بشكل غير متوقع)",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore(); return
            else: # إذا أصر المستخدم على الإغلاق
                 self.logger.info("وافق المستخدم على الإغلاق أثناء عمل الخيط.")
                 # لا يوجد إيقاف قسري للخيط، لكننا سنقوم بتنظيف اتصال المتصفح
        
        if self.browser_manager.is_connected_to_persistent_cdp:
            self.logger.info("إغلاق اتصال Playwright بالمتصفح الدائم عند إغلاق الواجهة...")
            self.browser_manager.close_connection_to_persistent_browser()
        
        self.logger.info("تم إغلاق واجهة مدير تسجيل الدخول.")
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_app_logger = Logger(name="SehaCafmHelperApp")
    main_app_logger.info("--- بدء تشغيل تطبيق SehaCafmHelper (وحدة مدير تسجيل الدخول) ---")
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    window = MainApplicationWindow()
    window.show()
    sys.exit(app.exec())