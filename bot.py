import sqlite3
import requests
import time

# إعدادات البوت
TOKEN = "8436742877:AAHmlmOKY2iQCGoOt004ruq09tZGderDGMQ"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"

# إعدادات API
API_KEY = "dc99e001ce2aae69452dd09c2c5156bb"
API_URL = "https://fast70.com/api/v2"

# تهيئة قاعدة البيانات
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

# حذف وإعادة إنشاء الجداول
c.execute('DROP TABLE IF EXISTS users')
c.execute('''CREATE TABLE users 
             (user_id INTEGER PRIMARY KEY, username TEXT, 
             balance REAL DEFAULT 0, is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0)''')

# إضافة المدير
c.execute("INSERT INTO users (user_id, username, balance, is_admin) VALUES (?, ?, ?, ?)",
          (ADMIN_ID, "المدير", 100000, 1))
conn.commit()

# جلب الأقسام من API
def get_categories():
    try:
        url = f"{API_URL}?key={API_KEY}&action=services"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            categories = []
            
            if isinstance(data, dict) and 'services' in data:
                for service in data['services']:
                    if 'category' in service:
                        cat = service['category']
                        if cat not in categories:
                            categories.append(cat)
            elif isinstance(data, list):
                for service in data:
                    if isinstance(service, dict) and 'category' in service:
                        cat = service['category']
                        if cat not in categories:
                            categories.append(cat)
            
            return categories[:10] if categories else ["سوشيال ميديا", "يوتيوب", "مواقع", "تطبيقات"]
    except:
        pass
    return ["سوشيال ميديا", "يوتيوب", "مواقع", "تطبيقات"]

# جلب خدمات القسم
def get_services(category):
    try:
        url = f"{API_URL}?key={API_KEY}&action=services"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            services = []
            
            if isinstance(data, dict) and 'services' in data:
                for service in data['services']:
                    if service.get('category') == category:
                        services.append(service)
            elif isinstance(data, list):
                for service in data:
                    if isinstance(service, dict) and service.get('category') == category:
                        services.append(service)
            
            return services[:15] if services else get_default_services()
    except:
        pass
    return get_default_services()

def get_default_services():
    return [
        {"id": 1, "name": "متابعين انستغرام حقيقي", "rate": 1000, "min": 100, "max": 10000},
        {"id": 2, "name": "لايكات انستغرام", "rate": 500, "min": 100, "max": 5000},
        {"id": 3, "name": "مشاهدات يوتيوب", "rate": 300, "min": 1000, "max": 100000}
    ]

# إرسال الرسائل
def send(chat_id, text, buttons=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        
        if buttons:
            import json
            keyboard = {"inline_keyboard": []}
            for row in buttons:
                kb_row = []
                for btn in row:
                    kb_row.append({"text": btn[0], "callback_data": btn[1]})
                keyboard["inline_keyboard"].append(kb_row)
            data['reply_markup'] = json.dumps(keyboard)
        
        requests.post(url, json=data, timeout=5)
        return True
    except:
        return False

# القوائم
def main_menu(user_id):
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        user = (user_id, None, 0, 0, 0)
    
    username = user[1] if user[1] else "مستخدم"
    balance = user[2]
    
    text = f"""👋 <b>أهلاً {username}</b>

<b>━━━━━━━━━━━━━━━</b>
<b>🆔 الآيدي:</b> <code>{user_id}</code>
<b>💰 الرصيد:</b> <b>{balance:,} UADT</b>
<b>━━━━━━━━━━━━━━━</b>

<b>📌 اختر من القائمة:</b>"""
    
    buttons = [
        [("🛍️ خدمات", "services"), ("💰 شحن", "charge")],
        [("💳 رصيدي", "balance"), ("📞 دعم", "support")]
    ]
    
    if user[3] == 1:
        buttons.append([("👑 لوحة التحكم", "admin_panel")])
    
    return text, buttons

def admin_menu():
    text = """👑 <b>لوحة تحكم المدير</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📌 اختر القسم:</b>"""
    
    buttons = [
        [("📊 الإحصائيات", "stats"), ("👥 المستخدمين", "users")],
        [("💳 شحن رصيد", "admin_charge"), ("🚫 المحظورين", "banned")],
        [("📢 الإذاعة", "broadcast")],
        [("🔙 الرئيسية", "main")]
    ]
    return text, buttons

def services_menu():
    categories = get_categories()
    
    text = """🛍️ <b>خدمات المتجر</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📁 اختر القسم:</b>"""
    
    buttons = []
    for i, cat in enumerate(categories[:8]):
        buttons.append([(f"📁 {cat}", f"cat_{i}")])
    
    buttons.append([("🔄 تحديث", "refresh_services"), ("🔙 رجوع", "main")])
    
    return text, buttons

def category_menu(cat_index):
    categories = get_categories()
    
    if cat_index >= len(categories):
        return services_menu()
    
    category = categories[cat_index]
    services = get_services(category)
    
    text = f"""🛍️ <b>قسم {category}</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📦 اختر الخدمة:</b>"""
    
    buttons = []
    for service in services[:10]:
        name = service.get('name', 'خدمة')[:25]
        price = service.get('rate', 0)
        service_id = service.get('id', 0)
        buttons.append([(f"📦 {name} - {price:,} UADT", f"service_{service_id}")])
    
    buttons.append([("🔙 رجوع", "services"), ("🏠 الرئيسية", "main")])
    
    return text, buttons

def service_menu(service_id, user_id):
    # البحث عن الخدمة في جميع الأقسام
    service_info = None
    categories = get_categories()
    
    for cat in categories:
        services = get_services(cat)
        for service in services:
            if str(service.get('id')) == str(service_id):
                service_info = service
                break
        if service_info:
            break
    
    if not service_info:
        service_info = {"name": "خدمة غير موجودة", "rate": 0, "min": 1, "max": 100}
    
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user_data = c.fetchone()
    user_balance = user_data[2] if user_data else 0
    
    text = f"""🛒 <b>تفاصيل الخدمة</b>

<b>━━━━━━━━━━━━━━━</b>
<b>📦 الخدمة:</b> {service_info.get('name', 'غير معروف')}
<b>💰 السعر:</b> <b>{service_info.get('rate', 0):,} UADT</b> لكل 1000
<b>🔢 الحد الأدنى:</b> {service_info.get('min', 1):,}
<b>🔢 الحد الأقصى:</b> {service_info.get('max', 100):,}
<b>━━━━━━━━━━━━━━━</b>
<b>💳 رصيدك الحالي:</b> <b>{user_balance:,} UADT</b>
<b>━━━━━━━━━━━━━━━</b>

<b>✍️ أرسل الكمية المطلوبة:</b>"""
    
    buttons = [
        [("🔙 رجوع", "services")],
        [("🏠 الرئيسية", "main")]
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
        [("🔙 رجوع", "main")]
    ]
    
    return text, buttons

# معالجة الأحداث
user_states = {}

def handle_start(chat_id, user_id, username):
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    is_new = False
    if not user:
        is_new = True
        c.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username or ""))
        conn.commit()
    
    # إشعار للمدير فقط للمستخدمين الجدد
    if is_new and user_id != ADMIN_ID:
        send(ADMIN_ID, f"👤 مستخدم جديد\n🆔: {user_id}\n📛: @{username or 'بدون'}")
    
    text, buttons = main_menu(user_id)
    send(chat_id, text, buttons)

