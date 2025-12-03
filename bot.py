import sqlite3
import requests
import time
import json
from datetime import datetime
import uuid

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
                 is_banned INTEGER DEFAULT 0, invited_by INTEGER DEFAULT 0,
                 invite_code TEXT UNIQUE)''')
    
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
    
    # إعدادات افتراضية
    default_settings = [
        ('maintenance', 'false'),
        ('maintenance_msg', 'البوت تحت الصيانة حالياً ⚠️'),
        ('invite_reward', '0.10'),
        ('invite_enabled', 'true')
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

def create_invoice_pdf(order_data, user_data):
    """إنشاء فاتورة PDF بسيطة"""
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    
    # إضافة ترويسة
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(300, 750, "فاتورة الطلب")
    
    # معلومات الفاتورة
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 700, f"رقم الفاتورة: #{order_data['order_id']}")
    pdf.drawString(50, 680, f"تاريخ الفاتورة: {order_data['date']}")
    
    # معلومات العميل
    pdf.drawString(50, 650, "معلومات العميل:")
    pdf.drawString(70, 630, f"رقم العميل: {user_data['user_id']}")
    if user_data['username']:
        pdf.drawString(70, 610, f"اسم المستخدم: @{user_data['username']}")
    
    # معلومات الخدمة
    pdf.drawString(50, 580, "تفاصيل الخدمة:")
    pdf.drawString(70, 560, f"الخدمة: {order_data['service_name']}")
    pdf.drawString(70, 540, f"الكمية: {order_data['quantity']:,}")
    pdf.drawString(70, 520, f"السعر لكل 1000: ${order_data['price_per_k']}")
    
    # الحسابات
    pdf.drawString(50, 480, "الحسابات:")
    price_per_unit = order_data['price_per_k'] / 1000
    total = price_per_unit * order_data['quantity']
    pdf.drawString(70, 460, f"السعر للوحدة: ${price_per_unit:.4f}")
    pdf.drawString(70, 440, f"المجموع قبل الضريبة: ${total:.2f}")
    pdf.drawString(70, 420, f"الإجمالي: ${total:.2f}")
    
    # ملاحظات
    pdf.drawString(50, 380, "ملاحظات:")
    pdf.drawString(70, 360, "شكراً لتعاملك معنا!")
    
    # تذييل
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawCentredString(300, 50, "هذه الفاتورة تم إنشاؤها تلقائياً")
    
    pdf.save()
    buffer.seek(0)
    return buffer

def send_pdf_invoice(chat_id, pdf_buffer, filename="invoice.pdf"):
    """إرسال ملف PDF"""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
        files = {'document': (filename, pdf_buffer, 'application/pdf')}
        data = {'chat_id': chat_id}
        response = requests.post(url, files=files, data=data)
        return response.status_code == 200
    except:
        return False

# القوائم
def main_menu(chat_id, user_id):
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

def services_menu(chat_id):
    c.execute("SELECT id, name FROM categories ORDER BY position")
    categories = c.fetchall()
    
    text = "🛍️ <b>خدمات المتجر</b>\n\n📁 اختر القسم:"
    
    if not categories:
        text = "📭 لا توجد أقسام حالياً"
        keyboard = {'inline_keyboard': [[{'text': '🔙 رجوع', 'callback_data': 'main'}]]}
    else:
        keyboard = {'inline_keyboard': []}
        for cat_id, cat_name in categories:
            keyboard['inline_keyboard'].append([{'text': f'📁 {cat_name}', 'callback_data': f'cat_{cat_id}'}])
        
        keyboard['inline_keyboard'].append([{'text': '🔙 رجوع', 'callback_data': 'main'}])
    
    send_message(chat_id, text, keyboard)

def category_menu(chat_id, cat_id):
    c.execute("SELECT name FROM categories WHERE id = ?", (cat_id,))
    cat = c.fetchone()
    
    if not cat:
        services_menu(chat_id)
        return
    
    c.execute("SELECT id, name, price_per_k FROM services WHERE category_id = ?", (cat_id,))
    services = c.fetchall()
    
    text = f"🛍️ <b>قسم {cat[0]}</b>\n\n📦 اختر الخدمة:"
    
    if not services:
        text += "\n\n📭 لا توجد خدمات في هذا القسم"
        keyboard = {'inline_keyboard': [[{'text': '🔙 رجوع', 'callback_data': 'services'}]]}
    else:
        keyboard = {'inline_keyboard': []}
        for service_id, service_name, price_per_k in services:
            btn_text = f"📦 {service_name[:20]} - {price_per_k} USD/1000"
            keyboard['inline_keyboard'].append([{'text': btn_text, 'callback_data': f'service_{service_id}'}])
        
        keyboard['inline_keyboard'].append([
            {'text': '🔙 رجوع', 'callback_data': 'services'},
            {'text': '🏠 الرئيسية', 'callback_data': 'main'}
        ])
    
    send_message(chat_id, text, keyboard)

def service_menu(chat_id, user_id, service_id):
    c.execute("""SELECT s.name, s.price_per_k, s.min_order, s.max_order, s.description, c.name 
                 FROM services s 
                 JOIN categories c ON s.category_id = c.id 
                 WHERE s.id = ?""", (service_id,))
    service = c.fetchone()
    
    if not service:
        send_message(chat_id, "❌ الخدمة غير موجودة")
        return
    
    name, price_per_k, min_order, max_order, description, cat_name = service
    
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance_result = c.fetchone()
    balance = balance_result[0] if balance_result else 0
    
    desc_text = f"\n📝 {description}" if description else ""
    
    text = f"""🛒 <b>تفاصيل الخدمة</b>

━━━━━━━━━━━━━━━
📦 الخدمة: {name}
📁 القسم: {cat_name}
💰 السعر: <b>{price_per_k} USD</b> لكل 1000
🔢 الحد الأدنى: {min_order:,}
🔢 الحد الأقصى: {max_order:,}{desc_text}
━━━━━━━━━━━━━━━
💳 رصيدك: <b>{balance:,.2f} USD</b>
━━━━━━━━━━━━━━━

✍️ أرسل الكمية المطلوبة ({min_order:,} - {max_order:,}):"""
    
    send_message(chat_id, text)
    
    # حفظ حالة المستخدم
    user_states[user_id] = {'type': 'order_qty', 'service_id': service_id}

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
    
    # إرسال القائمة الرئيسية
    main_menu(chat_id, user_id)

def process_order_qty(user_id, chat_id, text):
    if user_id not in user_states or user_states[user_id]['type'] != 'order_qty':
        return
    
    service_id = user_states[user_id]['service_id']
    
    c.execute("SELECT name, price_per_k, min_order, max_order FROM services WHERE id = ?", (service_id,))
    service = c.fetchone()
    
    if not service:
        send_message(chat_id, "❌ الخدمة غير موجودة")
        if user_id in user_states:
            del user_states[user_id]
        return
    
    name, price_per_k, min_order, max_order = service
    
    try:
        quantity = int(text)
    except:
        send_message(chat_id, "❌ الرجاء إدخال رقم صحيح")
        return
    
    if quantity < min_order:
        send_message(chat_id, f"❌ الحد الأدنى: {min_order:,}")
        return
    
    if quantity > max_order:
        send_message(chat_id, f"❌ الحد الأقصى: {max_order:,}")
        return
    
    # حساب السعر
    price_per_unit = price_per_k / 1000
    total_price = price_per_unit * quantity
    
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance_result = c.fetchone()
    balance = balance_result[0] if balance_result else 0
    
    if balance < total_price:
        send_message(chat_id, f"""❌ رصيدك غير كافي

💰 المطلوب: {total_price:,.2f} USD
💳 رصيدك: {balance:,.2f} USD""")
        
        if user_id in user_states:
            del user_states[user_id]
        return
    
    user_states[user_id] = {
        'type': 'order_link',
        'service_id': service_id,
        'quantity': quantity,
        'total_price': total_price,
        'price_per_k': price_per_k
    }
    
    send_message(chat_id, f"""📝 <b>إدخال الرابط/المعلومات</b>

━━━━━━━━━━━━━━━
📦 الخدمة: {name}
🔢 الكمية: {quantity:,}
💰 السعر لكل 1000: {price_per_k} USD
💰 السعر الإجمالي: {total_price:,.2f} USD
━━━━━━━━━━━━━━━

✍️ أرسل الرابط أو المعلومات المطلوبة:""")

def process_order_link(user_id, chat_id, link):
    if user_id not in user_states or user_states[user_id]['type'] != 'order_link':
        return
    
    data = user_states[user_id]
    link = link.strip()
    
    # التحقق من الرصيد مرة أخرى
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance_result = c.fetchone()
    balance = balance_result[0] if balance_result else 0
    
    if balance < data['total_price']:
        send_message(chat_id, "❌ رصيدك غير كافي")
        if user_id in user_states:
            del user_states[user_id]
        return
    
    # عرض الفاتورة للموافقة
    c.execute("SELECT name FROM services WHERE id = ?", (data['service_id'],))
    service_name_result = c.fetchone()
    service_name = service_name_result[0] if service_name_result else "غير معروف"
    
    invoice_text = f"""🧾 <b>فاتورة الطلب</b>

━━━━━━━━━━━━━━━
📦 الخدمة: {service_name}
📊 السعر/1000: {data['price_per_k']} USD
🔢 الكمية: {data['quantity']:,}
💰 السعر الإجمالي: <b>{data['total_price']:,.2f} USD</b>
🔗 الرابط: {link[:100]}
━━━━━━━━━━━━━━━
👤 المستخدم: <code>{user_id}</code>
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━
💳 الرصيد قبل: {balance:,.2f} USD
💳 الرصيد بعد: {balance - data['total_price']:,.2f} USD
━━━━━━━━━━━━━━━

✅ للتأكيد واضغط "اطلب الآن" """
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '✅ اطلب الآن', 'callback_data': f'confirm_{data["service_id"]}_{data["quantity"]}_{data["total_price"]}_{link[:100]}'}],
            [{'text': '❌ إلغاء', 'callback_data': 'services'}]
        ]
    }
    
    send_message(chat_id, invoice_text, keyboard)
    
    # حفظ البيانات للمرحلة التالية
    user_states[user_id] = {
        'type': 'pending_confirmation',
        'service_id': data['service_id'],
        'quantity': data['quantity'],
        'total_price': data['total_price'],
        'link': link,
        'price_per_k': data['price_per_k'],
        'service_name': service_name
    }

def confirm_order(user_id, chat_id, data):
    parts = data.split('_')
    service_id = parts[1]
    quantity = int(parts[2])
    total_price = float(parts[3])
    link = parts[4] if len(parts) > 4 else ""
    
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance_result = c.fetchone()
    balance = balance_result[0] if balance_result else 0
    
    if balance < total_price:
        send_message(chat_id, "❌ رصيدك غير كافي")
        return
    
    # خصم المبلغ
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_price, user_id))
    
    # إنشاء الطلب
    c.execute("""INSERT INTO orders (user_id, service_id, quantity, total_price, link, status) 
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (user_id, service_id, quantity, total_price, link, 'pending'))
    order_id = c.lastrowid
    conn.commit()
    
    # إشعار للمدير
    c.execute("SELECT name FROM services WHERE id = ?", (service_id,))
    service_name_result = c.fetchone()
    service_name = service_name_result[0] if service_name_result else "غير معروف"
    
    alert_text = f"""🆕 طلب جديد #{order_id}

👤 المستخدم: {user_id}
📦 الخدمة: {service_name}
🔢 الكمية: {quantity:,}
💰 المبلغ: {total_price:,.2f} USD
🔗 الرابط: {link[:100]}"""
    
    send_message(ADMIN_ID, alert_text)
    
    # تأكيد للمستخدم مع زر طباعة الفاتورة
    c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    username_result = c.fetchone()
    username = username_result[0] if username_result else None
    
    invoice_data = {
        'order_id': order_id,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'service_name': service_name,
        'quantity': quantity,
        'price_per_k': float(parts[5]) if len(parts) > 5 else 0,
        'total_price': total_price
    }
    
    user_data = {
        'user_id': user_id,
        'username': username
    }
    
    # إنشاء الفاتورة PDF
    try:
        pdf_buffer = create_invoice_pdf(invoice_data, user_data)
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🖨️ طباعة الفاتورة', 'callback_data': f'invoice_{order_id}'}],
                [{'text': '📋 طلباتي', 'callback_data': 'my_orders'}, {'text': '🏠 الرئيسية', 'callback_data': 'main'}]
            ]
        }
        
        send_message(chat_id, f"""✅ تم إرسال طلبك بنجاح!

━━━━━━━━━━━━━━━
📦 رقم الطلب: <code>#{order_id}</code>
💰 المبلغ المخصوم: {total_price:,.2f} USD
💳 رصيدك الجديد: {balance - total_price:,.2f} USD
📊 الحالة: ⏳ قيد المراجعة
━━━━━━━━━━━━━━━

🖨️ يمكنك طباعة الفاتورة من الزر أدناه.""", keyboard)
        
        # إرسال الفاتورة مباشرة
        send_pdf_invoice(chat_id, pdf_buffer, f"invoice_{order_id}.pdf")
        
    except Exception as e:
        send_message(chat_id, f"""✅ تم إرسال طلبك بنجاح!

رقم الطلب: #{order_id}
المبلغ: {total_price:,.2f} USD
الحالة: ⏳ قيد المراجعة""")
    
    if user_id in user_states:
        del user_states[user_id]

def handle_message(user_id, chat_id, text):
    # التحقق من الصيانة
    if get_setting('maintenance') == 'true' and user_id != ADMIN_ID:
        send_message(chat_id, get_setting('maintenance_msg'))
        return
    
    # التحقق من الحظر
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if user and user[0] == 1:
        send_message(chat_id, "🚫 تم حظرك من البوت")
        return
    
    # معالجة حالة المستخدم
    if user_id in user_states:
        state = user_states[user_id]
        
        if state['type'] == 'order_qty':
            process_order_qty(user_id, chat_id, text)
            return
        
        elif state['type'] == 'order_link':
            process_order_link(user_id, chat_id, text)
            return
        
        elif state.get('type') == 'add_category':
            if len(text.strip()) < 2:
                send_message(chat_id, "❌ اسم القسم قصير جداً")
                return
            
            c.execute("INSERT INTO categories (name) VALUES (?)", (text.strip(),))
            conn.commit()
            send_message(chat_id, f"✅ تم إضافة القسم: {text}")
            del user_states[user_id]
            return
        
        elif state.get('type') == 'add_service_name':
            c.execute("SELECT id FROM categories WHERE id = ?", (state['cat_id'],))
            if not c.fetchone():
                send_message(chat_id, "❌ القسم غير موجود")
                del user_states[user_id]
                return
            
            user_states[user_id] = {
                'type': 'add_service_price',
                'cat_id': state['cat_id'],
                'name': text.strip()
            }
            send_message(chat_id, "💰 أرسل سعر الخدمة لكل 1000 (مثال: 1.00):")
            return
        
        elif state.get('type') == 'add_service_price':
            try:
                price = float(text)
                user_states[user_id] = {
                    'type': 'add_service_min',
                    'cat_id': state['cat_id'],
                    'name': state['name'],
                    'price': price
                }
                send_message(chat_id, "🔢 أرسل الحد الأدنى للطلب (مثال: 100):")
            except:
                send_message(chat_id, "❌ سعر غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'add_service_min':
            try:
                min_order = int(text)
                user_states[user_id] = {
                    'type': 'add_service_max',
                    'cat_id': state['cat_id'],
                    'name': state['name'],
                    'price': state['price'],
                    'min_order': min_order
                }
                send_message(chat_id, "🔢 أرسل الحد الأقصى للطلب (مثال: 10000):")
            except:
                send_message(chat_id, "❌ رقم غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'add_service_max':
            try:
                max_order = int(text)
                
                c.execute("""INSERT INTO services (category_id, name, price_per_k, min_order, max_order) 
                             VALUES (?, ?, ?, ?, ?)""",
                          (state['cat_id'], state['name'], state['price'], state['min_order'], max_order))
                conn.commit()
                
                send_message(chat_id, f"""✅ تم إضافة الخدمة بنجاح

📦 الخدمة: {state['name']}
💰 السعر/1000: {state['price']} USD
🔢 الحد الأدنى: {state['min_order']:,}
🔢 الحد الأقصى: {max_order:,}""")
                
                del user_states[user_id]
            except Exception as e:
                send_message(chat_id, f"❌ خطأ: {str(e)}")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'admin_charge_user':
            if not text.isdigit():
                send_message(chat_id, "❌ آيدي غير صحيح")
                del user_states[user_id]
                return
            
            target_id = int(text)
            user_states[user_id] = {'type': 'admin_charge_amount', 'target_id': target_id}
            send_message(chat_id, f"💰 أرسل المبلغ للشحن للمستخدم {target_id}:")
            return
        
        elif state.get('type') == 'admin_charge_amount':
            try:
                amount = float(text)
                target_id = user_states[user_id]['target_id']
                
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                conn.commit()
                
                send_message(chat_id, f"✅ تم شحن {amount:,.2f} USD للمستخدم {target_id}")
                send_message(target_id, f"🎉 تم شحن رصيدك\nالمبلغ: {amount:,.2f} USD")
                
                del user_states[user_id]
            except:
                send_message(chat_id, "❌ مبلغ غير صحيح")
                del user_states[user_id]
            return
        
        elif state.get('type') == 'change_invite_reward':
            try:
                reward = float(text)
                if reward < 0:
                    send_message(chat_id, "❌ المبلغ يجب أن يكون موجباً")
                    return
                
                c.execute("UPDATE settings SET value = ? WHERE key = 'invite_reward'", (str(reward),))
                conn.commit()
                send_message(chat_id, f"✅ تم تحديث مكافأة الدعوة إلى: {reward} USD")
            except:
                send_message(chat_id, "❌ مبلغ غير صحيح")
            finally:
                del user_states[user_id]
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

def admin_panel(chat_id):
    keyboard = {
        'inline_keyboard': [
            [{'text': '📊 إحصائيات', 'callback_data': 'stats'}],
            [{'text': '👥 المستخدمين', 'callback_data': 'users'}],
            [{'text': '🛍️ إدارة الخدمات', 'callback_data': 'manage_services'}],
            [{'text': '💳 شحن رصيد', 'callback_data': 'admin_charge'}],
            [{'text': '📋 الطلبات', 'callback_data': 'admin_orders'}],
            [{'text': '👥 نظام الدعوة', 'callback_data': 'invite_settings'}],
            [{'text': '⚙️ إعدادات', 'callback_data': 'admin_settings'}],
            [{'text': '🔙 الرئيسية', 'callback_data': 'main'}]
        ]
    }
    send_message(chat_id, "👑 <b>لوحة تحكم المدير</b>", keyboard)

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
    if is_banned == 1:
        send_message(chat_id, "🚫 تم حظرك من البوت")
        return
    
    if data == 'main':
        main_menu(chat_id, user_id)
    
    elif data == 'services':
        services_menu(chat_id)
    
    elif data.startswith('cat_'):
        cat_id = data.split('_')[1]
        category_menu(chat_id, cat_id)
    
    elif data.startswith('service_'):
        service_id = data.split('_')[1]
        service_menu(chat_id, user_id, service_id)
    
    elif data == 'charge':
        text = f"""💰 <b>شحن الرصيد</b>

تواصل مع الدعم: @{SUPPORT_USERNAME}
وأرسل له آيديك: <code>{user_id}</code>"""
        send_message(chat_id, text)
    
    elif data == 'balance':
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance_result = c.fetchone()
        balance = balance_result[0] if balance_result else 0
        send_message(chat_id, f"💰 رصيدك: <b>{balance:,.2f} USD</b>")
    
    elif data == 'invite':
        c.execute("SELECT invite_code FROM users WHERE user_id = ?", (user_id,))
        code_result = c.fetchone()
        invite_code = code_result[0] if code_result else str(uuid.uuid4())[:8]
        
        if not code_result:
            c.execute("UPDATE users SET invite_code = ? WHERE user_id = ?", (invite_code, user_id))
            conn.commit()
        
        link = f"https://t.me/{BOT_USERNAME}?start={invite_code}"
        reward = get_setting('invite_reward')
        
        text = f"""👥 <b>دعوة أصدقاء</b>

💰 مكافأة لكل دعوة: {reward} USD
🔗 رابط دعوتك:
<code>{link}</code>"""
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '📤 مشاركة الرابط', 'url': f"https://t.me/share/url?url={link}&text=انضم%20إلي"}],
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
                     LIMIT 5""", (user_id,))
        orders = c.fetchall()
        
        if orders:
            text = "📋 <b>طلباتك الأخيرة</b>\n\n"
            for order_id, name, qty, price, status in orders:
                status_icon = '✅' if status == 'completed' else '⏳' if status == 'processing' else '❌'
                text += f"{status_icon} #{order_id} - {name[:20]}\n🔢 {qty:,} | 💰 {price:,.2f} USD\n━━━━━━\n"
        else:
            text = "📭 لا توجد طلبات سابقة"
        
        send_message(chat_id, text)
    
    elif data == 'support':
        send_message(chat_id, f"📞 الدعم: @{SUPPORT_USERNAME}\n\n🆔 آيديك: <code>{user_id}</code>")
    
    elif data == 'admin_panel':
        if is_admin != 1:
            send_message(chat_id, "🚫 ليس لديك صلاحية")
            return
        admin_panel(chat_id)
    
    elif data == 'stats':
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
    
    elif data == 'users':
        if is_admin != 1:
            return
        
        c.execute("SELECT user_id, username, balance, is_banned FROM users ORDER BY user_id DESC LIMIT 10")
        users = c.fetchall()
        
        text = "👥 <b>آخر 10 مستخدمين</b>\n\n"
        for u_id, username, balance, banned in users:
            status = "🚫" if banned == 1 else "✅"
            username_display = f"@{username}" if username else "بدون"
            text += f"{status} <code>{u_id}</code> - {username_display}\n💰 {balance:,.2f} USD\n━━━━━━\n"
        
        send_message(chat_id, text)
    
    elif data == 'manage_services':
        if is_admin != 1:
            return
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '📁 إدارة الأقسام', 'callback_data': 'manage_categories'}],
                [{'text': '➕ إضافة خدمة', 'callback_data': 'add_service'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
            ]
        }
        send_message(chat_id, "🛍️ <b>إدارة الخدمات</b>", keyboard)
    
    elif data == 'manage_categories':
        if is_admin != 1:
            return
        
        c.execute("SELECT id, name FROM categories")
        categories = c.fetchall()
        
        text = "📁 <b>الأقسام الحالية</b>\n\n"
        for cat_id, cat_name in categories:
            text += f"• {cat_name}\n<code>cat_{cat_id}</code>\n━━━━━━\n"
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '➕ إضافة قسم', 'callback_data': 'add_category'}],
                [{'text': '🔙 رجوع', 'callback_data': 'manage_services'}]
            ]
        }
        send_message(chat_id, text, keyboard)
    
    elif data == 'add_category':
        if is_admin != 1:
            return
        
        user_states[user_id] = {'type': 'add_category'}
        send_message(chat_id, "➕ أرسل اسم القسم الجديد:")
    
    elif data == 'add_service':
        if is_admin != 1:
            return
        
        c.execute("SELECT id, name FROM categories")
        categories = c.fetchall()
        
        if not categories:
            send_message(chat_id, "❌ لا توجد أقسام، أضف قسم أولاً")
            return
        
        keyboard = {'inline_keyboard': []}
        for cat_id, cat_name in categories:
            keyboard['inline_keyboard'].append([{'text': cat_name, 'callback_data': f'addserv_{cat_id}'}])
        
        keyboard['inline_keyboard'].append([{'text': '🔙 رجوع', 'callback_data': 'manage_services'}])
        
        send_message(chat_id, "📁 اختر قسم لإضافة الخدمة:", keyboard)
    
    elif data.startswith('addserv_'):
        if is_admin != 1:
            return
        
        cat_id = data.split('_')[1]
        user_states[user_id] = {'type': 'add_service_name', 'cat_id': cat_id}
        send_message(chat_id, "➕ أرسل اسم الخدمة الجديدة:")
    
    elif data == 'admin_charge':
        if is_admin != 1:
            return
        
        user_states[user_id] = {'type': 'admin_charge_user'}
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
    
    elif data == 'invite_settings':
        if is_admin != 1:
            return
        
        reward = get_setting('invite_reward')
        
        text = f"""👥 <b>إعدادات نظام الدعوة</b>

💰 مكافأة الدعوة: {reward} USD"""
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '💰 تغيير مكافأة الدعوة', 'callback_data': 'change_invite_reward'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
            ]
        }
        send_message(chat_id, text, keyboard)
    
    elif data == 'change_invite_reward':
        if is_admin != 1:
            return
        
        user_states[user_id] = {'type': 'change_invite_reward'}
        send_message(chat_id, "💰 أرسل المبلغ الجديد لمكافأة الدعوة (مثال: 0.10):")
    
    elif data == 'admin_settings':
        if is_admin != 1:
            return
        
        maintenance = get_setting('maintenance')
        maintenance_status = "✅ مفعل" if maintenance == 'true' else "❌ معطل"
        
        text = f"""⚙️ <b>إعدادات البوت</b>

🔧 وضع الصيانة: {maintenance_status}"""
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🔧 تفعيل/تعطيل الصيانة', 'callback_data': 'toggle_maintenance'}],
                [{'text': '🔙 رجوع', 'callback_data': 'admin_panel'}]
            ]
        }
        send_message(chat_id, text, keyboard)
    
    elif data == 'toggle_maintenance':
        if is_admin != 1:
            return
        
        current = get_setting('maintenance')
        new_value = 'false' if current == 'true' else 'true'
        c.execute("UPDATE settings SET value = ? WHERE key = 'maintenance'", (new_value,))
        conn.commit()
        
        status = "✅ تم تفعيل" if new_value == 'true' else "❌ تم تعطيل"
        send_message(chat_id, f"{status} وضع الصيانة")
    
    elif data.startswith('confirm_'):
        confirm_order(user_id, chat_id, data)
    
    elif data.startswith('invoice_'):
        order_id = data.split('_')[1]
        
        c.execute("""SELECT o.*, s.name, s.price_per_k, u.username 
                     FROM orders o 
                     JOIN services s ON o.service_id = s.id 
                     JOIN users u ON o.user_id = u.user_id 
                     WHERE o.id = ? AND o.user_id = ?""", (order_id, user_id))
        order = c.fetchone()
        
        if order:
            invoice_data = {
                'order_id': order[0],
                'date': order[8],
                'service_name': order[10],
                'quantity': order[3],
                'price_per_k': order[11],
                'total_price': order[4]
            }
            
            user_data = {
                'user_id': user_id,
                'username': order[12]
            }
            
            try:
                pdf_buffer = create_invoice_pdf(invoice_data, user_data)
                send_pdf_invoice(chat_id, pdf_buffer, f"invoice_{order_id}.pdf")
            except:
                send_message(chat_id, "❌ تعذر إنشاء الفاتورة")
        else:
            send_message(chat_id, "❌ الفاتورة غير موجودة")

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
        
        # تشغيل البولينج
        polling_loop()
        
    except KeyboardInterrupt:
        print("إيقاف البوت...")
    except Exception as e:
        print(f"خطأ غير متوقع: {e}")
    finally:
        conn.close()
