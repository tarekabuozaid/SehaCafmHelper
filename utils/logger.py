# utils/logger.py
import logging
import os
from datetime import datetime
from pathlib import Path

# تحديد المسار الأساسي للمشروع بناءً على موقع هذا الملف
# يفترض أن مجلد utils داخل المجلد الرئيسي للمشروع
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True) # التأكد من وجود مجلد السجلات

class Logger:
    _loggers = {} # قاموس لتخزين مثيلات المسجلات لمنع التكرار

    def __new__(cls, name="CAFM_App", level=logging.DEBUG):
        if name in cls._loggers:
            return cls._loggers[name] # إرجاع المثيل الموجود إذا تم إنشاؤه بنفس الاسم

        logger_instance = super(Logger, cls).__new__(cls)
        logger_instance.logger = logging.getLogger(name)
        
        if not logger_instance.logger.handlers: # إضافة المعالجات فقط إذا لم تكن موجودة
            logger_instance.logger.setLevel(level)
            
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - [%(levelname)s] - (%(threadName)s) - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            log_file = LOGS_DIR / f'app_{datetime.now().strftime("%Y%m%d")}.log'
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO) 
            console_handler.setFormatter(formatter)
            
            logger_instance.logger.addHandler(file_handler)
            logger_instance.logger.addHandler(console_handler)
        
        cls._loggers[name] = logger_instance
        return logger_instance

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message, exc_info=False):
        self.logger.error(message, exc_info=exc_info)

    def critical(self, message, exc_info=False):
        self.logger.critical(message, exc_info=exc_info)
    
    def exception(self, message): # لتسجيل الاستثناءات مع traceback
        self.logger.exception(message)