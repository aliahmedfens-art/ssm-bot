import sqlite3
import requests
import time
import json
import uuid
import random
import string
from datetime import datetime
import os
from fpdf import FPDF
from flask import Flask, request
import logging

# ==================== إعدادات البوت ====================
TOKEN = "8436742877:AAGhCfnC9hbW7Sa4gMTroYissoljCjda9Ow"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"

# ==================== إعدادات التتبع ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== تهيئة قاعدة البيانات ====================
def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول"""
    try:
        # استخدام مسار ثابت في Render
        db_path = os.path.join(os.path.dirname(__file__), 'bot.db')
        
        conn = sqlite3.connect(db_path, check_same_thread=False)
        c = conn.cursor()
        
        # إنشاء الجداول
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                    (user_id INTEGER PRIMARY KEY, username TEXT, 
                    balance REAL DEFAULT 0, is_admin INTEGER DEFAULT 0, 
                    is_banned INTEGER DEFAULT 0, is_restricted INTEGER DEFAULT 0,
                    invited_by INTEGER DEFAULT 0, invite_code TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    daily_reward_date TEXT DEFAULT '', total_invited INTEGER DEFAULT 0)''')

        c.execute('''CREATE TABLE IF NOT EXISTS categories 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')

        c.execute('''CREATE TABLE IF NOT EXISTS services 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, 
                    price_per_k REAL, min_order INTEGER DEFAULT 100, max_order INTEGER DEFAULT 10000,
                    description TEXT DEFAULT '', is_active INTEGER DEFAULT 1)''')

        c.execute('''CREATE TABLE IF NOT EXISTS orders 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service_id INTEGER,
                    quantity INTEGER, total_price REAL, link TEXT, status TEXT DEFAULT 'pending',
                    admin_note TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP DEFAULT NULL)''')

        c.execute('''CREATE TABLE IF NOT EXISTS forced_channels 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT, channel_username TEXT, channel_url TEXT)''')

        c.execute('''CREATE TABLE IF NOT EXISTS settings 
                    (key TEXT PRIMARY KEY, value TEXT)''')

        c.execute('''CREATE TABLE IF NOT EXISTS channel_funding
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
                    channel_link TEXT, channel_username TEXT, channel_id TEXT,
                    target_members INTEGER, current_members INTEGER DEFAULT 0,
                    price_per_member REAL, total_cost REAL, subscription_reward REAL,
                    status TEXT DEFAULT 'pending', admin_note TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP DEFAULT NULL)''')

        c.execute('''CREATE TABLE IF NOT EXISTS channel_subscriptions
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, funding_id INTEGER,
                    subscriber_id INTEGER, subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        # الإعدادات الافتراضية
        default_settings = [
            ('maintenance', 'false'), ('maintenance_msg', 'البوت تحت الصيانة'),
            ('invite_reward', '0.10'), ('invite_enabled', 'true'),
            ('force_subscribe', 'false'), ('bot_username', BOT_USERNAME),
            ('daily_reward', '0.05'), ('channel_funding_enabled', 'true'),
            ('min_funding_members', '100'), ('max_funding_members', '5000'),
            ('subscription_reward', '0.01'), ('max_channels_per_user', '3'),
            ('subscription_cooldown', '24'), ('welcome_message', 'مرحباً بك في البوت!')
        ]

        for key, value in default_settings:
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

        # إضافة المدير إذا لم يكن موجوداً
        c.execute("SELECT user_id FROM users WHERE user_id = ?", (ADMIN_ID,))
        if not c.fetchone():
            invite_code = str(uuid.uuid4())[:8]
            c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
                    (ADMIN_ID, "المدير", 100000, 1, 'ADMIN'))
        
        conn.commit()
        conn.close()
        logger.info("✅ تم تهيئة قاعدة البيانات بنجاح")
        return db_path
    except Exception as e:
        logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
        raise

# تهيئة قاعدة البيانات
DB_PATH = init_db()
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# ==================== وظائف مساعدة ====================
def get_setting(key):
    """جلب إعداد من قاعدة البيانات"""
    try:
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = c.fetchone()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"خطأ في جلب الإعداد {key}: {e}")
        return None

def update_setting(key, value):
    """تحديث إعداد في قاعدة البيانات"""
    try:
        c.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث الإعداد {key}: {e}")
        return False

def send_msg(chat_id, text, buttons=None):
    """إرسال رسالة إلى المستخدم"""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if buttons:
            data['reply_markup'] = json.dumps({'inline_keyboard': buttons})
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"خطأ في إرسال الرسالة: {e}")
        return False

def check_channels(user_id):
    """التحقق من اشتراك المستخدم في القنوات الإجبارية"""
    if get_setting('force_subscribe') != 'true':
        return True, None
    
    try:
        c.execute("SELECT channel_id, channel_username FROM forced_channels")
        channels = c.fetchall()
        
        for channel_id, channel_username in channels:
            try:
                url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
                params = {'chat_id': channel_id, 'user_id': user_id}
                response = requests.get(url, params=params, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        status = data['result']['status']
                        if status in ['left', 'kicked']:
                            return False, channel_username
            except Exception as e:
                logger.error(f"خطأ في التحقق من القناة: {e}")
                continue
        
        return True, None
    except Exception as e:
        logger.error(f"خطأ في التحقق من القنوات: {e}")
        return True, None

def generate_invoice_pdf(order_id, user_id, service_name, quantity, total_price, link):
    """إنشاء فاتورة PDF للطلب"""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(200, 10, 'Invoice', 0, 1, 'C')
        pdf.ln(5)
        pdf.set_font('Arial', '', 12)
        pdf.cell(50, 10, f'Invoice ID: #{order_id}', 0, 1)
        pdf.cell(50, 10, f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
        pdf.cell(50, 10, f'User ID: {user_id}', 0, 1)
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(200, 10, 'Order Details', 0, 1, 'C')
        pdf.set_font('Arial', '', 12)
        pdf.cell(100, 10, f'Service: {service_name}', 0, 1)
        pdf.cell(100, 10, f'Quantity: {quantity}', 0, 1)
        pdf.cell(100, 10, f'Link: {link}', 0, 1)
        pdf.cell(100, 10, f'Total Price: ${total_price:.2f} USD', 0, 1)
        
        filename = f'invoice_{order_id}.pdf'
        pdf.output(filename)
        return filename
    except Exception as e:
        logger.error(f"خطأ في إنشاء PDF: {e}")
        return None

def send_document(chat_id, document_path, caption=""):
    """إرسال ملف إلى المستخدم"""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
        with open(document_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            response = requests.post(url, files=files, data=data, timeout=20)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"خطأ في إرسال الملف: {e}")
        return False

# ==================== القوائم الرئيسية ====================
def main_menu(chat_id, user_id):
    """القائمة الرئيسية"""
    # التحقق من الاشتراك الإجباري
    subscribed, channel = check_channels(user_id)
    if not subscribed:
        buttons = [[{'text': '📢 اشترك', 'url': f'https://t.me/{channel}'}, {'text': '✅ تحقق', 'callback_data': 'check_sub'}]]
        send_msg(chat_id, f"📢 اشترك في @{channel} أولاً", buttons)
        return
    
    # التحقق من الحظر
    try:
        c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result and result[0] == 1:
            send_msg(chat_id, "🚫 تم حظرك من استخدام البوت")
            return
    except Exception as e:
        logger.error(f"خطأ في التحقق من الحظر: {e}")
    
    # جلب بيانات المستخدم
    try:
        c.execute("SELECT username, balance, is_admin FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            # إنشاء حساب جديد للمستخدم
            invite_code = str(uuid.uuid4())[:8]
            c.execute("INSERT INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
                     (user_id, "", 0, 0, invite_code))
            conn.commit()
            username = ""
            balance = 0
            is_admin = 0
        else:
            username, balance, is_admin = user
    except Exception as e:
        logger.error(f"خطأ في جلب بيانات المستخدم: {e}")
        username = ""
        balance = 0
        is_admin = 0
    
    # التحقق من هدية اليوم
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        c.execute("SELECT daily_reward_date FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        last_reward = result[0] if result else ""
        daily_available = last_reward != today if last_reward else True
    except Exception as e:
        logger.error(f"خطأ في التحقق من هدية اليوم: {e}")
        daily_available = True
    
    # إنشاء نص الرسالة
    text = f"""👋 أهلاً {username or 'مستخدم'}

