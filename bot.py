import sqlite3
import requests
import time
import json
import uuid
import random
import string
import os
from datetime import datetime

# إعدادات البوت
TOKEN = "8436742877:AAHmlmOKY2iQCGoOt004ruq09tZGderDGMQ"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"

# قاعدة البيانات
DB_PATH = 'bot.db'

# إنشاء مجلد للفواتير
if not os.path.exists('invoices'):
    os.makedirs('invoices', exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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

# إضافة المدير
c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
          (ADMIN_ID, "المدير", 100000, 1, 'ADMIN'))

# إضافة خدمات مثال إذا لم تكن موجودة
c.execute("SELECT COUNT(*) FROM categories")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO categories (name) VALUES ('خدمات السوشيال ميديا')")
    c.execute("INSERT INTO categories (name) VALUES ('خدمات اليوتيوب')")
    conn.commit()

c.execute("SELECT COUNT(*) FROM services")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO services (category_id, name, price_per_k, min_order, max_order) VALUES (1, 'متابعين انستغرام', 0.50, 100, 10000)")
    c.execute("INSERT INTO services (category_id, name, price_per_k, min_order, max_order) VALUES (1, 'لايكات تيك توك', 0.30, 100, 5000)")
    c.execute("INSERT INTO services (category_id, name, price_per_k, min_order, max_order) VALUES (2, 'مشاهدات يوتيوب', 0.20, 500, 50000)")
    conn.commit()

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

def send_document(chat_id, document_path, caption=""):
    """إرسال ملف"""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
        with open(document_path, 'rb') as doc:
            files = {'document': doc}
            data = {'chat_id': chat_id, 'caption': caption}
            requests.post(url, files=files, data=data, timeout=20)
    except Exception as e:
        print(f"⚠️ خطأ في إرسال الملف: {e}")

def check_channels(user_id):
    c.execute("SELECT value FROM settings WHERE key = 'force_subscribe'")
    result = c.fetchone()
    if not result or result[0] != 'true':
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

