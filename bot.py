import sqlite3
import requests
import time
import threading
import logging

# إعدادات البوت
TOKEN = "8436742877:AAHmlmOKY2iQCGoOt004ruq09tZGderDGMQ"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"

# تهيئة التسجيل
logging.basicConfig(level=logging.INFO)
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
        logger.error(f"Error sending message: {e}")
        return False

def answer_callback(callback_id):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
        requests.post(url, json={'callback_query_id': callback_id})
    except:
        pass

# معالجة الأوامر
user_states = {}

def handle_start(user_id, chat_id, username, start_param=None):
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
                c.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
                is_existing = c.fetchone()
                
                if not is_existing and get_setting('invite_enabled') == 'true':
                    reward = float(get_setting('invite_reward'))
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, inviter_id))
                    conn.commit()
                    
                    send_message(inviter_id, f"🎉 مكافأة دعوة!\n\nحصلت على {reward} USD لدعوة مستخدم جديد.")
    
    # إنشاء أو تحديث المستخدم
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        import uuid
        invite_code = str(uuid.uuid4())[:8]
        c.execute("INSERT INTO users (user_id, username, invite_code) VALUES (?, ?, ?)", 
                  (user_id, username, invite_code))
        conn.commit()
        
        if user_id != ADMIN_ID:
            send_message(ADMIN_ID, f"👤 مستخدم جديد\n🆔: {user_id}\n📛: @{username or 'بدون'}")
    
    # إرسال القائمة الرئيسية
    show_main_menu(chat_id, user_id)

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
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '🛍️ خدمات', 'callback_data': 'services'}],
            [{'text': '💰 شحن رصيد', 'callback_data': 'charge'}, {'text': '💳 رصيدي', 'callback_data': 'balance'}],
            [{'text': '👥 دعوة أصدقاء', 'callback_data': 'invite'}, {'text': '📋 طلباتي', 'callback_data': 'my_orders'}],
            [{'text': '📞 دعم', 'callback_data': 'support'}]
        ]
    }
    
    if is_admin == 1:
        keyboard['inline_keyboard'].append([{'text': '👑 لوحة التحكم', 'callback_data': 'admin_panel'}])
    
    send_message(chat_id, text, keyboard)

def show_services(chat_id):
    c.execute("SELECT id, name FROM categories ORDER BY position")
    categories = c.fetchall()
    
    text = "🛍️ <b>خدمات المتجر</b>\n\n📁 اختر القسم:"
    
    if not categories:
        text += "\n\n📭 لا توجد أقسام حالياً"
        keyboard = {'inline_keyboard': [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]}
    else:
        keyboard = {'inline_keyboard': []}
        for cat_id, cat_name in categories:
            keyboard['inline_keyboard'].append([{'text': f'📁 {cat_name}', 'callback_data': f'cat_{cat_id}'}])
        
        keyboard['inline_keyboard'].append([{'text': '🔙 رجوع', 'callback_data': 'main'}])
    
    send_message(chat_id, text, keyboard)

def show_category_services(chat_id, cat_id):
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
            keyboard['inline_keyboard'].append([
                {'text': f'{service_name} - {price:,.2f} USD', 'callback_data': f'service_{service_id}'}
            ])
        
        keyboard['inline_keyboard'].append([
            {'text': '🔙 رجوع', 'callback_data': 'services'},
            {'text': '🏠 الرئيسية', 'callback_data': 'main'}
        ])
    
    send_message(chat_id, text, keyboard)

def show_service_details(chat_id, user_id, service_id):
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
    balance = c.fetchone()[0]
    
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
    user_states[user_id] = {'type': 'order_qty', 'service_id': service_id}

def handle_order_quantity(user_id, chat_id, quantity):
    if user_id not in user_states or user_states[user_id]['type'] != 'order_qty':
        return
    
    service_id = user_states[user_id]['service_id']
    
    c.execute("SELECT name, price, min_quantity, max_quantity FROM services WHERE id = ?", (service_id,))
    service = c.fetchone()
    
    if not service:
        send_message(chat_id, "❌ الخدمة غير موجودة")
        del user_states[user_id]
        return
    
    name, price, min_qty, max_qty = service
    
    try:
        quantity = int(quantity)
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
    balance = c.fetchone()[0]
    
    if balance < total_price:
        send_message(chat_id, f"❌ رصيدك غير كافي\n\nالمطلوب: {total_price:,.2f} USD\nرصيدك: {balance:,.2f} USD")
        del user_states[user_id]
        return
    
    user_states[user_id] = {
        'type': 'order_link',
        'service_id': service_id,
        'quantity': quantity,
        'total_price': total_price
    }
    
    send_message(chat_id, f"""📝 <b>إدخال الرابط/المعلومات</b>

الخدمة: {name}
الكمية: {quantity:,}
السعر الإجمالي: {total_price:,.2f} USD

✍️ أرسل الرابط أو المعلومات المطلوبة:""")