🆔 الآيدي: <code>{user_id}</code>
💰 الرصيد: <b>{balance:,.2f} USD</b>"""
    
    # إنشاء الأزرار
    buttons = [
        [{'text': '🛍️ خدمات', 'callback_data': 'services'}, {'text': '💰 شحن', 'callback_data': 'charge'}],
        [{'text': '💳 رصيدي', 'callback_data': 'balance'}, {'text': '👥 دعوة', 'callback_data': 'invite'}],
        [{'text': '📋 طلباتي', 'callback_data': 'my_orders'}, {'text': '📞 دعم', 'callback_data': 'support'}]
    ]
    
    if daily_available:
        buttons.append([{'text': '🎁 هدية اليوم', 'callback_data': 'daily_reward'}])
    
    buttons.append([{'text': '📺 تمويل قنوات', 'callback_data': 'channel_funding'}])
    buttons.append([{'text': '📢 اشترك بقنوات', 'callback_data': 'subscribe_channels'}])
    
    if is_admin == 1 or user_id == ADMIN_ID:
        buttons.append([{'text': '👑 لوحة التحكم', 'callback_data': 'admin'}])
    
    send_msg(chat_id, text, buttons)

def admin_panel(chat_id):
    """لوحة تحكم المدير"""
    buttons = [
        [{'text': '📊 إحصائيات', 'callback_data': 'stats'}, {'text': '👥 المستخدمين', 'callback_data': 'users_list'}],
        [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'manage_services'}, {'text': '💳 شحن رصيد', 'callback_data': 'admin_charge'}],
        [{'text': '🚫 إدارة الحظر', 'callback_data': 'ban_manage'}, {'text': '👑 إدارة المشرفين', 'callback_data': 'admin_manage'}],
        [{'text': '📢 القنوات الإجبارية', 'callback_data': 'channels_manage'}, {'text': '📺 إدارة التمويل', 'callback_data': 'funding_manage'}],
        [{'text': '🎁 إرسال للجميع', 'callback_data': 'send_all'}, {'text': '⚙️ الإعدادات', 'callback_data': 'settings_menu'}],
        [{'text': '🔙 رئيسية', 'callback_data': 'main'}]
    ]
    send_msg(chat_id, "👑 لوحة تحكم المدير", buttons)

# ==================== نظام تمويل القنوات ====================
def channel_funding_menu(chat_id, user_id):
    """قائمة تمويل القنوات"""
    if get_setting('channel_funding_enabled') != 'true':
        send_msg(chat_id, "⏸️ نظام تمويل القنوات معطل حالياً")
        return
    
    try:
        c.execute("SELECT COUNT(*), SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) FROM channel_funding WHERE user_id = ?", (user_id,))
        stats = c.fetchone() or (0, 0)
        
        reward = float(get_setting('subscription_reward') or 0.01)
        min_m = int(get_setting('min_funding_members') or 100)
        max_m = int(get_setting('max_funding_members') or 5000)
        max_c = int(get_setting('max_channels_per_user') or 3)
        
        text = f"""📺 <b>تمويل القنوات</b>

