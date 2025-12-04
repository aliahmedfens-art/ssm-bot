import sqlite3
import requests
import time
import json
import uuid
import random
import string

# تأكد من تغيير الآيدي هذا إلى آيديك الحقيقي
TOKEN = "8436742877:AAHmlmOKY2iQCGoOt004ruq09tZGderDGMQ"
ADMIN_ID = 8462737195  # غير هذا الرقم إلى آيديك الحقيقي
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"

# قاعدة البيانات
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (user_id INTEGER PRIMARY KEY, username TEXT, 
             balance REAL DEFAULT 0, is_admin INTEGER DEFAULT 0, 
             is_banned INTEGER DEFAULT 0, is_restricted INTEGER DEFAULT 0,
             invited_by INTEGER DEFAULT 0, invite_code TEXT UNIQUE,
             total_invites INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

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

c.execute('''CREATE TABLE IF NOT EXISTS invoices 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER,
             user_id INTEGER, invoice_data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# إعدادات افتراضية
default_settings = [
    ('maintenance', 'false'),
    ('maintenance_msg', 'البوت تحت الصيانة'),
    ('invite_reward', '0.10'),
    ('invite_enabled', 'true'),
    ('force_subscribe', 'false'),
    ('bot_username', BOT_USERNAME)
]

for key, value in default_settings:
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

# تأكد من إضافة آيديك الحقيقي كمدير
c.execute("DELETE FROM users WHERE user_id = ?", (ADMIN_ID,))
c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
          (ADMIN_ID, "المدير", 1000, 1, 'ADMIN'))

# إضافة خدمات تجريبية
c.execute("SELECT COUNT(*) FROM categories")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO categories (name) VALUES ('متابعات')")
    c.execute("INSERT INTO categories (name) VALUES ('لايكات')")
    c.execute("INSERT INTO categories (name) VALUES ('مشاهدات')")

c.execute("SELECT COUNT(*) FROM services")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO services (category_id, name, price_per_k, min_order, max_order) VALUES (1, 'متابعين انستغرام', 0.5, 100, 10000)")
    c.execute("INSERT INTO services (category_id, name, price_per_k, min_order, max_order) VALUES (1, 'متابعين تيك توك', 0.4, 100, 5000)")
    c.execute("INSERT INTO services (category_id, name, price_per_k, min_order, max_order) VALUES (2, 'لايكات انستغرام', 0.3, 100, 10000)")
    c.execute("INSERT INTO services (category_id, name, price_per_k, min_order, max_order) VALUES (3, 'مشاهدات يوتيوب', 0.2, 500, 50000)")

conn.commit()

# وظائف مساعدة
def get_setting(key):
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = c.fetchone()
    return result[0] if result else None

def set_setting(key, value):
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()

def send_msg(chat_id, text, buttons=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if buttons:
            data['reply_markup'] = json.dumps({'inline_keyboard': buttons})
        requests.post(url, json=data, timeout=10)
    except:
        pass

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

def get_user_balance(user_id):
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result[0] if result else 0

def create_invoice(order_id, user_id, service_name, quantity, price_per_k, total_price, link):
    c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    user_result = c.fetchone()
    username = user_result[0] if user_result else "مستخدم"
    
    invoice_data = {
        'invoice_id': order_id,
        'user_id': user_id,
        'username': username,
        'service_name': service_name,
        'quantity': quantity,
        'price_per_k': price_per_k,
        'total_price': total_price,
        'link': link,
        'status': 'مدفوعة'
    }
    
    invoice_text = f"""
╔══════════════════════════╗
🛒 *فاتورة الشراء* #{order_id}
╚══════════════════════════╝

👤 *العميل:* {user_id}
📛 *اليوزر:* @{username}

📦 *الخدمة:* {service_name}
🔢 *الكمية:* {quantity:,}
💰 *السعر:* {price_per_k} دولار/1000
💵 *المجموع:* {total_price:,.2f} دولار

🔗 *الرابط:* {link[:50]}...

━━━━━━━━━━━━━━━━━━━━━━
💰 *الإجمالي:* {total_price:,.2f} دولار
━━━━━━━━━━━━━━━━━━━━━━

📞 *الدعم:* @{SUPPORT_USERNAME}
💙 *شكراً لشرائك!*
    """
    
    c.execute("INSERT INTO invoices (order_id, user_id, invoice_data) VALUES (?, ?, ?)",
             (order_id, user_id, json.dumps(invoice_data)))
    conn.commit()
    
    return invoice_text

user_states = {}

def main_menu(chat_id, user_id):
    c.execute("SELECT is_banned, is_restricted FROM users WHERE user_id = ?", (user_id,))
    user_status = c.fetchone()
    
    if user_status:
        if user_status[0] == 1:
            send_msg(chat_id, "🚫 تم حظرك من البوت")
            return
        if user_status[1] == 1:
            send_msg(chat_id, "⛔ حسابك مقيد")
            return
    
    subscribed, channel = check_channels(user_id)
    if not subscribed:
        buttons = [[
            {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
            {'text': '✅ تحقق', 'callback_data': 'check_sub'}
        ]]
        send_msg(chat_id, f"📢 يجب الاشتراك في @{channel} أولاً", buttons)
        return
    
    c.execute("SELECT username, balance, is_admin FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    username = user[0] if user else "مستخدم"
    balance = user[1] if user else 0
    is_admin = user[2] if user else 0
    
    text = f"""👋 أهلاً {username}

🆔 الآيدي: <code>{user_id}</code>
💰 الرصيد: <b>{balance:,.2f} دولار</b>

📌 اختر من القائمة:"""
    
    buttons = [
        [{'text': '🛍️ الخدمات', 'callback_data': 'services'}],
        [{'text': '💰 شحن الرصيد', 'callback_data': 'charge'}, {'text': '💳 رصيدي', 'callback_data': 'balance'}],
        [{'text': '👥 دعوة أصدقاء', 'callback_data': 'invite'}, {'text': '📋 طلباتي', 'callback_data': 'my_orders'}],
        [{'text': '📞 الدعم', 'callback_data': 'support'}]
    ]
    
    if is_admin == 1:
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
    send_msg(chat_id, "🛍️ اختر القسم:", buttons)

def category_menu(chat_id, cat_id):
    c.execute("SELECT id, name, price_per_k FROM services WHERE category_id = ?", (cat_id,))
    services = c.fetchall()
    
    if not services:
        send_msg(chat_id, "📭 لا توجد خدمات في هذا القسم")
        return
    
    buttons = []
    for serv_id, name, price in services:
        buttons.append([{'text': f'{name} - {price} دولار/1000', 'callback_data': f'serv_{serv_id}'}])
    
    buttons.append([{'text': '🔙 رجوع', 'callback_data': 'services'}])
    send_msg(chat_id, "📦 اختر الخدمة:", buttons)

def service_menu(chat_id, user_id, service_id):
    c.execute("SELECT name, price_per_k, min_order, max_order FROM services WHERE id = ?", (service_id,))
    serv = c.fetchone()
    
    if not serv:
        send_msg(chat_id, "❌ الخدمة غير موجودة")
        return
    
    name, price, min_q, max_q = serv
    send_msg(chat_id, f"🛒 {name}\n💰 السعر: {price} دولار/1000\n🔢 الحدود: {min_q}-{max_q}\n✍️ أرسل الكمية:")
    
    user_states[user_id] = {'type': 'order_qty', 'service_id': service_id}

def admin_panel(chat_id):
    buttons = [
        [{'text': '📊 الإحصائيات', 'callback_data': 'stats'}, {'text': '👥 إدارة المستخدمين', 'callback_data': 'users_management'}],
        [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'manage_services'}, {'text': '💳 شحن رصيد', 'callback_data': 'admin_charge'}],
        [{'text': '🚫 إدارة الحظر', 'callback_data': 'ban_management'}, {'text': '📢 القنوات الإجبارية', 'callback_data': 'channels_manage'}],
        [{'text': '🎁 إرسال للجميع', 'callback_data': 'send_all'}, {'text': '🧾 نظام الفواتير', 'callback_data': 'invoice_system'}],
        [{'text': '⚙️ الإعدادات', 'callback_data': 'settings_menu'}, {'text': '🔙 الرئيسية', 'callback_data': 'main'}]
    ]
    send_msg(chat_id, "👑 <b>لوحة تحكم المدير</b>", buttons)

def ban_management_menu(chat_id):
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
    total_banned = c.fetchone()[0]
    
    c.execute("SELECT user_id, username, balance FROM users WHERE is_banned = 1 LIMIT 10")
    banned_users = c.fetchall()
    
    text = f"🚫 <b>إدارة المستخدمين المحظورين</b>\n\n"
    text += f"👥 عدد المحظورين: {total_banned}\n━━━━━━\n"
    
    if banned_users:
        for user_id, username, balance in banned_users:
            text += f"🆔 {user_id} | @{username or 'بدون'}\n💰 {balance:,.2f} دولار\n━━━━━━\n"
    else:
        text += "📭 لا يوجد مستخدمين محظورين\n"
    
    buttons = []
    
    for user_id, username, balance in banned_users:
        buttons.append([
            {'text': f'✅ فك الحظر', 'callback_data': f'unban_{user_id}'},
            {'text': f'📩 رسالة', 'callback_data': f'msg_{user_id}'}
        ])
    
    buttons.append([
        {'text': '🚫 حظر مستخدم', 'callback_data': 'ban_by_id'},
        {'text': '🗑️ تنظيف المحظورين', 'callback_data': 'clean_banned'}
    ])
    
    buttons.append([{'text': '🔙 رجوع', 'callback_data': 'admin'}])
    
    send_msg(chat_id, text, buttons)

def users_management_menu(chat_id):
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT user_id, username, balance, is_banned, is_restricted, is_admin FROM users LIMIT 10")
    users = c.fetchall()
    
    text = f"👥 <b>إدارة المستخدمين</b>\n\n"
    text += f"📊 العدد الكلي: {total_users}\n━━━━━━\n"
    
    if users:
        for user_id, username, balance, is_banned, is_restricted, is_admin in users:
            status = "🚫" if is_banned else "⛔" if is_restricted else "👑" if is_admin else "✅"
            text += f"{status} {user_id} | @{username or 'بدون'}\n💰 {balance:,.2f} دولار\n━━━━━━\n"
    else:
        text += "📭 لا يوجد مستخدمين\n"
    
    buttons = []
    
    for user_id, username, balance, is_banned, is_restricted, is_admin in users:
        row1 = []
        if is_banned:
            row1.append({'text': '✅ فك', 'callback_data': f'unban_{user_id}'})
        else:
            row1.append({'text': '🚫 حظر', 'callback_data': f'ban_{user_id}'})
        
        if is_restricted:
            row1.append({'text': '🔓 فك', 'callback_data': f'unrestrict_{user_id}'})
        else:
            row1.append({'text': '⛔ تقييد', 'callback_data': f'restrict_{user_id}'})
        
        buttons.append(row1)
        
        buttons.append([
            {'text': '💰 شحن', 'callback_data': f'charge_{user_id}'},
            {'text': '📩 رسالة', 'callback_data': f'msg_{user_id}'}
        ])
    
    buttons.append([{'text': '🔍 بحث عن مستخدم', 'callback_data': 'search_users'}])
    buttons.append([{'text': '🔙 رجوع', 'callback_data': 'admin'}])
    
    send_msg(chat_id, text, buttons)

def invite_system_menu(chat_id, user_id):
    c.execute("SELECT invite_code, total_invites FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    
    if not user_data:
        send_msg(chat_id, "❌ المستخدم غير موجود")
        return
    
    invite_code, total_invites = user_data
    reward = float(get_setting('invite_reward'))
    
    bot_username = get_setting('bot_username') or BOT_USERNAME
    user_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    link = f"https://t.me/{bot_username}?start={invite_code}_{user_code}"
    
    text = f"""👥 <b>دعوة الأصدقاء</b>

💰 المكافأة لكل دعوة: {reward} دولار
👥 عدد المدعوين: {total_invites}
💰 إجمالي الأرباح: {total_invites * reward:,.2f} دولار

🔗 رابط الدعوة الخاص بك:
<code>{link}</code>"""
    
    buttons = [[
        {'text': '📤 مشاركة الرابط', 'url': f'tg://msg_url?url={link}'},
        {'text': '🔄 تحديث', 'callback_data': 'invite'}
    ], [
        {'text': '🔙 رجوع', 'callback_data': 'main'}
    ]]
    
    send_msg(chat_id, text, buttons)

def invoice_system_menu(chat_id):
    c.execute("SELECT COUNT(*) FROM invoices")
    total_invoices = c.fetchone()[0]
    
    text = f"🧾 <b>نظام الفواتير</b>\n\n"
    text += f"📊 إجمالي الفواتير: {total_invoices}\n\n"
    text += "📌 يمكنك استعراض الفواتير والبحث عنها"
    
    buttons = [
        [{'text': '🔍 بحث عن فاتورة', 'callback_data': 'search_invoice'}],
        [{'text': '📋 فواتير اليوم', 'callback_data': 'today_invoices'}],
        [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
    ]
    
    send_msg(chat_id, text, buttons)

def handle_message(chat_id, user_id, text):
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_msg(chat_id, get_setting('maintenance_msg'))
        return
    
    if text.startswith('/start'):
        parts = text.split()
        
        if len(parts) > 1:
            invite_code = parts[1].split('_')[0]
            
            c.execute("SELECT user_id FROM users WHERE invite_code = ?", (invite_code,))
            inviter = c.fetchone()
            
            if inviter and inviter[0] != user_id and get_setting('invite_enabled') == 'true':
                reward = float(get_setting('invite_reward'))
                c.execute("UPDATE users SET balance = balance + ?, total_invites = total_invites + 1 WHERE user_id = ?", 
                         (reward, inviter[0]))
                c.execute("UPDATE users SET invited_by = ? WHERE user_id = ?", (inviter[0], user_id))
                conn.commit()
                send_msg(inviter[0], f"🎉 مكافأة دعوة {reward} دولار! انضم مستخدم جديد.")
        
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not c.fetchone():
            invite_code = str(uuid.uuid4())[:8]
            c.execute("INSERT INTO users (user_id, invite_code) VALUES (?, ?)", (user_id, invite_code))
            conn.commit()
        
        main_menu(chat_id, user_id)
        return
    
    if text == '/admin' and user_id == ADMIN_ID:
        admin_panel(chat_id)
        return
    
    if user_id in user_states:
        state = user_states[user_id]
        
        if state.get('type') == 'order_qty':
            service_id = state['service_id']
            c.execute("SELECT name, price_per_k, min_order, max_order FROM services WHERE id = ?", (service_id,))
            serv = c.fetchone()
            
            if serv:
                name, price, min_q, max_q = serv
                try:
                    quantity = int(text)
                    if min_q <= quantity <= max_q:
                        total_price = (price / 1000) * quantity
                        user_states[user_id] = {'type': 'order_link', 'service_id': service_id, 'quantity': quantity, 'total': total_price}
                        send_msg(chat_id, f"✍️ أرسل الرابط لـ {name}:")
                    else:
                        send_msg(chat_id, f"❌ الحدود المسموحة {min_q}-{max_q}")
                except:
                    send_msg(chat_id, "❌ أدخل رقم صحيح")
            return
        
        elif state.get('type') == 'order_link':
            link = text.strip()
            service_id = state['service_id']
            quantity = state['quantity']
            total = state['total']
            
            if not link.startswith(('http://', 'https://')):
                send_msg(chat_id, "❌ رابط غير صالح. الرجاء إرسال رابط يبدأ بـ http:// أو https://")
                del user_states[user_id]
                return
            
            c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            balance = c.fetchone()[0]
            
            if balance >= total:
                c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total, user_id))
                
                c.execute("INSERT INTO orders (user_id, service_id, quantity, total_price, link) VALUES (?, ?, ?, ?, ?)",
                         (user_id, service_id, quantity, total, link))
                order_id = c.lastrowid
                
                c.execute("SELECT name, price_per_k FROM services WHERE id = ?", (service_id,))
                service_info = c.fetchone()
                service_name = service_info[0] if service_info else "خدمة"
                price_per_k = service_info[1] if service_info else 0
                
                conn.commit()
                
                invoice_text = create_invoice(order_id, user_id, service_name, quantity, price_per_k, total, link)
                
                send_msg(chat_id, f"""✅ تم إرسال الطلب #{order_id} بنجاح!

📦 الخدمة: {service_name}
🔢 الكمية: {quantity:,}
💰 المبلغ: {total:,.2f} دولار

📊 رصيدك الجديد: {balance - total:,.2f} دولار""")
                
                time.sleep(1)
                send_msg(chat_id, invoice_text)
                
                admin_msg = f"""🆕 طلب جديد #{order_id}

👤 المستخدم: {user_id}
📦 الخدمة: {service_name}
🔢 الكمية: {quantity:,}
💰 المبلغ: {total:,.2f} دولار
🔗 الرابط: {link}

📊 رصيد المستخدم: {balance - total:,.2f} دولار"""
                
                send_msg(ADMIN_ID, admin_msg)
                
            else:
                send_msg(chat_id, f"❌ رصيد غير كافي\nرصيدك: {balance:,.2f} دولار\nالمطلوب: {total:,.2f} دولار")
            
            if user_id in user_states:
                del user_states[user_id]
            return
        
        elif state.get('type') == 'ban_by_id':
            if text.isdigit():
                target_id = int(text)
                c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
                conn.commit()
                send_msg(chat_id, f"✅ تم حظر المستخدم {target_id}")
                send_msg(target_id, "🚫 تم حظرك من البوت")
            else:
                send_msg(chat_id, "❌ آيدي غير صحيح")
            
            if user_id in user_states:
                del user_states[user_id]
            return
        
        elif state.get('type') == 'admin_charge_user':
            if text.isdigit():
                target_id = int(text)
                user_states[user_id] = {'type': 'admin_charge_amount', 'target_id': target_id}
                send_msg(chat_id, f"💰 أرسل المبلغ للمستخدم {target_id}:")
            else:
                send_msg(chat_id, "❌ آيدي غير صحيح")
                if user_id in user_states:
                    del user_states[user_id]
            return
        
        elif state.get('type') == 'admin_charge_amount':
            try:
                amount = float(text)
                target_id = state['target_id']
                
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                
                send_msg(chat_id, f"✅ تم شحن {amount:,.2f} دولار للمستخدم {target_id}")
                send_msg(target_id, f"🎉 تم شحن رصيدك!\nالمبلغ: {amount:,.2f} دولار")
            except:
                send_msg(chat_id, "❌ مبلغ غير صحيح")
            
            if user_id in user_states:
                del user_states[user_id]
            return
    
    main_menu(chat_id, user_id)

def handle_callback(chat_id, user_id, data):
    if data != 'check_sub' and data != 'main':
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
        cat_id = int(data.split('_')[1])
        category_menu(chat_id, cat_id)
    
    elif data.startswith('serv_'):
        service_id = int(data.split('_')[1])
        service_menu(chat_id, user_id, service_id)
    
    elif data == 'charge':
        send_msg(chat_id, f"💰 للشحن راسل @{SUPPORT_USERNAME}\n🆔 آيديك: {user_id}")
    
    elif data == 'balance':
        balance = get_user_balance(user_id)
        send_msg(chat_id, f"💰 رصيدك: {balance:,.2f} دولار")
    
    elif data == 'invite':
        invite_system_menu(chat_id, user_id)
    
    elif data == 'my_orders':
        c.execute("""
            SELECT o.id, s.name, o.quantity, o.total_price, o.status 
            FROM orders o 
            JOIN services s ON o.service_id = s.id 
            WHERE o.user_id = ? 
            ORDER BY o.id DESC LIMIT 10
        """, (user_id,))
        orders = c.fetchall()
        
        if orders:
            text = "📋 <b>طلباتك الأخيرة</b>\n\n"
            for order in orders:
                status_icon = '✅' if order[4] == 'completed' else '⏳' if order[4] == 'processing' else '❌'
                text += f"{status_icon} #{order[0]} - {order[1]}\n"
                text += f"🔢 {order[2]:,} | 💰 {order[3]:,.2f} دولار\n━━━━━━\n"
        else:
            text = "📭 لا توجد طلبات"
        
        send_msg(chat_id, text)
    
    elif data == 'support':
        send_msg(chat_id, f"📞 الدعم: @{SUPPORT_USERNAME}\n🆔 آيديك: {user_id}")
    
    elif data == 'admin':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        
        if user and user[0] == 1:
            admin_panel(chat_id)
        else:
            send_msg(chat_id, "🚫 ليس لديك صلاحية")
    
    elif data == 'stats':
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        banned = c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
        admins = c.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
        balance = c.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
        orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        
        text = f"""📊 <b>إحصائيات البوت</b>

👥 المستخدمين: {users}
👑 المشرفين: {admins}
🚫 المحظورين: {banned}
💰 إجمالي الأرصدة: {balance:,.2f} دولار
📦 عدد الطلبات: {orders}"""
        
        send_msg(chat_id, text)
    
    elif data == 'users_management':
        users_management_menu(chat_id)
    
    elif data == 'ban_management':
        ban_management_menu(chat_id)
    
    elif data == 'ban_by_id':
        user_states[user_id] = {'type': 'ban_by_id'}
        send_msg(chat_id, "🚫 أرسل آيدي المستخدم للحظر:")
    
    elif data.startswith('unban_'):
        target_id = int(data.split('_')[1])
        c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم فك حظر المستخدم {target_id}")
        send_msg(target_id, "✅ تم فك حظرك من البوت")
        ban_management_menu(chat_id)
    
    elif data.startswith('charge_'):
        target_id = int(data.split('_')[1])
        user_states[user_id] = {'type': 'admin_charge_user'}
        send_msg(chat_id, f"💰 أرسل المبلغ للمستخدم {target_id}:")
    
    elif data.startswith('msg_'):
        target_id = int(data.split('_')[1])
        user_states[user_id] = {'type': 'send_user_message', 'target_id': target_id}
        send_msg(chat_id, f"📝 أرسل الرسالة للمستخدم {target_id}:")
    
    elif data == 'send_all':
        user_states[user_id] = {'type': 'send_to_all_amount'}
        send_msg(chat_id, "💰 أرسل المبلغ المراد إرساله للجميع:")
    
    elif data == 'settings_menu':
        maint = get_setting('maintenance')
        reward = get_setting('invite_reward')
        
        text = f"""⚙️ <b>إعدادات البوت</b>

🔧 الصيانة: {'✅ مفعل' if maint == 'true' else '❌ معطل'}
💰 مكافأة الدعوة: {reward} دولار"""
        
        buttons = [[
            {'text': '🔧 تبديل الصيانة', 'callback_data': 'toggle_maint'},
            {'text': '💰 تغيير المكافأة', 'callback_data': 'change_reward'}
        ], [
            {'text': '🔙 رجوع', 'callback_data': 'admin'}
        ]]
        
        send_msg(chat_id, text, buttons)
    
    elif data == 'toggle_maint':
        current = get_setting('maintenance')
        new_val = 'false' if current == 'true' else 'true'
        set_setting('maintenance', new_val)
        send_msg(chat_id, f"✅ تم {'تفعيل' if new_val == 'true' else 'تعطيل'} الصيانة")
    
    elif data == 'change_reward':
        user_states[user_id] = {'type': 'change_reward'}
        send_msg(chat_id, "💰 أرسل المبلغ الجديد:")
    
    elif data == 'invoice_system':
        invoice_system_menu(chat_id)

print("🚀 البوت يعمل بنجاح!")

offset = 0
while True:
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        params = {'offset': offset, 'timeout': 30}
        response = requests.get(url, params=params, timeout=35)
        
        if response.status_code == 200:
            updates = response.json()
            if updates.get('ok') and updates['result']:
                for update in updates['result']:
                    offset = update['update_id'] + 1
                    
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
        
        time.sleep(0.5)
        
    except:
        time.sleep(5)
