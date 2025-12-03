import sqlite3
import requests
import time
import threading
import logging
import sys

# إعدادات البوت
TOKEN = "8436742877:AAHmlmOKY2iQCGoOt004ruq09tZGderDGMQ"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"

# تهيئة التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# تهيئة قاعدة البيانات
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول
def init_db():
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, 
                 balance REAL DEFAULT 0, is_admin INTEGER DEFAULT 0, 
                 is_banned INTEGER DEFAULT 0, invited_by INTEGER DEFAULT 0,
                 invite_code TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS categories 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT UNIQUE, position INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS services 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 category_id INTEGER, name TEXT, 
                 price REAL, min_quantity INTEGER, max_quantity INTEGER,
                 description TEXT DEFAULT '',
                 FOREIGN KEY(category_id) REFERENCES categories(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER, service_id INTEGER, quantity INTEGER,
                 total_price REAL, link TEXT, status TEXT DEFAULT 'pending',
                 admin_note TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY(user_id) REFERENCES users(user_id),
                 FOREIGN KEY(service_id) REFERENCES services(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings 
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    # إعدادات افتراضية
    default_settings = [
        ('maintenance', 'false'),
        ('maintenance_msg', 'البوت تحت الصيانة حاليًا ⚠️'),
        ('invite_reward', '0.10'),
        ('invite_enabled', 'true')
    ]
    
    for key, value in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    
    # إضافة المدير
    c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
              (ADMIN_ID, "المدير", 100000, 1, 'ADMIN'))
    
    # إضافة قسم افتراضي
    c.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", ("خدمات عامة",))
    
    # إضافة خدمة افتراضية
    c.execute("SELECT id FROM categories WHERE name = ?", ("خدمات عامة",))
    cat_id = c.fetchone()
    if cat_id:
        c.execute("""INSERT OR IGNORE INTO services 
                     (category_id, name, price, min_quantity, max_quantity, description) 
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (cat_id[0], "متابعين انستغرام", 0.50, 100, 10000, "متابعين حقيقيين بجودة عالية"))
    
    conn.commit()

init_db()

# وظائف المساعدة
def get_setting(key, default=None):
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = c.fetchone()
    return result[0] if result else default

def set_setting(key, value):
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()

def send_message(chat_id, text, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        if reply_markup:
            payload['reply_markup'] = reply_markup
        
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending message to {chat_id}: {e}")
        return False

def answer_callback(callback_id):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
        requests.post(url, json={'callback_query_id': callback_id}, timeout=3)
    except:
        pass

# القوائم
def show_main_menu(chat_id, user_id):
    c.execute("SELECT username, balance, is_admin FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        return
    
    username, balance, is_admin = user
    
    text = f"""👋 أهلاً {username or 'مستخدم'}

━━━━━━━━━━━━━━━
🆔 الآيدي: <code>{user_id}</code>
💰 الرصيد: <b>{balance:,.2f} USD</b>
━━━━━━━━━━━━━━━

📌 اختر من القائمة:"""
    
    keyboard = {'inline_keyboard': []}
    
    # إضافة الأزرار الأساسية
    keyboard['inline_keyboard'].append([{'text': '🛍️ خدمات', 'callback_data': 'services'}])
    keyboard['inline_keyboard'].append([
        {'text': '💰 شحن رصيد', 'callback_data': 'charge'},
        {'text': '💳 رصيدي', 'callback_data': 'balance'}
    ])
    keyboard['inline_keyboard'].append([
        {'text': '👥 دعوة أصدقاء', 'callback_data': 'invite'},
        {'text': '📋 طلباتي', 'callback_data': 'my_orders'}
    ])
    keyboard['inline_keyboard'].append([{'text': '📞 دعم', 'callback_data': 'support'}])
    
    if is_admin == 1:
        keyboard['inline_keyboard'].append([{'text': '👑 لوحة التحكم', 'callback_data': 'admin_panel'}])
    
    send_message(chat_id, text, keyboard)

def show_services(chat_id):
    c.execute("SELECT id, name FROM categories ORDER BY position")
    categories = c.fetchall()
    
    text = "🛍️ <b>خدمات المتجر</b>\n\n📁 اختر القسم:"
    
    if not categories:
        text = "🛍️ <b>خدمات المتجر</b>\n\n📭 لا توجد أقسام حالياً"
        keyboard = {'inline_keyboard': [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]}
    else:
        keyboard = {'inline_keyboard': []}
        for cat_id, cat_name in categories:
            keyboard['inline_keyboard'].append([{'text': f'📁 {cat_name}', 'callback_data': f'cat_{cat_id}'}])
        
        keyboard['inline_keyboard'].append([{'text': '🔙 رجوع', 'callback_data': 'main'}])
    
    send_message(chat_id, text, keyboard)

def show_category_services(chat_id, cat_id):
    try:
        cat_id = int(cat_id)
    except:
        show_services(chat_id)
        return
    
    c.execute("SELECT name FROM categories WHERE id = ?", (cat_id,))
    cat = c.fetchone()
    
    if not cat:
        show_services(chat_id)
        return
    
    c.execute("SELECT id, name, price FROM services WHERE category_id = ?", (cat_id,))
    services = c.fetchall()
    
    text = f"🛍️ <b>قسم {cat[0]}</b>\n\n📦 اختر الخدمة:"
    
    if not services:
        text += "\n\n📭 لا توجد خدمات في هذا القسم"
        keyboard = {'inline_keyboard': [[{'text': '🔙 رجوع', 'callback_data': 'services'}]]}
    else:
        keyboard = {'inline_keyboard': []}
        for service_id, service_name, price in services:
            btn_text = f"📦 {service_name[:20]} - {price:,.2f} USD"
            keyboard['inline_keyboard'].append([{'text': btn_text, 'callback_data': f'service_{service_id}'}])
        
        keyboard['inline_keyboard'].append([
            {'text': '🔙 رجوع', 'callback_data': 'services'},
            {'text': '🏠 الرئيسية', 'callback_data': 'main'}
        ])
    
    send_message(chat_id, text, keyboard)

def show_service_details(chat_id, user_id, service_id):
    try:
        service_id = int(service_id)
    except:
        show_services(chat_id)
        return
    
    c.execute("""SELECT s.name, s.price, s.min_quantity, s.max_quantity, s.description, c.name 
                 FROM services s 
                 JOIN categories c ON s.category_id = c.id 
                 WHERE s.id = ?""", (service_id,))
    service = c.fetchone()
    
    if not service:
        send_message(chat_id, "❌ الخدمة غير موجودة")
        return
    
    name, price, min_qty, max_qty, desc, cat_name = service
    
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance_result = c.fetchone()
    balance = balance_result[0] if balance_result else 0
    
    text = f"""🛒 <b>تفاصيل الخدمة</b>

━━━━━━━━━━━━━━━
📦 الخدمة: {name}
📁 القسم: {cat_name}
💰 السعر: <b>{price:,.2f} USD</b> للوحدة
🔢 الحد الأدنى: {min_qty:,}
🔢 الحد الأقصى: {max_qty:,}
━━━━━━━━━━━━━━━
💳 رصيدك: <b>{balance:,.2f} USD</b>
━━━━━━━━━━━━━━━

✍️ أرسل الكمية المطلوبة:"""
    
    send_message(chat_id, text)
    
    # حفظ حالة المستخدم
    user_states[user_id] = {'type': 'order_qty', 'service_id': service_id}

# متغيرات حالة المستخدمين
user_states = {}

def handle_start(user_id, chat_id, username, start_param=None):
    # التحقق من الصيانة
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_message(chat_id, get_setting('maintenance_msg'))
        return
    
    # التحقق من كود الدعوة
    if start_param and start_param != 'start':
        c.execute("SELECT user_id FROM users WHERE invite_code = ? AND user_id != ?", (start_param, user_id))
        inviter = c.fetchone()
        
        if inviter:
            inviter_id = inviter[0]
            if inviter_id != user_id:
                # التحقق إذا كان المستخدم جديد
                c.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
                is_existing = c.fetchone()
                
                if not is_existing and get_setting('invite_enabled') == 'true':
                    reward = float(get_setting('invite_reward'))
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, inviter_id))
                    
                    # تحديث دعوة المستخدم
                    c.execute("UPDATE users SET invited_by = ? WHERE user_id = ?", (inviter_id, user_id))
                    conn.commit()
                    
                    # إرسال إشعار للمدعو
                    send_message(inviter_id, f"🎉 مكافأة دعوة!\n\nحصلت على {reward} USD لدعوة مستخدم جديد.")
    
    # إنشاء أو تحديث المستخدم
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        import uuid
        invite_code = str(uuid.uuid4())[:8]
        c.execute("INSERT INTO users (user_id, username, invite_code) VALUES (?, ?, ?)", 
                  (user_id, username or "", invite_code))
        conn.commit()
        
        if user_id != ADMIN_ID:
            send_message(ADMIN_ID, f"👤 مستخدم جديد\n🆔: {user_id}\n📛: @{username or 'بدون'}")
    
    # إرسال القائمة الرئيسية
    show_main_menu(chat_id, user_id)

def process_order_qty(user_id, chat_id, text):
    if user_id not in user_states or user_states[user_id]['type'] != 'order_qty':
        return
    
    service_id = user_states[user_id]['service_id']
    
    c.execute("SELECT name, price, min_quantity, max_quantity FROM services WHERE id = ?", (service_id,))
    service = c.fetchone()
    
    if not service:
        send_message(chat_id, "❌ الخدمة غير موجودة")
        if user_id in user_states:
            del user_states[user_id]
        return
    
    name, price, min_qty, max_qty = service
    
    try:
        quantity = int(text)
    except:
        send_message(chat_id, "❌ الرجاء إدخال رقم صحيح")
        return
    
    if quantity < min_qty:
        send_message(chat_id, f"❌ الحد الأدنى: {min_qty:,}")
        return
    
    if quantity > max_qty:
        send_message(chat_id, f"❌ الحد الأقصى: {max_qty:,}")
        return
    
    total_price = price * quantity
    
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance_result = c.fetchone()
    balance = balance_result[0] if balance_result else 0
    
    if balance < total_price:
        send_message(chat_id, f"""❌ رصيدك غير كافي

💰 المطلوب: {total_price:,.2f} USD
💳 رصيدك: {balance:,.2f} USD""")
        
        if user_id in user_states:
            del user_states[user_id]
        return
    
    user_states[user_id] = {
        'type': 'order_link',
        'service_id': service_id,
        'quantity': quantity,
        'total_price': total_price
    }
    
    send_message(chat_id, f"""📝 <b>إدخال الرابط/المعلومات</b>

━━━━━━━━━━━━━━━
📦 الخدمة: {name}
🔢 الكمية: {quantity:,}
💰 السعر الإجمالي: {total_price:,.2f} USD
━━━━━━━━━━━━━━━

✍️ أرسل الرابط أو المعلومات المطلوبة:""")

def process_order_link(user_id, chat_id, text):
    if user_id not in user_states or user_states[user_id]['type'] != 'order_link':
        return
    
    data = user_states[user_id]
    link = text.strip()
    
    # التحقق من الرصيد مرة أخرى
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance_result = c.fetchone()
    balance = balance_result[0] if balance_result else 0
    
    if balance < data['total_price']:
        send_message(chat_id, "❌ رصيدك غير كافي")
        if user_id in user_states:
            del user_states[user_id]
        return
    
    # خصم المبلغ
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (data['total_price'], user_id))
    
    # إنشاء الطلب
    c.execute("""INSERT INTO orders (user_id, service_id, quantity, total_price, link, status) 
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (user_id, data['service_id'], data['quantity'], data['total_price'], link, 'pending'))
    order_id = c.lastrowid
    conn.commit()
    
    # إشعار للمدير
    c.execute("SELECT name FROM services WHERE id = ?", (data['service_id'],))
    service_name_result = c.fetchone()
    service_name = service_name_result[0] if service_name_result else "غير معروف"
    
    alert_text = f"""🆕 طلب جديد #{order_id}

👤 المستخدم: {user_id}
📦 الخدمة: {service_name}
🔢 الكمية: {data['quantity']:,}
💰 المبلغ: {data['total_price']:,.2f} USD
🔗 الرابط: {link[:100]}"""
    
    send_message(ADMIN_ID, alert_text)
    
    # تأكيد للمستخدم
    send_message(chat_id, f"""✅ تم إرسال طلبك بنجاح!

━━━━━━━━━━━━━━━
📦 رقم الطلب: #{order_id}
💰 المبلغ المخصوم: {data['total_price']:,.2f} USD
💳 رصيدك الجديد: {balance - data['total_price']:,.2f} USD
📊 الحالة: ⏳ قيد المراجعة
━━━━━━━━━━━━━━━

📋 تابع قسم "طلباتي" لمعرفة آخر التحديثات.""")
    
    if user_id in user_states:
        del user_states[user_id]

def handle_admin_panel(chat_id):
    keyboard = {
        'inline_keyboard': [
            [{'text': '📊 إحصائيات', 'callback_data': 'admin_stats'}],
            [{'text': '👥 المستخدمين', 'callback_data': 'admin_users'}],
            [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'admin_services'}],
            [{'text': '💳 شحن رصيد', 'callback_data': 'admin_charge'}],
            [{'text': '📋 الطلبات', 'callback_data': 'admin_orders'}],
            [{'text': '⚙️ إعدادات', 'callback_data': 'admin_settings'}],
            [{'text': '🔙 الرئيسية', 'callback_data': 'main'}]
        ]
    }
    send_message(chat_id, "👑 <b>لوحة تحكم المدير</b>", keyboard)

