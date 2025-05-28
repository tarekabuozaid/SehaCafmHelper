# utils/browser_manager.py
from playwright.sync_api import sync_playwright, Playwright, Browser, Page, Error as PlaywrightError
from pathlib import Path
import time 
import logging 

# اسم مجلد بيانات المستخدم للمتصفح الدائم الذي يشغله المستخدم يدويًا
# يجب أن يكون هذا المسار متوافقًا مع ما يستخدمه المستخدم عند تشغيل المتصفح يدويًا
# هذا الكلاس لا يُطلق هذا المتصفح، بل يتصل به فقط.
# USER_DATA_DIR_CDP_PERSISTENT = Path(r"C:\MyPersistentChromeProfileForLoginManager") # كمثال، هذا يجب أن يحدده المستخدم

class BrowserManager:
    def __init__(self, logger_instance=None):
        self.playwright_instance: Playwright | None = None
        self.browser_connection: Browser | None = None 
        self.context = None
        self.page: Page | None = None
        
        self.logger = logger_instance if logger_instance else logging.getLogger(__name__)
        if not logger_instance and not self.logger.handlers:
            logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.is_connected_to_persistent_cdp = False

    def connect_to_existing_cdp_browser(self, cdp_url: str = "http://localhost:9222") -> bool:
        if self.is_connected_to_persistent_cdp and self.browser_connection and self.browser_connection.is_connected():
            self.logger.info(f"متصل بالفعل بالمتصفح على {cdp_url}")
            if not self.page or self.page.is_closed():
                if self.context: # لا يوجد طريقة عامة لمعرفة إذا كان السياق مغلقًا
                    try:
                        # التحقق مما إذا كان السياق لا يزال صالحًا بمحاولة استخدامه
                        if self.browser_connection and self.browser_connection.is_connected():
                             # لا يمكن التحقق من self.context._is_closed() لأنه خاصية داخلية
                             # بدلاً من ذلك، حاول إنشاء صفحة جديدة. إذا فشل، فالسياق غير صالح.
                            self.page = self.context.new_page()
                            self.logger.info("تم إنشاء صفحة جديدة في السياق الموجود (كانت الصفحة السابقة مغلقة أو غير موجودة).")
                        else:
                            self.logger.warning("الاتصال بالمتصفح مغلق، لا يمكن إنشاء صفحة جديدة في السياق.")
                            return False
                    except Exception as e:
                        self.logger.error(f"فشل في إنشاء صفحة جديدة للمتصفح المتصل (قد يكون السياق غير صالح): {e}")
                        # محاولة إعادة تهيئة السياق والصفحة إذا فشل السابق
                        try:
                            if self.browser_connection.contexts: self.context = self.browser_connection.contexts[0]
                            else: self.context = self.browser_connection.new_context()
                            self.page = self.context.new_page()
                            self.logger.info("تم إعادة إنشاء السياق والصفحة بنجاح.")
                        except Exception as e_recreate:
                            self.logger.error(f"فشل في إعادة إنشاء السياق/الصفحة للمتصفح المتصل: {e_recreate}")
                            return False
            return True

        try:
            self.logger.info(f"محاولة بدء Playwright للاتصال بـ CDP...")
            self.playwright_instance = sync_playwright().start()
            self.logger.info(f"محاولة الاتصال بالمتصفح على {cdp_url}...")
            self.browser_connection = self.playwright_instance.chromium.connect_over_cdp(cdp_url, timeout=15000)
            self.logger.info("تم الاتصال بالمتصفح الموجود (CDP) بنجاح!")

            if not self.browser_connection.contexts:
                self.logger.warning(f"المتصفح المتصل عبر CDP على {cdp_url} لا يحتوي على سياقات. محاولة إنشاء سياق جديد.")
                self.context = self.browser_connection.new_context()
            else:
                self.context = self.browser_connection.contexts[0]
            
            self.logger.info(f"تم الحصول على السياق من المتصفح (عدد الصفحات الحالية: {len(self.context.pages)}).")

            if self.context.pages:
                self.page = self.context.pages[0]
                self.logger.info(f"تم استخدام أول صفحة موجودة في السياق: {self.page.url}")
            else:
                self.page = self.context.new_page()
                self.logger.info("تم فتح صفحة جديدة في السياق.")
            
            self.is_connected_to_persistent_cdp = True
            return True
            
        except PlaywrightError as e:
            self.logger.error(f"فشل الاتصال بالمتصفح الموجود على {cdp_url}.")
            self.logger.error(f"يرجى التأكد من أنك قمت بتشغيل المتصفح يدويًا بالأمر المناسب مع منفذ CDP ({CDP_PORT}) ومجلد بيانات مستخدم (--user-data-dir).")
            self.logger.error(f"تفاصيل خطأ Playwright: {e}")
            if self.playwright_instance:
                self.playwright_instance.stop()
                self.playwright_instance = None
            return False
        except Exception as e:
            self.logger.error(f"حدث خطأ عام غير متوقع أثناء محاولة الاتصال بالمتصفح: {e}", exc_info=True)
            if self.playwright_instance:
                self.playwright_instance.stop()
                self.playwright_instance = None
            return False

    def get_current_page(self) -> Page | None:
        if self.page and not self.page.is_closed():
            return self.page
        elif self.context and self.browser_connection and self.browser_connection.is_connected(): 
            try:
                # محاولة استخدام السياق لإنشاء صفحة جديدة
                self.page = self.context.new_page()
                self.logger.info("تم إنشاء صفحة جديدة لأن الصفحة السابقة كانت مغلقة أو غير موجودة.")
                return self.page
            except Exception as e:
                self.logger.error(f"فشل في إنشاء صفحة جديدة بعد إغلاق الصفحة السابقة: {e}")
                return None
        self.logger.warning("لا يمكن الحصول على صفحة حالية (لا يوجد سياق صالح أو اتصال بالمتصفح).")
        return None

    def navigate_to_url(self, url: str, timeout: int = 60000, wait_until: str = "domcontentloaded") -> bool:
        page = self.get_current_page()
        if page:
            try:
                self.logger.info(f"الانتقال إلى: {url} (wait_until: {wait_until})")
                page.goto(url, timeout=timeout, wait_until=wait_until) # type: ignore
                self.logger.info(f"تم الانتقال بنجاح إلى: {page.url}")
                return True
            except PlaywrightError as e:
                self.logger.error(f"خطأ Playwright أثناء الانتقال إلى {url}: {e}")
            except Exception as e:
                self.logger.error(f"خطأ عام أثناء الانتقال إلى {url}: {e}", exc_info=True)
        else:
            self.logger.error("لا توجد صفحة صالحة للانتقال إليها.")
        return False

    def check_element_exists(self, selector: str, timeout: int = 10000) -> bool:
        page = self.get_current_page()
        if page:
            try:
                locator = page.locator(selector)
                # wait_for يجعل Playwright ينتظر ظهور العنصر وحالته
                locator.wait_for(state="visible", timeout=timeout) 
                # count() يمكن استخدامه للتحقق، ولكن wait_for يجب أن يكون كافيًا
                # إذا لم يثر wait_for استثناء، فالعنصر موجود ومرئي.
                self.logger.info(f"العنصر '{selector}' موجود ومرئي.")
                return True 
            except PlaywrightError: # يشمل TimeoutError
                self.logger.warning(f"العنصر '{selector}' لم يتم العثور عليه أو لم يصبح مرئيًا خلال المهلة المحددة.")
                return False
            except Exception as e:
                self.logger.error(f"خطأ أثناء التحقق من وجود العنصر '{selector}': {e}", exc_info=True)
                return False
        else:
            self.logger.error("لا توجد صفحة صالحة للتحقق من العنصر.")
            return False
            
    def save_current_session_state(self, file_path: str) -> bool:
        if self.context: 
            try:
                session_file = Path(file_path)
                session_file.parent.mkdir(parents=True, exist_ok=True) 
                
                self.context.storage_state(path=str(session_file))
                self.logger.info(f"تم حفظ حالة الجلسة بنجاح إلى: {session_file}")
                return True
            except PlaywrightError as e:
                self.logger.error(f"خطأ Playwright في حفظ حالة الجلسة إلى {file_path}: {e}", exc_info=True)
            except Exception as e:
                self.logger.error(f"خطأ عام في حفظ حالة الجلسة إلى {file_path}: {e}", exc_info=True)
        else:
            self.logger.warning("لا يوجد سياق متصفح صالح لحفظ حالته.")
        return False

    def close_connection_to_persistent_browser(self):
        self.logger.info("تنظيف اتصال Playwright بالمتصفح الدائم (المتصفح سيبقى مفتوحًا)...")
        self.page = None
        self.context = None 
        
        if self.browser_connection and self.browser_connection.is_connected():
            try:
                self.browser_connection.disconnect()
                self.logger.info("تم فصل الاتصال بنجاح عن متصفح CDP.")
            except Exception as e:
                self.logger.warning(f"خطأ أثناء فصل الاتصال بمتصفح CDP: {e}", exc_info=True)
        self.browser_connection = None
        
        if self.playwright_instance:
            try:
                self.playwright_instance.stop()
                self.logger.info("تم إيقاف Playwright.")
            except Exception as e:
                self.logger.warning(f"خطأ أثناء إيقاف Playwright: {e}", exc_info=True)
        self.playwright_instance = None
        self.is_connected_to_persistent_cdp = False
        self.logger.info("اكتمل تنظيف اتصال Playwright بالمتصفح الدائم.")

    # --- دوال لإدارة المتصفحات التي يطلقها البرنامج (إذا احتجنا إليها لاحقًا) ---
    # def launch_new_browser_with_session(self, session_file_path: str, headless: bool = False) -> Page | None:
    #     # ... منطق لإطلاق متصفح جديد وتحميل الجلسة ...
    #     # self.is_connected_to_persistent_cdp = False لهذه الحالة
    #     pass

    # def close_launched_browser(self):
    #     # ... منطق لإغلاق المتصفح الذي أطلقه البرنامج ...
    #     pass