# ========== القوائم الرئيسية ==========
def main_menu(chat_id, user_id):
    subscribed, channel = check_channels(user_id)
    if not subscribed:
        buttons = [[
            {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
            {'text': '✅ تحقق', 'callback_data': 'check_sub'}
        ]]
        send_msg(chat_id, f"📢 يجب الاشتراك في @{channel} أولاً", buttons)
        return
    
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
💰 الرصيد: <b>{user[1]:,.2f} دولار</b>

📌 اختر من القائمة:"""
    
    buttons = [
        [{'text': '🛍️ الخدمات', 'callback_data': 'services'}],
        [{'text': '💰 شحن الرصيد', 'callback_data': 'charge'}, {'text': '💳 رصيدي', 'callback_data': 'balance'}],
        [{'text': '👥 دعوة أصدقاء', 'callback_data': 'invite'}, {'text': '📋 طلباتي', 'callback_data': 'my_orders'}],
        [{'text': '📞 الدعم', 'callback_data': 'support'}]
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

# ========== لوحة التحكم المتكاملة ==========
def admin_panel(chat_id):
    buttons = [
        [{'text': '📊 الإحصائيات', 'callback_data': 'stats'}, {'text': '👥 إدارة المستخدمين', 'callback_data': 'users_management'}],
        [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'manage_services'}, {'text': '💳 شحن الرصيد', 'callback_data': 'admin_charge'}],
        [{'text': '🚫 إدارة الحظر', 'callback_data': 'ban_management'}, {'text': '👑 إدارة المشرفين', 'callback_data': 'admin_manage'}],
        [{'text': '📢 القنوات الإجبارية', 'callback_data': 'channels_manage'}, {'text': '🎁 إرسال للجميع', 'callback_data': 'send_all'}],
        [{'text': '🧾 نظام الفواتير', 'callback_data': 'invoice_system'}, {'text': '🗑️ إدارة البيانات', 'callback_data': 'data_management'}],
        [{'text': '⚙️ الإعدادات', 'callback_data': 'settings_menu'}, {'text': '🔙 الرئيسية', 'callback_data': 'main'}]
    ]
    send_msg(chat_id, "👑 <b>لوحة تحكم المدير</b>", buttons)

def ban_management_menu(chat_id, page=0):
    """قائمة إدارة الحظر"""
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
    total_banned = c.fetchone()[0]
    
    c.execute("SELECT user_id, username, balance FROM users WHERE is_banned = 1 LIMIT 10 OFFSET ?", (page * 10,))
    banned_users = c.fetchall()
    
    text = f"🚫 <b>إدارة المستخدمين المحظورين</b>\n\n"
    text += f"👥 عدد المحظورين: {total_banned}\n━━━━━━━━━━━━\n"
    
    if banned_users:
        for user_id, username, balance in banned_users:
            text += f"🆔 {user_id} | @{username or 'بدون'}\n💰 {balance:,.2f} دولار\n"
            text += f"━━━━━━\n"
    else:
        text += "📭 لا يوجد مستخدمين محظورين\n"
    
    buttons = []
    
    # أزرار المستخدمين
    for user_id, username, balance in banned_users:
        buttons.append([
            {'text': f'✅ فك الحظر', 'callback_data': f'unban_{user_id}'},
            {'text': f'📩 رسالة', 'callback_data': f'msg_{user_id}'},
            {'text': f'🗑️ حذف', 'callback_data': f'deleteuser_{user_id}'}
        ])
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append({'text': '⬅️ السابق', 'callback_data': f'banpage_{page-1}'})
    if len(banned_users) == 10:
        nav_buttons.append({'text': '➡️ التالي', 'callback_data': f'banpage_{page+1}'})
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # أزرار الإدارة
    buttons.append([
        {'text': '🚫 حظر مستخدم', 'callback_data': 'ban_by_id'},
        {'text': '🔍 بحث', 'callback_data': 'search_banned'}
    ])
    
    buttons.append([{'text': '🗑️ حذف كل المحظورين', 'callback_data': 'delete_all_banned_confirm'}])
    buttons.append([{'text': '🔙 رجوع', 'callback_data': 'admin'}])
    
    send_msg(chat_id, text, buttons)

def users_management_menu(chat_id, page=0, search_query=None):
    """إدارة المستخدمين الكاملة"""
    if search_query:
        c.execute("SELECT COUNT(*) FROM users WHERE user_id LIKE ? OR username LIKE ?", 
                  (f'%{search_query}%', f'%{search_query}%'))
        total_users = c.fetchone()[0]
        c.execute("SELECT user_id, username, balance, is_banned, is_restricted, is_admin FROM users WHERE user_id LIKE ? OR username LIKE ? LIMIT 10 OFFSET ?", 
                  (f'%{search_query}%', f'%{search_query}%', page * 10))
    else:
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT user_id, username, balance, is_banned, is_restricted, is_admin FROM users LIMIT 10 OFFSET ?", (page * 10,))
    
    users = c.fetchall()
    
    text = f"👥 <b>إدارة المستخدمين</b>\n\n"
    text += f"📊 العدد الكلي: {total_users}\n"
    if search_query:
        text += f"🔍 نتائج البحث: {search_query}\n"
    text += "━━━━━━━━━━━━\n"
    
    if users:
        for user_id, username, balance, is_banned, is_restricted, is_admin in users:
            status = "🚫" if is_banned else "⛔" if is_restricted else "👑" if is_admin else "✅"
            text += f"{status} {user_id} | @{username or 'بدون'}\n💰 {balance:,.2f} دولار\n━━━━━━\n"
    else:
        text += "📭 لا يوجد مستخدمين\n"
    
    buttons = []
    
    for user_id, username, balance, is_banned, is_restricted, is_admin in users:
        # الصف الأول: حظر/تقييد/رفع
        row1 = []
        if is_banned:
            row1.append({'text': '✅ فك الحظر', 'callback_data': f'unban_{user_id}'})
        else:
            row1.append({'text': '🚫 حظر', 'callback_data': f'ban_{user_id}'})
        
        if is_restricted:
            row1.append({'text': '🔓 فك التقييد', 'callback_data': f'unrestrict_{user_id}'})
        else:
            row1.append({'text': '⛔ تقييد', 'callback_data': f'restrict_{user_id}'})
        
        if is_admin:
            row1.append({'text': '👤 خفض صلاحيات', 'callback_data': f'demote_{user_id}'})
        else:
            row1.append({'text': '👑 رفع مشرف', 'callback_data': f'promote_{user_id}'})
        
        buttons.append(row1)
        
        # الصف الثاني: شحن/رسالة/حذف
        buttons.append([
            {'text': '💰 شحن رصيد', 'callback_data': f'charge_{user_id}'},
            {'text': '📩 إرسال رسالة', 'callback_data': f'msg_{user_id}'},
            {'text': '🗑️ حذف المستخدم', 'callback_data': f'deleteuser_{user_id}'}
        ])
    
    # التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append({'text': '⬅️ السابق', 'callback_data': f'userspage_{page-1}'})
    if len(users) == 10:
        nav_buttons.append({'text': '➡️ التالي', 'callback_data': f'userspage_{page+1}'})
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # أدوات الإدارة
    buttons.append([
        {'text': '🔍 بحث عن مستخدم', 'callback_data': 'search_users'},
        {'text': '📊 إحصائيات', 'callback_data': 'users_stats'}
    ])
    
    buttons.append([
        {'text': '🎁 شحن للجميع', 'callback_data': 'send_all'},
        {'text': '🗑️ حذف كل المستخدمين', 'callback_data': 'delete_all_users_confirm'}
    ])
    
    buttons.append([{'text': '🔙 رجوع', 'callback_data': 'admin'}])
    
    send_msg(chat_id, text, buttons)

def invite_system_menu(chat_id, user_id):
    """نظام الدعوة"""
    c.execute("SELECT invite_code, total_invites FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    
    if not user_data:
        send_msg(chat_id, "❌ المستخدم غير موجود")
        return
    
    invite_code, total_invites = user_data
    reward = float(get_setting('invite_reward'))
    
    # إنشاء رابط الدعوة الجديد
    bot_username = get_setting('bot_username') or BOT_USERNAME
    user_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    link = f"https://t.me/{bot_username}?start={invite_code}_{user_id}_{user_code}"
    
    # الحصول على المدعوين
    c.execute('''SELECT u.user_id, u.username, u.created_at 
                 FROM users u WHERE u.invited_by = ? ORDER BY u.created_at DESC LIMIT 10''', (user_id,))
    invited_users = c.fetchall()
    
    text = f"""👥 <b>دعوة الأصدقاء</b>

💰 المكافأة لكل دعوة: {reward} دولار
👥 عدد المدعوين: {total_invites}
💰 إجمالي الأرباح: {total_invites * reward:,.2f} دولار

🔗 رابط الدعوة الخاص بك:
<code>{link}</code>

📋 آخر المدعوين:"""
    
    if invited_users:
        for inv_user_id, inv_username, inv_date in invited_users:
            text += f"\n👤 @{inv_username or 'مستخدم'} - {inv_date[:10]}"
    else:
        text += "\n📭 لا يوجد مدعوين بعد"
    
    buttons = [[
        {'text': '📤 مشاركة الرابط', 'url': f'tg://msg_url?url={link}'},
        {'text': '🔄 تحديث', 'callback_data': 'invite_refresh'}
    ], [
        {'text': '📊 قائمة المدعوين', 'callback_data': 'invites_list'}
    ], [
        {'text': '🔙 رجوع', 'callback_data': 'main'}
    ]]
    
    send_msg(chat_id, text, buttons)

# ========== معالجة الطلبات مع الروابط ==========
user_states = {}

def handle_message(chat_id, user_id, text):
    subscribed, channel = check_channels(user_id)
    if not subscribed:
        buttons = [[
            {'text': '📢 اشترك في القناة', 'url': f'https://t.me/{channel}'},
            {'text': '✅ تحقق', 'callback_data': 'check_sub'}
        ]]
        send_msg(chat_id, f"📢 يجب الاشتراك في @{channel} أولاً", buttons)
        return
    
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
                        send_msg(chat_id, f"❌ الحدود المسموحة {min_q}-{max_q}")
                except:
                    send_msg(chat_id, "❌ أدخل رقم صحيح")
            return
        
        elif state['type'] == 'order_link':
            link = text.strip()
            service_id = state['service_id']
            quantity = state['quantity']
            total = state['total']
            
            # التحقق من صحة الرابط
            if not link.startswith(('http://', 'https://')):
                send_msg(chat_id, "❌ رابط غير صالح. أرسل رابط يبدأ بـ http:// أو https://")
                return
            
            c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            balance = c.fetchone()[0]
            
            if balance >= total:
                # خصم المبلغ
                c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total, user_id))
                
                # حفظ الطلب
                c.execute("INSERT INTO orders (user_id, service_id, quantity, total_price, link) VALUES (?, ?, ?, ?, ?)",
                          (user_id, service_id, quantity, total, link))
                order_id = c.lastrowid
                conn.commit()
                
                # إرسال إشعار للمستخدم
                c.execute("SELECT name FROM services WHERE id = ?", (service_id,))
                service_name = c.fetchone()[0]
                
                send_msg(chat_id, f"""✅ تم إرسال الطلب #{order_id} بنجاح!

📦 الخدمة: {service_name}
🔢 الكمية: {quantity:,}
💰 المبلغ: {total:,.2f} دولار
🔗 الرابط: {link[:50]}...

📊 رصيدك الجديد: {balance - total:,.2f} دولار""")
                
                # إرسال إشعار مفصل للمدير
                admin_msg = f"""🆕 طلب جديد #{order_id}

👤 المستخدم: {user_id}
📦 الخدمة: {service_name}
🔢 الكمية: {quantity:,}
💰 المبلغ: {total:,.2f} دولار
🔗 الرابط: {link}

📊 رصيد المستخدم: {balance - total:,.2f} دولار"""
                
                admin_buttons = [[
                    {'text': '✅ إكمال الطلب', 'callback_data': f'complete_{order_id}'},
                    {'text': '❌ إلغاء الطلب', 'callback_data': f'cancel_{order_id}'}
                ]]
                
                send_msg(ADMIN_ID, admin_msg, admin_buttons)
                
            else:
                send_msg(chat_id, "❌ رصيد غير كافي")
            
            del user_states[user_id]
            return
        
        # حالات إدارة الحظر
        elif state.get('type') == 'ban_by_id':
            if text.isdigit():
                target_id = int(text)
                c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
                conn.commit()
                send_msg(chat_id, f"✅ تم حظر المستخدم {target_id}")
                send_msg(target_id, "🚫 تم حظرك من البوت")
            else:
                send_msg(chat_id, "❌ آيدي غير صحيح")
            del user_states[user_id]
            return
        
        elif state.get('type') == 'search_users':
            users_management_menu(chat_id, search_query=text)
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
                target_id = state['target_id']
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                send_msg(chat_id, f"✅ تم شحن {amount:,.2f} دولار للمستخدم {target_id}")
                send_msg(target_id, f"🎉 تم شحن رصيدك!\nالمبلغ: {amount:,.2f} دولار")
                del user_states[user_id]
            except:
                send_msg(chat_id, "❌ مبلغ غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'send_user_message':
            target_id = state['target_id']
            send_msg(target_id, f"📩 رسالة من الإدارة:\n\n{text}")
            send_msg(chat_id, f"✅ تم إرسال الرسالة للمستخدم {target_id}")
            del user_states[user_id]
            return
    
    if text.startswith('/start'):
        # معالجة رابط الدعوة
        parts = text.split()
        if len(parts) > 1:
            invite_data = parts[1]
            if '_' in invite_data:
                invite_parts = invite_data.split('_')
                if len(invite_parts) >= 1:
                    invite_code = invite_parts[0]
                    c.execute("SELECT user_id FROM users WHERE invite_code = ?", (invite_code,))
                    inviter = c.fetchone()
                    
                    if inviter and inviter[0] != user_id and get_setting('invite_enabled') == 'true':
                        reward = float(get_setting('invite_reward'))
                        c.execute("UPDATE users SET balance = balance + ?, total_invites = total_invites + 1 WHERE user_id = ?", 
                                  (reward, inviter[0]))
                        c.execute("UPDATE users SET invited_by = ? WHERE user_id = ?", (inviter[0], user_id))
                        conn.commit()
                        send_msg(inviter[0], f"🎉 مكافأة دعوة {reward} دولار! انضم مستخدم جديد.")
        
        # تسجيل المستخدم الجديد
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
        send_msg(chat_id, f"💰 رصيدك: {balance:,.2f} دولار")
    
    elif data == 'invite':
        invite_system_menu(chat_id, user_id)
    
    elif data == 'my_orders':
        c.execute("SELECT o.id, s.name, o.quantity, o.total_price, o.status FROM orders o JOIN services s ON o.service_id = s.id WHERE o.user_id = ? ORDER BY o.id DESC LIMIT 10", (user_id,))
        orders = c.fetchall()
        
        if orders:
            text = "📋 <b>طلباتك</b>\n\n"
            for oid, name, qty, price, status in orders:
                status_icon = '✅' if status == 'completed' else '⏳' if status == 'processing' else '❌'
                text += f"{status_icon} #{oid} - {name}\n🔢 {qty:,} | 💰 {price:,.2f} دولار\n━━━━━━\n"
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
💰 إجمالي الأرصدة: {balance:,.2f} دولار
📦 الطلبات: {orders}"""
            send_msg(chat_id, text)
    
    elif data == 'users_management':
        users_management_menu(chat_id)
    
    elif data.startswith('userspage_'):
        page = int(data.split('_')[1])
        users_management_menu(chat_id, page)
    
    elif data == 'ban_management':
        ban_management_menu(chat_id)
    
    elif data.startswith('banpage_'):
        page = int(data.split('_')[1])
        ban_management_menu(chat_id, page)
    
    elif data == 'search_users':
        user_states[user_id] = {'type': 'search_users'}
        send_msg(chat_id, "🔍 أرسل آيدي المستخدم أو يوزره للبحث:")
    
    elif data == 'ban_by_id':
        user_states[user_id] = {'type': 'ban_by_id'}
        send_msg(chat_id, "🚫 أرسل آيدي المستخدم للحظر:")
    
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
        send_msg(target_id, "✅ تم فك حظرك من البوت")
    
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
    
    elif data.startswith('deleteuser_'):
        target_id = int(data.split('_')[1])
        buttons = [[
            {'text': '✅ نعم، احذف', 'callback_data': f'confirm_delete_{target_id}'},
            {'text': '❌ إلغاء', 'callback_data': 'users_management'}
        ]]
        send_msg(chat_id, f"⚠️ هل تريد حقاً حذف المستخدم {target_id}؟\nسيتم حذف جميع بياناته.", buttons)
    
    elif data.startswith('confirm_delete_'):
        target_id = int(data.split('_')[2])
        c.execute("DELETE FROM users WHERE user_id = ?", (target_id,))
        c.execute("DELETE FROM orders WHERE user_id = ?", (target_id,))
        conn.commit()
        send_msg(chat_id, f"✅ تم حذف المستخدم {target_id} وجميع بياناته")
    
    elif data == 'delete_all_users_confirm':
        buttons = [[
            {'text': '⚠️ نعم، احذف الكل', 'callback_data': 'delete_all_users'},
            {'text': '❌ إلغاء', 'callback_data': 'users_management'}
        ]]
        send_msg(chat_id, "⚠️ <b>تحذير!</b>\nهل تريد حقاً حذف جميع المستخدمين؟\nهذا الإجراء لا يمكن التراجع عنه.", buttons)
    
    elif data == 'delete_all_users':
        c.execute("DELETE FROM users WHERE user_id != ?", (ADMIN_ID,))
        c.execute("DELETE FROM orders")
        conn.commit()
        send_msg(chat_id, "✅ تم حذف جميع المستخدمين والطلبات")
    
    elif data == 'delete_all_banned_confirm':
        buttons = [[
            {'text': '⚠️ نعم، احذف المحظورين', 'callback_data': 'delete_all_banned'},
            {'text': '❌ إلغاء', 'callback_data': 'ban_management'}
        ]]
        send_msg(chat_id, "⚠️ هل تريد حذف جميع المستخدمين المحظورين؟", buttons)
    
    elif data == 'delete_all_banned':
        c.execute("DELETE FROM users WHERE is_banned = 1 AND user_id != ?", (ADMIN_ID,))
        conn.commit()
        send_msg(chat_id, "✅ تم حذف جميع المستخدمين المحظورين")
    
    elif data == 'manage_services':
        buttons = [
            [{'text': '📁 إضافة قسم', 'callback_data': 'add_category'}],
            [{'text': '➕ إضافة خدمة', 'callback_data': 'add_service'}],
            [{'text': '📋 قائمة الخدمات', 'callback_data': 'list_services'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
        ]
        send_msg(chat_id, "🛍️ إدارة الخدمات:", buttons)
    
    elif data == 'admin_charge':
        user_states[user_id] = {'type': 'admin_charge_user'}
        send_msg(chat_id, "💰 أرسل آيدي المستخدم:")
    
    elif data == 'admin_manage':
        buttons = [
            [{'text': '👑 رفع مشرف', 'callback_data': 'promote_admin'}, {'text': '👤 خفض مشرف', 'callback_data': 'demote_admin'}],
            [{'text': '📋 قائمة المشرفين', 'callback_data': 'list_admins'}, {'text': '🔙 رجوع', 'callback_data': 'admin'}]
        ]
        send_msg(chat_id, "👑 إدارة المشرفين:", buttons)
    
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
    
    elif data == 'send_all':
        user_states[user_id] = {'type': 'send_to_all_amount'}
        send_msg(chat_id, "💰 أرسل المبلغ المراد إرساله للجميع:")
    
    elif data == 'settings_menu':
        maint = get_setting('maintenance')
        reward = get_setting('invite_reward')
        
        text = f"""⚙️ <b>إعدادات البوت</b>

🔧 الصيانة: {'✅ مفعل' if maint == 'true' else '❌ معطل'}
💰 مكافأة الدعوة: {reward} دولار"""
        
        buttons = [
            [{'text': '🔧 تبديل الصيانة', 'callback_data': 'toggle_maint'}, {'text': '💰 تغيير المكافأة', 'callback_data': 'change_reward'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
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
    
    elif data == 'data_management':
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM orders")
        orders_count = c.fetchone()[0]
        
        text = f"""🗑️ <b>إدارة البيانات</b>

👥 عدد المستخدمين: {users_count}
📦 عدد الطلبات: {orders_count}

⚠️ <b>تحذير:</b> هذه العمليات لا يمكن التراجع عنها"""
        
        buttons = [
            [{'text': '🧹 تنظيف الطلبات القديمة', 'callback_data': 'clean_old_orders'}],
            [{'text': '🗑️ حذف جميع الطلبات', 'callback_data': 'delete_all_orders_confirm'}],
            [{'text': '🗑️ حذف جميع المستخدمين', 'callback_data': 'delete_all_users_confirm'}],
            [{'text': '💾 نسخ احتياطي', 'callback_data': 'backup_data'}],
            [{'text': '🔙 رجوع', 'callback_data': 'admin'}]
        ]
        send_msg(chat_id, text, buttons)

# ========== تشغيل البوت ==========
print("🚀 البوت يعمل...")
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