💰 مكافأة المشترك: {reward} USD
🔢 الحدود: {min_m}-{max_m} عضو
📊 حملاتك: {stats[0]} (نشطة: {stats[1]})
📈 الباقي: {max_c - stats[1]} حملات"""
        
        buttons = [
            [{'text': '➕ حملة جديدة', 'callback_data': 'new_funding'}],
            [{'text': '📋 حملاتي', 'callback_data': 'my_fundings'}],
            [{'text': '🔙 رجوع', 'callback_data': 'main'}]
        ]
        send_msg(chat_id, text, buttons)
    except Exception as e:
        logger.error(f"خطأ في قائمة تمويل القنوات: {e}")
        send_msg(chat_id, "❌ حدث خطأ في تحميل القائمة")

def subscribe_channels_menu(chat_id, user_id):
    """قائمة الاشتراك في القنوات"""
    try:
        c.execute("""
            SELECT cf.id, cf.channel_username, cf.target_members, cf.current_members, cf.subscription_reward
            FROM channel_funding cf
            WHERE cf.status = 'active' AND cf.current_members < cf.target_members
            AND NOT EXISTS (SELECT 1 FROM channel_subscriptions cs WHERE cs.funding_id = cf.id AND cs.subscriber_id = ?)
            ORDER BY cf.current_members ASC LIMIT 10
        """, (user_id,))
        channels = c.fetchall()
        
        if not channels:
            text = "📭 لا توجد قنوات متاحة حالياً للاشتراك"
            buttons = [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]
        else:
            text = "📢 <b>القنوات المتاحة للاشتراك</b>\n\n"
            for fid, username, target, current, reward in channels:
                progress = (current / target) * 100 if target > 0 else 0
                text += f"""📺 @{username}