def handle_text(chat_id, user_id, text):
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
        
        if state.startswith('charge_'):
            target_id = int(state.split('_')[1])
            if text.isdigit():
                amount = int(text)
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                send(chat_id, f"✅ تم شحن {amount:,} UADT للمستخدم {target_id}")
                send(target_id, f"""🎉 تم شحن رصيدك

💰 المبلغ: {amount:,} UADT""")
                del user_states[user_id]
        
        elif state.startswith('order_'):
            service_id = state.split('_')[1]
            
            if text.isdigit():
                quantity = int(text)
                
                # البحث عن الخدمة
                service_info = None
                categories = get_categories()
                
                for cat in categories:
                    services = get_services(cat)
                    for service in services:
                        if str(service.get('id')) == service_id:
                            service_info = service
                            break
                    if service_info:
                        break
                
                if service_info:
                    price_per_unit = service_info.get('rate', 0)
                    total_price = (price_per_unit * quantity) / 1000
                    
                    if quantity < service_info.get('min', 1):
                        send(chat_id, f"❌ الحد الأدنى: {service_info.get('min', 1):,}")
                        return
                    
                    if quantity > service_info.get('max', 100):
                        send(chat_id, f"❌ الحد الأقصى: {service_info.get('max', 100):,}")
                        return
                    
                    user_balance = user[2]
                    if user_balance < total_price:
                        send(chat_id, f"""❌ رصيدك غير كافي

💰 السعر الإجمالي: {total_price:,.0f} UADT
💳 رصيدك الحالي: {user_balance:,} UADT""")
                        del user_states[user_id]
                        return
                    
                    # عرض تأكيد الطلب
                    text_msg = f"""🛒 تأكيد الطلب

━━━━━━━━━━━━━━━
📦 الخدمة: {service_info.get('name')}
🔢 الكمية: {quantity:,}
💰 السعر الإجمالي: {total_price:,.0f} UADT
━━━━━━━━━━━━━━━
💳 رصيدك قبل: {user_balance:,} UADT
💳 رصيدك بعد: {user_balance - total_price:,.0f} UADT
━━━━━━━━━━━━━━━

✅ هل تريد تأكيد الطلب؟"""
                    
                    buttons = [
                        [("✅ تأكيد الطلب", f"confirm_{service_id}_{quantity}_{total_price}")],
                        [("❌ إلغاء", "main")]
                    ]
                    
                    send(chat_id, text_msg, buttons)
                    del user_states[user_id]
        
        elif state == 'broadcast':
            users = c.execute("SELECT user_id FROM users WHERE is_banned = 0").fetchall()
            sent = 0
            
            for u in users:
                if send(u[0], f"📢 إذاعة من الإدارة:\n\n{text}"):
                    sent += 1
                time.sleep(0.02)
            
            send(chat_id, f"✅ تم الإرسال لـ {sent} مستخدم")
            del user_states[user_id]
    
    elif text == '/admin' and user_id == ADMIN_ID:
        text_msg, buttons = admin_menu()
        send(chat_id, text_msg, buttons)
    
    elif text.startswith('/charge ') and user_id == ADMIN_ID:
        try:
            parts = text.split()
            if len(parts) == 3:
                target_id = int(parts[1])
                amount = int(parts[2])
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                send(chat_id, f"✅ تم شحن {amount:,} UADT للمستخدم {target_id}")
                send(target_id, f"🎉 تم شحن رصيدك\n💰 المبلغ: {amount:,} UADT")
        except:
            send(chat_id, "❌ استخدم: /charge آيدي المبلغ")
    
    elif text == '/start':
        username = ""
        handle_start(chat_id, user_id, username)

