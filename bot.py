import sqlite3
import requests
import time
import json
import uuid
import random
import string
from datetime import datetime, timedelta
import os
from fpdf import FPDF
import traceback

# ==================== إعدادات البوت ====================
TOKEN = "8436742877:AAGhCfnC9hbW7Sa4gMTroYissoljCjda9Ow"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"

# ==================== قاعدة البيانات ====================
conn = sqlite3.connect('/tmp/bot.db', check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (user_id INTEGER PRIMARY KEY, username TEXT, 
             balance REAL DEFAULT 0, is_admin INTEGER DEFAULT 0, 
             is_banned INTEGER DEFAULT 0, is_restricted INTEGER DEFAULT 0,
             invited_by INTEGER DEFAULT 0, invite_code TEXT UNIQUE,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
             daily_reward_date TEXT DEFAULT '',
             total_invited INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS categories 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')

c.execute('''CREATE TABLE IF NOT EXISTS services 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, 
             price_per_k REAL, min_order INTEGER DEFAULT 100, 
             max_order INTEGER DEFAULT 10000, description TEXT DEFAULT '',
             is_active INTEGER DEFAULT 1)''')

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
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, channel_link TEXT,
             channel_username TEXT, members_requested INTEGER, members_delivered INTEGER DEFAULT 0,
             price_per_member REAL, total_cost REAL, status TEXT DEFAULT 'pending',
             admin_note TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
             completed_at TIMESTAMP DEFAULT NULL)''')

c.execute('''CREATE TABLE IF NOT EXISTS funding_history
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, funding_id INTEGER,
             action TEXT, note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# إعدادات افتراضية
default_settings = [
    ('maintenance', 'false'),
    ('maintenance_msg', 'البوت تحت الصيانة'),
    ('invite_reward', '0.10'),
    ('invite_enabled', 'true'),
    ('force_subscribe', 'false'),
    ('bot_username', BOT_USERNAME),
    ('daily_reward', '0.05'),
    ('channel_funding_enabled', 'true'),
    ('price_per_member', '0.02'),
    ('min_members', '100'),
    ('max_members', '10000'),
    ('min_order_amount', '0.50'),
    ('max_orders_per_day', '10'),
    ('welcome_message', 'مرحباً بك في البوت!'),
    ('support_message', f'للتواصل مع الدعم: @{SUPPORT_USERNAME}')
]

for key, value in default_settings:
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

# إضافة المدير
c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
          (ADMIN_ID, "المدير", 100000, 1, 'ADMIN'))

conn.commit()

# ==================== وظائف مساعدة ====================
def get_setting(key):
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = c.fetchone()
    return result[0] if result else None

def update_setting(key, value):
    c.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    conn.commit()

def send_msg(chat_id, text, buttons=None, parse_mode='HTML'):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
        if buttons:
            data['reply_markup'] = json.dumps({'inline_keyboard': buttons})
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"⚠️ خطأ في الإرسال: {e}")
        return None

