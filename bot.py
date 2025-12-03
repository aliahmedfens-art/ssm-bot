import sqlite3
import requests
import time
import sys
import logging

# إعدادات البوت
TOKEN = "8436742877:AAHmlmOKY2iQCGoOt004ruq09tZGderDGMQ"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"

# تهيئة التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# تهيئة قاعدة البيانات
conn = sqlite3.connect('bot.db', check_same_thread=False, check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0, 
             is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, 
             invited_by INTEGER DEFAULT 0, invite_code TEXT UNIQUE)''')

c.execute('''CREATE TABLE IF NOT EXISTS categories 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')

c.execute('''CREATE TABLE IF NOT EXISTS services 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, 
             price REAL, min_quantity INTEGER, max_quantity INTEGER,
             FOREIGN KEY(category_id) REFERENCES categories(id))''')

c.execute('''CREATE TABLE IF NOT EXISTS orders 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service_id INTEGER, 
             quantity INTEGER, total_price REAL, link TEXT, status TEXT DEFAULT 'pending',
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

c.execute('''CREATE TABLE IF NOT EXISTS settings 
             (key TEXT PRIMARY KEY, value TEXT)''')

# إعدادات افتراضية
settings_default = [
    ('maintenance', 'false'),
    ('maintenance_msg', 'البوت تحت الصيانة'),
    ('invite_reward', '0.10'),
    ('invite_enabled', 'true')
]

for key, val in settings_default:
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

# إضافة المدير وقسم وخدمة افتراضية
c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
          (ADMIN_ID, "المدير", 100000, 1, 'ADMIN'))

c.execute("INSERT OR IGNORE INTO categories (name) VALUES ('خدمات عامة')")
c.execute("SELECT id FROM categories WHERE name = 'خدمات عامة'")
cat_id = c.fetchone()[0] if c.fetchone() else None

if cat_id:
    c.execute("INSERT OR IGNORE INTO services (category_id, name, price, min_quantity, max_quantity) VALUES (?, ?, ?, ?, ?)",
              (cat_id, 'متابعين انستغرام', 0.50, 100, 10000))

conn.commit()

# وظائف مساعدة
def get_setting(key):
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = c.fetchone()
    return result[0] if result else None

def send_msg(chat_id, text, markup=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if markup:
            data['reply_markup'] = markup
        requests.post(url, json=data, timeout=5)
        return True
    except:
        return False

def answer_callback(callback_id):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", 
                     json={'callback_query_id': callback_id}, timeout=3)
    except:
        pass

# متغير الحالة
user_state = {}

# القوائم الرئيسية
def main_menu(chat_id, user_id):
    c.execute("SELECT username, balance, is_admin FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone() or (None, 0, 0)
    
    text = f"""👋 أهلاً {user[0] or 'مستخدم'}

🆔 الآيدي: <code>{user_id}</code>
💰 الرصيد: <b>{user[1]:,.2f} USD</b>

📌 اختر من القائمة:"""
    
    keyboard = {'inline_keyboard': [
        [{'text': '🛍️ خدمات', 'callback_data': 'services'}],
        [{'text': '💰 شحن', 'callback_data': 'charge'}, {'text': '💳 رصيدي', 'callback_data': 'balance'}],
        [{'text': '👥 دعوة', 'callback_data': 'invite'}, {'text': '📋 طلباتي', 'callback_data': 'my_orders'}],
        [{'text': '📞 دعم', 'callback_data': 'support'}]
    ]}
    
    if user[2] == 1:
        keyboard['inline_keyboard'].append([{'text': '👑 لوحة التحكم', 'callback_data': 'admin'}])
    
    send_msg(chat_id, text, keyboard)

def services_menu(chat_id):
    c.execute("SELECT id, name FROM categories")
    cats = c.fetchall()
    
    if not cats:
        send_msg(chat_id, "📭 لا توجد أقسام")
        return
    
    keyboard = {'inline_keyboard': []}
    for cat_id, name in cats:
        keyboard['inline_keyboard'].append([{'text': f'📁 {name}', 'callback_data': f'cat_{cat_id}'}])
    
    keyboard['inline_keyboard'].append([{'text': '🔙 رجوع', 'callback_data': 'main'}])
    send_msg(chat_id, "🛍️ اختر قسم:", keyboard)

def cat_menu(chat_id, cat_id):
    c.execute("SELECT id, name, price FROM services WHERE category_id = ?", (cat_id,))
    services = c.fetchall()
    
    if not services:
        send_msg(chat_id, "📭 لا توجد خدمات")
        return
    
    keyboard = {'inline_keyboard': []}
    for serv_id, name, price in services:
        keyboard['inline_keyboard'].append([{'text': f'{name} - {price} USD', 'callback_data': f'serv_{serv_id}'}])
    
    keyboard['inline_keyboard'].append([{'text': '🔙 رجوع', 'callback_data': 'services'}])
    send_msg(chat_id, "📦 اختر خدمة:", keyboard)

def admin_menu(chat_id):
    keyboard = {'inline_keyboard': [
        [{'text': '📊 إحصائيات', 'callback_data': 'stats'}],
        [{'text': '👥 المستخدمين', 'callback_data': 'users'}],
        [{'text': '🛍️ خدمات', 'callback_data': 'manage_services'}],
        [{'text': '💳 شحن رصيد', 'callback_data': 'admin_charge'}],
        [{'text': '⚙️ إعدادات', 'callback_data': 'settings'}],
        [{'text': '🔙 رئيسية', 'callback_data': 'main'}]
    ]}
    send_msg(chat_id, "👑 لوحة التحكم:", keyboard)

# معالجة الرسائل
def handle_message(chat_id, user_id, text):
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_msg(chat_id, get_setting('maintenance_msg'))
        return
    
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if user and user[0] == 1:
        send_msg(chat_id, "🚫 تم حظرك")
        return
    
    if user_id in user_state:
        state = user_state[user_id]
        
        if state == 'add_category':
            if len(text) > 1:
                c.execute("INSERT INTO categories (name) VALUES (?)", (text,))
                conn.commit()
                send_msg(chat_id, f"✅ تم إضافة قسم: {text}")
            del user_state[user_id]
            return
        
        elif state == 'add_service_name':
            user_state[user_id] = {'step': 'add_service_price', 'name': text}
            send_msg(chat_id, "💰 أرسل سعر الخدمة:")
            return
        
        elif state.get('step') == 'add_service_price':
            try:
                price = float(text)
                user_state[user_id] = {'step': 'add_service_min', 'name': state['name'], 'price': price}
                send_msg(chat_id, "🔢 أرسل الحد الأدنى:")
            except:
                send_msg(chat_id, "❌ سعر غير صحيح")
                del user_state[user_id]
            return
        
        elif state.get('step') == 'add_service_min':
            try:
                min_qty = int(text)
                user_state[user_id] = {'step': 'add_service_max', 'name': state['name'], 'price': state['price'], 'min': min_qty}
                send_msg(chat_id, "🔢 أرسل الحد الأقصى:")
            except:
                send_msg(chat_id, "❌ رقم غير صحيح")
                del user_state[user_id]
            return
        
        elif state.get('step') == 'add_service_max':
            try:
                max_qty = int(text)
                cat_id = state.get('cat_id')
                
                c.execute("INSERT INTO services (category_id, name, price, min_quantity, max_quantity) VALUES (?, ?, ?, ?, ?)",
                          (cat_id, state['name'], state['price'], state['min'], max_qty))
                conn.commit()
                send_msg(chat_id, f"✅ تم إضافة خدمة: {state['name']}")
                del user_state[user_id]
            except:
                send_msg(chat_id, "❌ رقم غير صحيح")
                del user_state[user_id]
            return
        
        elif state.startswith('charge_'):
            target_id = int(state.split('_')[1])
            if text.isdigit():
                amount = float(text)
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                send_msg(chat_id, f"✅ تم شحن {amount} USD للمستخدم {target_id}")
                send_msg(target_id, f"🎉 تم شحن {amount} USD لحسابك")
                del user_state[user_id]
            return
        
        elif state.startswith('order_'):
            service_id = state.split('_')[1]
            if text.isdigit():
                quantity = int(text)
                c.execute("SELECT price, min_quantity, max_quantity, name FROM services WHERE id = ?", (service_id,))
                serv = c.fetchone()
                
                if serv:
                    price, min_q, max_q, name = serv
                    if quantity >= min_q and quantity <= max_q:
                        total = price * quantity
                        user_state[user_id] = f'order_link_{service_id}_{quantity}_{total}'
                        send_msg(chat_id, f"✍️ أرسل الرابط لـ {name}:")
                    else:
                        send_msg(chat_id, f"❌ الحد {min_q} إلى {max_q}")
                else:
                    send_msg(chat_id, "❌ خدمة غير موجودة")
                    del user_state[user_id]
            return
        
        elif state.startswith('order_link_'):
            parts = state.split('_')
            service_id, quantity, total = parts[2], int(parts[3]), float(parts[4])
            link = text
            
            c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            balance = c.fetchone()[0]
            
            if balance >= total:
                c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total, user_id))
                c.execute("INSERT INTO orders (user_id, service_id, quantity, total_price, link) VALUES (?, ?, ?, ?, ?)",
                          (user_id, service_id, quantity, total, link))
                conn.commit()
                order_id = c.lastrowid
                
                send_msg(chat_id, f"""✅ تم إرسال الطلب #{order_id}

💰 المبلغ: {total} USD
📊 الحالة: ⏳ قيد المراجعة""")
                
                # إشعار للمدير
                send_msg(ADMIN_ID, f"🆕 طلب جديد #{order_id}\n👤 المستخدم: {user_id}\n💰 المبلغ: {total} USD")
            else:
                send_msg(chat_id, "❌ رصيد غير كافي")
            
            del user_state[user_id]
            return
    
    elif text == '/start':
        import uuid
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not c.fetchone():
            invite_code = str(uuid.uuid4())[:8]
            c.execute("INSERT INTO users (user_id, invite_code) VALUES (?, ?)", (user_id, invite_code))
            conn.commit()
        
        main_menu(chat_id, user_id)
    
    elif text == '/admin' and user_id == ADMIN_ID:
        admin_menu(chat_id)
    
    else:
        main_menu(chat_id, user_id)

# معالجة الكولباك
def handle_callback(chat_id, user_id, callback_id, data):
    answer_callback(callback_id)
    
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_msg(chat_id, get_setting('maintenance_msg'))
        return
    
    c.execute("SELECT is_banned, is_admin FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if user and user[0] == 1:
        send_msg(chat_id, "🚫 تم حظرك")
        return
    
    if data == 'main':
        main_menu(chat_id, user_id)
    
    elif data == 'services':
        services_menu(chat_id)
    
    elif data.startswith('cat_'):
        cat_id = data.split('_')[1]
        cat_menu(chat_id, cat_id)
    
    elif data.startswith('serv_'):
        service_id = data.split('_')[1]
        c.execute("SELECT name, price, min_quantity, max_quantity FROM services WHERE id = ?", (service_id,))
        serv = c.fetchone()
        
        if serv:
            name, price, min_q, max_q = serv
            text = f"""🛒 {name}

💰 السعر: {price} USD
🔢 الحد الأدنى: {min_q}
🔢 الحد الأقصى: {max_q}

✍️ أرسل الكمية:"""
            send_msg(chat_id, text)
            user_state[user_id] = f'order_{service_id}'
    
    elif data == 'charge':
        text = f"""💰 الشحن عبر @{SUPPORT_USERNAME}

🆔 أرسل له آيديك:
<code>{user_id}</code>"""
        send_msg(chat_id, text)
    
    elif data == 'balance':
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = c.fetchone()[0]
        send_msg(chat_id, f"💰 رصيدك: {balance:,.2f} USD")
    
    elif data == 'invite':
        c.execute("SELECT invite_code FROM users WHERE user_id = ?", (user_id,))
        code = c.fetchone()[0]
        link = f"https://t.me/{BOT_USERNAME}?start={code}"
        reward = get_setting('invite_reward')
        
        text = f"""👥 دعوة أصدقاء

💰 المكافأة: {reward} USD
🔗 الرابط: {link}"""
        
        keyboard = {'inline_keyboard': [[
            {'text': '📤 مشاركة', 'url': f'tg://msg_url?url={link}'},
            {'text': '🔙 رجوع', 'callback_data': 'main'}
        ]]}
        send_msg(chat_id, text, keyboard)
    
    elif data == 'my_orders':
        c.execute("SELECT o.id, s.name, o.quantity, o.total_price, o.status FROM orders o JOIN services s ON o.service_id = s.id WHERE o.user_id = ? ORDER BY o.id DESC LIMIT 5", (user_id,))
        orders = c.fetchall()
        
        if orders:
            text = "📋 طلباتك:\n\n"
            for oid, name, qty, price, status in orders:
                text += f"#{oid} - {name[:15]}\n🔢 {qty} | 💰 {price} USD | {status}\n━━━━━━\n"
        else:
            text = "📭 لا توجد طلبات"
        
        send_msg(chat_id, text)
    
    elif data == 'support':
        send_msg(chat_id, f"📞 الدعم: @{SUPPORT_USERNAME}")
    
    elif data == 'admin':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            admin_menu(chat_id)
        else:
            send_msg(chat_id, "🚫 ليس لديك صلاحية")
    
    elif data == 'stats':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_balance = c.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
            total_orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            
            text = f"""📊 الإحصائيات:

👥 المستخدمين: {total_users}
💰 إجمالي الأرصدة: {total_balance:,.2f} USD
📦 الطلبات: {total_orders}"""
            send_msg(chat_id, text)
    
    elif data == 'users':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            c.execute("SELECT user_id, username, balance FROM users ORDER BY user_id DESC LIMIT 10")
            users = c.fetchall()
            
            text = "👥 آخر 10 مستخدمين:\n\n"
            for uid, uname, bal in users:
                text += f"{uid} - @{uname or 'بدون'}\n💰 {bal} USD\n━━━━━━\n"
            send_msg(chat_id, text)
    
    elif data == 'manage_services':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            keyboard = {'inline_keyboard': [
                [{'text': '📁 إضافة قسم', 'callback_data': 'add_category'}],
                [{'text': '➕ إضافة خدمة', 'callback_data': 'add_service'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
            ]}
            send_msg(chat_id, "🛍️ إدارة الخدمات:", keyboard)
    
    elif data == 'add_category':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            user_state[user_id] = 'add_category'
            send_msg(chat_id, "➕ أرسل اسم القسم الجديد:")
    
    elif data == 'add_service':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            c.execute("SELECT id, name FROM categories")
            cats = c.fetchall()
            
            if not cats:
                send_msg(chat_id, "❌ لا توجد أقسام")
                return
            
            keyboard = {'inline_keyboard': []}
            for cat_id, name in cats:
                keyboard['inline_keyboard'].append([{'text': name, 'callback_data': f'addserv_{cat_id}'}])
            
            keyboard['inline_keyboard'].append([{'text': '🔙 رجوع', 'callback_data': 'manage_services'}])
            send_msg(chat_id, "📁 اختر قسم:", keyboard)
    
    elif data.startswith('addserv_'):
        cat_id = data.split('_')[1]
        user_state[user_id] = {'cat_id': cat_id, 'step': 'add_service_name'}
        send_msg(chat_id, "➕ أرسل اسم الخدمة:")
    
    elif data == 'admin_charge':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            user_state[user_id] = 'charge_input'
            send_msg(chat_id, "💰 أرسل آيدي المستخدم:")
    
    elif data == 'settings':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            maint = get_setting('maintenance')
            reward = get_setting('invite_reward')
            
            text = f"""⚙️ الإعدادات:

🔧 الصيانة: {'✅ مفعل' if maint == 'true' else '❌ معطل'}
💰 مكافأة الدعوة: {reward} USD"""
            
            keyboard = {'inline_keyboard': [
                [{'text': '🔧 تبديل الصيانة', 'callback_data': 'toggle_maint'}],
                [{'text': '💰 تغيير المكافأة', 'callback_data': 'change_reward'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
            ]}
            send_msg(chat_id, text, keyboard)
    
    elif data == 'toggle_maint':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            current = get_setting('maintenance')
            new_val = 'false' if current == 'true' else 'true'
            c.execute("UPDATE settings SET value = ? WHERE key = 'maintenance'", (new_val,))
            conn.commit()
            send_msg(chat_id, f"✅ تم {'تفعيل' if new_val == 'true' else 'تعطيل'} الصيانة")
    
    elif data == 'change_reward':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            user_state[user_id] = 'change_reward'
            send_msg(chat_id, "💰 أرسل المبلغ الجديد:")

# البولينغ الرئيسي
def main():
    logger.info("🚀 بدء تشغيل البوت...")
    offset = 0
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            params = {'offset': offset, 'timeout': 30}
            resp = requests.get(url, params=params, timeout=35)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('ok'):
                    for update in data['result']:
                        offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            msg = update['message']
                            chat_id = msg['chat']['id']
                            user_id = msg['from']['id']
                            text = msg.get('text', '')
                            
                            if text:
                                handle_message(chat_id, user_id, text)
                        
                        elif 'callback_query' in update:
                            query = update['callback_query']
                            user_id = query['from']['id']
                            chat_id = query['message']['chat']['id']
                            callback_id = query['id']
                            data = query['data']
                            
                            handle_callback(chat_id, user_id, callback_id, data)
        
        except Exception as e:
            logger.error(f"خطأ: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
