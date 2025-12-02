import sqlite3
import requests
import time
import uuid

# إعدادات البوت
TOKEN = "8436742877:AAHmlmOKY2iQCGoOt004ruq09tZGderDGMQ"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"
BOT_USERNAME = "Flashback70bot"

# تهيئة قاعدة البيانات
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول (بدون حذف)
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

# إضافة المدير إذا لم يكن موجود
c.execute("INSERT OR IGNORE INTO users (user_id, username, balance, is_admin, invite_code) VALUES (?, ?, ?, ?, ?)",
          (ADMIN_ID, "المدير", 100000, 1, 'ADMIN'))
conn.commit()

# توليد كود دعوة للمستخدمين الجدد
def generate_invite_code():
    return str(uuid.uuid4())[:8]

# التحقق من الصيانة
def is_maintenance():
    c.execute("SELECT value FROM settings WHERE key = 'maintenance'")
    result = c.fetchone()
    return result and result[0] == 'true'

# جلب رسالة الصيانة
def get_maintenance_msg():
    c.execute("SELECT value FROM settings WHERE key = 'maintenance_msg'")
    result = c.fetchone()
    return result[1] if result else "البوت تحت الصيانة حاليًا ⚠️"

# إرسال الرسائل
def send(chat_id, text, buttons=None, parse_mode='HTML'):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
        
        if buttons:
            import json
            keyboard = {"inline_keyboard": []}
            for row in buttons:
                kb_row = []
                for btn in row:
                    if 'url' in btn:
                        kb_row.append({"text": btn['text'], "url": btn['url']})
                    else:
                        kb_row.append({"text": btn['text'], "callback_data": btn['data']})
                keyboard["inline_keyboard"].append(kb_row)
            data['reply_markup'] = json.dumps(keyboard)
        
        response = requests.post(url, json=data, timeout=5)
        return response.status_code == 200
    except:
        return False

# القوائم
def main_menu(user_id):
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        invite_code = generate_invite_code()
        c.execute("INSERT INTO users (user_id, invite_code) VALUES (?, ?)", (user_id, invite_code))
        conn.commit()
        user = (user_id, None, 0, 0, 0, 0, invite_code)
    
    username = user[1] if user[1] else "مستخدم"
    balance = user[2]
    invite_code = user[6] if user[6] else generate_invite_code()
    
    # تحديث كود الدعوة إذا لم يكن موجود
    if not user[6]:
        c.execute("UPDATE users SET invite_code = ? WHERE user_id = ?", (invite_code, user_id))
        conn.commit()
    
    text = f"""👋 <b>أهلاً {username}</b>

<b>━━━━━━━━━━━━━━━</b>
<b>🆔 الآيدي:</b> <code>{user_id}</code>
<b>💰 الرصيد:</b> <b>{balance:,.2f} USD</b>
<b>━━━━━━━━━━━━━━━</b>

<b>📌 اختر من القائمة:</b>"""
    
    buttons = [
        [{"text": "🛍️ خدمات", "data": "services"}, {"text": "💰 شحن", "data": "charge"}],
        [{"text": "💳 رصيدي", "data": "balance"}, {"text": "📞 دعم", "data": "support"}],
        [{"text": "👥 دعوة أصدقاء", "data": "invite"}],
        [{"text": "📋 طلباتي", "data": "my_orders"}]
    ]
    
    if user[3] == 1:
        buttons.append([{"text": "👑 لوحة التحكم", "data": "admin_panel"}])
    
    return text, buttons

def admin_menu():
    c.execute("SELECT value FROM settings WHERE key = 'maintenance'")
    maintenance_status = "🔴 ON" if c.fetchone()[0] == 'true' else "🟢 OFF"
    
    text = f"""👑 <b>لوحة تحكم المدير</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📊 حالة الصيانة:</b> {maintenance_status}
<b>━━━━━━━━━━━━━━━</b>
<b>📌 اختر القسم:</b>"""
    
    buttons = [
        [{"text": "📊 الإحصائيات", "data": "stats"}, {"text": "👥 المستخدمين", "data": "users"}],
        [{"text": "🛍️ إدارة الخدمات", "data": "manage_services"}, {"text": "📋 إدارة الطلبات", "data": "manage_orders"}],
        [{"text": "💳 شحن رصيد", "data": "admin_charge"}, {"text": "🚫 حظر/فك حظر", "data": "ban_user"}],
        [{"text": "👥 نظام الدعوة", "data": "invite_settings"}, {"text": "⚙️ إعدادات", "data": "settings"}],
        [{"text": "📢 الإذاعة", "data": "broadcast"}],
        [{"text": "🔙 الرئيسية", "data": "main"}]
    ]
    return text, buttons

def services_menu():
    c.execute("SELECT id, name FROM categories ORDER BY position")
    categories = c.fetchall()
    
    text = """🛍️ <b>خدمات المتجر</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📁 اختر القسم:</b>"""
    
    buttons = []
    for cat_id, cat_name in categories:
        buttons.append([{"text": f"📁 {cat_name}", "data": f"cat_{cat_id}"}])
    
    if not categories:
        buttons.append([{"text": "📁 لا توجد أقسام", "data": "no_cats"}])
    
    buttons.append([{"text": "🔙 رجوع", "data": "main"}])
    
    return text, buttons