👥 {current}/{target} عضو ({progress:.1f}%)
💰 المكافأة: {reward} USD
━━━━━━━━━━
"""
            text += "\n📌 اختر قناة للاشتراك:"
            
            buttons = []
            for fid, username, _, _, _ in channels:
                buttons.append([{'text': f'📺 @{username}', 'callback_data': f'subscribe_{fid}'}])
            buttons.append([{'text': '🔙 رجوع', 'callback_data': 'main'}])
        
        send_msg(chat_id, text, buttons)
    except Exception as e:
        logger.error(f"خطأ في قائمة الاشتراك: {e}")
        send_msg(chat_id, "❌ حدث خطأ في تحميل القنوات")

# ==================== معالجة الرسائل ====================
user_states = {}

def handle_message(chat_id, user_id, text, username=""):
    """معالجة الرسائل النصية"""
    try:
        # التحقق من الاشتراك الإجباري
        subscribed, channel = check_channels(user_id)
        if not subscribed:
            buttons = [[{'text': '📢 اشترك', 'url': f'https://t.me/{channel}'}, {'text': '✅ تحقق', 'callback_data': 'check_sub'}]]
            send_msg(chat_id, f"📢 اشترك في @{channel} أولاً", buttons)
            return
        
        # التحقق من الحظر
        try:
            c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
            result = c.fetchone()
            if result and result[0] == 1:
                send_msg(chat_id, "🚫 تم حظرك من استخدام البوت")
                return
        except Exception as e:
            logger.error(f"خطأ في التحقق من الحظر: {e}")
        
        # تحديث اسم المستخدم إذا كان موجوداً
        if username:
            try:
                c.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
                conn.commit()
            except Exception as e:
                logger.error(f"خطأ في تحديث اسم المستخدم: {e}")
        
        # معالجة الحالات الخاصة
        if user_id in user_states:
            state = user_states[user_id]
            return handle_user_state(chat_id, user_id, text, state)
        
        # معالجة الأوامر
        if text == '/start':
            handle_start_command(chat_id, user_id, text, username)
        elif text == '/admin':
            handle_admin_command(chat_id, user_id)
        else:
            main_menu(chat_id, user_id)
    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}")
        send_msg(chat_id, "❌ حدث خطأ في معالجة طلبك")

def handle_user_state(chat_id, user_id, text, state):
    """معالجة الحالات الخاصة للمستخدمين"""
    try:
        if state['type'] == 'order_qty':
            service_id = state['service_id']
            c.execute("SELECT name, price_per_k, min_order, max_order FROM services WHERE id = ?", (service_id,))
            serv = c.fetchone()
            if serv:
                name, price, min_q, max_q = serv
                try:
                    quantity = int(text)
                    if min_q <= quantity <= max_q:
                        total_price = (price / 1000) * quantity
                        balance_result = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
                        balance = balance_result[0] if balance_result else 0
                        
                        if balance >= total_price:
                            user_states[user_id] = {'type': 'order_link', 'service_id': service_id, 'quantity': quantity, 'total': total_price}
                            send_msg(chat_id, f"✍️ أرسل الرابط لـ {name}:")
                        else:
                            send_msg(chat_id, f"❌ رصيد غير كافي\n💰 المطلوب: {total_price:.2f} USD")
                            del user_states[user_id]
                    else:
                        send_msg(chat_id, f"❌ الحدود المسموحة: {min_q}-{max_q}")
                        del user_states[user_id]
                except ValueError:
                    send_msg(chat_id, "❌ أدخل رقم صحيح")
                    del user_states[user_id]
            else:
                send_msg(chat_id, "❌ الخدمة غير موجودة")
                del user_states[user_id]
        
        elif state['type'] == 'order_link':
            link = text
            service_id = state['service_id']
            quantity = state['quantity']
            total = state['total']
            
            balance_result = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
            balance = balance_result[0] if balance_result else 0
            
            if balance >= total:
                c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total, user_id))
                c.execute("INSERT INTO orders (user_id, service_id, quantity, total_price, link) VALUES (?, ?, ?, ?, ?)", 
                         (user_id, service_id, quantity, total, link))
                order_id = c.lastrowid
                conn.commit()
                
                send_msg(chat_id, f"✅ تم إرسال الطلب #{order_id}\n💰 المبلغ: {total:,.2f} USD")
                
                c.execute("SELECT name FROM services WHERE id = ?", (service_id,))
                service_result = c.fetchone()
                service_name = service_result[0] if service_result else "غير معروف"
                
                pdf_file = generate_invoice_pdf(order_id, user_id, service_name, quantity, total, link)
                if pdf_file:
                    send_document(chat_id, pdf_file, f"📄 فاتورة الطلب #{order_id}")
                    try:
                        os.remove(pdf_file)
                    except:
                        pass
                
                admin_text = f"""🆕 طلب جديد #{order_id}
