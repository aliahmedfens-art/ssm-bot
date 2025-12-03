import sqlite3
import requests
import time

TOKEN = "8436742877:AAHmlmOKY2iQCGoOt004ruq09tZGderDGMQ"
ADMIN_ID = 6130994941

# قاعدة البيانات
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0,
              is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS categories
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')

c.execute('''CREATE TABLE IF NOT EXISTS services
             (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT,
              price REAL, min INTEGER, max INTEGER)''')

c.execute('''CREATE TABLE IF NOT EXISTS orders
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service_id INTEGER,
              quantity INTEGER, total_price REAL, link TEXT, status TEXT DEFAULT 'pending')''')

# إضافة البيانات الأساسية
c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin) VALUES (?, ?, ?, ?)",
          (ADMIN_ID, "المدير", 100000, 1))

c.execute("INSERT OR IGNORE INTO categories (name) VALUES ('خدمات عامة')")
c.execute("SELECT id FROM categories WHERE name = 'خدمات عامة'")
cat_id = c.fetchone()
if cat_id:
    c.execute("INSERT OR IGNORE INTO services (category_id, name, price, min, max) VALUES (?, ?, ?, ?, ?)",
              (cat_id[0], 'متابعين انستغرام', 0.50, 100, 10000))

conn.commit()

# إرسال الرسائل
def send(chat_id, text, buttons=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if buttons:
            import json
            data['reply_markup'] = json.dumps({'inline_keyboard': buttons})
        requests.post(url, json=data, timeout=5)
    except:
        pass

# القوائم
def main_menu(chat_id, user_id):
    c.execute("SELECT username, balance, is_admin FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone() or (None, 0, 0)
    
    text = f"👋 أهلاً {user[0] or 'مستخدم'}\n💰 رصيدك: {user[1]:,.2f} USD\n\n📌 اختر:"
    
    buttons = [
        [{'text': '🛍️ خدمات', 'callback_data': 'services'}],
        [{'text': '💰 شحن', 'callback_data': 'charge'}, {'text': '💳 رصيدي', 'callback_data': 'balance'}],
        [{'text': '📞 دعم', 'callback_data': 'support'}]
    ]
    
    if user[2] == 1:
        buttons.append([{'text': '👑 لوحة التحكم', 'callback_data': 'admin'}])
    
    send(chat_id, text, buttons)

def services_menu(chat_id):
    c.execute("SELECT id, name FROM categories")
    cats = c.fetchall()
    
    buttons = []
    for cat_id, name in cats:
        buttons.append([{'text': f'📁 {name}', 'callback_data': f'cat_{cat_id}'}])
    
    buttons.append([{'text': '🔙 رجوع', 'callback_data': 'main'}])
    send(chat_id, "🛍️ اختر قسم:", buttons)

def category_menu(chat_id, cat_id):
    c.execute("SELECT id, name, price FROM services WHERE category_id = ?", (cat_id,))
    services = c.fetchall()
    
    buttons = []
    for serv_id, name, price in services:
        buttons.append([{'text': f'{name} - {price} USD', 'callback_data': f'serv_{serv_id}'}])
    
    buttons.append([{'text': '🔙 رجوع', 'callback_data': 'services'}])
    send(chat_id, "📦 اختر خدمة:", buttons)

# معالجة الرسائل
user_states = {}

def handle_message(chat_id, user_id, text):
    if user_id in user_states:
        state = user_states[user_id]
        
        if state == 'add_category':
            c.execute("INSERT INTO categories (name) VALUES (?)", (text,))
            conn.commit()
            send(chat_id, f"✅ تم إضافة قسم: {text}")
            del user_states[user_id]
            return
        
        elif state.startswith('order_'):
            service_id = state.split('_')[1]
            if text.isdigit():
                quantity = int(text)
                c.execute("SELECT price, min, max, name FROM services WHERE id = ?", (service_id,))
                serv = c.fetchone()
                
                if serv:
                    price, min_q, max_q, name = serv
                    if quantity >= min_q and quantity <= max_q:
                        total = price * quantity
                        user_states[user_id] = f'link_{service_id}_{quantity}_{total}'
                        send(chat_id, f"✍️ أرسل الرابط لـ {name}:")
                    else:
                        send(chat_id, f"❌ الحد {min_q} إلى {max_q}")
            return
        
        elif state.startswith('link_'):
            parts = state.split('_')
            service_id, quantity, total = parts[1], int(parts[2]), float(parts[3])
            link = text
            
            c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            balance = c.fetchone()[0]
            
            if balance >= total:
                c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total, user_id))
                c.execute("INSERT INTO orders (user_id, service_id, quantity, total_price, link) VALUES (?, ?, ?, ?, ?)",
                          (user_id, service_id, quantity, total, link))
                conn.commit()
                
                send(chat_id, f"✅ تم إرسال الطلب\n💰 المبلغ: {total} USD")
                send(ADMIN_ID, f"🆕 طلب جديد من {user_id}\n💰 المبلغ: {total} USD")
            else:
                send(chat_id, "❌ رصيد غير كافي")
            
            del user_states[user_id]
            return
    
    if text == '/start':
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            conn.commit()
        
        main_menu(chat_id, user_id)
    
    elif text == '/admin' and user_id == ADMIN_ID:
        buttons = [
            [{'text': '📊 إحصائيات', 'callback_data': 'stats'}],
            [{'text': '👥 المستخدمين', 'callback_data': 'users'}],
            [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'manage'}],
            [{'text': '🔙 رئيسية', 'callback_data': 'main'}]
        ]
        send(chat_id, "👑 لوحة التحكم:", buttons)
    
    else:
        main_menu(chat_id, user_id)

