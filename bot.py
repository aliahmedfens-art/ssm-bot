import sqlite3
import requests
import time
import json
import uuid
from datetime import datetime

# إعدادات البوت
TOKEN = "8436742877:AAHmlmOKY2iQCGoOt004ruq09tZGderDGMQ"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"

# تهيئة قاعدة البيانات
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول
def init_db():
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, 
                 balance REAL DEFAULT 0, is_admin INTEGER DEFAULT 0, 
                 is_banned INTEGER DEFAULT 0, is_restricted INTEGER DEFAULT 0,
                 invited_by INTEGER DEFAULT 0, invite_code TEXT UNIQUE,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS categories 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT UNIQUE, position INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS services 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 category_id INTEGER, name TEXT, 
                 price_per_k REAL, min_order INTEGER DEFAULT 100, 
                 max_order INTEGER DEFAULT 10000,
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
    
    c.execute('''CREATE TABLE IF NOT EXISTS forced_channels 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 channel_id TEXT, channel_username TEXT,
                 channel_url TEXT, position INTEGER DEFAULT 0)''')
    
    # إعدادات افتراضية
    default_settings = [
        ('maintenance', 'false'),
        ('maintenance_msg', 'البوت تحت الصيانة حالياً ⚠️'),
        ('invite_reward', '0.10'),
        ('invite_enabled', 'true'),
        ('force_subscribe', 'false')
    ]
    
    for key, value in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    
    # إضافة المدير
    c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
              (ADMIN_ID, "المدير", 100000, 1, 'ADMIN'))
    
    conn.commit()

init_db()

# وظائف مساعدة
def get_setting(key):
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = c.fetchone()
    return result[0] if result else None

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
            payload['reply_markup'] = json.dumps(reply_markup)
        
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except:
        return False

def answer_callback(callback_id):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
        requests.post(url, json={'callback_query_id': callback_id}, timeout=3)
    except:
        pass

# التحقق من اشتراك القنوات الإجبارية
def check_channels_subscription(user_id):
    c.execute("SELECT value FROM settings WHERE key = 'force_subscribe'")
    if c.fetchone()[0] != 'true':
        return True
    
    c.execute("SELECT channel_id, channel_username FROM forced_channels ORDER BY position")
    channels = c.fetchall()
    
    for channel_id, channel_username in channels:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
            params = {
                'chat_id': channel_id,
                'user_id': user_id
            }
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

# القوائم
def main_menu(chat_id, user_id):
    # التحقق من القيود
    c.execute("SELECT is_restricted FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if user and user[0] == 1:
        send_message(chat_id, "⛔ حسابك مقيد، لا يمكنك استخدام الخدمات")
        return
    
    # التحقق من الاشتراك الإجباري
    subscribed, channel = check_channels_subscription(user_id)
    if not subscribed:
        keyboard = {
            'inline_keyboard': [[
                {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
                {'text': '✅ تحقق من الاشتراك', 'callback_data': 'check_subscription'}
            ]]
        }
        send_message(chat_id, f"📢 يجب الاشتراك في القناة @{channel} أولاً لاستخدام البوت", keyboard)
        return
    
    c.execute("SELECT username, balance, is_admin FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        # إنشاء مستخدم جديد
        invite_code = str(uuid.uuid4())[:8]
        c.execute("INSERT INTO users (user_id, invite_code) VALUES (?, ?)", (user_id, invite_code))
        conn.commit()
        user = (None, 0, 0)
    
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
            [{'text': '👥 دعوة أصدقاء', 'callback_data': 'invite'}],
            [{'text': '📋 طلباتي', 'callback_data': 'my_orders'}],
            [{'text': '📞 دعم', 'callback_data': 'support'}]
        ]
    }
    
    if is_admin == 1:
        keyboard['inline_keyboard'].append([{'text': '👑 لوحة التحكم', 'callback_data': 'admin_panel'}])
    
    send_message(chat_id, text, keyboard)

def admin_panel(chat_id):
    keyboard = {
        'inline_keyboard': [
            [{'text': '📊 الإحصائيات', 'callback_data': 'stats'}],
            [{'text': '👥 إدارة المستخدمين', 'callback_data': 'manage_users'}],
            [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'manage_services'}],
            [{'text': '💳 شحن/إرسال رصيد', 'callback_data': 'admin_balance'}],
            [{'text': '📋 إدارة الطلبات', 'callback_data': 'admin_orders'}],
            [{'text': '⚙️ إعدادات البوت', 'callback_data': 'admin_settings'}],
            [{'text': '🔧 إعدادات القنوات', 'callback_data': 'channels_settings'}],
            [{'text': '🔙 الرئيسية', 'callback_data': 'main'}]
        ]
    }
    send_message(chat_id, "👑 <b>لوحة تحكم المدير</b>", keyboard)