def handle_callback(chat_id, message_id, user_id, data):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", 
                     json={'callback_query_id': str(user_id)})
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
        cat_index = int(data.split('_')[1])
        text, buttons = category_menu(cat_index)
        send(chat_id, text, buttons)
    
    elif data.startswith("service_"):
        service_id = data.split('_')[1]
        text, buttons = service_menu(service_id, user_id)
        send(chat_id, text, buttons)
        user_states[user_id] = f'order_{service_id}'
    
    elif data == "charge":
        text, buttons = charge_menu(user_id)
        send(chat_id, text, buttons)
    
    elif data == "balance":
        send(chat_id, f"""💰 رصيدك الحالي

🆔 الآيدي: <code>{user_id}</code>
💳 الرصيد: <b>{user[2]:,} UADT</b>""")
    
    elif data == "support":
        send(chat_id, f"""📞 الدعم الفني

👤 تواصل مع: @{SUPPORT_USERNAME}
🆔 أرسل له الآيدي: <code>{user_id}</code>""")
    
    elif data == "stats":
        if user[3] == 1:
            total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            banned_users = c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
            total_balance = c.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
            
            text = f"""📊 إحصائيات النظام

👥 المستخدمين: {total_users}
🚫 المحظورين: {banned_users}
💰 إجمالي الأرصدة: {total_balance:,} UADT"""
            
            send(chat_id, text)
    
    elif data == "users":
        if user[3] == 1:
            users = c.execute("SELECT user_id, username, balance, is_banned FROM users ORDER BY user_id DESC LIMIT 10").fetchall()
            text = "👥 آخر 10 مستخدمين:\n\n"
            for u in users:
                status = "🚫" if u[3] == 1 else "✅"
                username_display = f"@{u[1]}" if u[1] else "بدون"
                text += f"{status} {u[0]} - {username_display}\n💰 {u[2]:,} UADT\n\n"
            send(chat_id, text)
    
    elif data == "admin_charge":
        if user[3] == 1:
            send(chat_id, """💰 شحن رصيد لمستخدم

استخدم الأمر:
<code>/charge آيدي_المستخدم المبلغ</code>

مثال:
<code>/charge 123456 5000</code>""")
    
    elif data == "banned":
        if user[3] == 1:
            users = c.execute("SELECT user_id, username FROM users WHERE is_banned = 1").fetchall()
            if users:
                text = "🚫 المستخدمين المحظورين:\n\n"
                for u in users:
                    text += f"👤 {u[0]} - @{u[1] or 'بدون'}\n"
                send(chat_id, text)
            else:
                send(chat_id, "✅ لا يوجد مستخدمين محظورين")
    
    elif data.startswith("charge_"):
        if user[3] == 1:
            target_id = int(data.split('_')[1])
            user_states[user_id] = f'charge_{target_id}'
            send(chat_id, f"💰 أرسل المبلغ للشحن للمستخدم {target_id}:")
    
    elif data == "broadcast":
        if user[3] == 1:
            user_states[user_id] = 'broadcast'
            send(chat_id, "📢 أرسل نص الإذاعة:")
    
    elif data == "refresh_services":
        text, buttons = services_menu()
        send(chat_id, text, buttons)
    
    elif data.startswith("confirm_"):
        parts = data.split('_')
        service_id = parts[1]
        quantity = int(parts[2])
        total_price = float(parts[3])
        
        user_balance = user[2]
        if user_balance < total_price:
            send(chat_id, "❌ رصيدك غير كافي")
            return
        
        # خصم المبلغ
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_price, user_id))
        conn.commit()
        
        send(chat_id, f"""✅ تم تنفيذ طلبك بنجاح

🔢 الكمية: {quantity:,}
💰 المبلغ المخصوم: {total_price:,.0f} UADT
💳 رصيدك الجديد: {user_balance - total_price:,.0f} UADT""")

# النظام الرئيسي
print("🚀 البوت يعمل...")
print("👑 المدير:", ADMIN_ID)
print("💼 الدعم:", SUPPORT_USERNAME)
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
                            handle_start(chat_id, user_id, username)
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