def category_menu(cat_id):
    c.execute("SELECT name FROM categories WHERE id = ?", (cat_id,))
    cat_result = c.fetchone()
    
    if not cat_result:
        return services_menu()
    
    category_name = cat_result[0]
    
    c.execute("SELECT id, name, price FROM services WHERE category_id = ?", (cat_id,))
    services = c.fetchall()
    
    text = f"""🛍️ <b>قسم {category_name}</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📦 اختر الخدمة:</b>"""
    
    buttons = []
    for service_id, service_name, price in services:
        buttons.append([{"text": f"📦 {service_name} - {price:,.2f} USD", "data": f"service_{service_id}"}])
    
    if not services:
        buttons.append([{"text": "📭 لا توجد خدمات في هذا القسم", "data": "no_services"}])
    
    buttons.append([{"text": "🔙 رجوع للاقسام", "data": "services"}, {"text": "🏠 الرئيسية", "data": "main"}])
    
    return text, buttons

def service_menu(service_id, user_id):
    c.execute("""SELECT s.id, s.name, s.price, s.min_quantity, s.max_quantity, s.description, c.name 
                 FROM services s 
                 JOIN categories c ON s.category_id = c.id 
                 WHERE s.id = ?""", (service_id,))
    service = c.fetchone()
    
    if not service:
        return "❌ الخدمة غير موجودة", [[{"text": "🔙 رجوع", "data": "services"}]]
    
    s_id, s_name, s_price, s_min, s_max, s_desc, cat_name = service
    
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user_balance = c.fetchone()[0]
    
    desc_text = f"\n📝 {s_desc}" if s_desc else ""
    
    text = f"""🛒 <b>تفاصيل الخدمة</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📦 الخدمة:</b> {s_name}
<b>📁 القسم:</b> {cat_name}
<b>💰 السعر:</b> <b>{s_price:,.2f} USD</b> للوحدة
<b>🔢 الحد الأدنى:</b> {s_min:,}
<b>🔢 الحد الأقصى:</b> {s_max:,}{desc_text}
<b>━━━━━━━━━━━━━━━</b>
<b>💳 رصيدك الحالي:</b> <b>{user_balance:,.2f} USD</b>
<b>━━━━━━━━━━━━━━━</b>

<b>✍️ أرسل الكمية المطلوبة:</b>"""
    
    buttons = [
        [{"text": "🔙 رجوع", "data": f"cat_{service[0]}"}],
        [{"text": "🏠 الرئيسية", "data": "main"}]
    ]
    
    return text, buttons

def charge_menu(user_id):
    text = f"""💰 <b>شحن الرصيد</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📞 للشحن تواصل مع:</b>
<b>👤 @{SUPPORT_USERNAME}</b>

<b>📝 أرسل له:</b>
"أريد شحن رصيد، آيدي حسابي: <code>{user_id}</code>"
<b>━━━━━━━━━━━━━━━</b>"""
    
    buttons = [
        [{"text": "🔙 رجوع", "data": "main"}]
    ]
    
    return text, buttons