def send_document(chat_id, document_path, caption=""):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
        with open(document_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            response = requests.post(url, files=files, data=data, timeout=20)
            return response.json()
    except Exception as e:
        print(f"⚠️ خطأ في إرسال الملف: {e}")
        return None

def edit_message(chat_id, message_id, text, buttons=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        if buttons:
            data['reply_markup'] = json.dumps({'inline_keyboard': buttons})
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"⚠️ خطأ في تعديل الرسالة: {e}")
        return None

def check_channels(user_id):
    if get_setting('force_subscribe') != 'true':
        return True, None
    
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
        except:
            continue
    
    return True, None

def generate_invite_code():
    """إنشاء كود دعوة فريد"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        c.execute("SELECT COUNT(*) FROM users WHERE invite_code = ?", (code,))
        if c.fetchone()[0] == 0:
            return code

def generate_invoice_pdf(order_id, user_id, service_name, quantity, total_price, link):
    """إنشاء فاتورة PDF للطلب"""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(200, 10, 'Flashbot Invoice', 0, 1, 'C')
        pdf.ln(5)
        
        # Invoice Details
        pdf.set_font('Arial', '', 12)
        pdf.cell(50, 10, f'Invoice ID: #{order_id}', 0, 1)
        pdf.cell(50, 10, f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
        pdf.cell(50, 10, f'User ID: {user_id}', 0, 1)
        pdf.ln(5)
        
        # Order Details
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(200, 10, 'Order Details', 0, 1, 'C')
        pdf.set_font('Arial', '', 12)
        pdf.cell(100, 10, f'Service: {service_name}', 0, 1)
        pdf.cell(100, 10, f'Quantity: {quantity}', 0, 1)
        pdf.cell(100, 10, f'Link: {link}', 0, 1)
        pdf.cell(100, 10, f'Total Price: ${total_price:.2f} USD', 0, 1)
        pdf.ln(10)
        
        # Thank You Message
        thank_you_messages = [
            "Thank you for your order! We appreciate your business.",
            "Your support means a lot to us. Thank you for choosing our service!",
            "We're grateful for your trust in our services. Thank you for your order!",
            "Thank you for your purchase! We're committed to providing the best service.",
            "Your satisfaction is our priority. Thank you for ordering with us!"
        ]
        pdf.set_font('Arial', 'I', 12)
        pdf.multi_cell(0, 10, random.choice(thank_you_messages))
        
        # Footer
        pdf.ln(10)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 10, 'Powered by Flashbot - Professional Telegram Bot', 0, 1, 'C')
        
        # Save PDF
        filename = f'invoice_{order_id}.pdf'
        pdf.output(filename)
        return filename
    except Exception as e:
        print(f"⚠️ خطأ في إنشاء PDF: {e}")
        return None

def generate_funding_pdf(funding_id, user_id, channel_link, members_requested, total_cost):
    """إنشاء فاتورة PDF لتمويل القنوات"""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(200, 10, 'Channel Funding Invoice', 0, 1, 'C')
        pdf.ln(5)
        
        pdf.set_font('Arial', '', 12)
        pdf.cell(50, 10, f'Funding ID: #{funding_id}', 0, 1)
        pdf.cell(50, 10, f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
        pdf.cell(50, 10, f'User ID: {user_id}', 0, 1)
        pdf.ln(5)
        
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(200, 10, 'Funding Details', 0, 1, 'C')
        pdf.set_font('Arial', '', 12)
        pdf.cell(100, 10, f'Channel: {channel_link}', 0, 1)
        pdf.cell(100, 10, f'Members Requested: {members_requested}', 0, 1)
        pdf.cell(100, 10, f'Price per Member: ${get_setting("price_per_member")} USD', 0, 1)
        pdf.cell(100, 10, f'Total Cost: ${total_cost:.2f} USD', 0, 1)
        pdf.ln(10)
        
        thank_you_messages = [
            "Thank you for funding your channel with us!",
            "We'll help grow your channel effectively. Thank you!",
            "Your channel growth is our mission. Thank you for trusting us!",
            "Professional channel funding service. Thank you for your order!",
            "Let's make your channel bigger together. Thank you!"
        ]
        pdf.set_font('Arial', 'I', 12)
        pdf.multi_cell(0, 10, random.choice(thank_you_messages))
        
        pdf.ln(10)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 10, 'Channel Funding Service - Flashbot', 0, 1, 'C')
        
        filename = f'funding_{funding_id}.pdf'
        pdf.output(filename)
        return filename
    except Exception as e:
        print(f"⚠️ خطأ في إنشاء PDF للتمويل: {e}")
        return None

def is_user_admin(user_id):
    """التحقق إذا كان المستخدم مشرف"""
    c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result and result[0] == 1

def is_user_banned(user_id):
    """التحقق إذا كان المستخدم محظور"""
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result and result[0] == 1

def get_user_balance(user_id):
    """الحصول على رصيد المستخدم"""
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result[0] if result else 0

# ==================== القوائم الرئيسية ====================
def main_menu(chat_id, user_id, message_id=None):
    """القائمة الرئيسية"""
    # التحقق من الصيانة
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_msg(chat_id, get_setting('maintenance_msg'))
        return
    
    # التحقق من القنوات
    subscribed, channel = check_channels(user_id)
    if not subscribed:
        buttons = [[
            {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
            {'text': '✅ تحقق من الاشتراك', 'callback_data': 'check_sub'}
        ]]
        send_msg(chat_id, f"📢 يجب الاشتراك في @{channel} أولاً لتتمكن من استخدام البوت", buttons)
        return
    
    # التحقق من الحظر
    if is_user_banned(user_id):
        send_msg(chat_id, "🚫 تم حظرك من استخدام البوت")
        return
    
    c.execute("SELECT username, balance, is_admin FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone() or (None, 0, 0)
    
    # التحقق من هدية اليوم
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT daily_reward_date FROM users WHERE user_id = ?", (user_id,))
    last_reward = c.fetchone()
    daily_reward_available = False
    if last_reward and last_reward[0] != today:
        daily_reward_available = True
    
    text = f"""👋 أهلاً {user[0] or 'مستخدم'}

🆔 الآيدي: <code>{user_id}</code>
💰 الرصيد: <b>{user[1]:,.2f} USD</b>
📅 تاريخ اليوم: {today}

📌 اختر من القائمة:"""
    
    buttons = [
        [{'text': '🛍️ خدمات', 'callback_data': 'services'}],
        [{'text': '💰 شحن الرصيد', 'callback_data': 'charge'}, {'text': '💳 رصيدي', 'callback_data': 'balance'}],
        [{'text': '👥 دعوة أصدقاء', 'callback_data': 'invite'}, {'text': '📋 طلباتي', 'callback_data': 'my_orders'}]
    ]
    
    if daily_reward_available:
        buttons.append([{'text': '🎁 هدية اليوم', 'callback_data': 'daily_reward'}])
    
    buttons.append([{'text': '📺 تمويل القنوات', 'callback_data': 'channel_funding'}, {'text': '📞 الدعم', 'callback_data': 'support'}])
    
    if user[2] == 1 or user_id == ADMIN_ID:
        buttons.append([{'text': '👑 لوحة التحكم', 'callback_data': 'admin_panel'}])
    
    if message_id:
        edit_message(chat_id, message_id, text, buttons)
    else:
        send_msg(chat_id, text, buttons)

def services_menu(chat_id, message_id=None):
    """قائمة الخدمات"""
    c.execute("SELECT id, name FROM categories")
    categories = c.fetchall()
    
    if not categories:
        text = "📭 لا توجد أقسام خدمات متاحة حالياً"
        buttons = [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]
    else:
        text = "🛍️ <b>الأقسام المتاحة</b>\n\nاختر القسم الذي تريد:"
        buttons = []
        for cat_id, name in categories:
            buttons.append([{'text': f'📁 {name}', 'callback_data': f'cat_{cat_id}'}])
        buttons.append([{'text': '🔙 رجوع', 'callback_data': 'main'}])
    
    if message_id:
        edit_message(chat_id, message_id, text, buttons)
    else:
        send_msg(chat_id, text, buttons)

def category_menu(chat_id, category_id, message_id=None):
    """قائمة خدمات القسم"""
    c.execute("SELECT id, name, price_per_k, min_order, max_order FROM services WHERE category_id = ? AND is_active = 1", (category_id,))
    services = c.fetchall()
    
    if not services:
        text = "📭 لا توجد خدمات في هذا القسم حالياً"
        buttons = [[{'text': '🔙 رجوع', 'callback_data': 'services'}]]
    else:
        c.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
        cat_name = c.fetchone()[0]
        
        text = f"📦 <b>خدمات قسم {cat_name}</b>\n\nاختر الخدمة التي تريد:"
        buttons = []
        for service_id, name, price, min_q, max_q in services:
            btn_text = f'{name} - {price} USD/1000'
            buttons.append([{'text': btn_text, 'callback_data': f'serv_{service_id}'}])
        buttons.append([{'text': '🔙 رجوع', 'callback_data': 'services'}])
    
    if message_id:
        edit_message(chat_id, message_id, text, buttons)
    else:
        send_msg(chat_id, text, buttons)

def invite_menu(chat_id, user_id, message_id=None):
    """قائمة الدعوة"""
    c.execute("SELECT invite_code, total_invited FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    
    if not user_data:
        send_msg(chat_id, "❌ خطأ في بيانات المستخدم")
        return
    
    invite_code, total_invited = user_data
    reward = float(get_setting('invite_reward'))
    
    # إنشاء رابط الدعوة الصحيح
    bot_username = get_setting('bot_username') or BOT_USERNAME
    unique_code = f"{invite_code}_{user_id}_{random.randint(1000, 9999)}"
    invite_link = f"https://t.me/{bot_username}?start={unique_code}"
    
    text = f"""👥 <b>دعوة أصدقاء</b>

💰 المكافأة: <code>{reward} USD</code> لكل صديق
👥 عدد الدعوات: <code>{total_invited}</code> صديق
💰 أرباحك من الدعوة: <code>{total_invited * reward:.2f} USD</code>

🔗 <b>رابط دعوتك:</b>
<code>{invite_link}</code>

📝 <b>كيفية العمل:</b>
1. أرسل الرابط لأصدقائك
2. عندما يسجل صديق عبر رابطك
3. تحصل على <code>{reward} USD</code> تلقائياً
4. يمكنك سحب الأرباح أو استخدامها في الطلبات"""
    
    buttons = [
        [{'text': '📤 مشاركة الرابط', 'url': f'tg://msg_url?url={invite_link}&text=انضم%20للحصول%20على%20خدمات%20رائعة'}],
        [{'text': '💰 أرباحي من الدعوة', 'callback_data': 'invite_earnings'}],
        [{'text': '🔙 رجوع', 'callback_data': 'main'}]
    ]
    
    if message_id:
        edit_message(chat_id, message_id, text, buttons)
    else:
        send_msg(chat_id, text, buttons)

def channel_funding_menu(chat_id, user_id, message_id=None):
    """قائمة تمويل القنوات"""
    if get_setting('channel_funding_enabled') != 'true':
        text = "⏸️ خدمة تمويل القنوات معطلة حالياً من قبل الإدارة"
        buttons = [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]
    else:
        price_per_member = float(get_setting('price_per_member'))
        min_members = int(get_setting('min_members'))
        max_members = int(get_setting('max_members'))
        
        # حساب طلبات المستخدم
        c.execute("""
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                   SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM channel_funding 
            WHERE user_id = ?
        """, (user_id,))
        stats = c.fetchone() or (0, 0, 0)
        
        text = f"""📺 <b>تمويل القنوات</b>

💰 سعر العضو الواحد: <code>{price_per_member} USD</code>
🔢 الحد الأدنى للأعضاء: <code>{min_members}</code>
🔢 الحد الأقصى للأعضاء: <code>{max_members}</code>

📊 <b>إحصائيات طلباتك:</b>
📋 إجمالي الطلبات: <code>{stats[0]}</code>
✅ المكتملة: <code>{stats[1]}</code>
⏳ المعلقة: <code>{stats[2]}</code>

📝 <b>شروط الخدمة:</b>
1. يجب أن يكون البوت @{BOT_USERNAME} مشرفاً في القناة
2. الدفع مسبقاً من الرصيد
3. مدة التنفيذ: 24-72 ساعة
4. في حالة رفض الطلب، يتم إرجاع المبلغ"""
        
        buttons = [
            [{'text': '📤 طلب تمويل جديد', 'callback_data': 'new_funding_request'}],
            [{'text': '📋 طلبات التمويل', 'callback_data': 'my_funding_requests'}],
            [{'text': '🔙 رجوع', 'callback_data': 'main'}]
        ]
    
    if message_id:
        edit_message(chat_id, message_id, text, buttons)
    else:
        send_msg(chat_id, text, buttons)

def admin_panel_menu(chat_id, message_id=None):
    """لوحة تحكم المدير"""
    if message_id:
        edit_func = edit_message
    else:
        edit_func = send_msg
    
    # إحصائيات سريعة
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    pending_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM channel_funding WHERE status = 'pending'")
    pending_funding = c.fetchone()[0]
    
    c.execute("SELECT SUM(balance) FROM users")
    total_balance = c.fetchone()[0] or 0
    
    text = f"""👑 <b>لوحة تحكم المدير</b>

📊 <b>إحصائيات سريعة:</b>
👥 المستخدمين: <code>{total_users}</code>
📦 طلبات معلقة: <code>{pending_orders}</code>
📺 تمويل معلق: <code>{pending_funding}</code>
💰 إجمالي الأرصدة: <code>{total_balance:,.2f} USD</code>

📌 اختر من القائمة:"""
    
    buttons = [
        [{'text': '📊 الإحصائيات', 'callback_data': 'admin_stats'}, {'text': '👥 المستخدمين', 'callback_data': 'admin_users'}],
        [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'admin_services'}, {'text': '📦 إدارة الطلبات', 'callback_data': 'admin_orders'}],
        [{'text': '🚫 إدارة الحظر', 'callback_data': 'admin_bans'}, {'text': '👑 إدارة المشرفين', 'callback_data': 'admin_admins'}],
        [{'text': '📢 القنوات الإجبارية', 'callback_data': 'admin_channels'}, {'text': '📺 إدارة التمويل', 'callback_data': 'admin_funding'}],
        [{'text': '⚙️ الإعدادات', 'callback_data': 'admin_settings'}, {'text': '🎁 إرسال للجميع', 'callback_data': 'admin_broadcast'}],
        [{'text': '🔙 الرئيسية', 'callback_data': 'main'}]
    ]
    
    edit_func(chat_id, text, buttons)

# ==================== معالجة الرسائل ====================
user_states = {}

def handle_message(chat_id, user_id, text, username=""):
    """معالجة الرسائل النصية"""
    try:
        # تحديث اسم المستخدم إذا كان موجوداً
        if username:
            c.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
            conn.commit()
        
        # التحقق من الصيانة
        if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
            send_msg(chat_id, get_setting('maintenance_msg'))
            return
        
        # التحقق من القنوات الإجبارية
        subscribed, channel = check_channels(user_id)
        if not subscribed:
            buttons = [[
                {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
                {'text': '✅ تحقق من الاشتراك', 'callback_data': 'check_sub'}
            ]]
            send_msg(chat_id, f"📢 يجب الاشتراك في @{channel} أولاً", buttons)
            return
        
        # التحقق من الحظر
        if is_user_banned(user_id):
            send_msg(chat_id, "🚫 تم حظرك من استخدام البوت")
            return
        
        # التحقق من الحالات النشطة
        if user_id in user_states:
            state = user_states[user_id]
            handle_user_state(chat_id, user_id, text, state)
            return
        
        # أوامر خاصة
        if text == '/start':
            handle_start_command(chat_id, user_id, text, username)
        elif text == '/admin' and (user_id == ADMIN_ID or is_user_admin(user_id)):
            admin_panel_menu(chat_id)
        else:
            main_menu(chat_id, user_id)
            
    except Exception as e:
        print(f"⚠️ خطأ في handle_message: {e}")
        traceback.print_exc()
        send_msg(chat_id, "❌ حدث خطأ غير متوقع. الرجاء المحاولة لاحقاً.")

def handle_start_command(chat_id, user_id, text, username):
    """معالجة أمر /start"""
    # التحقق من كود الدعوة
    if len(text.split()) > 1:
        invite_data = text.split()[1]
        if '_' in invite_data:
            try:
                parts = invite_data.split('_')
                if len(parts) >= 2:
                    invite_code = parts[0]
                    inviter_id = int(parts[1])
                    
                    # التحقق من صحة الدعوة
                    if inviter_id != user_id and get_setting('invite_enabled') == 'true':
                        c.execute("SELECT user_id FROM users WHERE invite_code = ?", (invite_code,))
                        inviter = c.fetchone()
                        
                        if inviter and inviter[0] == inviter_id:
                            reward = float(get_setting('invite_reward'))
                            c.execute("UPDATE users SET balance = balance + ?, total_invited = total_invited + 1 WHERE user_id = ?", 
                                    (reward, inviter_id))
                            conn.commit()
                            
                            # إشعار الداعي
                            send_msg(inviter_id, f"🎉 مكافأة دعوة!\n💰 حصلت على {reward} USD\n👤 قام {username or user_id} بالتسجيل عبر رابطك")
            except:
                pass
    
    # تسجيل المستخدم الجديد
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        invite_code = generate_invite_code()
        c.execute("INSERT INTO users (user_id, username, invite_code) VALUES (?, ?, ?)", 
                 (user_id, username, invite_code))
        conn.commit()
        
        # إشعار المدير بمستخدم جديد
        if user_id != ADMIN_ID:
            send_msg(ADMIN_ID, f"👤 مستخدم جديد!\n🆔 {user_id}\n📛 @{username}\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # عرض الرسالة الترحيبية
    welcome_msg = get_setting('welcome_message')
    if welcome_msg:
        send_msg(chat_id, welcome_msg)
    
    main_menu(chat_id, user_id)

def handle_user_state(chat_id, user_id, text, state):
    """معالجة الحالات النشطة للمستخدم"""
    try:
        if state['type'] == 'order_quantity':
            service_id = state['service_id']
            c.execute("SELECT name, price_per_k, min_order, max_order FROM services WHERE id = ?", (service_id,))
            service = c.fetchone()
            
            if service:
                name, price, min_q, max_q = service
                try:
                    quantity = int(text)
                    if min_q <= quantity <= max_q:
                        total_price = (price / 1000) * quantity
                        
                        # التحقق من الرصيد
                        balance = get_user_balance(user_id)
                        if balance >= total_price:
                            user_states[user_id] = {
                                'type': 'order_link',
                                'service_id': service_id,
                                'quantity': quantity,
                                'total_price': total_price
                            }
                            send_msg(chat_id, f"✅ الكمية: {quantity}\n💰 الإجمالي: {total_price:.2f} USD\n✍️ أرسل الرابط الآن:")
                        else:
                            send_msg(chat_id, f"❌ رصيد غير كافي\n💰 المطلوب: {total_price:.2f} USD\n💳 رصيدك: {balance:.2f} USD")
                            del user_states[user_id]
                    else:
                        send_msg(chat_id, f"❌ الكمية خارج النطاق\n🔢 المسموح: {min_q} - {max_q}")
                except:
                    send_msg(chat_id, "❌ الرجاء إدخال رقم صحيح")
            else:
                send_msg(chat_id, "❌ الخدمة غير موجودة")
                del user_states[user_id]
        
        elif state['type'] == 'order_link':
            link = text.strip()
            service_id = state['service_id']
            quantity = state['quantity']
            total_price = state['total_price']
            
            # التحقق من صحة الرابط
            if not link.startswith(('http://', 'https://')):
                send_msg(chat_id, "❌ الرابط غير صحيح. يجب أن يبدأ بـ http:// أو https://")
                return
            
            # خصم المبلغ وإنشاء الطلب
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_price, user_id))
            c.execute("""INSERT INTO orders (user_id, service_id, quantity, total_price, link, status) 
                         VALUES (?, ?, ?, ?, ?, 'pending')""",
                     (user_id, service_id, quantity, total_price, link))
            order_id = c.lastrowid
            
            # الحصول على اسم الخدمة
            c.execute("SELECT name FROM services WHERE id = ?", (service_id,))
            service_name = c.fetchone()[0]
            
            conn.commit()
            
            # إرسال تأكيد للمستخدم مع فاتورة PDF
            send_msg(chat_id, f"""✅ تم إنشاء الطلب #{order_id}
📦 الخدمة: {service_name}
🔢 الكمية: {quantity}
💰 المبلغ: {total_price:.2f} USD
🔗 الرابط: {link[:50]}...

⏳ سيتم معالجة طلبك قريباً""")
            
            # إنشاء وإرسال فاتورة PDF
            pdf_file = generate_invoice_pdf(order_id, user_id, service_name, quantity, total_price, link)
            if pdf_file:
                send_document(chat_id, pdf_file, f"📄 فاتورة الطلب #{order_id}")
                os.remove(pdf_file)
            
            # إشعار المدير مع أزرار التحكم
            c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
            username = c.fetchone()[0] or f"ID: {user_id}"
            
            admin_text = f"""🆕 <b>طلب جديد #{order_id}</b>

👤 المستخدم: {username}
🆔 الآيدي: <code>{user_id}</code>
📦 الخدمة: {service_name}
🔢 الكمية: {quantity}
💰 المبلغ: {total_price:.2f} USD
🔗 الرابط: {link}

📅 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            admin_buttons = [
                [{'text': '✅ قبول الطلب', 'callback_data': f'approve_order_{order_id}'},
                 {'text': '❌ رفض الطلب', 'callback_data': f'reject_order_{order_id}'}],
                [{'text': '👁️ عرض التفاصيل', 'callback_data': f'view_order_{order_id}'}]
            ]
            
            send_msg(ADMIN_ID, admin_text, admin_buttons)
            
            del user_states[user_id]
        
        elif state['type'] == 'funding_channel':
            channel_link = text.strip()
            
            # التحقق من صحة رابط القناة
            if not ('t.me/' in channel_link or 'telegram.me/' in channel_link):
                send_msg(chat_id, "❌ رابط غير صحيح. يجب أن يكون رابط قناة تليجرام")
                return
            
            user_states[user_id] = {
                'type': 'funding_members',
                'channel_link': channel_link
            }
            
            price_per_member = float(get_setting('price_per_member'))
            min_members = int(get_setting('min_members'))
            max_members = int(get_setting('max_members'))
            
            send_msg(chat_id, f"""🔗 تم حفظ رابط القناة
💰 سعر العضو: {price_per_member} USD
🔢 الحد الأدنى: {min_members} عضو
🔢 الحد الأقصى: {max_members} عضو

✍️ أرسل عدد الأعضاء المطلوب:""")
        
        elif state['type'] == 'funding_members':
            try:
                members = int(text)
                price_per_member = float(get_setting('price_per_member'))
                min_members = int(get_setting('min_members'))
                max_members = int(get_setting('max_members'))
                channel_link = state['channel_link']
                
                if members < min_members:
                    send_msg(chat_id, f"❌ الحد الأدنى هو {min_members} عضو")
                    return
                if members > max_members:
                    send_msg(chat_id, f"❌ الحد الأقصى هو {max_members} عضو")
                    return
                
                total_cost = members * price_per_member
                balance = get_user_balance(user_id)
                
                if balance < total_cost:
                    send_msg(chat_id, f"""❌ رصيد غير كافي
💰 المطلوب: {total_cost:.2f} USD
💳 رصيدك: {balance:.2f} USD
➕ تحتاج: {total_cost - balance:.2f} USD""")
                    del user_states[user_id]
                    return
                
                user_states[user_id] = {
                    'type': 'funding_confirm',
                    'channel_link': channel_link,
                    'members': members,
                    'total_cost': total_cost
                }
                
                # استخراج يوزر القناة
                channel_username = ""
                if 't.me/' in channel_link:
                    channel_username = channel_link.split('t.me/')[-1].replace('@', '')
                
                confirm_text = f"""📺 <b>تأكيد طلب التمويل</b>

🔗 القناة: {channel_link}
👥 عدد الأعضاء: {members}
💰 سعر العضو: {price_per_member} USD
💰 الإجمالي: {total_cost:.2f} USD
💳 رصيدك الحالي: {balance:.2f} USD
💳 الرصيد بعد الخصم: {balance - total_cost:.2f} USD

⚠️ <b>ملاحظات مهمة:</b>
1. يجب أن يكون البوت @{BOT_USERNAME} مشرفاً في القناة
2. مدة التنفيذ: 24-72 ساعة
3. في حالة رفض الطلب، يتم إرجاع المبلغ"""
                
                buttons = [
                    [{'text': '✅ تأكيد الطلب', 'callback_data': 'confirm_funding'}],
                    [{'text': '❌ إلغاء', 'callback_data': 'cancel_funding'}]
                ]
                
                send_msg(chat_id, confirm_text, buttons)
                
            except ValueError:
                send_msg(chat_id, "❌ الرجاء إدخال رقم صحيح")
        
        elif state['type'] == 'reject_reason':
            order_id = state['order_id']
            reason = text
            
            c.execute("UPDATE orders SET status = 'rejected', admin_note = ? WHERE id = ?", (reason, order_id))
            c.execute("SELECT user_id, total_price FROM orders WHERE id = ?", (order_id,))
            order_data = c.fetchone()
            
            if order_data:
                target_user, amount = order_data
                # إرجاع الرصيد
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user))
                conn.commit()
                
                # إعلام المستخدم
                send_msg(target_user, f"""❌ تم رفض طلبك #{order_id}
📝 السبب: {reason}
💰 تم إرجاع {amount:.2f} USD إلى رصيدك""")
                
                send_msg(chat_id, f"✅ تم رفض الطلب #{order_id} وإرجاع المبلغ")
            
            del user_states[user_id]
        
        elif state['type'] == 'admin_charge_user':
            try:
                target_id = int(text)
                c.execute("SELECT username FROM users WHERE user_id = ?", (target_id,))
                if c.fetchone():
                    user_states[user_id] = {
                        'type': 'admin_charge_amount',
                        'target_id': target_id
                    }
                    send_msg(chat_id, f"💰 أرسل المبلغ لإضافة رصيد للمستخدم {target_id}:")
                else:
                    send_msg(chat_id, "❌ المستخدم غير موجود")
                    del user_states[user_id]
            except:
                send_msg(chat_id, "❌ آيدي غير صحيح")
                del user_states[user_id]
        
        elif state['type'] == 'admin_charge_amount':
            try:
                amount = float(text)
                target_id = state['target_id']
                
                if amount <= 0:
                    send_msg(chat_id, "❌ المبلغ يجب أن يكون أكبر من صفر")
                    return
                
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                
                send_msg(chat_id, f"✅ تم إضافة {amount:.2f} USD لرصيد المستخدم {target_id}")
                send_msg(target_id, f"🎉 تم إضافة رصيد لحسابك\n💰 المبلغ: {amount:.2f} USD\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                
                del user_states[user_id]
            except:
                send_msg(chat_id, "❌ مبلغ غير صحيح")
                del user_states[user_id]
        
        elif state['type'] == 'broadcast_message':
            message = text
            user_states[user_id] = {
                'type': 'broadcast_confirm',
                'message': message
            }
            
            text = f"""📢 <b>تأكيد الإرسال للجميع</b>

📝 الرسالة:
{message}

⚠️ سيتم إرسال هذه الرسالة لجميع المستخدمين غير المحظورين."""
            
            buttons = [
                [{'text': '✅ تأكيد الإرسال', 'callback_data': 'confirm_broadcast'},
                 {'text': '❌ إلغاء', 'callback_data': 'cancel_broadcast'}]
            ]
            
            send_msg(chat_id, text, buttons)
        
        elif state['type'] == 'add_service_price':
            try:
                price = float(text)
                user_states[user_id] = {
                    'type': 'add_service_min',
                    'category_id': state['category_id'],
                    'name': state['name'],
                    'price': price
                }
                send_msg(chat_id, "🔢 أدخل الحد الأدنى للطلب:")
            except:
                send_msg(chat_id, "❌ سعر غير صحيح")
                del user_states[user_id]
        
        elif state['type'] == 'add_service_min':
            try:
                min_order = int(text)
                user_states[user_id] = {
                    'type': 'add_service_max',
                    'category_id': state['category_id'],
                    'name': state['name'],
                    'price': state['price'],
                    'min_order': min_order
                }
                send_msg(chat_id, "🔢 أدخل الحد الأقصى للطلب:")
            except:
                send_msg(chat_id, "❌ رقم غير صحيح")
                del user_states[user_id]
        
        elif state['type'] == 'add_service_max':
            try:
                max_order = int(text)
                category_id = state['category_id']
                name = state['name']
                price = state['price']
                min_order = state['min_order']
                
                c.execute("""INSERT INTO services (category_id, name, price_per_k, min_order, max_order, is_active) 
                             VALUES (?, ?, ?, ?, ?, 1)""",
                         (category_id, name, price, min_order, max_order))
                conn.commit()
                
                send_msg(chat_id, f"✅ تم إضافة الخدمة '{name}' بنجاح")
                del user_states[user_id]
            except Exception as e:
                send_msg(chat_id, f"❌ خطأ في الإضافة: {str(e)}")
                del user_states[user_id]
        
        elif state['type'] == 'change_price_per_member':
            try:
                new_price = float(text)
                update_setting('price_per_member', str(new_price))
                send_msg(chat_id, f"✅ تم تغيير سعر العضو إلى {new_price} USD")
                del user_states[user_id]
            except:
                send_msg(chat_id, "❌ سعر غير صحيح")
                del user_states[user_id]
        
        elif state['type'] == 'change_min_members':
            try:
                new_min = int(text)
                update_setting('min_members', str(new_min))
                send_msg(chat_id, f"✅ تم تغيير الحد الأدنى إلى {new_min} عضو")
                del user_states[user_id]
            except:
                send_msg(chat_id, "❌ رقم غير صحيح")
                del user_states[user_id]
        
        elif state['type'] == 'change_max_members':
            try:
                new_max = int(text)
                update_setting('max_members', str(new_max))
                send_msg(chat_id, f"✅ تم تغيير الحد الأقصى إلى {new_max} عضو")
                del user_states[user_id]
            except:
                send_msg(chat_id, "❌ رقم غير صحيح")
                del user_states[user_id]
                
    except Exception as e:
        print(f"⚠️ خطأ في handle_user_state: {e}")
        traceback.print_exc()
        send_msg(chat_id, "❌ حدث خطأ في المعالجة")
        if user_id in user_states:
            del user_states[user_id]

# ==================== معالجة الكال باك ====================
def handle_callback(chat_id, user_id, data, message_id):
    """معالجة أحداث الكال باك"""
    try:
        if data == 'main':
            main_menu(chat_id, user_id, message_id)
        
        elif data == 'check_sub':
            subscribed, channel = check_channels(user_id)
            if subscribed:
                send_msg(chat_id, "✅ أنت مشترك في جميع القنوات الإجبارية")
                main_menu(chat_id, user_id)
            else:
                buttons = [[
                    {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
                    {'text': '✅ تحقق من الاشتراك', 'callback_data': 'check_sub'}
                ]]
                send_msg(chat_id, f"❌ لم تشترك بعد في @{channel}", buttons)
        
        elif data == 'services':
            services_menu(chat_id, message_id)
        
        elif data.startswith('cat_'):
            category_id = data.split('_')[1]
            category_menu(chat_id, category_id, message_id)
        
        elif data.startswith('serv_'):
            service_id = data.split('_')[1]
            c.execute("SELECT name, price_per_k FROM services WHERE id = ?", (service_id,))
            service = c.fetchone()
            
            if service:
                name, price = service
                user_states[user_id] = {
                    'type': 'order_quantity',
                    'service_id': service_id
                }
                send_msg(chat_id, f"🛒 {name}\n💰 السعر: {price} USD لكل 1000\n✍️ أرسل الكمية المطلوبة:")
        
        elif data == 'charge':
            send_msg(chat_id, f"💰 <b>شحن الرصيد</b>\n\n📞 للشحن تواصل مع الدعم:\n👤 @{SUPPORT_USERNAME}\n🆔 آيديك: <code>{user_id}</code>")
        
        elif data == 'balance':
            balance = get_user_balance(user_id)
            send_msg(chat_id, f"💰 <b>رصيدك الحالي:</b> <code>{balance:.2f} USD</code>")
        
        elif data == 'invite':
            invite_menu(chat_id, user_id, message_id)
        
        elif data == 'daily_reward':
            today = datetime.now().strftime("%Y-%m-%d")
            c.execute("SELECT daily_reward_date FROM users WHERE user_id = ?", (user_id,))
            last_reward = c.fetchone()[0]
            
            if last_reward == today:
                send_msg(chat_id, "⏳ لقد حصلت على هدية اليوم بالفعل. عد غداً!")
            else:
                reward = float(get_setting('daily_reward'))
                c.execute("UPDATE users SET balance = balance + ?, daily_reward_date = ? WHERE user_id = ?",
                         (reward, today, user_id))
                conn.commit()
                
                send_msg(chat_id, f"🎉 <b>مبروك! حصلت على هدية اليوم</b>\n💰 المبلغ: <code>{reward} USD</code>\n💳 رصيدك الجديد: <code>{get_user_balance(user_id):.2f} USD</code>")
        
        elif data == 'my_orders':
            c.execute("""
                SELECT o.id, s.name, o.quantity, o.total_price, o.status, o.link, o.created_at
                FROM orders o
                JOIN services s ON o.service_id = s.id
                WHERE o.user_id = ?
                ORDER BY o.created_at DESC
                LIMIT 10
            """, (user_id,))
            orders = c.fetchall()
            
            if orders:
                text = "📋 <b>طلباتك الأخيرة</b>\n\n"
                for order in orders:
                    oid, name, qty, price, status, link, created_at = order
                    status_icons = {
                        'pending': '🕒',
                        'processing': '⏳',
                        'completed': '✅',
                        'rejected': '❌'
                    }
                    icon = status_icons.get(status, '📌')
                    text += f"{icon} <b>#{oid}</b> - {name}\n"
                    text += f"🔢 {qty} | 💰 {price:.2f} USD\n"
                    text += f"📊 {status} | 📅 {created_at[:10]}\n"
                    if link:
                        text += f"🔗 {link[:40]}...\n"
                    text += "━━━━━━━━━━\n"
            else:
                text = "📭 لا توجد طلبات سابقة"
            
            send_msg(chat_id, text)
        
        elif data == 'channel_funding':
            channel_funding_menu(chat_id, user_id, message_id)
        
        elif data == 'new_funding_request':
            if get_setting('channel_funding_enabled') != 'true':
                send_msg(chat_id, "⏸️ الخدمة معطلة حالياً")
                return
            
            user_states[user_id] = {
                'type': 'funding_channel'
            }
            send_msg(chat_id, "📺 <b>طلب تمويل قناة جديد</b>\n\n🔗 أرسل رابط القناة (يجب أن يكون البوت مشرفاً فيها):")
        
        elif data == 'my_funding_requests':
            c.execute("""
                SELECT id, channel_link, members_requested, members_delivered, status, total_cost, created_at
                FROM channel_funding
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 10
            """, (user_id,))
            requests = c.fetchall()
            
            if requests:
                text = "📺 <b>طلبات تمويل القنوات</b>\n\n"
                for req in requests:
                    req_id, channel, req_members, del_members, status, cost, created = req
                    status_icons = {
                        'pending': '🕒',
                        'processing': '⏳',
                        'completed': '✅',
                        'rejected': '❌'
                    }
                    icon = status_icons.get(status, '📌')
                    text += f"{icon} <b>#{req_id}</b> - {channel[:20]}...\n"
                    text += f"👥 {del_members}/{req_members} | 💰 {cost:.2f} USD\n"
                    text += f"📊 {status} | 📅 {created[:10]}\n"
                    text += "━━━━━━━━━━\n"
            else:
                text = "📭 لا توجد طلبات تمويل سابقة"
            
            send_msg(chat_id, text)
        
        elif data == 'confirm_funding':
            if user_id in user_states and user_states[user_id]['type'] == 'funding_confirm':
                state = user_states[user_id]
                channel_link = state['channel_link']
                members = state['members']
                total_cost = state['total_cost']
                
                # استخراج يوزر القناة
                channel_username = ""
                if 't.me/' in channel_link:
                    channel_username = channel_link.split('t.me/')[-1].replace('@', '')
                
                # خصم المبلغ
                balance = get_user_balance(user_id)
                if balance < total_cost:
                    send_msg(chat_id, "❌ رصيد غير كافي")
                    del user_states[user_id]
                    return
                
                c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, user_id))
                
                # إنشاء طلب التمويل
                price_per_member = float(get_setting('price_per_member'))
                c.execute("""INSERT INTO channel_funding 
                            (user_id, channel_link, channel_username, members_requested, 
                             price_per_member, total_cost, status) 
                            VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
                         (user_id, channel_link, channel_username, members, price_per_member, total_cost))
                funding_id = c.lastrowid
                
                conn.commit()
                
                # إرسال تأكيد للمستخدم مع فاتورة PDF
                send_msg(chat_id, f"""✅ تم إنشاء طلب التمويل #{funding_id}
📺 القناة: {channel_link}
👥 الأعضاء المطلوبة: {members}
💰 التكلفة: {total_cost:.2f} USD

⏳ سيتم مراجعة طلبك من قبل الإدارة""")
                
                # إنشاء وإرسال فاتورة PDF
                pdf_file = generate_funding_pdf(funding_id, user_id, channel_link, members, total_cost)
                if pdf_file:
                    send_document(chat_id, pdf_file, f"📄 فاتورة تمويل القناة #{funding_id}")
                    os.remove(pdf_file)
                
                # إشعار المدير
                c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
                username = c.fetchone()[0] or f"ID: {user_id}"
                
                admin_text = f"""📺 <b>طلب تمويل قناة جديد #{funding_id}</b>

👤 المستخدم: {username}
🆔 الآيدي: <code>{user_id}</code>
🔗 القناة: {channel_link}
👥 الأعضاء: {members}
💰 التكلفة: {total_cost:.2f} USD

📅 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                
                admin_buttons = [
                    [{'text': '✅ قبول الطلب', 'callback_data': f'approve_funding_{funding_id}'},
                     {'text': '❌ رفض الطلب', 'callback_data': f'reject_funding_{funding_id}'}],
                    [{'text': '👁️ عرض التفاصيل', 'callback_data': f'view_funding_{funding_id}'}]
                ]
                
                send_msg(ADMIN_ID, admin_text, admin_buttons)
                
                del user_states[user_id]
        
        elif data == 'cancel_funding':
            if user_id in user_states:
                del user_states[user_id]
            send_msg(chat_id, "❌ تم إلغاء طلب التمويل")
            channel_funding_menu(chat_id, user_id)
        
        elif data == 'support':
            support_msg = get_setting('support_message')
            if support_msg:
                send_msg(chat_id, support_msg)
            else:
                send_msg(chat_id, f"📞 للتواصل مع الدعم:\n👤 @{SUPPORT_USERNAME}\n🆔 آيديك: <code>{user_id}</code>")
        
        # ==================== لوحة التحكم ====================
        elif data == 'admin_panel':
            if user_id == ADMIN_ID or is_user_admin(user_id):
                admin_panel_menu(chat_id, message_id)
            else:
                send_msg(chat_id, "🚫 ليس لديك صلاحية الوصول")
        
        elif data == 'admin_stats':
            if user_id == ADMIN_ID or is_user_admin(user_id):
                c.execute("SELECT COUNT(*) FROM users")
                total_users = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
                banned_users = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
                today_users = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM orders")
                total_orders = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
                pending_orders = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
                completed_orders = c.fetchone()[0]
                
                c.execute("SELECT SUM(total_price) FROM orders WHERE status = 'completed'")
                total_income = c.fetchone()[0] or 0
                
                c.execute("SELECT SUM(balance) FROM users")
                total_balance = c.fetchone()[0] or 0
                
                c.execute("SELECT COUNT(*) FROM channel_funding")
                total_funding = c.fetchone()[0]
              