def handle_admin_services(chat_id):
    keyboard = {
        'inline_keyboard': [
            [{'text': '📁 إدارة الأقسام', 'callback_data': 'admin_categories'}],
            [{'text': '➕ إضافة خدمة', 'callback_data': 'admin_add_service'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
        ]
    }
    send_message(chat_id, "🛍️ <b>إدارة الخدمات</b>", keyboard)

def handle_admin_categories(chat_id):
    c.execute("SELECT id, name FROM categories")
    categories = c.fetchall()
    
    text = "📁 <b>الأقسام الحالية</b>\n\n"
    if categories:
        for cat_id, cat_name in categories:
            text += f"• {cat_name}\n<code>cat_{cat_id}</code>\n━━━━━━\n"
    else:
        text += "📭 لا توجد أقسام\n"
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '➕ إضافة قسم', 'callback_data': 'admin_add_category'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin_services'}]
        ]
    }
    send_message(chat_id, text, keyboard)

def handle_message(user_id, chat_id, text):
    # التحقق من الصيانة
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_message(chat_id, get_setting('maintenance_msg'))
        return
    
    # التحقق من الحظر
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if user and user[0] == 1:
        send_message(chat_id, "🚫 تم حظرك من البوت")
        return
    
    # معالجة حالة المستخدم
    if user_id in user_states:
        state = user_states[user_id]
        
        if state['type'] == 'order_qty':
            process_order_qty(user_id, chat_id, text)
            return
        
        elif state['type'] == 'order_link':
            process_order_link(user_id, chat_id, text)
            return
        
        elif state['type'] == 'admin_add_category':
            if len(text.strip()) < 2:
                send_message(chat_id, "❌ اسم القسم قصير جداً")
                return
            
            c.execute("INSERT INTO categories (name) VALUES (?)", (text.strip(),))
            conn.commit()
            send_message(chat_id, f"✅ تم إضافة القسم: {text}")
            del user_states[user_id]
            return
        
        elif state['type'] == 'admin_charge_user':
            if not text.isdigit():
                send_message(chat_id, "❌ آيدي غير صحيح")
                del user_states[user_id]
                return
            
            target_id = int(text)
            user_states[user_id] = {'type': 'admin_charge_amount', 'target_id': target_id}
            send_message(chat_id, f"💰 أرسل المبلغ للشحن للمستخدم {target_id}:")
            return
        
        elif state['type'] == 'admin_charge_amount':
            try:
                amount = float(text)
                target_id = user_states[user_id]['target_id']
                
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                
                send_message(chat_id, f"✅ تم شحن {amount:,.2f} USD للمستخدم {target_id}")
                send_message(target_id, f"🎉 تم شحن رصيدك\nالمبلغ: {amount:,.2f} USD")
                
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ مبلغ غير صحيح")
                del user_states[user_id]
            return
    
    # معالجة الأوامر
    if text.startswith('/'):
        if text == '/start':
            handle_start(user_id, chat_id, "", None)
        elif text == '/admin' and user_id == ADMIN_ID:
            handle_admin_panel(chat_id)
        else:
            show_main_menu(chat_id, user_id)
    else:
        show_main_menu(chat_id, user_id)