def invite_menu(user_id):
    c.execute("SELECT invite_code, balance FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    invite_code = user_data[0] if user_data else generate_invite_code()
    
    c.execute("SELECT COUNT(*) FROM users WHERE invited_by = ?", (user_id,))
    invited_count = c.fetchone()[0]
    
    c.execute("SELECT value FROM settings WHERE key = 'invite_reward'")
    reward = float(c.fetchone()[1])
    
    invite_link = f"https://t.me/{BOT_USERNAME}?start={invite_code}"
    
    text = f"""👥 <b>دعوة الأصدقاء</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📊 عدد المدعوين:</b> {invited_count}
<b>💰 المكافأة لكل دعوة:</b> {reward} USD
<b>━━━━━━━━━━━━━━━</b>
<b>🔗 رابط الدعوة الخاص بك:</b>
<code>{invite_link}</code>

<b>📋 كود الدعوة:</b>
<code>{invite_code}</code>

<b>📌 كيف تعمل:</b>
1. أرسل الرابط لصديقك
2. عندما ينضم صديقك بالرابط
3. تحصل على {reward} USD تلقائيًا
<b>━━━━━━━━━━━━━━━</b>"""
    
    buttons = [
        [{"text": "📤 مشاركة الرابط", "url": f"https://t.me/share/url?url={invite_link}&text=انضم%20إلي%20في%20هذا%20البوت%20الرائع!"}],
        [{"text": "🔙 رجوع", "data": "main"}]
    ]
    
    return text, buttons

def my_orders_menu(user_id, page=0):
    offset = page * 5
    c.execute("""SELECT o.id, s.name, o.quantity, o.total_price, o.status, o.created_at 
                 FROM orders o 
                 JOIN services s ON o.service_id = s.id 
                 WHERE o.user_id = ? 
                 ORDER BY o.id DESC 
                 LIMIT 5 OFFSET ?""", (user_id, offset))
    orders = c.fetchall()
    
    c.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
    total_orders = c.fetchone()[0]
    
    text = f"""📋 <b>طلباتي</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📊 عدد الطلبات:</b> {total_orders}
<b>━━━━━━━━━━━━━━━</b>"""
    
    if orders:
        for order_id, service_name, quantity, total_price, status, created_at in orders:
            status_icon = "✅" if status == 'completed' else "⏳" if status == 'processing' else "❌" if status == 'rejected' else "📝"
            text += f"\n{status_icon} <b>#{order_id}</b> | {service_name[:20]}"
            text += f"\n🔢 {quantity:,} | 💰 {total_price:,.2f} USD"
            text += f"\n📅 {created_at[:10]} | 📊 {status}"
            text += f"\n<b>━━━━━━</b>"
    else:
        text += "\n\n📭 لا توجد طلبات سابقة"
    
    buttons = []
    if page > 0:
        buttons.append({"text": "⬅️ السابق", "data": f"myorders_{page-1}"})
    if offset + 5 < total_orders:
        buttons.append({"text": "التالي ➡️", "data": f"myorders_{page+1}"})
    
    if buttons:
        nav_buttons = [buttons]
    else:
        nav_buttons = []
    
    nav_buttons.append([{"text": "🏠 الرئيسية", "data": "main"}])
    
    return text, nav_buttons

def manage_services_menu():
    text = """🛍️ <b>إدارة الخدمات</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📌 اختر القسم:</b>"""
    
    buttons = [
        [{"text": "📁 إدارة الأقسام", "data": "manage_categories"}],
        [{"text": "➕ إضافة خدمة", "data": "add_service"}],
        [{"text": "✏️ تعديل خدمة", "data": "edit_service"}],
        [{"text": "🗑️ حذف خدمة", "data": "delete_service"}],
        [{"text": "🔙 رجوع للوحة التحكم", "data": "admin_panel"}]
    ]
    
    return text, buttons

def manage_categories_menu():
    c.execute("SELECT id, name, position FROM categories ORDER BY position")
    categories = c.fetchall()
    
    text = """📁 <b>إدارة الأقسام</b>

<b>━━━━━━━━━━━━━━━</b>"""
    
    for cat_id, cat_name, position in categories:
        text += f"\n<b>{position + 1}.</b> {cat_name}"
        text += f"\n<code>cat_{cat_id}</code>\n<b>━━━━━━</b>"
    
    text += "\n\n<b>📌 اختر:</b>"
    
    buttons = [
        [{"text": "➕ إضافة قسم", "data": "add_category"}],
        [{"text": "✏️ تعديل قسم", "data": "edit_category"}],
        [{"text": "🗑️ حذف قسم", "data": "delete_category"}],
        [{"text": "🔙 رجوع", "data": "manage_services"}]
    ]
    
    return text, buttons

def manage_orders_menu(page=0):
    offset = page * 5
    c.execute("""SELECT o.id, u.user_id, s.name, o.quantity, o.total_price, o.status, o.created_at 
                 FROM orders o 
                 JOIN users u ON o.user_id = u.user_id 
                 JOIN services s ON o.service_id = s.id 
                 ORDER BY o.id DESC 
                 LIMIT 5 OFFSET ?""", (offset,))
    orders = c.fetchall()
    
    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]
    
    text = f"""📋 <b>إدارة الطلبات</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📊 إجمالي الطلبات:</b> {total_orders}
<b>━━━━━━━━━━━━━━━</b>"""
    
    if orders:
        for order_id, user_id, service_name, quantity, total_price, status, created_at in orders:
            status_icon = "✅" if status == 'completed' else "⏳" if status == 'processing' else "❌" if status == 'rejected' else "📝"
            text += f"\n{status_icon} <b>#{order_id}</b> | 👤 {user_id}"
            text += f"\n📦 {service_name[:20]} | 🔢 {quantity:,}"
            text += f"\n💰 {total_price:,.2f} USD | 📊 {status}"
            text += f"\n<code>order_{order_id}</code>\n<b>━━━━━━</b>"
    else:
        text += "\n\n📭 لا توجد طلبات حالياً"
    
    buttons = []
    if page > 0:
        buttons.append({"text": "⬅️ السابق", "data": f"adminorders_{page-1}"})
    if offset + 5 < total_orders:
        buttons.append({"text": "التالي ➡️", "data": f"adminorders_{page+1}"})
    
    if buttons:
        nav_buttons = [buttons]
    else:
        nav_buttons = []
    
    nav_buttons.append([
        {"text": "🔍 تفاصيل طلب", "data": "view_order"},
        {"text": "🔄 تحديث حالة", "data": "update_order"}
    ])
    nav_buttons.append([{"text": "🔙 رجوع", "data": "admin_panel"}])
    
    return text, nav_buttons

def invite_settings_menu():
    c.execute("SELECT value FROM settings WHERE key = 'invite_reward'")
    reward = c.fetchone()[1]
    
    c.execute("SELECT value FROM settings WHERE key = 'invite_enabled'")
    enabled = c.fetchone()[1]
    enabled_text = "✅ مفعل" if enabled == 'true' else "❌ معطل"
    
    text = f"""👥 <b>إعدادات نظام الدعوة</b>

<b>━━━━━━━━━━━━━━━</b>
<b>💰 مكافأة الدعوة:</b> {reward} USD
<b>⚙️ حالة النظام:</b> {enabled_text}
<b>━━━━━━━━━━━━━━━</b>

<b>📌 اختر الإجراء:</b>"""
    
    buttons = [
        [{"text": "💰 تغيير مكافأة الدعوة", "data": "change_invite_reward"}],
        [{"text": "✅ تفعيل النظام", "data": "enable_invite"}, {"text": "❌ تعطيل النظام", "data": "disable_invite"}],
        [{"text": "📊 إحصائيات الدعوات", "data": "invite_stats"}],
        [{"text": "🔙 رجوع", "data": "admin_panel"}]
    ]
    
    return text, buttons

