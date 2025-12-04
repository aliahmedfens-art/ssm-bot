import sqlite3
import requests
import time
import json
import uuid
import random
import string

# إعدادات البوت
TOKEN = "8436742877:AAHmlmOKY2iQCGoOt004ruq09tZGderDGMQ"
ADMIN_ID = 8462737195
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"  # تم إضافة يوزر البوت هنا

# قاعدة البيانات
conn = sqlite3.connect('/tmp/bot.db', check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (user_id INTEGER PRIMARY KEY, username TEXT, 
             balance REAL DEFAULT 0, is_admin INTEGER DEFAULT 0, 
             is_banned INTEGER DEFAULT 0, is_restricted INTEGER DEFAULT 0,
             invited_by INTEGER DEFAULT 0, invite_code TEXT UNIQUE,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

c.execute('''CREATE TABLE IF NOT EXISTS categories 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')

c.execute('''CREATE TABLE IF NOT EXISTS services 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, 
             price_per_k REAL, min_order INTEGER DEFAULT 100, 
             max_order INTEGER DEFAULT 10000, description TEXT DEFAULT '')''')

c.execute('''CREATE TABLE IF NOT EXISTS orders 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service_id INTEGER,
             quantity INTEGER, total_price REAL, link TEXT, status TEXT DEFAULT 'pending',
             admin_note TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

c.execute('''CREATE TABLE IF NOT EXISTS forced_channels 
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
             channel_id TEXT, channel_username TEXT, channel_url TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS settings 
             (key TEXT PRIMARY KEY, value TEXT)''')

# إعدادات افتراضية
default_settings = [
    ('maintenance', 'false'),
    ('maintenance_msg', 'البوت تحت الصيانة'),
    ('invite_reward', '0.10'),
    ('invite_enabled', 'true'),
    ('force_subscribe', 'false'),
    ('bot_username', BOT_USERNAME)  # إضافة إعداد يوزر البوت
]

for key, value in default_settings:
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

# إضافة المدير
c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
          (ADMIN_ID, "المدير", 100000, 1, 'ADMIN'))

conn.commit()

# وظائف مساعدة
def get_setting(key):
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = c.fetchone()
    return result[0] if result else None

def send_msg(chat_id, text, buttons=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if buttons:
            data['reply_markup'] = json.dumps({'inline_keyboard': buttons})
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"⚠️ خطأ في الإرسال: {e}")

def check_channels(user_id):
    c.execute("SELECT value FROM settings WHERE key = 'force_subscribe'")
    if c.fetchone()[0] != 'true':
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

def generate_user_code(length=6):
    """إنشاء رمز عشوائي للمستخدم"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# القوائم
def main_menu(chat_id, user_id):
    # التحقق من القنوات
    subscribed, channel = check_channels(user_id)
    if not subscribed:
        buttons = [[
            {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
            {'text': '✅ تحقق', 'callback_data': 'check_sub'}
        ]]
        send_msg(chat_id, f"📢 يجب الاشتراك في @{channel} أولاً", buttons)
        return
    
    # التحقق من الحظر
    c.execute("SELECT is_banned, is_restricted FROM users WHERE user_id = ?", (user_id,))
    user_status = c.fetchone()
    if user_status:
        if user_status[0] == 1:
            send_msg(chat_id, "🚫 تم حظرك من البوت")
            return
        if user_status[1] == 1:
            send_msg(chat_id, "⛔ حسابك مقيد")
            return
    
    c.execute("SELECT username, balance, is_admin FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone() or (None, 0, 0)
    
    text = f"""👋 أهلاً {user[0] or 'مستخدم'}

🆔 الآيدي: <code>{user_id}</code>
💰 الرصيد: <b>{user[1]:,.2f} USD</b>

📌 اختر:"""
    
    buttons = [
        [{'text': '🛍️ خدمات', 'callback_data': 'services'}],
        [{'text': '💰 شحن', 'callback_data': 'charge'}, {'text': '💳 رصيدي', 'callback_data': 'balance'}],
        [{'text': '👥 دعوة', 'callback_data': 'invite'}, {'text': '📋 طلباتي', 'callback_data': 'my_orders'}],
        [{'text': '📞 دعم', 'callback_data': 'support'}]
    ]
    
    if user[2] == 1:
        buttons.append([{'text': '👑 لوحة التحكم', 'callback_data': 'admin'}])
    
    send_msg(chat_id, text, buttons)

def services_menu(chat_id):
    c.execute("SELECT id, name FROM categories")
    cats = c.fetchall()
    
    if not cats:
        send_msg(chat_id, "📭 لا توجد أقسام")
        return
    
    buttons = []
    for cat_id, name in cats:
        buttons.append([{'text': f'📁 {name}', 'callback_data': f'cat_{cat_id}'}])
    
    buttons.append([{'text': '🔙 رجوع', 'callback_data': 'main'}])
    send_msg(chat_id, "🛍️ اختر قسم:", buttons)

def category_menu(chat_id, cat_id):
    c.execute("SELECT id, name, price_per_k FROM services WHERE category_id = ?", (cat_id,))
    services = c.fetchall()
    
    if not services:
        send_msg(chat_id, "📭 لا توجد خدمات")
        return
    
    buttons = []
    for serv_id, name, price in services:
        buttons.append([{'text': f'{name} - {price} USD/1000', 'callback_data': f'serv_{serv_id}'}])
    
    buttons.append([{'text': '🔙 رجوع', 'callback_data': 'services'}])
    send_msg(chat_id, "📦 اختر خدمة:", buttons)

def service_menu(chat_id, user_id, service_id):
    c.execute("SELECT name, price_per_k, min_order, max_order FROM services WHERE id = ?", (service_id,))
    serv = c.fetchone()
    
    if not serv:
        send_msg(chat_id, "❌ الخدمة غير موجودة")
        return
    
    name, price, min_q, max_q = serv
    send_msg(chat_id, f"🛒 {name}\n💰 السعر: {price} USD/1000\n🔢 الحدود: {min_q}-{max_q}\n✍️ أرسل الكمية:")
    user_states[user_id] = {'type': 'order_qty', 'service_id': service_id}

def admin_panel(chat_id):
    buttons = [
        [{'text': '📊 إحصائيات', 'callback_data': 'stats'}, {'text': '👥 المستخدمين', 'callback_data': 'users_list'}],
        [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'manage_services'}, {'text': '💳 شحن رصيد', 'callback_data': 'admin_charge'}],
        [{'text': '🚫 إدارة الحظر', 'callback_data': 'ban_manage'}, {'text': '👑 إدارة المشرفين', 'callback_data': 'admin_manage'}],
        [{'text': '📢 القنوات الإجبارية', 'callback_data': 'channels_manage'}, {'text': '🎁 إرسال للجميع', 'callback_data': 'send_all'}],
        [{'text': '⚙️ الإعدادات', 'callback_data': 'settings_menu'}, {'text': '🔗 تغيير آيدي مستخدم', 'callback_data': 'change_user_id'}],  # تم الإضافة
        [{'text': '🔙 رئيسية', 'callback_data': 'main'}]
    ]
    send_msg(chat_id, "👑 <b>لوحة تحكم المدير</b>", buttons)

def user_details(chat_id, target_id):
    c.execute("SELECT * FROM users WHERE user_id = ?", (target_id,))
    user = c.fetchone()
    
    if not user:
        send_msg(chat_id, "❌ المستخدم غير موجود")
        return
    
    status = "🚫 محظور" if user[4] == 1 else "⛔ مقيد" if user[5] == 1 else "👑 مشرف" if user[3] == 1 else "✅ نشط"
    
    text = f"""👤 <b>معلومات المستخدم</b>

🆔 الآيدي: <code>{target_id}</code>
📛 اليوزر: @{user[1] or 'بدون'}
💰 الرصيد: {user[2]:,.2f} USD
📊 الحالة: {status}
📅 تاريخ الإنشاء: {user[8]}
"""
    
    buttons = [
        [{'text': '🚫 حظر', 'callback_data': f'ban_{target_id}'}, {'text': '✅ فك حظر', 'callback_data': f'unban_{target_id}'}],
        [{'text': '⛔ تقييد', 'callback_data': f'restrict_{target_id}'}, {'text': '🔓 فك تقييد', 'callback_data': f'unrestrict_{target_id}'}],
        [{'text': '👑 رفع مشرف', 'callback_data': f'promote_{target_id}'}, {'text': '👤 خفض مشرف', 'callback_data': f'demote_{target_id}'}],
        [{'text': '💰 شحن رصيد', 'callback_data': f'charge_{target_id}'}, {'text': '📩 إرسال رسالة', 'callback_data': f'msg_{target_id}'}],
        [{'text': '🔙 رجوع', 'callback_data': 'users_list'}]
    ]
    
    send_msg(chat_id, text, buttons)

# معالجة الرسائل
user_states = {}

def handle_message(chat_id, user_id, text):
    # التحقق من القنوات
    subscribed, channel = check_channels(user_id)
    if not subscribed:
        buttons = [[
            {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
            {'text': '✅ تحقق', 'callback_data': 'check_sub'}
        ]]
        send_msg(chat_id, f"📢 يجب الاشتراك في @{channel} أولاً", buttons)
        return
    
    # التحقق من الحظر
    c.execute("SELECT is_banned, is_restricted FROM users WHERE user_id = ?", (user_id,))
    user_status = c.fetchone()
    if user_status:
        if user_status[0] == 1:
            send_msg(chat_id, "🚫 تم حظرك من البوت")
            return
        if user_status[1] == 1 and user_id != ADMIN_ID:
            send_msg(chat_id, "⛔ حسابك مقيد")
            return
    
    if user_id in user_states:
        state = user_states[user_id]
        
        if state['type'] == 'order_qty':
            service_id = state['service_id']
            c.execute("SELECT name, price_per_k, min_order, max_order FROM services WHERE id = ?", (service_id,))
            serv = c.fetchone()
            
            if serv:
                name, price, min_q, max_q = serv
                try:
                    quantity = int(text)
                    if quantity >= min_q and quantity <= max_q:
                        total_price = (price / 1000) * quantity
                        user_states[user_id] = {'type': 'order_link', 'service_id': service_id, 'quantity': quantity, 'total': total_price}
                        send_msg(chat_id, f"✍️ أرسل الرابط لـ {name}:")
                    else:
                        send_msg(chat_id, f"❌ الحدود {min_q}-{max_q}")
                except:
                    send_msg(chat_id, "❌ أدخل رقم صحيح")
            return
        
        elif state['type'] == 'order_link':
            link = text
            service_id = state['service_id']
            quantity = state['quantity']
            total = state['total']
            
            c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            balance = c.fetchone()[0]
            
            if balance >= total:
                c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total, user_id))
                c.execute("INSERT INTO orders (user_id, service_id, quantity, total_price, link) VALUES (?, ?, ?, ?, ?)",
                          (user_id, service_id, quantity, total, link))
                order_id = c.lastrowid
                conn.commit()
                
                send_msg(chat_id, f"✅ تم إرسال الطلب #{order_id}\n💰 المبلغ: {total:,.2f} USD")
                
                # إشعار للمدير
                c.execute("SELECT name FROM services WHERE id = ?", (service_id,))
                service_name = c.fetchone()[0]
                send_msg(ADMIN_ID, f"🆕 طلب جديد #{order_id}\n👤 {user_id}\n📦 {service_name}\n💰 {total:,.2f} USD")
            else:
                send_msg(chat_id, "❌ رصيد غير كافي")
            
            del user_states[user_id]
            return
        
        elif state.get('type') == 'add_category':
            if len(text) > 1:
                c.execute("INSERT INTO categories (name) VALUES (?)", (text,))
                conn.commit()
                send_msg(chat_id, f"✅ تم إضافة قسم: {text}")
            del user_states[user_id]
            return
        
        elif state.get('type') == 'add_service_name':
            c.execute("SELECT id FROM categories WHERE id = ?", (state['cat_id'],))
            if not c.fetchone():
                send_msg(chat_id, "❌ القسم غير موجود")
                del user_states[user_id]
                return
            
            user_states[user_id] = {'type': 'add_service_price', 'cat_id': state['cat_id'], 'name': text}
            send_msg(chat_id, "💰 أرسل السعر لكل 1000:")
            return
        
        elif state.get('type') == 'add_service_price':
            try:
                price = float(text)
                user_states[user_id] = {'type': 'add_service_min', 'cat_id': state['cat_id'], 'name': state['name'], 'price': price}
                send_msg(chat_id, "🔢 أرسل الحد الأدنى:")
            except:
                send_msg(chat_id, "❌ سعر غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'add_service_min':
            try:
                min_order = int(text)
                user_states[user_id] = {'type': 'add_service_max', 'cat_id': state['cat_id'], 'name': state['name'], 
                                       'price': state['price'], 'min': min_order}
                send_msg(chat_id, "🔢 أرسل الحد الأقصى:")
            except:
                send_msg(chat_id, "❌ رقم غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'add_service_max':
            try:
                max_order = int(text)
                c.execute("INSERT INTO services (category_id, name, price_per_k, min_order, max_order) VALUES (?, ?, ?, ?, ?)",
                          (state['cat_id'], state['name'], state['price'], state['min'], max_order))
                conn.commit()
                send_msg(chat_id, f"✅ تم إضافة الخدمة: {state['name']}")
                del user_states[user_id]
            except:
                send_msg(chat_id, "❌ رقم غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'add_channel_id':
            channel_id = text
            user_states[user_id] = {'type': 'add_channel_user', 'channel_id': channel_id}
            send_msg(chat_id, "📛 أرسل يوزر القناة (بدون @):")
            return
        
        elif state.get('type') == 'add_channel_user':
            channel_user = text
            user_states[user_id] = {'type': 'add_channel_url', 'channel_id': state['channel_id'], 'channel_user': channel_user}
            send_msg(chat_id, "🔗 أرسل رابط القناة:")
            return
        
        elif state.get('type') == 'add_channel_url':
            channel_url = text
            c.execute("INSERT INTO forced_channels (channel_id, channel_username, channel_url) VALUES (?, ?, ?)",
                      (state['channel_id'], state['channel_user'], channel_url))
            conn.commit()
            send_msg(chat_id, f"✅ تم إضافة القناة @{state['channel_user']}")
            del user_states[user_id]
            return
        
        elif state.get('type') == 'admin_charge_user':
            if text.isdigit():
                target_id = int(text)
                user_states[user_id] = {'type': 'admin_charge_amount', 'target_id': target_id}
                send_msg(chat_id, f"💰 أرسل المبلغ للمستخدم {target_id}:")
            else:
                send_msg(chat_id, "❌ آيدي غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'admin_charge_amount':
            try:
                amount = float(text)
                target_id = user_states[user_id]['target_id']
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                send_msg(chat_id, f"✅ تم شحن {amount:,.2f} USD للمستخدم {target_id}")
                send_msg(target_id, f"🎉 تم شحن رصيدك\nالمبلغ: {amount:,.2f} USD")
                del user_states[user_id]
            except:
                send_msg(chat_id, "❌ مبلغ غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'send_to_all_amount':
            try:
                amount = float(text)
                user_states[user_id] = {'type': 'send_to_all_msg', 'amount': amount}
                send_msg(chat_id, "📝 أرسل الرسالة المراد إرسالها مع المبلغ:")
            except:
                send_msg(chat_id, "❌ مبلغ غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'send_to_all_msg':
            message = text
            amount = user_states[user_id]['amount']
            
            c.execute("SELECT user_id FROM users WHERE is_banned = 0")
            users = c.fetchall()
            
            count = 0
            for u in users:
                user_id_target = u[0]
                if user_id_target != ADMIN_ID:
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id_target))
                    send_msg(user_id_target, f"🎁 {message}\n💰 المكافأة: {amount:,.2f} USD")
                    count += 1
                    time.sleep(0.1)
            
            conn.commit()
            send_msg(chat_id, f"✅ تم إرسال {amount:,.2f} USD لـ {count} مستخدم")
            del user_states[user_id]
            return
        
        elif state.get('type') == 'send_user_message':
            target_id = state['target_id']
            send_msg(target_id, f"📩 رسالة من الإدارة:\n\n{text}")
            send_msg(chat_id, f"✅ تم إرسال الرسالة للمستخدم {target_id}")
            del user_states[user_id]
            return
        
        # ===== التعديلات الجديدة =====
        elif state.get('type') == 'change_user_id':
            if text.isdigit():
                old_id = int(text)
                user_states[user_id] = {'type': 'change_user_id_new', 'old_id': old_id}
                send_msg(chat_id, f"🔁 أرسل الآيدي الجديد للمستخدم {old_id}:")
            else:
                send_msg(chat_id, "❌ آيدي غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'change_user_id_new':
            try:
                old_id = state['old_id']
                new_id = int(text)
                
                # التحقق من وجود المستخدم القديم
                c.execute("SELECT * FROM users WHERE user_id = ?", (old_id,))
                if not c.fetchone():
                    send_msg(chat_id, "❌ المستخدم القديم غير موجود")
                    del user_states[user_id]
                    return
                
                # التحقق من عدم وجود مستخدم بالآيدي الجديد
                c.execute("SELECT * FROM users WHERE user_id = ?", (new_id,))
                if c.fetchone():
                    send_msg(chat_id, "❌ الآيدي الجديد موجود مسبقاً")
                    del user_states[user_id]
                    return
                
                # نقل جميع البيانات
                # 1. نسخ بيانات المستخدم
                c.execute("UPDATE users SET user_id = ? WHERE user_id = ?", (new_id, old_id))
                
                # 2. تحديث الطلبات
                c.execute("UPDATE orders SET user_id = ? WHERE user_id = ?", (new_id, old_id))
                
                # 3. تحديث الدعوات
                c.execute("UPDATE users SET invited_by = ? WHERE invited_by = ?", (new_id, old_id))
                
                conn.commit()
                send_msg(chat_id, f"✅ تم تغيير آيدي المستخدم من {old_id} إلى {new_id}")
                send_msg(new_id, f"🔄 تم تغيير آيدي حسابك إلى {new_id}")
                del user_states[user_id]
            except:
                send_msg(chat_id, "❌ حدث خطأ في تغيير الآيدي")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'change_reward':
            try:
                new_reward = float(text)
                if new_reward < 0:
                    send_msg(chat_id, "❌ المبلغ يجب أن يكون موجباً")
                else:
                    c.execute("UPDATE settings SET value = ? WHERE key = 'invite_reward'", (str(new_reward),))
                    conn.commit()
                    send_msg(chat_id, f"✅ تم تغيير مكافأة الدعوة إلى {new_reward} USD")
                del user_states[user_id]
            except:
                send_msg(chat_id, "❌ مبلغ غير صحيح")
                del user_states[user_id]
            return
        # ===== نهاية التعديلات الجديدة =====
    
    if text == '/start':
        # التحقق من كود الدعوة
        if ' ' in text:
            invite_code = text.split(' ')[1]
            c.execute("SELECT user_id FROM users WHERE invite_code = ?", (invite_code,))
            inviter = c.fetchone()
            
            if inviter and inviter[0] != user_id and get_setting('invite_enabled') == 'true':
                reward = float(get_setting('invite_reward'))
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, inviter[0]))
                conn.commit()
                send_msg(inviter[0], f"🎉 مكافأة دعوة {reward} USD")
        
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not c.fetchone():
            invite_code = str(uuid.uuid4())[:8]
            c.execute("INSERT INTO users (user_id, invite_code) VALUES (?, ?)", (user_id, invite_code))
            conn.commit()
        
        main_menu(chat_id, user_id)
    
    elif text == '/admin' and user_id == ADMIN_ID:
        admin_panel(chat_id)
    
    else:
        main_menu(chat_id, user_id)

def handle_callback(chat_id, user_id, data):
    # التحقق من القنوات
    if data != 'check_sub':
        subscribed, channel = check_channels(user_id)
        if not subscribed:
            buttons = [[
                {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
                {'text': '✅ تحقق', 'callback_data': 'check_sub'}
            ]]
            send_msg(chat_id, f"📢 يجب الاشتراك في @{channel} أولاً", buttons)
            return
    
    if data == 'main':
        main_menu(chat_id, user_id)
    
    elif data == 'check_sub':
        subscribed, channel = check_channels(user_id)
        if subscribed:
            send_msg(chat_id, "✅ أنت مشترك في جميع القنوات")
            main_menu(chat_id, user_id)
        else:
            buttons = [[
                {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
                {'text': '✅ تحقق', 'callback_data': 'check_sub'}
            ]]
            send_msg(chat_id, f"❌ لم تشترك بعد في @{channel}", buttons)
    
    elif data == 'services':
        services_menu(chat_id)
    
    elif data.startswith('cat_'):
        cat_id = data.split('_')[1]
        category_menu(chat_id, cat_id)
    
    elif data.startswith('serv_'):
        service_id = data.split('_')[1]
        service_menu(chat_id, user_id, service_id)
    
    elif data == 'charge':
        send_msg(chat_id, f"💰 للشحن راسل @{SUPPORT_USERNAME}\n🆔 آيديك: {user_id}")
    
    elif data == 'balance':
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = c.fetchone()[0]
        send_msg(chat_id, f"💰 رصيدك: {balance:,.2f} USD")
    
    elif data == 'invite':
        c.execute("SELECT invite_code FROM users WHERE user_id = ?", (user_id,))
        code = c.fetchone()[0]
        
        # ===== التعديل: رابط الدعوة الجديد =====
        # إنشاء رابط على شكل: https://t.me/Flashback70bot?start=CODE_USERID_RANDOM
        bot_username = get_setting('bot_username') or BOT_USERNAME
        user_code = generate_user_code()
        link = f"https://t.me/{bot_username}?start={code}_{user_id}_{user_code}"
        # ===== نهاية التعديل =====
        
        reward = get_setting('invite_reward')
        
        text = f"""👥 <b>دعوة أصدقاء</b>

💰 المكافأة: {reward} USD
🔗 رابطك: {link}"""
        
        buttons = [[
            {'text': '📤 مشاركة', 'url': f'tg://msg_url?url={link}'},
            {'text': '🔙 رجوع', 'callback_data': 'main'}
        ]]
        send_msg(chat_id, text, buttons)
    
    elif data == 'my_orders':
        c.execute("SELECT o.id, s.name, o.quantity, o.total_price, o.status FROM orders o JOIN services s ON o.service_id = s.id WHERE o.user_id = ? ORDER BY o.id DESC LIMIT 5", (user_id,))
        orders = c.fetchall()
        
        if orders:
            text = "📋 <b>طلباتك</b>\n\n"
            for oid, name, qty, price, status in orders:
                status_icon = '✅' if status == 'completed' else '⏳' if status == 'processing' else '❌'
                text += f"{status_icon} #{oid} - {name[:15]}\n🔢 {qty} | 💰 {price:,.2f} USD\n━━━━━━\n"
        else:
            text = "📭 لا توجد طلبات"
        
        send_msg(chat_id, text)
    
    elif data == 'support':
        send_msg(chat_id, f"📞 الدعم: @{SUPPORT_USERNAME}\n🆔 آيديك: {user_id}")
    
    elif data == 'admin':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            admin_panel(chat_id)
        else:
            send_msg(chat_id, "🚫 ليس لديك صلاحية")
    
    elif data == 'stats':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            banned = c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
            restricted = c.execute("SELECT COUNT(*) FROM users WHERE is_restricted = 1").fetchone()[0]
            admins = c.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
            balance = c.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
            orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            
            text = f"""📊 <b>إحصائيات البوت</b>

👥 المستخدمين: {users}
👑 المشرفين: {admins}
🚫 المحظورين: {banned}
⛔ المقيدين: {restricted}
💰 إجمالي الأرصدة: {balance:,.2f} USD
📦 الطلبات: {orders}"""
            send_msg(chat_id, text)
    
    elif data == 'users_list':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1:
            user_states[user_id] = {'type': 'view_user'}
            send_msg(chat_id, "🔍 أرسل آيدي المستخدم:")
    
    elif data.startswith('ban_'):
        target_id = int(data.split('_')[1])
        c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم حظر المستخدم {target_id}")
        send_msg(target_id, "🚫 تم حظرك من البوت")
    
    elif data.startswith('unban_'):
        target_id = int(data.split('_')[1])
        c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم فك حظر المستخدم {target_id}")
        send_msg(target_id, "✅ تم فك حظرك")
    
    elif data.startswith('restrict_'):
        target_id = int(data.split('_')[1])
        c.execute("UPDATE users SET is_restricted = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم تقييد المستخدم {target_id}")
        send_msg(target_id, "⛔ تم تقييد حسابك")
    
    elif data.startswith('unrestrict_'):
        target_id = int(data.split('_')[1])
        c.execute("UPDATE users SET is_restricted = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم فك تقييد المستخدم {target_id}")
        send_msg(target_id, "✅ تم فك تقييد حسابك")
    
    elif data.startswith('promote_'):
        target_id = int(data.split('_')[1])
        c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم رفع المستخدم {target_id} كمشرف")
        send_msg(target_id, "👑 تم رفعك كمشرف")
    
    elif data.startswith('demote_'):
        target_id = int(data.split('_')[1])
        c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم خفض المستخدم {target_id} لمستخدم عادي")
        send_msg(target_id, "👤 تم خفض صلاحياتك")
    
    elif data.startswith('charge_'):
        target_id = int(data.split('_')[1])
        user_states[user_id] = {'type': 'admin_charge_user'}
        send_msg(chat_id, f"💰 أرسل المبلغ للمستخدم {target_id}:")
    
    elif data.startswith('msg_'):
        target_id = int(data.split('_')[1])
        user_states[user_id] = {'type': 'send_user_message', 'target_id': target_id}
        send_msg(chat_id, f"📝 أرسل الرسالة للمستخدم {target_id}:")
    
    elif data == 'manage_services':
        buttons = [
            [{'text': '📁 إضافة قسم', 'callback_data': 'add_category'}],
            [{'text': '➕ إضافة خدمة', 'callback_data': 'add_service'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
        ]
        send_msg(chat_id, "🛍️ إدارة الخدمات:", buttons)
    
    elif data == 'add_category':
        user_states[user_id] = {'type': 'add_category'}
        send_msg(chat_id, "➕ أرسل اسم القسم الجديد:")
    
    elif data == 'add_service':
        c.execute("SELECT id, name FROM categories")
        cats = c.fetchall()
        
        if not cats:
            send_msg(chat_id, "❌ لا توجد أقسام")
            return
        
        buttons = []
        for cat_id, name in cats:
            buttons.append([{'text': name, 'callback_data': f'addserv_{cat_id}'}])
        
        buttons.append([{'text': '🔙 رجوع', 'callback_data': 'manage_services'}])
        send_msg(chat_id, "📁 اختر قسم:", buttons)
    
    elif data.startswith('addserv_'):
        cat_id = data.split('_')[1]
        user_states[user_id] = {'type': 'add_service_name', 'cat_id': cat_id}
        send_msg(chat_id, "➕ أرسل اسم الخدمة:")
    
    elif data == 'admin_charge':
        user_states[user_id] = {'type': 'admin_charge_user'}
        send_msg(chat_id, "💰 أرسل آيدي المستخدم:")
    
    elif data == 'ban_manage':
        buttons = [
            [{'text': '🚫 حظر مستخدم', 'callback_data': 'ban_user'}, {'text': '✅ فك حظر', 'callback_data': 'unban_user'}],
            [{'text': '⛔ تقييد مستخدم', 'callback_data': 'restrict_user'}, {'text': '🔓 فك تقييد', 'callback_data': 'unrestrict_user'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
        ]
        send_msg(chat_id, "🚫 إدارة الحظر:", buttons)
    
    elif data == 'ban_user':
        user_states[user_id] = {'type': 'ban_user'}
        send_msg(chat_id, "🚫 أرسل آيدي المستخدم للحظر:")
    
    elif data == 'unban_user':
        user_states[user_id] = {'type': 'unban_user'}
        send_msg(chat_id, "✅ أرسل آيدي المستخدم لفك الحظر:")
    
    elif data == 'restrict_user':
        user_states[user_id] = {'type': 'restrict_user'}
        send_msg(chat_id, "⛔ أرسل آيدي المستخدم للتقييد:")
    
    elif data == 'unrestrict_user':
        user_states[user_id] = {'type': 'unrestrict_user'}
        send_msg(chat_id, "🔓 أرسل آيدي المستخدم لفك التقييد:")
    
    elif data == 'admin_manage':
        buttons = [
            [{'text': '👑 رفع مشرف', 'callback_data': 'promote_admin'}, {'text': '👤 خفض مشرف', 'callback_data': 'demote_admin'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
        ]
        send_msg(chat_id, "👑 إدارة المشرفين:", buttons)
    
    elif data == 'promote_admin':
        user_states[user_id] = {'type': 'promote_admin'}
        send_msg(chat_id, "👑 أرسل آيدي المستخدم للرفع:")
    
    elif data == 'demote_admin':
        user_states[user_id] = {'type': 'demote_admin'}
        send_msg(chat_id, "👤 أرسل آيدي المستخدم للخفض:")
    
    elif data == 'channels_manage':
        c.execute("SELECT * FROM forced_channels")
        channels = c.fetchall()
        
        text = "📢 <b>القنوات الإجبارية</b>\n\n"
        if channels:
            for ch in channels:
                text += f"🔗 @{ch[2]}\n━━━━━━\n"
        else:
            text += "📭 لا توجد قنوات\n"
        
        buttons = [
            [{'text': '➕ إضافة قناة', 'callback_data': 'add_channel'}, {'text': '🗑️ حذف قناة', 'callback_data': 'remove_channel'}],
            [{'text': '✅ تفعيل النظام', 'callback_data': 'enable_force'}, {'text': '❌ تعطيل النظام', 'callback_data': 'disable_force'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
        ]
        send_msg(chat_id, text, buttons)
    
    elif data == 'add_channel':
        user_states[user_id] = {'type': 'add_channel_id'}
        send_msg(chat_id, "🆔 أرسل آيدي القناة:")
    
    elif data == 'remove_channel':
        c.execute("SELECT id, channel_username FROM forced_channels")
        channels = c.fetchall()
        
        if not channels:
            send_msg(chat_id, "📭 لا توجد قنوات")
            return
        
        buttons = []
        for ch_id, ch_user in channels:
            buttons.append([{'text': f'🗑️ @{ch_user}', 'callback_data': f'remchannel_{ch_id}'}])
        
        buttons.append([{'text': '🔙 رجوع', 'callback_data': 'channels_manage'}])
        send_msg(chat_id, "🗑️ اختر قناة للحذف:", buttons)
    
    elif data.startswith('remchannel_'):
        ch_id = int(data.split('_')[1])
        c.execute("DELETE FROM forced_channels WHERE id = ?", (ch_id,))
        conn.commit()
        send_msg(chat_id, "✅ تم حذف القناة")
    
    elif data == 'enable_force':
        c.execute("UPDATE settings SET value = 'true' WHERE key = 'force_subscribe'")
        conn.commit()
        send_msg(chat_id, "✅ تم تفعيل الاشتراك الإجباري")
    
    elif data == 'disable_force':
        c.execute("UPDATE settings SET value = 'false' WHERE key = 'force_subscribe'")
        conn.commit()
        send_msg(chat_id, "❌ تم تعطيل الاشتراك الإجباري")
    
    elif data == 'send_all':
        user_states[user_id] = {'type': 'send_to_all_amount'}
        send_msg(chat_id, "💰 أرسل المبلغ المراد إرساله للجميع:")
    
    elif data == 'settings_menu':
        maint = get_setting('maintenance')
        reward = get_setting('invite_reward')
        bot_user = get_setting('bot_username')
        
        text = f"""⚙️ <b>إعدادات البوت</b>

🔧 الصيانة: {'✅ مفعل' if maint == 'true' else '❌ معطل'}
💰 مكافأة الدعوة: {reward} USD
🤖 يوزر البوت: @{bot_user}"""
        
        buttons = [
            [{'text': '🔧 تبديل الصيانة', 'callback_data': 'toggle_maint'}, {'text': '💰 تغيير المكافأة', 'callback_data': 'change_reward'}],
            [{'text': '🤖 تغيير يوزر البوت', 'callback_data': 'change_bot_user'}, {'text': '🔙 رجوع', 'callback_data': 'admin'}]
        ]
        send_msg(chat_id, text, buttons)
    
    elif data == 'toggle_maint':
        current = get_setting('maintenance')
        new_val = 'false' if current == 'true' else 'true'
        c.execute("UPDATE settings SET value = ? WHERE key = 'maintenance'", (new_val,))
        conn.commit()
        send_msg(chat_id, f"✅ تم {'تفعيل' if new_val == 'true' else 'تعطيل'} الصيانة")
    
    elif data == 'change_reward':
        user_states[user_id] = {'type': 'change_reward'}
        send_msg(chat_id, "💰 أرسل المبلغ الجديد:")
    
    elif data == 'change_bot_user':
        user_states[user_id] = {'type': 'change_bot_user'}
        send_msg(chat_id, "🤖 أرسل يوزر البوت الجديد (بدون @):")
    
    # ===== التعديلات الجديدة =====
    elif data == 'change_user_id':
        user_states[user_id] = {'type': 'change_user_id'}
        send_msg(chat_id, "🔁 أرسل الآيدي القديم للمستخدم:")
    # ===== نهاية التعديلات الجديدة =====

# ===== حل مشكلة Render =====
def run_background_worker():
    """تشغيل البوت كـ Background Worker"""
    print("🚀 البوت يعمل على Render كـ Background Worker...")
    print(f"👑 المدير: {ADMIN_ID}")
    print(f"📞 الدعم: @{SUPPORT_USERNAME}")
    print(f"🤖 البوت: @{BOT_USERNAME}")
    
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            params = {'offset': offset, 'timeout': 30}
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code == 200:
                updates = response.json()
                if updates.get('ok'):
                    for update in updates['result']:
                        offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            msg = update['message']
                            chat_id = msg['chat']['id']
                            user_id = msg['from']['id']
                            username = msg['from'].get('username', '')
                            
                            if 'text' in msg:
                                text = msg['text']
                                handle_message(chat_id, user_id, text)
                        
                        elif 'callback_query' in update:
                            query = update['callback_query']
                            chat_id = query['message']['chat']['id']
                            user_id = query['from']['id']
                            data = query['data']
                            
                            try:
                                handle_callback(chat_id, user_id, data)
                            except Exception as e:
                                print(f"⚠️ خطأ في الكال باك: {e}")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"⚠️ خطأ في البولينغ: {e}")
            time.sleep(5)

# ===== الإضافة: خيار تشغيل كـ Web Service =====
def run_web_service():
    """تشغيل البوت كـ Web Service"""
    from flask import Flask, request
    import threading
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "🤖 البوت يعمل على Render كـ Web Service"
    
    @app.route(f'/{TOKEN}', methods=['POST'])
    def webhook():
        update = request.json
        if update:
            if 'message' in update:
                msg = update['message']
                chat_id = msg['chat']['id']
                user_id = msg['from']['id']
                
                if 'text' in msg:
                    text = msg['text']
                    handle_message(chat_id, user_id, text)
            
            elif 'callback_query' in update:
                query = update['callback_query']
                chat_id = query['message']['chat']['id']
                user_id = query['from']['id']
                data = query['data']
                
                try:
                    handle_callback(chat_id, user_id, data)
                except:
                    pass
        
        return 'OK'
    
    # تشغيل البولينغ في خيط منفصل
    threading.Thread(target=run_background_worker, daemon=True).start()
    
    # تشغيل Flask
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# التشغيل الرئيسي
if __name__ == '__main__':
    import os
    
    # اختيار وضع التشغيل حسب البيئة
    if os.environ.get('RENDER', '').lower() == 'true':
        # على Render - استخدم Web Service
        print("🌐 تشغيل كـ Web Service...")
        run_web_service()
    else:
        # محلي أو Background Worker
        print("⚙️ تشغيل كـ Background Worker...")
        run_background_worker()