def handle_callback(user_id, chat_id, callback_id, data):
    answer_callback(callback_id)
    
    # التحقق من الصيانة
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_message(chat_id, get_setting('maintenance_msg'))
        return
    
    # التحقق من الحظر
    c.execute("SELECT is_banned, is_admin FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        return
    
    is_banned, is_admin = user
    if is_banned == 1:
        send_message(chat_id, "🚫 تم حظرك من البوت")
        return
    
    if data == 'main':
        show_main_menu(chat_id, user_id)
    
    elif data == 'services':
        show_services(chat_id)
    
    elif data.startswith('cat_'):
        cat_id = data.split('_')[1]
        show_category_services(chat_id, cat_id)
    
    elif data.startswith('service_'):
        service_id = data.split('_')[1]
        show_service_details(chat_id, user_id, service_id)
    
    elif data == 'charge':
        text = f"""💰 <b>شحن الرصيد</b>

━━━━━━━━━━━━━━━
📞 للشحن تواصل مع:
👤 @{SUPPORT_USERNAME}
━━━━━━━━━━━━━━━
🆔 أرسل له آيديك:
<code>{user_id}</code>
━━━━━━━━━━━━━━━"""
        keyboard = {'inline_keyboard': [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]}
        send_message(chat_id, text, keyboard)
    
    elif data == 'balance':
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance_result = c.fetchone()
        balance = balance_result[0] if balance_result else 0
        send_message(chat_id, f"💰 رصيدك الحالي: <b>{balance:,.2f} USD</b>")
    
    elif data == 'invite':
        c.execute("SELECT invite_code FROM users WHERE user_id = ?", (user_id,))
        code_result = c.fetchone()
        invite_code = code_result[0] if code_result else user_id
        
        link = f"https://t.me/{BOT_USERNAME}?start={invite_code}"
        reward = get_setting('invite_reward')
        
        text = f"""👥 <b>دعوة أصدقاء</b>

━━━━━━━━━━━━━━━
💰 مكافأة لكل دعوة: {reward} USD
━━━━━━━━━━━━━━━
🔗 رابط دعوتك:
<code>{link}</code>
━━━━━━━━━━━━━━━
📋 كود الدعوة:
<code>{invite_code}</code>
━━━━━━━━━━━━━━━"""
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '📤 مشاركة الرابط', 'url': f"https://t.me/share/url?url={link}&text=انضم%20إلي%20في%20هذا%20البوت%20الرائع"}],
                [{'text': '🔙 رجوع', 'callback_data': 'main'}]
            ]
        }
        send_message(chat_id, text, keyboard)
    
    elif data == 'my_orders':
        c.execute("""SELECT o.id, s.name, o.quantity, o.total_price, o.status 
                     FROM orders o 
                     JOIN services s ON o.service_id = s.id 
                     WHERE o.user_id = ? 
                     ORDER BY o.id DESC 
                     LIMIT 5""", (user_id,))
        orders = c.fetchall()
        
        if orders:
            text = "📋 <b>طلباتك الأخيرة</b>\n\n━━━━━━━━━━━━━━━\n"
            for order_id, name, qty, price, status in orders:
                status_icon = '✅' if status == 'completed' else '⏳' if status == 'processing' else '❌' if status == 'rejected' else '📝'
                text += f"{status_icon} <b>#{order_id}</b> - {name[:20]}\n🔢 {qty:,} | 💰 {price:,.2f} USD\n📊 {status}\n━━━━━━\n"
        else:
            text = "📭 لا توجد طلبات سابقة"
        
        keyboard = {'inline_keyboard': [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]}
        send_message(chat_id, text, keyboard)
    
    elif data == 'support':
        text = f"""📞 <b>الدعم الفني</b>

━━━━━━━━━━━━━━━
👤 تواصل مع:
@{SUPPORT_USERNAME}
━━━━━━━━━━━━━━━
🆔 أرسل له آيديك:
<code>{user_id}</code>
━━━━━━━━━━━━━━━"""
        send_message(chat_id, text)
    
    elif data == 'admin_panel':
        if is_admin != 1:
            send_message(chat_id, "🚫 ليس لديك صلاحية")
            return
        handle_admin_panel(chat_id)
    
    elif data == 'admin_stats':
        if is_admin != 1:
            return
        
        total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        banned_users = c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
        total_balance = c.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
        total_orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        
        text = f"""📊 <b>إحصائيات النظام</b>

━━━━━━━━━━━━━━━
👥 المستخدمين: {total_users}
🚫 المحظورين: {banned_users}
💰 إجمالي الأرصدة: {total_balance:,.2f} USD
📦 إجمالي الطلبات: {total_orders}
━━━━━━━━━━━━━━━"""
        
        send_message(chat_id, text)
    
    elif data == 'admin_users':
        if is_admin != 1:
            return
        
        c.execute("SELECT user_id, username, balance, is_banned FROM users ORDER BY user_id DESC LIMIT 10")
        users = c.fetchall()
        
        text = "👥 <b>آخر 10 مستخدمين</b>\n\n━━━━━━━━━━━━━━━\n"
        for u_id, username, balance, banned in users:
            status = "🚫" if banned == 1 else "✅"
            username_display = f"@{username}" if username else "بدون"
            text += f"{status} <code>{u_id}</code> - {username_display}\n💰 {balance:,.2f} USD\n━━━━━━\n"
        
        send_message(chat_id, text)
    
    elif data == 'admin_services':
        if is_admin != 1:
            return
        handle_admin_services(chat_id)
    
    elif data == 'admin_categories':
        if is_admin != 1:
            return
        handle_admin_categories(chat_id)
    
    elif data == 'admin_add_category':
        if is_admin != 1:
            return
        
        user_states[user_id] = {'type': 'admin_add_category'}
        send_message(chat_id, "➕ أرسل اسم القسم الجديد:")
    
    elif data == 'admin_add_service':
        if is_admin != 1:
            return
        
        c.execute("SELECT id, name FROM categories")
        categories = c.fetchall()
        
        if not categories:
            send_message(chat_id, "❌ لا توجد أقسام، أضف قسم أولاً")
            return
        
        keyboard = {'inline_keyboard': []}
        for cat_id, cat_name in categories:
            keyboard['inline_keyboard'].append([{'text': cat_name, 'callback_data': f'addservice_{cat_id}'}])
        
        keyboard['inline_keyboard'].append([{'text': '🔙 رجوع', 'callback_data': 'admin_services'}])
        
        send_message(chat_id, "📁 اختر قسم لإضافة الخدمة:", keyboard)
    
    elif data.startswith('addservice_'):
        if is_admin != 1:
            return
        
        cat_id = data.split('_')[1]
        user_states[user_id] = {
            'type': 'add_service',
            'step': 0,
            'cat_id': cat_id,
            'data': {}
        }
        send_message(chat_id, "➕ أرسل اسم الخدمة الجديدة:")
    
    elif data == 'admin_charge':
        if is_admin != 1:
            return
        
        user_states[user_id] = {'type': 'admin_charge_user'}
        send_message(chat_id, "💰 أرسل آيدي المستخدم للشحن:")
    
    elif data == 'admin_orders':
        if is_admin != 1:
            return
        
        c.execute("""SELECT o.id, u.user_id, s.name, o.quantity, o.status 
                     FROM orders o 
                     JOIN users u ON o.user_id = u.user_id 
                     JOIN services s ON o.service_id = s.id 
                     ORDER BY o.id DESC 
                     LIMIT 10""")
        orders = c.fetchall()
        
        if orders:
            text = "📋 <b>آخر 10 طلبات</b>\n\n━━━━━━━━━━━━━━━\n"
            for order_id, u_id, name, qty, status in orders:
                status_icon = '✅' if status == 'completed' else '⏳' if status == 'processing' else '❌'
                text += f"{status_icon} <b>#{order_id}</b> | 👤 {u_id}\n📦 {name[:20]}\n🔢 {qty:,}\n━━━━━━\n"
        else:
            text = "📭 لا توجد طلبات حالياً"
        
        send_message(chat_id, text)
    
    elif data == 'admin_settings':
        if is_admin != 1:
            return
        
        maintenance = get_setting('maintenance')
        maintenance_status = "✅ مفعل" if maintenance == 'true' else "❌ معطل"
        reward = get_setting('invite_reward')
        
        text = f"""⚙️ <b>إعدادات البوت</b>

━━━━━━━━━━━━━━━
🔧 وضع الصيانة: {maintenance_status}
💰 مكافأة الدعوة: {reward} USD
━━━━━━━━━━━━━━━"""
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🔧 تفعيل/تعطيل الصيانة', 'callback_data': 'toggle_maintenance'}],
                [{'text': '💰 تغيير مكافأة الدعوة', 'callback_data': 'change_reward'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
            ]
        }
        send_message(chat_id, text, keyboard)
    
    elif data == 'toggle_maintenance':
        if is_admin != 1:
            return
        
        current = get_setting('maintenance')
        new_value = 'false' if current == 'true' else 'true'
        set_setting('maintenance', new_value)
        
        status = "✅ تم تفعيل" if new_value == 'true' else "❌ تم تعطيل"
        send_message(chat_id, f"{status} وضع الصيانة")
    
    elif data == 'change_reward':
        if is_admin != 1:
            return
        
        user_states[user_id] = {'type': 'change_reward'}
        send_message(chat_id, "💰 أرسل المبلغ الجديد لمكافأة الدعوة (مثال: 0.10):")