# معالجة الكولباك
def handle_callback(chat_id, user_id, data):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", 
                     json={'callback_query_id': str(user_id)})
    except:
        pass
    
    if data == 'main':
        main_menu(chat_id, user_id)
    
    elif data == 'services':
        services_menu(chat_id)
    
    elif data.startswith('cat_'):
        cat_id = data.split('_')[1]
        category_menu(chat_id, cat_id)
    
    elif data.startswith('serv_'):
        service_id = data.split('_')[1]
        c.execute("SELECT name, price, min, max FROM services WHERE id = ?", (service_id,))
        serv = c.fetchone()
        
        if serv:
            name, price, min_q, max_q = serv
            send(chat_id, f"🛒 {name}\n💰 السعر: {price} USD\n✍️ أرسل الكمية ({min_q}-{max_q}):")
            user_states[user_id] = f'order_{service_id}'
    
    elif data == 'charge':
        send(chat_id, f"💰 للشحن راسل @Allawi04\n🆔 آيديك: {user_id}")
    
    elif data == 'balance':
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = c.fetchone()[0]
        send(chat_id, f"💰 رصيدك: {balance:,.2f} USD")
    
    elif data == 'support':
        send(chat_id, f"📞 الدعم: @Allawi04\n🆔 آيديك: {user_id}")
    
    elif data == 'admin':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            buttons = [
                [{'text': '📊 إحصائيات', 'callback_data': 'stats'}],
                [{'text': '👥 المستخدمين', 'callback_data': 'users'}],
                [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'manage'}],
                [{'text': '🔙 رئيسية', 'callback_data': 'main'}]
            ]
            send(chat_id, "👑 لوحة التحكم:", buttons)
    
    elif data == 'stats':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            balance = c.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
            orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            
            send(chat_id, f"📊 الإحصائيات:\n👥 المستخدمين: {users}\n💰 الأرصدة: {balance:,.2f} USD\n📦 الطلبات: {orders}")
    
    elif data == 'users':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            c.execute("SELECT user_id, username, balance FROM users ORDER BY user_id DESC LIMIT 10")
            users = c.fetchall()
            
            text = "👥 آخر 10 مستخدمين:\n"
            for uid, uname, bal in users:
                text += f"{uid} - @{uname or 'بدون'}\n💰 {bal} USD\n"
            send(chat_id, text)
    
    elif data == 'manage':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            buttons = [
                [{'text': '📁 إضافة قسم', 'callback_data': 'add_cat'}],
                [{'text': '➕ إضافة خدمة', 'callback_data': 'add_serv'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
            ]
            send(chat_id, "🛍️ إدارة الخدمات:", buttons)
    
    elif data == 'add_cat':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            user_states[user_id] = 'add_category'
            send(chat_id, "➕ أرسل اسم القسم الجديد:")

# البولينغ الرئيسي
print("🚀 البوت يعمل...")
offset = 0

while True:
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        params = {'offset': offset, 'timeout': 20}
        response = requests.get(url, params=params, timeout=25)
        
        if response.status_code == 200:
            updates = response.json()
            if updates.get('ok'):
                for update in updates['result']:
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
                        chat_id = query['message']['chat']['id']
                        user_id = query['from']['id']
                        data = query['data']
                        
                        handle_callback(chat_id, user_id, data)
        
        time.sleep(0.5)
        
    except Exception as e:
        print(f"⚠️ خطأ: {e}")
        time.sleep(2)
