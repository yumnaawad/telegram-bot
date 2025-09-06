import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackQueryHandler, ContextTypes
)

# -----------------------------
# إعداد المتغيرات
# -----------------------------
TOKEN = os.getenv("BOT_TOKEN")  # ضع التوكن في Environment Variables على Render
LOGIN = 1
SESSIONS_FILE = "sessions.json"
WORKSHEETS_PATH = "worksheets"

# -----------------------------
# قاعدة بيانات الجلسات
# -----------------------------
try:
    with open(SESSIONS_FILE, "r") as f:
        logged_in_users = json.load(f)
except FileNotFoundError:
    logged_in_users = {}

def save_sessions():
    with open(SESSIONS_FILE, "w") as f:
        json.dump(logged_in_users, f)

# -----------------------------
# Google Sheets
# -----------------------------
def load_student_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("bot_reader.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("StudentsDB").sheet1
    records = sheet.get_all_records()

    data = {}
    for row in records:
        password = str(row['password'])
        data[password] = {
            "name": row['name'],
            "class": row['class'],
            "grades": {
                "امتحان": json.loads(row['grades_exam']),
                "مذاكرة": json.loads(row['grades_test']),
                "سبر": json.loads(row['grades_quiz'])
            },
            "notes": row['notes'],
            "schedule": row['schedule'],
            "attendance": row['attendance'],
            "duties": row['duties'],
            "photo": row['photo'],
            "announcements": row['announcements']
        }
    return data

def get_student_by_chat_id(chat_id):
    students_db = load_student_data()
    user = logged_in_users.get(str(chat_id))
    if not user:
        return None
    return students_db.get(user["password"])

# -----------------------------
# البوت
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    if user_id in logged_in_users:
        student = get_student_by_chat_id(update.effective_chat.id)
        if student:
            await show_main_menu(update, context, student)
        else:
            await update.message.reply_text("⚠️ حدث خطأ أثناء جلب البيانات. أعد تسجيل الدخول.")
    else:
        await update.message.reply_text("مرحباً! سجل الدخول باستخدام /login")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل كلمة المرور الخاصة بك:")
    return LOGIN

async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    user_id = str(update.effective_chat.id)
    students_db = load_student_data()

    if password in students_db:
        logged_in_users[user_id] = {"password": password}
        save_sessions()
        await update.message.reply_text("✅ تم تسجيل الدخول بنجاح!")
        await show_main_menu(update, context, students_db[password])
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ كلمة المرور غير صحيحة. حاول مرة أخرى.")
        return LOGIN

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

# -----------------------------
# القائمة الرئيسية
# -----------------------------
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("حول المدرسة", callback_data="about")],
        [InlineKeyboardButton("🗓️ برنامج الدوام", callback_data="schedule")],
        [InlineKeyboardButton("🗓️ الواجبات", callback_data="duties")],
        [InlineKeyboardButton("📄 أوراق العمل", callback_data="worksheets")],
        [InlineKeyboardButton("📢 الإعلانات", callback_data="announcements")],
        [InlineKeyboardButton("📊 العلامات", callback_data="grades")],
        [InlineKeyboardButton("📝 الملاحظات", callback_data="notes")],
        [InlineKeyboardButton("✅ الدوام", callback_data="attendance")],
        [InlineKeyboardButton("📸 الصوري", callback_data="photo")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, student):
    message = f"مرحباً {student.get('name', 'بدون اسم')}! اختر من القائمة:"
    if update.message:
        await update.message.reply_text(message, reply_markup=main_keyboard())
    else:
        await update.callback_query.edit_message_text(message, reply_markup=main_keyboard())

# -----------------------------
# التعامل مع الأزرار
# -----------------------------
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.message.chat.id)
    student = get_student_by_chat_id(user_id)
    if not student:
        await query.edit_message_text("يجب تسجيل الدخول أولاً باستخدام /login")
        return

    data = query.data

    if data == "about":
        text = "مدرسة الأفق الجديد روضة - ابتدائي - إعدادي\nعنوان المدرسة: سهل الزبداني مفرق مضايا\nللتواصل: 0947180707"
        await query.edit_message_text(text=text, reply_markup=main_keyboard())

    elif data == "schedule":
        await query.edit_message_text(f"✅ برنامج الدوام:\n{student['schedule']}", reply_markup=main_keyboard())

    elif data == "duties":
        await query.edit_message_text(f"✅ واجباتك:\n{student['duties']}", reply_markup=main_keyboard())

    elif data == "notes":
        await query.edit_message_text(f"✅ الملاحظات:\n{student['notes']}", reply_markup=main_keyboard())

    elif data == "announcements":
        await query.edit_message.edit_message_text(f"📢 الإعلانات:\n{student.get('announcements','')}", reply_markup=main_keyboard())

    elif data == "photo":
        await query.edit_message_text(f"{student['photo']}", reply_markup=main_keyboard())

    elif data == "worksheets":
        subjects = [d for d in os.listdir(WORKSHEETS_PATH) if os.path.isdir(os.path.join(WORKSHEETS_PATH, d))]
        if not subjects:
            await query.edit_message_text("⚠️ لا توجد مواد في أوراق العمل.", reply_markup=main_keyboard())
            return
        keyboard = [[InlineKeyboardButton(subj, callback_data=f"worksheet_subject:{subj}")] for subj in subjects]
        await query.edit_message_text("اختر المادة:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("worksheet_subject:"):
        subject = data.split(":", 1)[1]
        subject_path = os.path.join(WORKSHEETS_PATH, subject)
        files = [f for f in os.listdir(subject_path) if f.endswith(".pdf")]
        keyboard = [[InlineKeyboardButton(f, callback_data=f"worksheet_file:{subject}:{f}")] for f in files]
        await query.edit_message_text(f"اختر ملف:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("worksheet_file:"):
        parts = data.split(":", 2)
        subject = parts[1]
        filename = parts[2]
        file_path = os.path.join(WORKSHEETS_PATH, subject, filename)
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                await context.bot.send_document(chat_id=query.message.chat.id, document=InputFile(f), filename=filename)
        await show_main_menu(update, context, student)

    elif data == "grades":
        keyboard = [
            [InlineKeyboardButton("📘 الامتحانات", callback_data="grades_exam")],
            [InlineKeyboardButton("📗 المذاكرات", callback_data="grades_test")],
            [InlineKeyboardButton("📙 السبر", callback_data="grades_quiz")]
        ]
        await query.edit_message_text("اختر نوع التقييم:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("grades_"):
        type_map = {"grades_exam": "امتحان", "grades_test": "مذاكرة", "grades_quiz": "سبر"}
        grade_type = type_map[data]
        grades = student['grades'].get(grade_type, {})
        if grades:
            text = "\n".join([f"{subj}: {val}" for subj, val in grades.items()])
        else:
            text = "لا توجد علامات متاحة."
        await query.edit_message_text(f"📊 {grade_type}:\n{text}", reply_markup=main_keyboard())

# -----------------------------
# Flask + Webhook
# -----------------------------
flask_app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# إضافة Handlers
login_conv = ConversationHandler(
    entry_points=[CommandHandler("login", login)],
    states={LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)]},
    fallbacks=[CommandHandler("cancel", cancel)]
)
application.add_handler(CommandHandler("start", start))
application.add_handler(login_conv)
application.add_handler(CallbackQueryHandler(handle_button))

# Route Webhook ثابت
@flask_app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

@flask_app.route("/")
def home():
    return "بوت تلغرام شغال ✅"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