def manage_users_menu(chat_id):
    keyboard = {
        'inline_keyboard': [
            [{'text': '🔍 عرض مستخدم', 'callback_data': 'view_user'}],
            [{'text': '🚫 حظر مستخدم', 'callback_data': 'ban_user'}, {'text': '✅ فك حظر', 'callback_data': 'unban_user'}],
            [{'text': '⛔ تقييد مستخدم', 'callback_data': 'restrict_user'}, {'text': '🔓 فك التقييد', 'callback_data': 'unrestrict_user'}],
            [{'text': '👑 رفع مشرف', 'callback_data': 'promote_admin'}, {'text': '👤 خفض مشرف', 'callback_data': 'demote_admin'}],
            [{'text': '📩 إرسال رسالة', 'callback_data': 'send_user_message'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
        ]
    }
    send_message(chat_id, "👥 <b>إدارة المستخدمين</b>", keyboard)

def view_user_details(chat_id, user_id):
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        send_message(chat_id, "❌ المستخدم غير موجود")
        return
    
    status = ""
    if user[4] == 1:
        status = "🚫 محظور"
    elif user[5] == 1:
        status = "⛔ مقيد"
    elif user[3] == 1:
        status = "👑 مشرف"
    else:
        status = "✅ نشط"
    
    c.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
    orders_count = c.fetchone()[0]
    
    c.execute("SELECT SUM(total_price) FROM orders WHERE user_id = ?", (user_id,))
    total_spent = c.fetchone()[0] or 0
    
    text = f"""👤 <b>معلومات المستخدم</b>

━━━━━━━━━━━━━━━
🆔 الآيدي: <code>{user_id}</code>
📛 اليوزر: @{user[1] or 'بدون'}
💰 الرصيد: {user[2]:,.2f} USD
📊 الحالة: {status}
📅 تاريخ الإنشاء: {user[8]}
━━━━━━━━━━━━━━━
📦 عدد الطلبات: {orders_count}
💰 إجمالي المشتريات: {total_spent:,.2f} USD
━━━━━━━━━━━━━━━"""
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '🚫 حظر', 'callback_data': f'ban_{user_id}'}, 
             {'text': '✅ فك حظر', 'callback_data': f'unban_{user_id}'}],
            [{'text': '⛔ تقييد', 'callback_data': f'restrict_{user_id}'}, 
             {'text': '🔓 فك تقييد', 'callback_data': f'unrestrict_{user_id}'}],
            [{'text': '👑 رفع مشرف', 'callback_data': f'promote_{user_id}'}, 
             {'text': '👤 خفض مشرف', 'callback_data': f'demote_{user_id}'}],
            [{'text': '💰 شحن رصيد', 'callback_data': f'charge_{user_id}'}],
            [{'text': '📩 إرسال رسالة', 'callback_data': f'message_{user_id}'}],
            [{'text': '🔙 رجوع', 'callback_data': 'manage_users'}]
        ]
    }
    
    send_message(chat_id, text, keyboard)