def handle_order_link(user_id, chat_id, link):
    if user_id not in user_states or user_states[user_id]['type'] != 'order_link':
        return
    
    data = user_states[user_id]
    
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
    service_name = c.fetchone()[0]
    
    alert_text = f"""🆕 طلب جديد #{order_id}

👤 المستخدم: {user_id}
📦 الخدمة: {service_name}
🔢 الكمية: {data['quantity']:,}
💰 المبلغ: {data['total_price']:,.2f} USD
🔗 الرابط: {link[:100]}"""
    
    send_message(ADMIN_ID, alert_text)
    
    # تأكيد للمستخدم
    send_message(chat_id, f"""✅ تم إرسال طلبك بنجاح!

رقم الطلب: #{order_id}
الحالة: ⏳ قيد المراجعة

تابع قسم "طلباتي" لمعرفة آخر التحديثات.""")
    
    del user_states[user_id]

def handle_admin_charge(user_id, chat_id, target_id):
    try:
        target_id = int(target_id)
        user_states[user_id] = {'type': 'admin_charge_amount', 'target_id': target_id}
        send_message(chat_id, f"💰 أرسل المبلغ للشحن للمستخدم {target_id}:")
    except:
        send_message(chat_id, "❌ آيدي غير صحيح")

def handle_admin_charge_amount(user_id, chat_id, amount):
    if user_id not in user_states or user_states[user_id]['type'] != 'admin_charge_amount':
        return
    
    target_id = user_states[user_id]['target_id']
    
    try:
        amount = float(amount)
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
        conn.commit()
        
        send_message(chat_id, f"✅ تم شحن {amount:,.2f} USD للمستخدم {target_id}")
        send_message(target_id, f"🎉 تم شحن رصيدك\nالمبلغ: {amount:,.2f} USD")
        
        del user_states[user_id]
    except:
        send_message(chat_id, "❌ مبلغ غير صحيح")

def handle_add_service(user_id, chat_id, cat_id):
    user_states[user_id] = {
        'type': 'add_service_data',
        'cat_id': cat_id,
        'step': 0,
        'data': {}
    }
    
    send_message(chat_id, "➕ أرسل اسم الخدمة الجديدة:")

def handle_add_service_data(user_id, chat_id, text):
    if user_id not in user_states or user_states[user_id]['type'] != 'add_service_data':
        return
    
    data = user_states[user_id]
    
    if data['step'] == 0:
        data['data']['name'] = text
        data['step'] = 1
        send_message(chat_id, "💰 أرسل سعر الخدمة (مثال: 0.50):")
    
    elif data['step'] == 1:
        try:
            data['data']['price'] = float(text)
            data['step'] = 2
            send_message(chat_id, "🔢 أرسل الحد الأدنى للكمية (مثال: 100):")
        except:
            send_message(chat_id, "❌ سعر غير صحيح")
    
    elif data['step'] == 2:
        try:
            data['data']['min_qty'] = int(text)
            data['step'] = 3
            send_message(chat_id, "🔢 أرسل الحد الأقصى للكمية (مثال: 5000):")
        except:
            send_message(chat_id, "❌ رقم غير صحيح")
    
    elif data['step'] == 3:
        try:
            data['data']['max_qty'] = int(text)
            data['step'] = 4
            send_message(chat_id, "📝 أرسل وصف الخدمة (اختياري، أو أرسل - لتخطي):")
        except:
            send_message(chat_id, "❌ رقم غير صحيح")