# دالة البولينج الرئيسية
def polling_loop():
    offset = 0
    logger.info("🚀 بدء تشغيل البوت...")
    logger.info(f"👑 المدير: {ADMIN_ID}")
    logger.info(f"🤖 البوت: @{BOT_USERNAME}")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            params = {
                'offset': offset,
                'timeout': 30,
                'allowed_updates': ['message', 'callback_query']
            }
            
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    updates = data.get('result', [])
                    
                    for update in updates:
                        offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            msg = update['message']
                            chat_id = msg['chat']['id']
                            user_id = msg['from']['id']
                            username = msg['from'].get('username', '')
                            
                            if 'text' in msg:
                                text = msg['text']
                                
                                if text == '/start':
                                    # استخراج معامل start إذا موجود
                                    start_param = None
                                    if 'entities' in msg:
                                        for entity in msg['entities']:
                                            if entity['type'] == 'bot_command':
                                                cmd_text = text[entity['offset']:entity['offset'] + entity['length']]
                                                if cmd_text == '/start' and len(text) > len(cmd_text):
                                                    start_param = text[len(cmd_text):].strip()
                                    handle_start(user_id, chat_id, username, start_param)
                                else:
                                    handle_message(user_id, chat_id, text)
                        
                        elif 'callback_query' in update:
                            query = update['callback_query']
                            user_id = query['from']['id']
                            chat_id = query['message']['chat']['id']
                            callback_id = query['id']
                            data = query['data']
                            
                            handle_callback(user_id, chat_id, callback_id, data)
        
        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.ConnectionError:
            logger.warning("فقدان الاتصال، إعادة المحاولة...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"خطأ في البولينج: {e}")
            time.sleep(2)

# تشغيل البوت
if __name__ == '__main__':
    try:
        # اختبار الاتصال
        test = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=10)
        if test.status_code == 200:
            bot_info = test.json()
            if bot_info.get('ok'):
                username = bot_info['result'].get('username', 'غير معروف')
                logger.info(f"✅ البوت متصل: @{username}")
            else:
                logger.error("❌ توكن البوت غير صحيح")
                sys.exit(1)
        else:
            logger.error("❌ فشل الاتصال بالسيرفر")
            sys.exit(1)
        
        # تشغيل البولينج
        polling_loop()
        
    except KeyboardInterrupt:
        logger.info("إيقاف البوت...")
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {e}")
    finally:
        conn.close()
