import os
import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import pygsheets
import nest_asyncio
import asyncio
from telegram import InputFile

TOKEN = "8115750679:AAF3bVGEGXRICAPPLlz2UXKsfH9xvEwIPjo"
LOGIN = 1
SESSIONS_FILE = "sessions.json"

# إعداد Google Sheets باستخدام pygsheets
gc = pygsheets.authorize(service_file='bot_reader.json')  # حدد المسار إلى ملف الـ JSON الخاص بك
SPREADSHEET_ID = '1AtlAxRYjypE6meQ2Jztu9GV4k8ucP-Ndc1DJV-a8g10'
worksheet = gc.open_by_key(SPREADSHEET_ID).sheet1  # نستخدم الشيت الأول

keyboard = [
    [InlineKeyboardButton("حول مدرسة الأفق الجديد", callback_data="about")],
    [InlineKeyboardButton("🗓️ برنامج الدوام", callback_data="schedule")],
    [InlineKeyboardButton("🗓️الواجبات", callback_data="duties")],
    [InlineKeyboardButton("📄 أوراق العمل", callback_data="worksheets")],
    [InlineKeyboardButton("📢 الإعلانات", callback_data="announcements")],
    [InlineKeyboardButton("📊العلامات", callback_data="grades")],
    [InlineKeyboardButton("📝 الملاحظات", callback_data="notes")],
    [InlineKeyboardButton("✅ الدوام", callback_data="attendance")],
    [InlineKeyboardButton("📸 الصوري", callback_data="photo")]
]
reply_markup = InlineKeyboardMarkup(keyboard)

# تحميل الجلسات
try:
    with open(SESSIONS_FILE, "r") as f:
        logged_in_users = json.load(f)
except FileNotFoundError:
    logged_in_users = {}

# تحميل بيانات الطلاب من Google Sheets باستخدام pygsheets
def load_student_data():
    students = {}
    rows = worksheet.get_all_values()  # الحصول على جميع القيم من الشيت
    for row in rows[1:]:  # تخطي رأس الجدول
        if len(row) >= 11:  # تأكد من أن السطر يحتوي على البيانات الكافية
            password = row[0]
            students[password] = {
                "name": row[1],
                "class": row[2],
                "grades": {
                    "امتحان": json.loads(row[3]),
                    "مذاكرة": json.loads(row[4]),
                    "سبر": json.loads(row[5])
                },
                "notes": row[6],
                "schedule": row[7],
                "attendance": row[8],
                "duties": row[9],
                "photo": row[10],
                "announcements": row[11] if len(row) > 11 else "لا توجد إعلانات"
            }
    return students

# استرجاع بيانات الطالب بناءً على chat_id
def get_student_by_chat_id(chat_id):
    students_db = load_student_data()
    user = logged_in_users.get(str(chat_id))
    if not user:
        return None
    return students_db.get(user["password"])

# حفظ الجلسات
def save_sessions():
    with open(SESSIONS_FILE, "w") as f:
        json.dump(logged_in_users, f)

# بدء البوت
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

# تسجيل الدخول
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل كلمة المرور الخاصة بك:")
    return LOGIN

async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    user_id = str(update.effective_chat.id)
    students_db = load_student_data()

    if password in students_db:
        logged_in_users[user_id] = {
            "password": password
        }
        save_sessions()
        await update.message.reply_text("✅ تم تسجيل الدخول بنجاح!")
        await show_main_menu(update, context, students_db[password])
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ كلمة المرور غير صحيحة. حاول مرة أخرى.")
        return LOGIN

# القائمة الرئيسية
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, student):
    message = f"مرحباً {student.get('name', 'بدون اسم')}! اختر من القائمة:"
    if update.message:
        await update.message.reply_text(message, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup)

# التعامل مع الأزرار
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
        await query.edit_message_text(f"مدرسة الأفق الجديد... للتواصل: 0947180707", reply_markup=reply_markup)
    elif data == "schedule":
        await query.edit_message_text(f"✅ برنامج الدوام: {student['schedule']}", reply_markup=reply_markup)
    elif data == "duties":
        await query.edit_message_text(f"✅ واجباتك لليوم: {student['duties']}", reply_markup=reply_markup)
    elif data == "notes":
        await query.edit_message_text(f"✅ ملاحظات: {student['notes']}", reply_markup=reply_markup)
    elif data == "attendance":
        await query.edit_message_text(f"✅ نسبة الحضور: {student['attendance']}", reply_markup=reply_markup)
    elif data == "announcements":
        await query.edit_message_text(f"📢 الإعلانات: {student['announcements']}", reply_markup=reply_markup)
    elif data == "grades":
        keyboard = [
            [InlineKeyboardButton("📘 الامتحانات", callback_data="grades_exam")],
            [InlineKeyboardButton("📗 المذاكرات", callback_data="grades_test")],
            [InlineKeyboardButton("📙 السبر", callback_data="grades_quiz")]
        ]
        await query.edit_message_text("📊 اختر نوع التقييم:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("grades_") and ":" not in data:
        type_map = {"grades_exam": "امتحان", "grades_test": "مذاكرة", "grades_quiz": "سبر"}
        grade_type = type_map[data]
        grades = student['grades'].get(grade_type, {})
        keyboard = [
            [InlineKeyboardButton(subj, callback_data=f"{data}:{subj}")] for subj in grades
        ]
        await query.edit_message_text(f"📚 اختر المادة ({grade_type}):", reply_markup=InlineKeyboardMarkup(keyboard))
    elif ":" in data and data.startswith("grades_"):
        type_key, subject = data.split(":")
        grade_type = {"grades_exam": "امتحان", "grades_test": "مذاكرة", "grades_quiz": "سبر"}.get(type_key, "غير معروف")
        grade = student['grades'].get(grade_type, {}).get(subject)
        if grade is not None:
            await query.edit_message_text(f"📌 علامتك في {subject} ({grade_type}): {grade}", reply_markup=reply_markup)
        else:
            await query.edit_message_text(f"❌ لا توجد علامة في {subject} ({grade_type})", reply_markup=reply_markup)
    elif data == "photo":
        try:
            await query.edit_message_text(f"{student['photo']}", reply_markup=reply_markup)
        except Exception as e:
            print("Error sending photo:", e)
            await query.edit_message_text("⚠️ تعذر إرسال الصورة.", reply_markup=reply_markup)

# إلغاء
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END


# تشغيل البوت
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    login_conv = ConversationHandler(
        entry_points=[CommandHandler("login", login)],
        states={LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(login_conv)
    app.add_handler(CallbackQueryHandler(handle_button))

    await app.run_polling()

asyncio.run(main())