def settings_menu():
    c.execute("SELECT value FROM settings WHERE key = 'maintenance'")
    maintenance = c.fetchone()[1]
    maintenance_status = "✅ مفعل" if maintenance == 'true' else "❌ معطل"
    
    c.execute("SELECT value FROM settings WHERE key = 'maintenance_msg'")
    maintenance_msg = c.fetchone()[1]
    
    text = f"""⚙️ <b>إعدادات البوت</b>

<b>━━━━━━━━━━━━━━━</b>
<b>🔧 وضع الصيانة:</b> {maintenance_status}
<b>📝 رسالة الصيانة:</b>
{maintenance_msg[:50]}...
<b>━━━━━━━━━━━━━━━</b>

<b>📌 اختر الإجراء:</b>"""
    
    buttons = [
        [{"text": "🔧 تفعيل/تعطيل الصيانة", "data": "toggle_maintenance"}],
        [{"text": "📝 تغيير رسالة الصيانة", "data": "change_maintenance_msg"}],
        [{"text": "🔙 رجوع", "data": "admin_panel"}]
    ]
    
    return text, buttons

# معالجة الأحداث
user_states = {}
user_attempts = {}
user_last_action = {}

def check_security(user_id, action_type):
    """نظام حماية متقدم"""
    current_time = time.time()
    
    if user_id not in user_attempts:
        user_attempts[user_id] = {'count': 0, 'last_time': current_time, 'actions': {}}
    
    if user_id not in user_last_action:
        user_last_action[user_id] = current_time
    
    # التحقق من التكرار السريع
    time_diff = current_time - user_last_action[user_id]
    if time_diff < 0.5:  # أقل من نصف ثانية بين الإجراءات
        user_attempts[user_id]['count'] += 1
        
        if user_attempts[user_id]['count'] >= 5:
            # حظر المستخدم
            c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            
            # إرسال إشعار للمدير
            c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
            username = c.fetchone()
            username = username[0] if username else "غير معروف"
            
            alert_text = f"""🚨 <b>تنبيه أمني - حظر مستخدم</b>

<b>━━━━━━━━━━━━━━━</b>
<b>👤 المستخدم:</b> <code>{user_id}</code>
<b>📛 اليوزر:</b> @{username or 'بدون'}
<b>⚠️ السبب:</b> تكرار إجراءات سريعة (تلاعب محتمل)
<b>🕒 الوقت:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}
<b>📊 عدد المحاولات:</b> {user_attempts[user_id]['count']}
<b>━━━━━━━━━━━━━━━</b>"""
            
            send(ADMIN_ID, alert_text)
            return False
    
    user_last_action[user_id] = current_time
    
    # التحقق من الإجراءات المشبوهة
    if action_type not in user_attempts[user_id]['actions']:
        user_attempts[user_id]['actions'][action_type] = 1
    else:
        user_attempts[user_id]['actions'][action_type] += 1
    
    # إعادة تعيين العدادات بعد 5 دقائق
    if current_time - user_attempts[user_id]['last_time'] > 300:
        user_attempts[user_id] = {'count': 0, 'last_time': current_time, 'actions': {}}
    
    return True

def handle_start(chat_id, user_id, username, start_param=None):
    if is_maintenance() and user_id != ADMIN_ID:
        send(chat_id, get_maintenance_msg())
        return
    
    if not check_security(user_id, 'start'):
        send(chat_id, "🚫 تم حظرك بسبب نشاط مشبوه")
        return
    
    # التحقق من كود الدعوة
    if start_param and start_param != 'start':
        c.execute("SELECT user_id FROM users WHERE invite_code = ? AND user_id != ?", (start_param, user_id))
        inviter = c.fetchone()
        
        if inviter:
            inviter_id = inviter[0]
            
            # التحقق من عدم دعوة النفس
            if inviter_id != user_id:
                c.execute("SELECT COUNT(*) FROM users WHERE user_id = ? AND invited_by = 0", (user_id,))
                is_new = c.fetchone()[0] > 0
                
                if is_new:
                    c.execute("UPDATE users SET invited_by = ? WHERE user_id = ?", (inviter_id, user_id))
                    
                    c.execute("SELECT value FROM settings WHERE key = 'invite_enabled'")
                    invite_enabled = c.fetchone()[1]
                    
                    if invite_enabled == 'true':
                        c.execute("SELECT value FROM settings WHERE key = 'invite_reward'")
                        reward = float(c.fetchone()[1])
                        
                        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, inviter_id))
                        conn.commit()
                        
                        send(inviter_id, f"""🎉 <b>مكافأة دعوة جديدة!</b>

✅ تم انضمام مستخدم جديد برابط دعوتك
💰 المكافأة: {reward} USD
📊 تم إضافة المكافأة تلقائياً لرصيدك""")
    
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    is_new = False
    if not user:
        is_new = True
        invite_code = generate_invite_code()
        c.execute("INSERT INTO users (user_id, username, invite_code) VALUES (?, ?, ?)", 
                  (user_id, username or "", invite_code))
        conn.commit()
        
        if user_id != ADMIN_ID:
            send(ADMIN_ID, f"👤 <b>مستخدم جديد</b>\n\n🆔: <code>{user_id}</code>\n📛: @{username or 'بدون'}")
    
    text, buttons = main_menu(user_id)
    send(chat_id, text, buttons)