def handle_add_service_final(user_id, chat_id, description):
    if user_id not in user_states or user_states[user_id]['type'] != 'add_service_data':
        return
    
    data = user_states[user_id]
    
    if description != '-':
        data['data']['description'] = description
    
    try:
        c.execute("""INSERT INTO services (category_id, name, price, min_quantity, max_quantity, description) 
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (data['cat_id'], 
                   data['data']['name'], 
                   data['data']['price'], 
                   data['data']['min_qty'], 
                   data['data']['max_qty'], 
                   data['data'].get('description', '')))
        conn.commit()
        
        send_message(chat_id, f"✅ تم إضافة الخدمة: {data['data']['name']}")
        del user_states[user_id]
    except Exception as e:
        send_message(chat_id, f"❌ خطأ: {str(e)}")
        del user_states[user_id]

def handle_callback(user_id, chat_id, callback_id, data):
    answer_callback(callback_id)
    
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_message(chat_id, get_setting('maintenance_msg'))
        return
    
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

تواصل مع الدعم: @{SUPPORT_USERNAME}
وأرسل له آيديك: <code>{user_id}</code>"""
        keyboard = {'inline_keyboard': [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]}
        send_message(chat_id, text, keyboard)
    
    elif data == 'balance':
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = c.fetchone()[0]
        send_message(chat_id, f"💰 رصيدك: <b>{balance:,.2f} USD</b>")
    
    elif data == 'invite':
        c.execute("SELECT invite_code FROM users WHERE user_id = ?", (user_id,))
        invite_code = c.fetchone()[0]
        
        link = f"https://t.me/{BOT_USERNAME}?start={invite_code}"
        reward = get_setting('invite_reward')
        
        text = f"""👥 <b>دعوة أصدقاء</b>

🔗 رابط دعوتك:
<code>{link}</code>

💰 مكافأة لكل دعوة: {reward} USD"""
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '📤 مشاركة الرابط', 'url': f"tg://msg_url?text=انضم%20إلي&url={link}"}],
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
                     LIMIT 10""", (user_id,))
        orders = c.fetchall()
        
        if orders:
            text = "📋 <b>طلباتك الأخيرة</b>\n\n"
            for order_id, name, qty, price, status in orders:
                status_icon = '✅' if status == 'completed' else '⏳' if status == 'processing' else '❌'
                text += f"{status_icon} #{order_id}: {name[:20]}\n🔢 {qty:,} | 💰 {price:,.2f} USD\n━━━━━━\n"
        else:
            text = "📭 لا توجد طلبات سابقة"
        
        keyboard = {'inline_keyboard': [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]}
        send_message(chat_id, text, keyboard)
    
    elif data == 'support':
        send_message(chat_id, f"📞 الدعم: @{SUPPORT_USERNAME}\n\n🆔 أرسل آيديك: <code>{user_id}</code>")
    
    elif data == 'admin_panel':
        if is_admin != 1:
            send_message(chat_id, "🚫 ليس لديك صلاحية")
            return
        
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
    
    elif data == 'admin_stats':
        if is_admin != 1:
            return
        
        total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        banned_users = c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
        total_balance = c.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
        total_orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        
        text = f"""📊 <b>الإحصائيات</b>

👥 المستخدمين: {total_users}
🚫 المحظورين: {banned_users}
💰 إجمالي الأرصدة: {total_balance:,.2f} USD
📦 إجمالي الطلبات: {total_orders}"""
        
        send_message(chat_id, text)
    
    elif data == 'admin_users':
        if is_admin != 1:
            return
        
        c.execute("SELECT user_id, username, balance, is_banned FROM users ORDER BY user_id DESC LIMIT 10")
        users = c.fetchall()
        
        text = "👥 <b>آخر 10 مستخدمين</b>\n\n"
        for u_id, username, balance, banned in users:
            status = "🚫" if banned == 1 else "✅"
            text += f"{status} {u_id} - @{username or 'بدون'}\n💰 {balance:,.2f} USD\n━━━━━━\n"
        
        send_message(chat_id, text)
    
    elif data == 'admin_services':
        if is_admin != 1:
            return
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '📁 إدارة الأقسام', 'callback_data': 'admin_categories'}],
                [{'text': '➕ إضافة خدمة', 'callback_data': 'admin_add_service'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
            ]
        }
        send_message(chat_id, "🛍️ <b>إدارة الخدمات</b>", keyboard)
    
    elif data == 'admin_categories':
        if is_admin != 1:
            return
        
        c.execute("SELECT id, name FROM categories")
        categories = c.fetchall()
        
        text = "📁 <b>الأقسام</b>\n\n"
        for cat_id, cat_name in categories:
            text += f"• {cat_name}\n<code>cat_{cat_id}</code>\n━━━━━━\n"
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '➕ إضافة قسم', 'callback_data': 'admin_add_category'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin_services'}]
            ]
        }
        send_message(chat_id, text, keyboard)
    
    elif data == 'admin_add_category':
        if is_admin != 1:
            return
        
        user_states[user_id] = {'type': 'add_category'}
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
            keyboard['inline_keyboard'].append(
                [{'text': cat_name, 'callback_data': f'addservice_{cat_id}'}]
            )
        
        keyboard['inline_keyboard'].append([{'text': '🔙 رجوع', 'callback_data': 'admin_services'}])
        
        send_message(chat_id, "📁 اختر قسم لإضافة الخدمة:", keyboard)
    
    elif data.startswith('addservice_'):
        if is_admin != 1:
            return
        
        cat_id = data.split('_')[1]
        handle_add_service(user_id, chat_id, cat_id)
    
    elif data == 'admin_charge':
        if is_admin != 1:
            return
        
        user_states[user_id] = {'type': 'admin_charge'}
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
            text = "📋 <b>آخر 10 طلبات</b>\n\n"
            for order_id, u_id, name, qty, status in orders:
                status_icon = '✅' if status == 'completed' else '⏳' if status == 'processing' else '❌'
                text += f"{status_icon} #{order_id} | 👤 {u_id}\n📦 {name[:20]}\n🔢 {qty:,}\n━━━━━━\n"
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

🔧 وضع الصيانة: {maintenance_status}
💰 مكافأة الدعوة: {reward} USD"""
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🔧 تفعيل/تعطيل الصيانة', 'callback_data': 'toggle_maintenance'}],
                [{'text': '💰 تغيير مكافأة الدعوة', 'callback_data': 'change_invite_reward'}],
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
    
    elif data == 'change_invite_reward':
        if is_admin != 1:
            return
        
        user_states[user_id] = {'type': 'change_invite_reward'}
        send_message(chat_id, "💰 أرسل المبلغ الجديد لمكافأة الدعوة (مثال: 0.10):")