# معالجة الأحداث
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
        invite_code = str(uuid.uuid4())[:8]
        c.execute("INSERT INTO users (user_id, username, invite_code) VALUES (?, ?, ?)", 
                  (user_id, username or "", invite_code))
        conn.commit()
        
        if user_id != ADMIN_ID:
            send_message(ADMIN_ID, f"👤 مستخدم جديد\n🆔: {user_id}\n📛: @{username or 'بدون'}")
    else:
        # تحديث اليوزرنيم إذا تغير
        if username and username != user[1]:
            c.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
            conn.commit()
    
    # التحقق من الحظر
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    banned = c.fetchone()
    if banned and banned[0] == 1:
        send_message(chat_id, "🚫 تم حظرك من البوت")
        return
    
    # التحقق من القنوات الإجبارية
    subscribed, channel = check_channels_subscription(user_id)
    if not subscribed:
        keyboard = {
            'inline_keyboard': [[
                {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
                {'text': '✅ تحقق من الاشتراك', 'callback_data': 'check_subscription'}
            ]]
        }
        send_message(chat_id, f"📢 يجب الاشتراك في القناة @{channel} أولاً لاستخدام البوت", keyboard)
        return
    
    # إرسال القائمة الرئيسية
    main_menu(chat_id, user_id)

def handle_message(user_id, chat_id, text):
    # التحقق من الصيانة
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_message(chat_id, get_setting('maintenance_msg'))
        return
    
    # التحقق من الحظر
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    banned = c.fetchone()
    if banned and banned[0] == 1:
        send_message(chat_id, "🚫 تم حظرك من البوت")
        return
    
    # التحقق من القيود
    c.execute("SELECT is_restricted FROM users WHERE user_id = ?", (user_id,))
    restricted = c.fetchone()
    if restricted and restricted[0] == 1 and user_id != ADMIN_ID:
        send_message(chat_id, "⛔ حسابك مقيد، لا يمكنك استخدام الخدمات")
        return
    
    # التحقق من القنوات الإجبارية
    subscribed, channel = check_channels_subscription(user_id)
    if not subscribed:
        keyboard = {
            'inline_keyboard': [[
                {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
                {'text': '✅ تحقق من الاشتراك', 'callback_data': 'check_subscription'}
            ]]
        }
        send_message(chat_id, f"📢 يجب الاشتراك في القناة @{channel} أولاً", keyboard)
        return
    
    # معالجة حالة المستخدم
    if user_id in user_states:
        state = user_states[user_id]
        
        # ... (بقية كود معالجة الحالات كما هو) ...
        
        return
    
    # معالجة الأوامر
    if text.startswith('/'):
        if text == '/start':
            handle_start(user_id, chat_id, "", None)
        elif text == '/admin' and user_id == ADMIN_ID:
            admin_panel(chat_id)
        else:
            main_menu(chat_id, user_id)
    else:
        main_menu(chat_id, user_id)

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
    if is_banned == 1 and user_id != ADMIN_ID:
        send_message(chat_id, "🚫 تم حظرك من البوت")
        return
    
    # التحقق من القيود
    c.execute("SELECT is_restricted FROM users WHERE user_id = ?", (user_id,))
    restricted = c.fetchone()
    if restricted and restricted[0] == 1 and user_id != ADMIN_ID:
        send_message(chat_id, "⛔ حسابك مقيد")
        return
    
    # التحقق من القنوات الإجبارية
    if data != 'check_subscription':
        subscribed, channel = check_channels_subscription(user_id)
        if not subscribed:
            keyboard = {
                'inline_keyboard': [[
                    {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
                    {'text': '✅ تحقق من الاشتراك', 'callback_data': 'check_subscription'}
                ]]
            }
            send_message(chat_id, f"📢 يجب الاشتراك في القناة @{channel} أولاً", keyboard)
            return
    
    if data == 'main':
        main_menu(chat_id, user_id)
    
    elif data == 'check_subscription':
        subscribed, channel = check_channels_subscription(user_id)
        if subscribed:
            send_message(chat_id, "✅ أنت مشترك في جميع القنوات المطلوبة")
            main_menu(chat_id, user_id)
        else:
            keyboard = {
                'inline_keyboard': [[
                    {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
                    {'text': '✅ تحقق من الاشتراك', 'callback_data': 'check_subscription'}
                ]]
            }
            send_message(chat_id, f"❌ لم تشترك بعد في @{channel}", keyboard)
    
    elif data == 'admin_panel':
        if is_admin != 1:
            send_message(chat_id, "🚫 ليس لديك صلاحية")
            return
        admin_panel(chat_id)
    
    elif data == 'manage_users':
        if is_admin != 1:
            return
        manage_users_menu(chat_id)
    
    elif data == 'view_user':
        if is_admin != 1:
            return
        user_states[user_id] = {'type': 'view_user'}
        send_message(chat_id, "🔍 أرسل آيدي المستخدم:")
    
    elif data == 'ban_user':
        if is_admin != 1:
            return
        user_states[user_id] = {'type': 'ban_user'}
        send_message(chat_id, "🚫 أرسل آيدي المستخدم للحظر:")
    
    elif data == 'unban_user':
        if is_admin != 1:
            return
        user_states[user_id] = {'type': 'unban_user'}
        send_message(chat_id, "✅ أرسل آيدي المستخدم لفك الحظر:")
    
    elif data == 'restrict_user':
        if is_admin != 1:
            return
        user_states[user_id] = {'type': 'restrict_user'}
        send_message(chat_id, "⛔ أرسل آيدي المستخدم للتقييد:")
    
    elif data == 'unrestrict_user':
        if is_admin != 1:
            return
        user_states[user_id] = {'type': 'unrestrict_user'}
        send_message(chat_id, "🔓 أرسل آيدي المستخدم لفك التقييد:")
    
    elif data == 'promote_admin':
        if is_admin != 1:
            return
        user_states[user_id] = {'type': 'promote_admin'}
        send_message(chat_id, "👑 أرسل آيدي المستخدم لرفعه كمشرف:")
    
    elif data == 'demote_admin':
        if is_admin != 1:
            return
        user_states[user_id] = {'type': 'demote_admin'}
        send_message(chat_id, "👤 أرسل آيدي المستخدم لخفضه لمستخدم عادي:")
    
    elif data.startswith('ban_'):
        target_id = int(data.split('_')[1])
        if is_admin != 1:
            return
        
        c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        
        c.execute("SELECT username FROM users WHERE user_id = ?", (target_id,))
        target_user = c.fetchone()
        username = target_user[0] if target_user else "بدون"
        
        send_message(chat_id, f"✅ تم حظر المستخدم {target_id} (@{username})")
        send_message(target_id, "🚫 تم حظرك من البوت من قبل الإدارة")
    
    elif data.startswith('unban_'):
        target_id = int(data.split('_')[1])
        if is_admin != 1:
            return
        
        c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        
        send_message(chat_id, f"✅ تم فك حظر المستخدم {target_id}")
        send_message(target_id, "✅ تم فك حظرك من البوت")
    
    elif data.startswith('restrict_'):
        target_id = int(data.split('_')[1])
        if is_admin != 1:
            return
        
        c.execute("UPDATE users SET is_restricted = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        
        send_message(chat_id, f"✅ تم تقييد المستخدم {target_id}")
        send_message(target_id, "⛔ تم تقييد حسابك من قبل الإدارة")
    
    elif data.startswith('unrestrict_'):
        target_id = int(data.split('_')[1])
        if is_admin != 1:
            return
        
        c.execute("UPDATE users SET is_restricted = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        
        send_message(chat_id, f"✅ تم فك تقييد المستخدم {target_id}")
        send_message(target_id, "✅ تم فك تقييد حسابك")
    
    elif data.startswith('promote_'):
        target_id = int(data.split('_')[1])
        if is_admin != 1:
            return
        
        c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        
        send_message(chat_id, f"✅ تم رفع المستخدم {target_id} كمشرف")
        send_message(target_id, "👑 تم رفعك كمشرف في البوت")
    
    elif data.startswith('demote_'):
        target_id = int(data.split('_')[1])
        if is_admin != 1:
            return
        
        c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        
        send_message(chat_id, f"✅ تم خفض المستخدم {target_id} لمستخدم عادي")
        send_message(target_id, "👤 تم خفض صلاحيتك لمستخدم عادي")
    
    elif data == 'channels_settings':
        if is_admin != 1:
            return
        
        c.execute("SELECT * FROM forced_channels ORDER BY position")
        channels = c.fetchall()
        
        text = "📢 <b>إعدادات القنوات الإجبارية</b>\n\n"
        
        if get_setting('force_subscribe') == 'true':
            text += "✅ <b>النظام مفعل</b>\n\n"
        else:
            text += "❌ <b>النظام معطل</b>\n\n"
        
        if channels:
            text += "<b>القنوات الحالية:</b>\n"
            for channel in channels:
                text += f"\n📢 @{channel[2]}\n🔗 {channel[3]}\n━━━━━━\n"
        else:
            text += "📭 لا توجد قنوات مضافة\n"
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '➕ إضافة قناة', 'callback_data': 'add_channel'}],
                [{'text': '🗑️ حذف قناة', 'callback_data': 'remove_channel'}],
                [{'text': '✅ تفعيل النظام', 'callback_data': 'enable_force_sub'}, 
                 {'text': '❌ تعطيل النظام', 'callback_data': 'disable_force_sub'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
            ]
        }
        
        send_message(chat_id, text, keyboard)
    
    elif data == 'admin_balance':
        if is_admin != 1:
            return
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '💰 شحن لمستخدم', 'callback_data': 'charge_user'}],
                [{'text': '🎁 إرسال للجميع', 'callback_data': 'send_to_all'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
            ]
        }
        send_message(chat_id, "💳 <b>إدارة الأرصدة</b>", keyboard)
    
    elif data == 'send_to_all':
        if is_admin != 1:
            return
        
        user_states[user_id] = {'type': 'send_to_all_amount'}
        send_message(chat_id, "💰 أرسل المبلغ المراد إرساله لجميع المستخدمين:")
    
    # ... (بقية كود الكولباك كما هو) ...

# البولينج الرئيسي
def polling_loop():
    offset = 0
    print("🚀 بدء تشغيل البوت...")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            params = {'offset': offset, 'timeout': 30}
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
        
        except Exception as e:
            print(f"خطأ: {e}")
            time.sleep(2)

if __name__ == '__main__':
    try:
        # اختبار الاتصال
        test = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=10)
        if test.status_code == 200:
            bot_info = test.json()
            if bot_info.get('ok'):
                print(f"✅ البوت متصل: @{bot_info['result'].get('username')}")
            else:
                print("❌ توكن البوت غير صحيح")
        else:
            print("❌ فشل الاتصال بالسيرفر")
        
        # تشغيل البولينج
        polling_loop()
        
    except KeyboardInterrupt:
        print("إيقاف البوت...")
    except Exception as e:
        print(f"خطأ غير متوقع: {e}")
    finally:
        conn.close()
