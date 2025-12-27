import sqlite3, requests, uuid, random, os, json, logging
from datetime import datetime
from fpdf import FPDF
from flask import Flask, request

# ==================== CONFIGURATION ====================
TOKEN = "8436742877:AAGhCfnC9hbW7Sa4gMTroYissoljCjda9Ow"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== DATABASE ====================
def init_db():
    db_path = os.path.join(os.path.dirname(__file__), 'bot.db')
    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, 
               balance REAL DEFAULT 0, is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, 
               is_restricted INTEGER DEFAULT 0, invite_code TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               daily_reward_date TEXT DEFAULT '', total_invited INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, 
               name TEXT, price_per_k REAL, min_order INTEGER DEFAULT 100, max_order INTEGER DEFAULT 10000,
               is_active INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
               service_id INTEGER, quantity INTEGER, total_price REAL, link TEXT, status TEXT DEFAULT 'pending',
               admin_note TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS forced_channels (id INTEGER PRIMARY KEY AUTOINCREMENT,
               channel_id TEXT, channel_username TEXT, channel_url TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS channel_funding (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
               channel_link TEXT, channel_username TEXT, channel_id TEXT, target_members INTEGER, 
               current_members INTEGER DEFAULT 0, price_per_member REAL, total_cost REAL, 
               subscription_reward REAL, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS channel_subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, 
               funding_id INTEGER, subscriber_id INTEGER, subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    default_settings = [
        ('maintenance', 'false'), ('invite_reward', '0.10'), ('invite_enabled', 'true'),
        ('force_subscribe', 'false'), ('bot_username', BOT_USERNAME), ('daily_reward', '0.05'),
        ('channel_funding_enabled', 'true'), ('min_funding_members', '100'), ('max_funding_members', '5000'),
        ('subscription_reward', '0.01'), ('max_channels_per_user', '3'), ('welcome_message', 'مرحباً بك!')
    ]
    
    for key, value in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    
    c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
              (ADMIN_ID, "المدير", 100000, 1, 'ADMIN'))
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")
    return db_path

DB_PATH = init_db()
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# ==================== HELPER FUNCTIONS ====================
def get_setting(key):
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = c.fetchone()
    return result[0] if result else None

def update_setting(key, value):
    c.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    conn.commit()
    return True

def send_msg(chat_id, text, buttons=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if buttons:
            data['reply_markup'] = json.dumps({'inline_keyboard': buttons})
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

def check_channels(user_id):
    if get_setting('force_subscribe') != 'true':
        return True, None
    
    c.execute("SELECT channel_id, channel_username FROM forced_channels")
    for channel_id, channel_username in c.fetchall():
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
            params = {'chat_id': channel_id, 'user_id': user_id}
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200 and response.json().get('ok'):
                status = response.json()['result']['status']
                if status in ['left', 'kicked']:
                    return False, channel_username
        except:
            continue
    return True, None

def generate_invoice_pdf(order_id, user_id, service_name, quantity, total_price, link):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(200, 10, 'FLASHBOT INVOICE', 0, 1, 'C')
        pdf.ln(5)
        pdf.set_font('Arial', '', 12)
        pdf.cell(50, 10, f'Invoice ID: #{order_id}', 0, 1)
        pdf.cell(50, 10, f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
        pdf.cell(50, 10, f'User ID: {user_id}', 0, 1)
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(200, 10, 'Order Details', 0, 1, 'C')
        pdf.set_font('Arial', '', 12)
        pdf.cell(100, 10, f'• Service: {service_name}', 0, 1)
        pdf.cell(100, 10, f'• Quantity: {quantity}', 0, 1)
        pdf.cell(100, 10, f'• Link: {link}', 0, 1)
        pdf.cell(100, 10, f'• Total: ${total_price:.2f} USD', 0, 1)
        pdf.ln(10)
        pdf.set_font('Arial', 'I', 12)
        pdf.cell(200, 10, random.choice(["شكراً لثقتك بنا!", "نقدر عملك معنا.", "Thank you for ordering!"]), 0, 1, 'C')
        
        filename = f"invoice_{order_id}.pdf"
        pdf.output(filename)
        return filename
    except Exception as e:
        logger.error(f"PDF Error: {e}")
        return None

def send_document(chat_id, document_path, caption=""):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
        with open(document_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'caption': caption}
            requests.post(url, files=files, data=data, timeout=20)
    except Exception as e:
        logger.error(f"Document Error: {e}")

# ==================== MENUS ====================
def main_menu(chat_id, user_id):
    subscribed, channel = check_channels(user_id)
    if not subscribed:
        buttons = [[{'text': '📢 اشترك', 'url': f'https://t.me/{channel}'}, {'text': '✅ تحقق', 'callback_data': 'check_sub'}]]
        send_msg(chat_id, f"📢 اشترك في @{channel} أولاً", buttons)
        return
    
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0] == 1:
        send_msg(chat_id, "🚫 تم حظرك")
        return
    
    c.execute("SELECT username, balance, is_admin FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    username, balance, is_admin = user if user else ("مستخدم", 0, 0)
    
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT daily_reward_date FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    daily_available = result[0] != today if result and result[0] else True
    
    text = f"""👋 أهلاً {username}
🆔 الآيدي: <code>{user_id}</code>
💰 الرصيد: <b>{balance:,.2f} USD</b>"""
    
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
    buttons = [
        [{'text': '📊 إحصائيات', 'callback_data': 'stats'}, {'text': '👥 المستخدمين', 'callback_data': 'users_list'}],
        [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'manage_services'}, {'text': '💳 شحن رصيد', 'callback_data': 'admin_charge'}],
        [{'text': '🚫 إدارة الحظر', 'callback_data': 'ban_manage'}, {'text': '👑 إدارة المشرفين', 'callback_data': 'admin_manage'}],
        [{'text': '📢 القنوات الإجبارية', 'callback_data': 'channels_manage'}, {'text': '📺 إدارة التمويل', 'callback_data': 'funding_manage'}],
        [{'text': '🎁 إرسال للجميع', 'callback_data': 'send_all'}, {'text': '⚙️ الإعدادات', 'callback_data': 'settings_menu'}],
        [{'text': '🔙 رئيسية', 'callback_data': 'main'}]
    ]
    send_msg(chat_id, "👑 لوحة التحكم", buttons)

# ==================== MESSAGE HANDLING ====================
user_states = {}

def handle_message(chat_id, user_id, text, username=""):
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_msg(chat_id, get_setting('maintenance_msg') or 'البوت تحت الصيانة')
        return
    
    subscribed, channel = check_channels(user_id)
    if not subscribed:
        buttons = [[{'text': '📢 اشترك', 'url': f'https://t.me/{channel}'}, {'text': '✅ تحقق', 'callback_data': 'check_sub'}]]
        send_msg(chat_id, f"📢 اشترك في @{channel} أولاً", buttons)
        return
    
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0] == 1:
        send_msg(chat_id, "🚫 تم حظرك")
        return
    
    if username:
        c.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        conn.commit()
    
    if user_id in user_states:
        state = user_states[user_id]
        handle_user_state(chat_id, user_id, text, state)
        return
    
    if text == '/start':
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not c.fetchone():
            invite_code = str(uuid.uuid4())[:8]
            c.execute("INSERT INTO users (user_id, username, invite_code) VALUES (?, ?, ?)", (user_id, username, invite_code))
            conn.commit()
        
        if ' ' in text:
            parts = text.split()
            if len(parts) > 1:
                invite_data = parts[1]
                if '_' in invite_data:
                    try:
                        invite_code, inviter_id, _ = invite_data.split('_')
                        inviter_id = int(inviter_id)
                        if inviter_id != user_id and get_setting('invite_enabled') == 'true':
                            c.execute("SELECT user_id FROM users WHERE invite_code = ?", (invite_code,))
                            inviter = c.fetchone()
                            if inviter and inviter[0] == inviter_id:
                                reward = float(get_setting('invite_reward'))
                                c.execute("UPDATE users SET balance = balance + ?, total_invited = total_invited + 1 WHERE user_id = ?", (reward, inviter_id))
                                conn.commit()
                                send_msg(inviter_id, f"🎉 مكافأة دعوة {reward} USD")
                    except:
                        pass
        
        main_menu(chat_id, user_id)
    
    elif text == '/admin':
        if user_id == ADMIN_ID:
            admin_panel(chat_id)
        else:
            c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
            result = c.fetchone()
            if result and result[0] == 1:
                admin_panel(chat_id)
            else:
                send_msg(chat_id, "🚫 ليس لديك صلاحية")
    
    else:
        main_menu(chat_id, user_id)

def handle_user_state(chat_id, user_id, text, state):
    state_type = state['type']
    
    if state_type == 'order_qty':
        service_id = state['service_id']
        c.execute("SELECT name, price_per_k, min_order, max_order FROM services WHERE id = ?", (service_id,))
        serv = c.fetchone()
        if serv:
            name, price, min_q, max_q = serv
            try:
                quantity = int(text)
                if min_q <= quantity <= max_q:
                    total_price = (price / 1000) * quantity
                    balance = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]
                    if balance >= total_price:
                        user_states[user_id] = {'type': 'order_link', 'service_id': service_id, 'quantity': quantity, 'total': total_price}
                        send_msg(chat_id, f"✍️ أرسل الرابط لـ {name}:")
                    else:
                        send_msg(chat_id, f"❌ رصيد غير كافي")
                else:
                    send_msg(chat_id, f"❌ الحدود {min_q}-{max_q}")
            except:
                send_msg(chat_id, "❌ أدخل رقم صحيح")
        del user_states[user_id]
    
    elif state_type == 'order_link':
        link = text
        service_id = state['service_id']
        quantity = state['quantity']
        total = state['total']
        
        balance = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]
        if balance >= total:
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total, user_id))
            c.execute("INSERT INTO orders (user_id, service_id, quantity, total_price, link) VALUES (?, ?, ?, ?, ?)", 
                     (user_id, service_id, quantity, total, link))
            order_id = c.lastrowid
            conn.commit()
            
            send_msg(chat_id, f"✅ تم إرسال الطلب #{order_id}")
            c.execute("SELECT name FROM services WHERE id = ?", (service_id,))
            service_name = c.fetchone()[0]
            
            pdf_file = generate_invoice_pdf(order_id, user_id, service_name, quantity, total, link)
            if pdf_file:
                send_document(chat_id, pdf_file, f"📄 فاتورة الطلب #{order_id}")
                try:
                    os.remove(pdf_file)
                except:
                    pass
            
            admin_text = f"""🆕 طلب جديد #{order_id}
👤 {user_id}
📦 {service_name}
💰 {total:.2f} USD"""
            admin_buttons = [[{'text': '✅ قبول', 'callback_data': f'approve_{order_id}'}, {'text': '❌ رفض', 'callback_data': f'reject_{order_id}'}]]
            send_msg(ADMIN_ID, admin_text, admin_buttons)
        else:
            send_msg(chat_id, "❌ رصيد غير كافي")
        del user_states[user_id]
    
    elif state_type == 'new_funding_channel':
        channel_link = text.strip()
        user_states[user_id] = {'type': 'new_funding_target', 'channel_link': channel_link}
        send_msg(chat_id, f"🔢 أرسل عدد الأعضاء المطلوب (100-5000):")
    
    elif state_type == 'new_funding_target':
        try:
            target = int(text)
            if 100 <= target <= 5000:
                channel_link = state['channel_link']
                reward = float(get_setting('subscription_reward') or 0.01)
                price_per_member = reward * 2
                total_cost = target * price_per_member
                user_states[user_id] = {'type': 'confirm_funding', 'channel_link': channel_link, 'target': target, 'total_cost': total_cost, 'reward': reward}
                
                balance = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]
                text_msg = f"""📺 تأكيد الحملة
🔗 {channel_link}
👥 الأعضاء: {target}
💰 الإجمالي: {total_cost:.2f} USD
💳 رصيدك: {balance:.2f} USD"""
                buttons = [[{'text': '✅ تأكيد', 'callback_data': 'confirm_funding'}, {'text': '❌ إلغاء', 'callback_data': 'cancel_funding'}]]
                send_msg(chat_id, text_msg, buttons)
            else:
                send_msg(chat_id, "❌ الحدود 100-5000")
                del user_states[user_id]
        except:
            send_msg(chat_id, "❌ أدخل رقم صحيح")
            del user_states[user_id]
    
    elif state_type == 'add_service_name':
        if text:
            user_states[user_id] = {'type': 'add_service_price', 'cat_id': state['cat_id'], 'name': text}
            send_msg(chat_id, "💰 أرسل السعر لكل 1000:")
        else:
            send_msg(chat_id, "❌ الاسم فارغ")
            del user_states[user_id]
    
    elif state_type == 'add_service_price':
        try:
            price = float(text)
            user_states[user_id] = {'type': 'add_service_min', 'cat_id': state['cat_id'], 'name': state['name'], 'price': price}
            send_msg(chat_id, "🔢 أرسل الحد الأدنى:")
        except:
            send_msg(chat_id, "❌ سعر غير صحيح")
            del user_states[user_id]
    
    elif state_type == 'add_service_min':
        try:
            min_order = int(text)
            user_states[user_id] = {'type': 'add_service_max', 'cat_id': state['cat_id'], 'name': state['name'], 'price': state['price'], 'min': min_order}
            send_msg(chat_id, "🔢 أرسل الحد الأقصى:")
        except:
            send_msg(chat_id, "❌ رقم غير صحيح")
            del user_states[user_id]
    
    elif state_type == 'add_service_max':
        try:
            max_order = int(text)
            c.execute("INSERT INTO services (category_id, name, price_per_k, min_order, max_order) VALUES (?, ?, ?, ?, ?)", 
                     (state['cat_id'], state['name'], state['price'], state['min'], max_order))
            conn.commit()
            send_msg(chat_id, f"✅ تم إضافة: {state['name']}")
            del user_states[user_id]
        except:
            send_msg(chat_id, "❌ رقم غير صحيح")
            del user_states[user_id]
    
    elif state_type == 'reject_reason':
        order_id = state['order_id']
        reason = text
        c.execute("UPDATE orders SET status = 'rejected', admin_note = ? WHERE id = ?", (reason, order_id))
        c.execute("SELECT user_id, total_price FROM orders WHERE id = ?", (order_id,))
        order = c.fetchone()
        if order:
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (order[1], order[0]))
            send_msg(order[0], f"❌ تم رفض طلبك #{order_id}")
        conn.commit()
        send_msg(chat_id, f"✅ تم رفض الطلب #{order_id}")
        del user_states[user_id]
    
    elif state_type == 'admin_charge_user':
        if text.isdigit():
            target_id = int(text)
            user_states[user_id] = {'type': 'admin_charge_amount', 'target_id': target_id}
            send_msg(chat_id, f"💰 أرسل المبلغ للمستخدم {target_id}:")
        else:
            send_msg(chat_id, "❌ آيدي غير صحيح")
            del user_states[user_id]
    
    elif state_type == 'admin_charge_amount':
        try:
            amount = float(text)
            target_id = state['target_id']
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
            conn.commit()
            send_msg(chat_id, f"✅ تم شحن {amount} USD للمستخدم {target_id}")
            send_msg(target_id, f"🎉 تم شحن رصيدك\n💰 {amount} USD")
            del user_states[user_id]
        except:
            send_msg(chat_id, "❌ مبلغ غير صحيح")
            del user_states[user_id]
    
    elif state_type == 'send_to_all_amount':
        try:
            amount = float(text)
            user_states[user_id] = {'type': 'send_to_all_msg', 'amount': amount}
            send_msg(chat_id, "📝 أرسل الرسالة:")
        except:
            send_msg(chat_id, "❌ مبلغ غير صحيح")
            del user_states[user_id]
    
    elif state_type == 'send_to_all_msg':
        message = text
        amount = state['amount']
        c.execute("SELECT user_id FROM users WHERE is_banned = 0")
        users = c.fetchall()
        count = 0
        for u in users:
            uid = u[0]
            if uid != ADMIN_ID:
                if amount > 0:
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, uid))
                send_msg(uid, f"🎁 {message}" + (f"\n💰 {amount} USD" if amount > 0 else ""))
                count += 1
        conn.commit()
        send_msg(chat_id, f"✅ تم الإرسال لـ {count} مستخدم")
        del user_states[user_id]
    
    elif state_type == 'add_channel_id':
        channel_id = text.strip()
        user_states[user_id] = {'type': 'add_channel_username', 'channel_id': channel_id}
        send_msg(chat_id, "👤 أرسل يوزر القناة (بدون @):")
    
    elif state_type == 'add_channel_username':
        channel_username = text.strip().replace('@', '')
        user_states[user_id] = {'type': 'add_channel_url', 'channel_id': state['channel_id'], 'channel_username': channel_username}
        send_msg(chat_id, "🔗 أرسل رابط القناة:")
    
    elif state_type == 'add_channel_url':
        channel_url = text.strip()
        channel_id = state['channel_id']
        channel_username = state['channel_username']
        c.execute("INSERT INTO forced_channels (channel_id, channel_username, channel_url) VALUES (?, ?, ?)",
                 (channel_id, channel_username, channel_url))
        conn.commit()
        send_msg(chat_id, f"✅ تم إضافة القناة: @{channel_username}")
        del user_states[user_id]
    
    elif state_type == 'view_user':
        if text.isdigit():
            target_id = int(text)
            c.execute("SELECT username, balance, is_admin, is_banned, is_restricted, total_invited, created_at, invite_code FROM users WHERE user_id = ?", (target_id,))
            user_data = c.fetchone()
            if user_data:
                username, balance, is_admin, is_banned, is_restricted, total_invited, created_at, invite_code = user_data
                
                text_info = f"""👤 <b>معلومات المستخدم</b>

🆔 الآيدي: <code>{target_id}</code>
👤 اليوزر: @{username if username else 'بدون'}
💰 الرصيد: {balance:.2f} USD
👥 الدعوات: {total_invited}
📅 التسجيل: {created_at[:10]}
🔑 كود الدعوة: {invite_code}

📊 الحالة:
• 👑 مشرف: {'✅' if is_admin == 1 else '❌'}
• 🚫 محظور: {'✅' if is_banned == 1 else '❌'}
• ⚠️ مقيد: {'✅' if is_restricted == 1 else '❌'}"""
                
                buttons = [
                    [{'text': '🚫 حظر', 'callback_data': f'ban_{target_id}'}, {'text': '✅ فك حظر', 'callback_data': f'unban_{target_id}'}],
                    [{'text': '⚠️ تقييد', 'callback_data': f'restrict_{target_id}'}, {'text': '🔓 فك تقييد', 'callback_data': f'unrestrict_{target_id}'}],
                    [{'text': '👑 رفع مشرف', 'callback_data': f'promote_{target_id}'}, {'text': '👤 خفض مشرف', 'callback_data': f'demote_{target_id}'}],
                    [{'text': '💳 شحن رصيد', 'callback_data': f'chargeuser_{target_id}'}],
                    [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
                ]
                
                send_msg(chat_id, text_info, buttons)
            else:
                send_msg(chat_id, "❌ المستخدم غير موجود")
        else:
            send_msg(chat_id, "❌ آيدي غير صحيح")
        del user_states[user_id]
    
    else:
        send_msg(chat_id, "⚠️ حالة غير معروفة")
        del user_states[user_id]

# ==================== CALLBACK HANDLING ====================
def handle_callback(chat_id, user_id, data):
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
            send_msg(chat_id, "✅ أنت مشترك")
            main_menu(chat_id, user_id)
        else:
            buttons = [[{'text': '📢 اشترك', 'url': f'https://t.me/{channel}'}, {'text': '✅ تحقق', 'callback_data': 'check_sub'}]]
            send_msg(chat_id, f"❌ لم تشترك بعد في @{channel}", buttons)
    
    elif data == 'services':
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
    
    elif data.startswith('cat_'):
        cat_id = data.split('_')[1]
        c.execute("SELECT id, name, price_per_k FROM services WHERE category_id = ? AND is_active = 1", (cat_id,))
        services = c.fetchall()
        if not services:
            send_msg(chat_id, "📭 لا توجد خدمات")
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
            send_msg(chat_id, f"✍️ أرسل الكمية:")
    
    elif data == 'charge':
        send_msg(chat_id, f"💰 للشحن: @{SUPPORT_USERNAME}\n🆔 {user_id}")
    
    elif data == 'balance':
        balance = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]
        send_msg(chat_id, f"💰 رصيدك: {balance:.2f} USD")
    
    elif data == 'invite':
        code = c.execute("SELECT invite_code FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]
        bot_user = get_setting('bot_username') or BOT_USERNAME
        link = f"https://t.me/{bot_user}?start={code}_{user_id}_{random.randint(1000,9999)}"
        reward = get_setting('invite_reward')
        text = f"""👥 دعوة أصدقاء
💰 المكافأة: {reward} USD
🔗 {link}"""
        buttons = [[{'text': '📤 مشاركة', 'url': f'tg://msg_url?url={link}'}, {'text': '🔙 رجوع', 'callback_data': 'main'}]]
        send_msg(chat_id, text, buttons)
    
    elif data == 'daily_reward':
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT daily_reward_date FROM users WHERE user_id = ?", (user_id,))
        last = c.fetchone()[0]
        if last == today:
            send_msg(chat_id, "⏳ لقد أخذت هدية اليوم")
        else:
            reward = float(get_setting('daily_reward'))
            c.execute("UPDATE users SET balance = balance + ?, daily_reward_date = ? WHERE user_id = ?", (reward, today, user_id))
            conn.commit()
            send_msg(chat_id, f"🎉 هدية اليوم: {reward} USD")
    
    elif data == 'my_orders':
        c.execute("SELECT o.id, s.name, o.quantity, o.total_price, o.status FROM orders o JOIN services s ON o.service_id = s.id WHERE o.user_id = ? ORDER BY o.id DESC LIMIT 5", (user_id,))
        orders = c.fetchall()
        if orders:
            text = "📋 طلباتك\n\n"
            for oid, name, qty, price, status in orders:
                status_icon = '✅' if status == 'completed' else '⏳' if status == 'processing' else '❌'
                text += f"{status_icon} #{oid} - {name}\n🔢 {qty} | 💰 {price:.2f} USD\n"
        else:
            text = "📭 لا توجد طلبات"
        send_msg(chat_id, text)
    
    elif data == 'channel_funding':
        if get_setting('channel_funding_enabled') != 'true':
            send_msg(chat_id, "⏸️ الخدمة معطلة")
            return
        c.execute("SELECT COUNT(*), SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) FROM channel_funding WHERE user_id = ?", (user_id,))
        stats = c.fetchone() or (0, 0)
        reward = float(get_setting('subscription_reward'))
        text = f"""📺 تمويل القنوات
💰 مكافأة المشترك: {reward} USD
📊 حملاتك: {stats[0]} (نشطة: {stats[1]})"""
        buttons = [
            [{'text': '➕ حملة جديدة', 'callback_data': 'new_funding'}],
            [{'text': '📋 حملاتي', 'callback_data': 'my_fundings'}],
            [{'text': '🔙 رجوع', 'callback_data': 'main'}]
        ]
        send_msg(chat_id, text, buttons)
    
    elif data == 'subscribe_channels':
        c.execute("""
            SELECT cf.id, cf.channel_username, cf.target_members, cf.current_members, cf.subscription_reward
            FROM channel_funding cf
            WHERE cf.status = 'active' AND cf.current_members < cf.target_members
            AND NOT EXISTS (SELECT 1 FROM channel_subscriptions cs WHERE cs.funding_id = cf.id AND cs.subscriber_id = ?)
            ORDER BY cf.current_members ASC LIMIT 10
        """, (user_id,))
        channels = c.fetchall()
        if not channels:
            text = "📭 لا توجد قنوات متاحة"
            buttons = [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]
        else:
            text = "📢 القنوات المتاحة\n\n"
            for fid, username, target, current, reward in channels:
                progress = (current / target) * 100
                text += f"""📺 @{username}
👥 {current}/{target} ({progress:.1f}%)
💰 {reward} USD
━━━━━━━━━━
"""
            text += "\n📌 اختر قناة:"
            buttons = []
            for fid, username, _, _, _ in channels:
                buttons.append([{'text': f'📺 @{username}', 'callback_data': f'subscribe_{fid}'}])
            buttons.append([{'text': '🔙 رجوع', 'callback_data': 'main'}])
        send_msg(chat_id, text, buttons)
    
    elif data.startswith('subscribe_'):
        funding_id = int(data.split('_')[1])
        c.execute("SELECT 1 FROM channel_subscriptions WHERE funding_id = ? AND subscriber_id = ?", (funding_id, user_id))
        if c.fetchone():
            send_msg(chat_id, "⚠️ أنت مشترك مسبقاً")
            return
        c.execute("SELECT channel_link, channel_username, subscription_reward, channel_id FROM channel_funding WHERE id = ? AND status = 'active'", (funding_id,))
        channel = c.fetchone()
        if not channel:
            send_msg(chat_id, "❌ القناة غير متاحة")
            return
        channel_link, username, reward, channel_id = channel
        buttons = [
            [{'text': '📢 انضم للقناة', 'url': channel_link}],
            [{'text': '✅ تحقق', 'callback_data': f'verify_sub_{funding_id}'}],
            [{'text': '🔙 رجوع', 'callback_data': 'subscribe_channels'}]
        ]
        send_msg(chat_id, f"📺 @{username}\n💰 المكافأة: {reward} USD\n\nانضم للقناة ثم اضغط تحقق", buttons)
    
    elif data.startswith('verify_sub_'):
        funding_id = int(data.split('_')[2])
        c.execute("SELECT channel_id, channel_username, subscription_reward FROM channel_funding WHERE id = ?", (funding_id,))
        channel = c.fetchone()
        if not channel:
            send_msg(chat_id, "❌ القناة غير موجودة")
            return
        channel_id, username, reward = channel
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
            params = {'chat_id': channel_id, 'user_id': user_id}
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data_resp = response.json()
                if data_resp.get('ok'):
                    status = data_resp['result']['status']
                    if status not in ['left', 'kicked']:
                        c.execute("INSERT INTO channel_subscriptions (funding_id, subscriber_id) VALUES (?, ?)", (funding_id, user_id))
                        c.execute("UPDATE channel_funding SET current_members = current_members + 1 WHERE id = ?", (funding_id,))
                        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
                        c.execute("SELECT target_members, current_members, user_id FROM channel_funding WHERE id = ?", (funding_id,))
                        target, current, owner_id = c.fetchone()
                        if current >= target:
                            c.execute("UPDATE channel_funding SET status = 'completed' WHERE id = ?", (funding_id,))
                            send_msg(owner_id, f"✅ اكتملت حملة @{username}")
                        conn.commit()
                        send_msg(chat_id, f"✅ تم الاشتراك في @{username}\n💰 حصلت على {reward} USD")
                    else:
                        send_msg(chat_id, f"❌ لم تنضم بعد إلى @{username}")
        except Exception as e:
            logger.error(f"Subscription error: {e}")
            send_msg(chat_id, "❌ حدث خطأ في التحقق")
    
    elif data == 'new_funding':
        c.execute("SELECT COUNT(*) FROM channel_funding WHERE user_id = ? AND status = 'active'", (user_id,))
        active_count = c.fetchone()[0]
        max_channels = int(get_setting('max_channels_per_user'))
        if active_count >= max_channels:
            send_msg(chat_id, f"❌ وصلت للحد الأقصى ({max_channels})")
            return
        user_states[user_id] = {'type': 'new_funding_channel'}
        send_msg(chat_id, "🔗 أرسل رابط قناتك:")
    
    elif data == 'my_fundings':
        c.execute("SELECT id, channel_username, target_members, current_members, status FROM channel_funding WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (user_id,))
        fundings = c.fetchall()
        if not fundings:
            text = "📭 لا توجد حملات"
        else:
            text = "📋 حملاتك\n\n"
            for fid, username, target, current, status in fundings:
                status_icons = {'active': '🟢', 'completed': '✅', 'pending': '🟡'}
                icon = status_icons.get(status, '📌')
                progress = (current / target) * 100 if target > 0 else 0
                text += f"""{icon} @{username}
👥 {current}/{target} ({progress:.1f}%)
━━━━━━━━━━
"""
        send_msg(chat_id, text)
    
    elif data == 'confirm_funding':
        if user_id in user_states and user_states[user_id]['type'] == 'confirm_funding':
            state = user_states[user_id]
            channel_link = state['channel_link']
            target = state['target']
            total_cost = state['total_cost']
            reward = state['reward']
            
            channel_username = ""
            if 't.me/' in channel_link:
                channel_username = channel_link.split('t.me/')[-1].replace('@', '')
            
            balance = c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]
            if balance < total_cost:
                send_msg(chat_id, "❌ رصيد غير كافي")
                del user_states[user_id]
                return
            
            channel_id = ""
            try:
                if channel_username:
                    url = f"https://api.telegram.org/bot{TOKEN}/getChat"
                    params = {'chat_id': f'@{channel_username}'}
                    response = requests.get(url, params=params, timeout=5)
                    if response.status_code == 200:
                        data_resp = response.json()
                        if data_resp.get('ok'):
                            channel_id = str(data_resp['result']['id'])
            except:
                pass
            
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, user_id))
            c.execute("""INSERT INTO channel_funding (user_id, channel_link, channel_username, channel_id, 
                     target_members, price_per_member, total_cost, subscription_reward, status) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                     (user_id, channel_link, channel_username, channel_id, target, reward * 2, total_cost, reward))
            conn.commit()
            send_msg(chat_id, f"""✅ تم إنشاء الحملة
📺 @{channel_username}
👥 الهدف: {target} عضو
💰 التكلفة: {total_cost:.2f} USD""")
            del user_states[user_id]
    
    elif data == 'cancel_funding':
        if user_id in user_states:
            del user_states[user_id]
        send_msg(chat_id, "❌ تم الإلغاء")
    
    elif data == 'support':
        send_msg(chat_id, f"📞 الدعم: @{SUPPORT_USERNAME}\n🆔 {user_id}")
    
    elif data == 'admin':
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone()[0] == 1 or user_id == ADMIN_ID:
            admin_panel(chat_id)
        else:
            send_msg(chat_id, "🚫 ليس لديك صلاحية")
    
    elif data == 'stats':
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        banned = c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
        balance = c.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
        orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        funding = c.execute("SELECT COUNT(*) FROM channel_funding").fetchone()[0]
        text = f"""📊 إحصائيات
👥 المستخدمين: {users}
🚫 المحظورين: {banned}
💰 إجمالي الأرصدة: {balance:.2f} USD
📦 الطلبات: {orders}
📺 حملات التمويل: {funding}"""
        send_msg(chat_id, text)
    
    elif data == 'funding_manage':
        c.execute("SELECT COUNT(*) FROM channel_funding WHERE status = 'active'")
        active = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM channel_funding WHERE status = 'pending'")
        pending = c.fetchone()[0]
        text = f"""📺 إدارة التمويل
🟢 نشطة: {active}
🟡 معلقة: {pending}"""
        buttons = [
            [{'text': '📋 جميع الحملات', 'callback_data': 'view_all_funding_admin'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
        ]
        send_msg(chat_id, text, buttons)
    
    elif data == 'view_all_funding_admin':
        c.execute("SELECT cf.id, u.username, cf.channel_username, cf.target_members, cf.current_members, cf.status, cf.created_at FROM channel_funding cf LEFT JOIN users u ON cf.user_id = u.user_id ORDER BY cf.created_at DESC LIMIT 15")
        all_funding = c.fetchall()
        if not all_funding:
            text = "📭 لا توجد حملات"
        else:
            text = "📊 جميع الحملات\n\n"
            for fid, owner, channel, target, current, status, created in all_funding:
                status_icons = {'active': '🟢', 'completed': '✅', 'pending': '🟡'}
                icon = status_icons.get(status, '📌')
                text += f"{icon} #{fid} - @{channel}\n👤 {owner or 'بدون'}\n👥 {current}/{target}\n📅 {created[:10]}\n"
        send_msg(chat_id, text)
    
    elif data == 'users_list':
        user_states[user_id] = {'type': 'view_user'}
        send_msg(chat_id, "🔍 أرسل آيدي المستخدم:")
    
    elif data == 'manage_services':
        buttons = [
            [{'text': '📁 إضافة قسم', 'callback_data': 'add_category'}],
            [{'text': '➕ إضافة خدمة', 'callback_data': 'add_service'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
        ]
        send_msg(chat_id, "🛍️ إدارة الخدمات", buttons)
    
    elif data == 'add_category':
        user_states[user_id] = {'type': 'add_category'}
        send_msg(chat_id, "➕ أرسل اسم القسم:")
    
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
            [{'text': '🚫 حظر مستخدم', 'callback_data': 'ban_user'}],
            [{'text': '✅ فك حظر', 'callback_data': 'unban_user'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
        ]
        send_msg(chat_id, "🚫 إدارة الحظر", buttons)
    
    elif data == 'ban_user':
        user_states[user_id] = {'type': 'ban_user'}
        send_msg(chat_id, "🚫 أرسل آيدي المستخدم للحظر:")
    
    elif data == 'unban_user':
        user_states[user_id] = {'type': 'unban_user'}
        send_msg(chat_id, "✅ أرسل آيدي المستخدم لفك الحظر:")
    
    elif data == 'admin_manage':
        buttons = [
            [{'text': '👑 رفع مشرف', 'callback_data': 'promote_admin'}],
            [{'text': '👤 خفض مشرف', 'callback_data': 'demote_admin'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
        ]
        send_msg(chat_id, "👑 إدارة المشرفين", buttons)
    
    elif data == 'promote_admin':
        user_states[user_id] = {'type': 'promote_admin'}
        send_msg(chat_id, "👑 أرسل آيدي المستخدم للرفع:")
    
    elif data == 'demote_admin':
        user_states[user_id] = {'type': 'demote_admin'}
        send_msg(chat_id, "👤 أرسل آيدي المشرف للخفض:")
    
    elif data == 'channels_manage':
        buttons = [
            [{'text': '➕ إضافة قناة', 'callback_data': 'add_channel'}],
            [{'text': '✅ تفعيل', 'callback_data': 'enable_force'}],
            [{'text': '❌ تعطيل', 'callback_data': 'disable_force'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
        ]
        send_msg(chat_id, "📢 القنوات الإجبارية", buttons)
    
    elif data == 'add_channel':
        user_states[user_id] = {'type': 'add_channel_id'}
        send_msg(chat_id, "🆔 أرسل آيدي القناة:")
    
    elif data == 'enable_force':
        update_setting('force_subscribe', 'true')
        send_msg(chat_id, "✅ تم تفعيل الاشتراك الإجباري")
    
    elif data == 'disable_force':
        update_setting('force_subscribe', 'false')
        send_msg(chat_id, "❌ تم تعطيل الاشتراك الإجباري")
    
    elif data == 'send_all':
        user_states[user_id] = {'type': 'send_to_all_amount'}
        send_msg(chat_id, "💰 أرسل المبلغ للجميع:")
    
    elif data == 'settings_menu':
        maint = get_setting('maintenance')
        invite_r = get_setting('invite_reward')
        daily_r = get_setting('daily_reward')
        text = f"""⚙️ الإعدادات
🔧 الصيانة: {'✅ مفعل' if maint == 'true' else '❌ معطل'}
💰 مكافأة الدعوة: {invite_r} USD
🎁 هدية اليوم: {daily_r} USD"""
        buttons = [
            [{'text': '🔧 تبديل الصيانة', 'callback_data': 'toggle_maint'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
        ]
        send_msg(chat_id, text, buttons)
    
    elif data == 'toggle_maint':
        current = get_setting('maintenance')
        new = 'false' if current == 'true' else 'true'
        update_setting('maintenance', new)
        send_msg(chat_id, f"✅ تم {'تعطيل' if new == 'false' else 'تفعيل'} الصيانة")
    
    elif data.startswith('approve_'):
        order_id = int(data.split('_')[1])
        c.execute("UPDATE orders SET status = 'processing' WHERE id = ?", (order_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم قبول الطلب #{order_id}")
        c.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
        target = c.fetchone()[0]
        send_msg(target, f"✅ تم قبول طلبك #{order_id}")
    
    elif data.startswith('reject_'):
        order_id = int(data.split('_')[1])
        user_states[user_id] = {'type': 'reject_reason', 'order_id': order_id}
        send_msg(chat_id, f"📝 أرسل سبب رفض الطلب #{order_id}:")
    
    elif data.startswith('ban_'):
        target_id = int(data.split('_')[1])
        if target_id == ADMIN_ID:
            send_msg(chat_id, "❌ لا يمكن حظر المدير")
        else:
            c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
            conn.commit()
            send_msg(chat_id, f"✅ تم حظر المستخدم {target_id}")
            send_msg(target_id, "🚫 تم حظرك")
    
    elif data.startswith('unban_'):
        target_id = int(data.split('_')[1])
        c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم فك حظر المستخدم {target_id}")
        send_msg(target_id, "✅ تم فك حظرك")
    
    elif data.startswith('restrict_'):
        target_id = int(data.split('_')[1])
        if target_id == ADMIN_ID:
            send_msg(chat_id, "❌ لا يمكن تقييد المدير")
        else:
            c.execute("UPDATE users SET is_restricted = 1 WHERE user_id = ?", (target_id,))
            conn.commit()
            send_msg(chat_id, f"✅ تم تقييد المستخدم {target_id}")
            send_msg(target_id, "⚠️ تم تقييد حسابك")
    
    elif data.startswith('unrestrict_'):
        target_id = int(data.split('_')[1])
        c.execute("UPDATE users SET is_restricted = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم فك تقييد المستخدم {target_id}")
        send_msg(target_id, "✅ تم فك تقييد حسابك")
    
    elif data.startswith('promote_'):
        target_id = int(data.split('_')[1])
        if target_id == ADMIN_ID:
            send_msg(chat_id, "❌ هذا المستخدم هو المدير")
        else:
            c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (target_id,))
            conn.commit()
            send_msg(chat_id, f"✅ تم رفع المستخدم {target_id}")
            send_msg(target_id, "👑 تمت ترقيتك إلى مشرف")
    
    elif data.startswith('demote_'):
        target_id = int(data.split('_')[1])
        if target_id == ADMIN_ID:
            send_msg(chat_id, "❌ لا يمكن خفض المدير")
        else:
            c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (target_id,))
            conn.commit()
            send_msg(chat_id, f"✅ تم خفض المشرف {target_id}")
            send_msg(target_id, "👤 تم خفض صلاحياتك")
    
    elif data.startswith('chargeuser_'):
        target_id = int(data.split('_')[1])
        user_states[user_id] = {'type': 'admin_charge_amount', 'target_id': target_id}
        send_msg(chat_id, f"💰 أرسل المبلغ للشحن للمستخدم {target_id}:")
    
    elif data == 'admin_panel':
        admin_panel(chat_id)
    
    else:
        send_msg(chat_id, "⚠️ أمر غير معروف")

# ==================== FLASK APP ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 البوت يعمل بنجاح!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = request.json
    if update:
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
                logger.error(f"Callback error: {e}")
    return 'OK'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