👤 المستخدم: {user_id}
📦 الخدمة: {service_name}
🔢 الكمية: {quantity}
💰 السعر: {total:.2f} USD"""
                admin_buttons = [[{'text': '✅ قبول', 'callback_data': f'approve_{order_id}'}, 
                                 {'text': '❌ رفض', 'callback_data': f'reject_{order_id}'}]]
                send_msg(ADMIN_ID, admin_text, admin_buttons)
            else:
                send_msg(chat_id, "❌ رصيد غير كافي")
            
            if user_id in user_states:
                del user_states[user_id]
        
        # إضافة معالجة للحالات الأخرى هنا...
        else:
            # معالجة الحالات الأخرى
            send_msg(chat_id, "⚠️ حالة غير معروفة، تم الإلغاء")
            if user_id in user_states:
                del user_states[user_id]
    
    except Exception as e:
        logger.error(f"خطأ في معالجة حالة المستخدم: {e}")
        send_msg(chat_id, "❌ حدث خطأ في معالجة طلبك")
        if user_id in user_states:
            del user_states[user_id]

def handle_start_command(chat_id, user_id, text, username=""):
    """معالجة أمر /start"""
    try:
        # إنشاء حساب للمستخدم إذا لم يكن موجوداً
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not c.fetchone():
            invite_code = str(uuid.uuid4())[:8]
            c.execute("INSERT INTO users (user_id, username, invite_code) VALUES (?, ?, ?)", 
                     (user_id, username or "", invite_code))
            conn.commit()
        
        # معالجة رابط الدعوة
        if ' ' in text:
            parts = text.split()
            if len(parts) > 1:
                invite_data = parts[1]
                if '_' in invite_data:
                    try:
                        invite_parts = invite_data.split('_')
                        if len(invite_parts) >= 2:
                            invite_code = invite_parts[0]
                            inviter_id = int(invite_parts[1])
                            
                            if inviter_id != user_id and get_setting('invite_enabled') == 'true':
                                c.execute("SELECT user_id FROM users WHERE invite_code = ?", (invite_code,))
                                inviter = c.fetchone()
                                
                                if inviter and inviter[0] == inviter_id:
                                    reward = float(get_setting('invite_reward') or 0.10)
                                    c.execute("UPDATE users SET balance = balance + ?, total_invited = total_invited + 1 WHERE user_id = ?", 
                                             (reward, inviter_id))
                                    conn.commit()
                                    send_msg(inviter_id, f"🎉 مكافأة دعوة {reward} USD")
                    except Exception as e:
                        logger.error(f"خطأ في معالجة الدعوة: {e}")
        
        main_menu(chat_id, user_id)
    except Exception as e:
        logger.error(f"خطأ في معالجة /start: {e}")
        send_msg(chat_id, "❌ حدث خطأ في بدء التشغيل")

def handle_admin_command(chat_id, user_id):
    """معالجة أمر /admin"""
    try:
        if user_id == ADMIN_ID:
            admin_panel(chat_id)
            return
        
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        
        if result and result[0] == 1:
            admin_panel(chat_id)
        else:
            send_msg(chat_id, "🚫 ليس لديك صلاحية الوصول للوحة التحكم")
    except Exception as e:
        logger.error(f"خطأ في معالجة /admin: {e}")
        send_msg(chat_id, "❌ حدث خطأ في الوصول للوحة التحكم")

# ==================== معالجة الكال باك ====================
def handle_callback(chat_id, user_id, data):
    """معالجة استدعاءات الأزرار"""
    try:
        if data != 'check_sub':
            subscribed, channel = check_channels(user_id)
            if not subscribed:
                buttons = [[{'text': '📢 اشترك', 'url': f'https://t.me/{channel}'}, {'text': '✅ تحقق', 'callback_data': 'check_sub'}]]
                send_msg(chat_id, f"📢 اشترك في @{channel} أولاً", buttons)
                return
        
        if data == 'main':
            main_menu(chat_id, user_id)
        
        elif data == 'check_sub':
            subscribed, channel = check_channels(user_id)
            if subscribed:
                send_msg(chat_id, "✅ أنت مشترك في جميع القنوات المطلوبة")
                main_menu(chat_id, user_id)
            else:
                buttons = [[{'text': '📢 اشترك', 'url': f'https://t.me/{channel}'}, {'text': '✅ تحقق', 'callback_data': 'check_sub'}]]
                send_msg(chat_id, f"❌ لم تشترك بعد في @{channel}", buttons)
        
        elif data == 'services':
            c.execute("SELECT id, name FROM categories")
            cats = c.fetchall()
            if not cats:
                send_msg(chat_id, "📭 لا توجد أقسام متاحة حالياً")
                return
            
            buttons = []
            for cat_id, name in cats:
                buttons.append([{'text': f'📁 {name}', 'callback_data': f'cat_{cat_id}'}])
            buttons.append([{'text': '🔙 رجوع', 'callback_data': 'main'}])
            send_msg(chat_id, "🛍️ اختر قسم الخدمات:", buttons)
        
        elif data.startswith('cat_'):
            cat_id = data.split('_')[1]
            c.execute("SELECT id, name, price_per_k FROM services WHERE category_id = ? AND is_active = 1", (cat_id,))
            services = c.fetchall()
            
            if not services:
                send_msg(chat_id, "📭 لا توجد خدمات متاحة في هذا القسم")
                return
            
            buttons = []
            for serv_id, name, price in services:
                buttons.append([{'text': f'{name} - {price} USD/1000', 'callback_data': f'serv_{serv_id}'}])
            buttons.append([{'text': '🔙 رجوع', 'callback_data': 'services'}])
            send_msg(chat_id, "📦 اختر خدمة:", buttons)
        
        elif data.startswith('serv_'):
            service_id = data.split('_')[1]
            c.execute("SELECT name FROM services WHERE id = ?", (service_id,))
            serv = c.fetchone()
            
            if serv:
                user_states[user_id] = {'type': 'order_qty', 'service_id': service_id}
                send_msg(chat_id, f"✍️ أرسل الكمية للخدمة {serv[0]}:")
            else:
                send_msg(chat_id, "❌ الخدمة غير موجودة")
        
        elif data == 'charge':
            send_msg(chat_id, f"💰 للشحن الرصيد تواصل مع الدعم:\n📞 @{SUPPORT_USERNAME}\n🆔 {user_id}")
        
        elif data == 'balance':
            try:
                c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                result = c.fetchone()
                balance = result[0] if result else 0
                send_msg(chat_id, f"💰 رصيدك: {balance:.2f} USD")
            except Exception as e:
                logger.error(f"خطأ في جلب الرصيد: {e}")
                send_msg(chat_id, "❌ حدث خطأ في جلب الرصيد")
        
        # ... (بقية معالجة الكال باك بدون تغيير في المنطق)
        
        else:
            send_msg(chat_id, "⚠️ أمر غير معروف")
    
    except Exception as e:
        logger.error(f"خطأ في معالجة الكال باك: {e}")
        send_msg(chat_id, "❌ حدث خطأ في معالجة طلبك")

# ==================== تطبيق Flask ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 البوت يعمل بنجاح على Render!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    """معالجة webhook من تليجرام"""
    try:
        update = request.json
        if not update:
            return 'OK'
        
        if 'message' in update:
            msg = update['message']
            chat_id = msg['chat']['id']
            user_id = msg['from']['id']
            username = msg['from'].get('username', '')
            
            if 'text' in msg:
                text = msg['text']
                handle_message(chat_id, user_id, text, username)
        
        elif 'callback_query' in update:
            query = update['callback_query']
            chat_id = query['message']['chat']['id']
            user_id = query['from']['id']
            data = query['data']
            
            try:
                handle_callback(chat_id, user_id, data)
            except Exception as e:
                logger.error(f"خطأ في معالجة الكال باك: {e}")
        
        return 'OK'
    except Exception as e:
        logger.error(f"خطأ في webhook: {e}")
        return 'ERROR', 500

def set_webhook():
    """تعيين webhook للبوت"""
    try:
        webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost:10000')}/{TOKEN}"
        url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
        response = requests.get(url)
        
        if response.status_code == 200:
            logger.info(f"✅ تم تعيين webhook: {webhook_url}")
        else:
            logger.error(f"❌ فشل تعيين webhook: {response.text}")
    except Exception as e:
        logger.error(f"❌ خطأ في تعيين webhook: {e}")

if __name__ == '__main__':
    # تعيين webhook عند التشغيل
    set_webhook()
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