def handle_message(user_id, chat_id, text):
    if user_id in user_states:
        state = user_states[user_id]
        
        if state['type'] == 'order_qty':
            handle_order_quantity(user_id, chat_id, text)
        
        elif state['type'] == 'order_link':
            handle_order_link(user_id, chat_id, text)
        
        elif state['type'] == 'admin_charge':
            handle_admin_charge(user_id, chat_id, text)
        
        elif state['type'] == 'admin_charge_amount':
            handle_admin_charge_amount(user_id, chat_id, text)
        
        elif state['type'] == 'add_category':
            c.execute("INSERT INTO categories (name) VALUES (?)", (text,))
            conn.commit()
            send_message(chat_id, f"✅ تم إضافة القسم: {text}")
            del user_states[user_id]
        
        elif state['type'] == 'change_invite_reward':
            try:
                reward = float(text)
                set_setting('invite_reward', str(reward))
                send_message(chat_id, f"✅ تم تحديث مكافأة الدعوة إلى: {reward} USD")
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ مبلغ غير صحيح")
        
        elif state['type'] == 'add_service_data':
            if state['step'] < 4:
                handle_add_service_data(user_id, chat_id, text)
            else:
                handle_add_service_final(user_id, chat_id, text)
        
        else:
            del user_states[user_id]
    
    elif text.startswith('/'):
        if text == '/start':
            handle_start(user_id, chat_id, "", None)
        elif text == '/admin' and user_id == ADMIN_ID:
            handle_callback(user_id, chat_id, 'admin_callback', 'admin_panel')

# خادم ويب بسيط للتحقق من الصحة
from flask import Flask, request
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ البوت يعمل بشكل طبيعي"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = request.json
    process_update(update)
    return 'OK'

def process_update(update):
    try:
        if 'message' in update:
            msg = update['message']
            chat_id = msg['chat']['id']
            user_id = msg['from']['id']
            username = msg['from'].get('username', '')
            text = msg.get('text', '')
            
            if 'entities' in msg and msg['entities'][0]['type'] == 'bot_command':
                if text == '/start':
                    start_param = None
                    if ' ' in text:
                        start_param = text.split(' ')[1]
                    handle_start(user_id, chat_id, username, start_param)
                else:
                    handle_message(user_id, chat_id, text)
            elif text:
                handle_message(user_id, chat_id, text)
        
        elif 'callback_query' in update:
            query = update['callback_query']
            user_id = query['from']['id']
            chat_id = query['message']['chat']['id']
            callback_id = query['id']
            data = query['data']
            
            handle_callback(user_id, chat_id, callback_id, data)
    
    except Exception as e:
        logger.error(f"Error processing update: {e}")

# تشغيل البوت
if __name__ == '__main__':
    import os
    
    # تعيين webhook
    try:
        webhook_url = f"https://your-domain.com/{TOKEN}"  # ضع رابطك هنا
        requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}")
        logger.info("Webhook set successfully")
    except:
        logger.info("Using polling mode")
    
    # تشغيل خادم فلاسك
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