def handle_text(chat_id, user_id, text):
    if is_maintenance() and user_id != ADMIN_ID:
        send(chat_id, get_maintenance_msg())
        return
    
    if not check_security(user_id, 'text'):
        send(chat_id, "🚫 تم حظرك بسبب نشاط مشبوه")
        return
    
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        send(chat_id, "❌ حسابك غير موجود")
        return
    
    if user[4] == 1:
        send(chat_id, "🚫 تم حظرك من البوت")
        return
    
    if user_id in user_states:
        state = user_states[user_id]
        
        if state.startswith('add_category_'):
            if len(text) < 2:
                send(chat_id, "❌ اسم القسم قصير جداً (أقل من حرفين)")
                return
            
            c.execute("SELECT id FROM categories WHERE name = ?", (text,))
            if c.fetchone():
                send(chat_id, "❌ هذا القسم موجود مسبقاً")
                del user_states[user_id]
                return
            
            c.execute("INSERT INTO categories (name) VALUES (?)", (text,))
            conn.commit()
            send(chat_id, f"✅ تم إضافة قسم: <b>{text}</b>")
            del user_states[user_id]
            return
        
        elif state.startswith('add_service_'):
            parts = text.split('\n')
            if len(parts) < 3:
                send(chat_id, """❌ استخدم التنسيق:
<code>اسم الخدمة
السعر
الحد الأدنى
الحد الأقصى
(اختياري) الوصف</code>""")
                return
            
            try:
                service_name = parts[0].strip()
                price = float(parts[1].strip())
                min_qty = int(parts[2].strip())
                max_qty = int(parts[3].strip()) if len(parts) > 3 else min_qty * 10
                description = parts[4].strip() if len(parts) > 4 else ""
                
                cat_id = state.split('_')[2]
                
                c.execute("""INSERT INTO services (category_id, name, price, min_quantity, max_quantity, description) 
                             VALUES (?, ?, ?, ?, ?, ?)""", 
                          (cat_id, service_name, price, min_qty, max_qty, description))
                conn.commit()
                
                send(chat_id, f"""✅ <b>تم إضافة الخدمة بنجاح</b>

📦 <b>الخدمة:</b> {service_name}
💰 <b>السعر:</b> {price:,.2f} USD
🔢 <b>الحد الأدنى:</b> {min_qty:,}
🔢 <b>الحد الأقصى:</b> {max_qty:,}
📁 <b>القسم:</b> {cat_id}""")
                
            except ValueError:
                send(chat_id, "❌ تأكد من صحة الأرقام المدخلة")
            finally:
                del user_states[user_id]
            return
        
        elif state.startswith('order_qty_'):
            service_id = state.split('_')[2]
            
            if not text.isdigit():
                send(chat_id, "❌ الرجاء إدخال رقم صحيح")
                return
            
            quantity = int(text)
            
            c.execute("SELECT price, min_quantity, max_quantity, name FROM services WHERE id = ?", (service_id,))
            service = c.fetchone()
            
            if not service:
                send(chat_id, "❌ الخدمة غير موجودة")
                del user_states[user_id]
                return
            
            price, min_qty, max_qty, service_name = service
            
            if quantity < min_qty:
                send(chat_id, f"❌ الحد الأدنى: {min_qty:,}")
                return
            
            if quantity > max_qty:
                send(chat_id, f"❌ الحد الأقصى: {max_qty:,}")
                return
            
            total_price = price * quantity
            
            c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            user_balance = c.fetchone()[0]
            
            if user_balance < total_price:
                send(chat_id, f"""❌ رصيدك غير كافي

💰 السعر الإجمالي: {total_price:,.2f} USD
💳 رصيدك الحالي: {user_balance:,.2f} USD""")
                del user_states[user_id]
                return
            
            user_states[user_id] = f'order_link_{service_id}_{quantity}_{total_price}'
            send(chat_id, f"""📝 <b>إدخال الرابط/المعلومات</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📦 الخدمة:</b> {service_name}
<b>🔢 الكمية:</b> {quantity:,}
<b>💰 السعر الإجمالي:</b> {total_price:,.2f} USD
<b>━━━━━━━━━━━━━━━</b>

<b>✍️ أرسل الرابط أو المعلومات المطلوبة:</b>
- رابط الحساب
- رقم الهاتف
- يوزرنيم
- أو أي معلومات مطلوبة""")
            return
        
        elif state.startswith('order_link_'):
            parts = state.split('_')
            service_id = parts[2]
            quantity = int(parts[3])
            total_price = float(parts[4])
            link = text.strip()
            
            c.execute("SELECT name FROM services WHERE id = ?", (service_id,))
            service_name = c.fetchone()[0]
            
            # إنشاء الفاتورة
            invoice_text = f"""🧾 <b>فاتورة الطلب</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📦 الخدمة:</b> {service_name}
<b>🔢 الكمية:</b> {quantity:,}
<b>💰 السعر الإجمالي:</b> <b>{total_price:,.2f} USD</b>
<b>🔗 الرابط/المعلومات:</b>
<code>{link[:200]}</code>
<b>━━━━━━━━━━━━━━━</b>
<b>👤 المستخدم:</b> <code>{user_id}</code>
<b>📅 التاريخ:</b> {time.strftime('%Y-%m-%d %H:%M')}
<b>━━━━━━━━━━━━━━━</b>

<b>✅ للتأكيد واضغط "اطلب الآن"</b>"""
            
            buttons = [
                [{"text": "✅ اطلب الآن", "data": f"confirm_{service_id}_{quantity}_{total_price}_{link[:100]}"}],
                [{"text": "❌ إلغاء", "data": "services"}]
            ]
            
            send(chat_id, invoice_text, buttons)
            del user_states[user_id]
            return
        
        elif state == 'broadcast':
            users = c.execute("SELECT user_id FROM users WHERE is_banned = 0").fetchall()
            sent = 0
            
            for u in users:
                if send(u[0], f"📢 <b>إذاعة من الإدارة:</b>\n\n{text}"):
                    sent += 1
                time.sleep(0.02)
            
            send(chat_id, f"✅ تم الإرسال لـ {sent} مستخدم")
            del user_states[user_id]
            return
        
        elif state == 'change_maintenance_msg':
            if len(text) < 5:
                send(chat_id, "❌ الرسالة قصيرة جداً")
                return
            
            c.execute("UPDATE settings SET value = ? WHERE key = 'maintenance_msg'", (text,))
            conn.commit()
            send(chat_id, f"✅ تم تحديث رسالة الصيانة:\n{text}")
            del user_states[user_id]
            return
        
        elif state == 'change_invite_reward':
            try:
                reward = float(text)
                if reward < 0:
                    send(chat_id, "❌ المبلغ يجب أن يكون موجباً")
                    return
                
                c.execute("UPDATE settings SET value = ? WHERE key = 'invite_reward'", (str(reward),))
                conn.commit()
                send(chat_id, f"✅ تم تحديث مكافأة الدعوة إلى: {reward} USD")
            except ValueError:
                send(chat_id, "❌ الرجاء إدخال رقم صحيح")
            finally:
                del user_states[user_id]
            return
        
        elif state.startswith('admin_charge_'):
            target_id = state.split('_')[2]
            if text.isdigit():
                amount = float(text)
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                send(chat_id, f"✅ تم شحن {amount:,.2f} USD للمستخدم {target_id}")
                send(target_id, f"""🎉 <b>تم شحن رصيدك</b>

💰 المبلغ: {amount:,.2f} USD
📅 التاريخ: {time.strftime('%Y-%m-%d %H:%M')}""")
                del user_states[user_id]
            return
        
        elif state.startswith('ban_user_'):
            action = state.split('_')[2]
            target_id = text
            
            if not target_id.isdigit():
                send(chat_id, "❌ آيدي غير صحيح")
                del user_states[user_id]
                return
            
            target_id = int(target_id)
            
            if action == 'ban':
                c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
                send(chat_id, f"✅ تم حظر المستخدم {target_id}")
                send(target_id, "🚫 تم حظرك من البوت من قبل الإدارة")
            else:
                c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
                send(chat_id, f"✅ تم فك حظر المستخدم {target_id}")
                send(target_id, "✅ تم فك حظرك من البوت")
            
            conn.commit()
            del user_states[user_id]
            return
    
    elif text == '/admin' and user_id == ADMIN_ID:
        text_msg, buttons = admin_menu()
        send(chat_id, text_msg, buttons)
    
    elif text.startswith('/charge ') and user_id == ADMIN_ID:
        try:
            parts = text.split()
            if len(parts) == 3:
                target_id = int(parts[1])
                amount = float(parts[2])
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                send(chat_id, f"✅ تم شحن {amount:,.2f} USD للمستخدم {target_id}")
                send(target_id, f"""🎉 <b>تم شحن رصيدك</b>

💰 المبلغ: {amount:,.2f} USD
📅 التاريخ: {time.strftime('%Y-%m-%d %H:%M')}""")
        except:
            send(chat_id, "❌ استخدم: <code>/charge آيدي المبلغ</code>")
    
    elif text == '/start':
        handle_start(chat_id, user_id, "")

def handle_callback(chat_id, message_id, user_id, data):
    if is_maintenance() and user_id != ADMIN_ID:
        send(chat_id, get_maintenance_msg())
        return
    
    if not check_security(user_id, 'callback'):
        send(chat_id, "🚫 تم حظرك بسبب نشاط مشبوه")
        return
    
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", 
                     json={'callback_query_id': str(message_id)})
    except:
        pass
    
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        send(chat_id, "❌ حسابك غير موجود")
        return
    
    if user[4] == 1:
        send(chat_id, "🚫 تم حظرك من البوت")
        return
    
    if data == "main":
        text, buttons = main_menu(user_id)
        send(chat_id, text, buttons)
    
    elif data == "admin_panel":
        if user[3] == 1:
            text, buttons = admin_menu()
            send(chat_id, text, buttons)
        else:
            send(chat_id, "🚫 ليس لديك صلاحية")
    
    elif data == "services":
        text, buttons = services_menu()
        send(chat_id, text, buttons)
    
    elif data.startswith("cat_"):
        cat_id = data.split('_')[1]
        text, buttons = category_menu(cat_id)
        send(chat_id, text, buttons)
    
    elif data.startswith("service_"):
        service_id = data.split('_')[1]
        text, buttons = service_menu(service_id, user_id)
        send(chat_id, text, buttons)
        user_states[user_id] = f'order_qty_{service_id}'
    
    elif data == "charge":
        text, buttons = charge_menu(user_id)
        send(chat_id, text, buttons)
    
    elif data == "balance":
        balance = user[2]
        send(chat_id, f"""💰 <b>رصيدك الحالي</b>

<b>━━━━━━━━━━━━━━━</b>
<b>🆔 الآيدي:</b> <code>{user_id}</code>
<b>💳 الرصيد:</b> <b>{balance:,.2f} USD</b>
<b>━━━━━━━━━━━━━━━</b>""")
    
    elif data == "support":
        send(chat_id, f"""📞 <b>الدعم الفني</b>

<b>━━━━━━━━━━━━━━━</b>
<b>👤 تواصل مع:</b> @{SUPPORT_USERNAME}
<b>🆔 أرسل له الآيدي:</b> <code>{user_id}</code>
<b>━━━━━━━━━━━━━━━</b>""")
    
    elif data == "invite":
        text, buttons = invite_menu(user_id)
        send(chat_id, text, buttons)
    
    elif data == "my_orders":
        text, buttons = my_orders_menu(user_id)
        send(chat_id, text, buttons)
    
    elif data.startswith("myorders_"):
        page = int(data.split('_')[1])
        text, buttons = my_orders_menu(user_id, page)
        send(chat_id, text, buttons)
    
    elif data == "stats":
        if user[3] == 1:
            total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            banned_users = c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
            total_balance = c.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
            total_orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            pending_orders = c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'").fetchone()[0]
            
            text = f"""📊 <b>إحصائيات النظام</b>

<b>━━━━━━━━━━━━━━━</b>
<b>👥 المستخدمين:</b> {total_users}
<b>🚫 المحظورين:</b> {banned_users}
<b>💰 إجمالي الأرصدة:</b> {total_balance:,.2f} USD
<b>📦 إجمالي الطلبات:</b> {total_orders}
<b>⏳ الطلبات المعلقة:</b> {pending_orders}
<b>━━━━━━━━━━━━━━━</b>"""
            
            send(chat_id, text)
    
    elif data == "users":
        if user[3] == 1:
            users = c.execute("SELECT user_id, username, balance, is_banned FROM users ORDER BY user_id DESC LIMIT 10").fetchall()
            text = "<b>👥 آخر 10 مستخدمين:</b>\n\n"
            for u in users:
                status = "🚫" if u[3] == 1 else "✅"
                username_display = f"@{u[1]}" if u[1] else "بدون"
                text += f"{status} <code>{u[0]}</code> - {username_display}\n💰 {u[2]:,.2f} USD\n<b>━━━━━━</b>\n"
            send(chat_id, text)
    
    elif data == "admin_charge":
        if user[3] == 1:
            send(chat_id, """💰 <b>شحن رصيد لمستخدم</b>

<b>أرسل لي آيدي المستخدم:</b>""")
            user_states[user_id] = "admin_charge_target"
    
    elif data == "ban_user":
        if user[3] == 1:
            buttons = [
                [{"text": "🚫 حظر مستخدم", "data": "ban_action"}, {"text": "✅ فك حظر مستخدم", "data": "unban_action"}],
                [{"text": "🔙 رجوع", "data": "admin_panel"}]
            ]
            send(chat_id, "🚫 <b>إدارة حظر المستخدمين</b>\n\nاختر الإجراء:", buttons)
    
    elif data == "ban_action":
        if user[3] == 1:
            send(chat_id, "🚫 <b>أرسل آيدي المستخدم للحظر:</b>")
            user_states[user_id] = "ban_user_ban"
    
    elif data == "unban_action":
        if user[3] == 1:
            send(chat_id, "✅ <b>أرسل آيدي المستخدم لفك الحظر:</b>")
            user_states[user_id] = "ban_user_unban"
    
    elif data.startswith("adminorders_"):
        page = int(data.split('_')[1])
        text, buttons = manage_orders_menu(page)
        send(chat_id, text, buttons)
    
    elif data == "broadcast":
        if user[3] == 1:
            user_states[user_id] = 'broadcast'
            send(chat_id, "📢 <b>أرسل نص الإذاعة:</b>")
    
    elif data == "manage_services":
        if user[3] == 1:
            text, buttons = manage_services_menu()
            send(chat_id, text, buttons)
    
    elif data == "manage_categories":
        if user[3] == 1:
            text, buttons = manage_categories_menu()
            send(chat_id, text, buttons)
    
    elif data == "add_category":
        if user[3] == 1:
            user_states[user_id] = 'add_category_'
            send(chat_id, "➕ <b>أرسل اسم القسم الجديد:</b>")
    
    elif data.startswith("add_service"):
        if user[3] == 1:
            if '_' in data:
                cat_id = data.split('_')[2]
                user_states[user_id] = f'add_service_{cat_id}'
                send(chat_id, """➕ <b>إضافة خدمة جديدة</b>

<b>أرسل البيانات بالتنسيق:</b>
<code>اسم الخدمة
السعر (مثال: 0.50)
الحد الأدنى (مثال: 100)
الحد الأقصى (مثال: 10000)
(اختياري) وصف الخدمة</code>

<b>مثال:</b>
<code>متابعين انستغرام
0.30
100
5000
متابعين حقيقيين بجودة عالية</code>""")
            else:
                c.execute("SELECT id, name FROM categories")
                categories = c.fetchall()
                
                if not categories:
                    send(chat_id, "❌ لا توجد أقسام، أضف قسم أولاً")
                    return
                
                buttons = []
                for cat_id, cat_name in categories:
                    buttons.append([{"text": f"📁 {cat_name}", "data": f"add_service_{cat_id}"}])
                
                buttons.append([{"text": "🔙 رجوع", "data": "manage_services"}])
                
                send(chat_id, "📁 <b>اختر القسم لإضافة الخدمة:</b>", buttons)
    
    elif data == "manage_orders":
        if user[3] == 1:
            text, buttons = manage_orders_menu()
            send(chat_id, text, buttons)
    
    elif data.startswith("confirm_"):
        parts = data.split('_')
        service_id = parts[1]
        quantity = int(parts[2])
        total_price = float(parts[3])
        link = parts[4] if len(parts) > 4 else ""
        
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        user_balance = c.fetchone()[0]
        
        if user_balance < total_price:
            send(chat_id, "❌ رصيدك غير كافي")
            return
        
        # خصم المبلغ
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_price, user_id))
        
        # إنشاء الطلب
        c.execute("""INSERT INTO orders (user_id, service_id, quantity, total_price, link, status) 
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (user_id, service_id, quantity, total_price, link, 'pending'))
        order_id = c.lastrowid
        
        conn.commit()
        
        # إرسال إشعار للمدير
        c.execute("SELECT name FROM services WHERE id = ?", (service_id,))
        service_name = c.fetchone()[0]
        
        alert_text = f"""🆕 <b>طلب جديد #{order_id}</b>

<b>━━━━━━━━━━━━━━━</b>
<b>👤 المستخدم:</b> <code>{user_id}</code>
<b>📦 الخدمة:</b> {service_name}
<b>🔢 الكمية:</b> {quantity:,}
<b>💰 المبلغ:</b> {total_price:,.2f} USD
<b>🔗 الرابط:</b>
<code>{link[:100]}</code>
<b>━━━━━━━━━━━━━━━</b>
<b>📅 التاريخ:</b> {time.strftime('%Y-%m-%d %H:%M')}
<b>━━━━━━━━━━━━━━━</b>"""
        
        send(ADMIN_ID, alert_text)
        
        send(chat_id, f"""✅ <b>تم إرسال طلبك بنجاح!</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📦 رقم الطلب:</b> <code>#{order_id}</code>
<b>💰 المبلغ المخصوم:</b> {total_price:,.2f} USD
<b>💳 رصيدك الجديد:</b> {user_balance - total_price:,.2f} USD
<b>📊 الحالة:</b> ⏳ قيد المراجعة
<b>━━━━━━━━━━━━━━━</b>

<b>📋 تابع قسم "طلباتي" لمعرفة آخر التحديثات على طلبك.</b>""")
    
    elif data == "invite_settings":
        if user[3] == 1:
            text, buttons = invite_settings_menu()
            send(chat_id, text, buttons)
    
    elif data == "change_invite_reward":
        if user[3] == 1:
            user_states[user_id] = 'change_invite_reward'
            send(chat_id, "💰 <b>أرسل المبلغ الجديد لمكافأة الدعوة:</b>\n\nمثال: <code>0.10</code>")
    
    elif data == "enable_invite":
        if user[3] == 1:
            c.execute("UPDATE settings SET value = 'true' WHERE key = 'invite_enabled'")
            conn.commit()
            send(chat_id, "✅ تم تفعيل نظام الدعوة")
    
    elif data == "disable_invite":
        if user[3] == 1:
            c.execute("UPDATE settings SET value = 'false' WHERE key = 'invite_enabled'")
            conn.commit()
            send(chat_id, "❌ تم تعطيل نظام الدعوة")
    
    elif data == "invite_stats":
        if user[3] == 1:
            total_invited = c.execute("SELECT COUNT(*) FROM users WHERE invited_by != 0").fetchone()[0]
            total_reward = c.execute("SELECT SUM(balance) FROM users WHERE invited_by != 0").fetchone()[0] or 0
            
            text = f"""📊 <b>إحصائيات الدعوات</b>

<b>━━━━━━━━━━━━━━━</b>
<b>👥 عدد المدعوين:</b> {total_invited}
<b>💰 إجمالي المكافآت:</b> {total_reward:,.2f} USD
<b>━━━━━━━━━━━━━━━</b>"""
            
            send(chat_id, text)
    
    elif data == "settings":
        if user[3] == 1:
            text, buttons = settings_menu()
            send(chat_id, text, buttons)
    
    elif data == "toggle_maintenance":
        if user[3] == 1:
            c.execute("SELECT value FROM settings WHERE key = 'maintenance'")
            current = c.fetchone()[0]
            new_value = 'false' if current == 'true' else 'true'
            status_text = "✅ تم تفعيل" if new_value == 'true' else "❌ تم تعطيل"
            
            c.execute("UPDATE settings SET value = ? WHERE key = 'maintenance'", (new_value,))
            conn.commit()
            send(chat_id, f"{status_text} وضع الصيانة")
    
    elif data == "change_maintenance_msg":
        if user[3] == 1:
            user_states[user_id] = 'change_maintenance_msg'
            send(chat_id, "📝 <b>أرسل رسالة الصيانة الجديدة:</b>")
    
    elif data == "admin_charge_target":
        if user[3] == 1:
            if data.isdigit():
                target_id = int(data)
                user_states[user_id] = f'admin_charge_{target_id}'
                send(chat_id, f"💰 <b>أرسل المبلغ للشحن للمستخدم {target_id}:</b>")
            else:
                send(chat_id, "❌ آيدي غير صحيح")

# النظام الرئيسي
print("🚀 البوت يعمل...")
print("👑 المدير:", ADMIN_ID)
print("💼 الدعم:", SUPPORT_USERNAME)
print("🤖 البوت:", BOT_USERNAME)
print("📱 أرسل /start")

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
                        username = msg['from'].get('username', '')
                        text = msg.get('text', '')
                        
                        if text == '/start':
                            start_param = msg.get('entities', [{}])[0].get('url', '').split('=')[-1] if msg.get('entities') else None
                            handle_start(chat_id, user_id, username, start_param)
                        elif text:
                            handle_text(chat_id, user_id, text)
                    
                    elif 'callback_query' in update:
                        query = update['callback_query']
                        chat_id = query['message']['chat']['id']
                        message_id = query['message']['message_id']
                        user_id = query['from']['id']
                        data = query['data']
                        
                        handle_callback(chat_id, message_id, user_id, data)
        
        time.sleep(0.5)
        
    except Exception as e:
        print("⚠️ خطأ:", str(e)[:50])
        time.sleep(2)

conn.close()
