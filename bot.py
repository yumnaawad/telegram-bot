import os
import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from google.oauth2 import service_account
from googleapiclient.discovery import build
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import nest_asyncio
import asyncio
nest_asyncio.apply()
from telegram import InputFile


TOKEN = "8115750679:AAF3bVGEGXRICAPPLlz2UXKsfH9xvEwIPjo"
LOGIN = 1
SESSIONS_FILE = "sessions.json"

# إعداد الـ Google Sheets API
SERVICE_ACCOUNT_FILE = "schoolbot.json"  # وضع المسار إلى ملف البيانات
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = '1AtlAxRYjypE6meQ2Jztu9GV4k8ucP-Ndc1DJV-a8g10' # معرف الشيت الذي تريد الوصول إليه
RANGE_NAME = 'Sheet1!A1:Z1000'  # النطاق الذي تريد الوصول إليه (يمكن تعديله)

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

# تحميل بيانات الطلاب من Google Sheets
def load_student_data():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=credentials)

    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    rows = result.get('values', [])

    students = {}
    for row in rows[1:]:  # تخطي رأس الجدول
        if len(row) >= 11:  # تأكد من أن السطر يحتوي على البيانات الكافية (password, name, class, grades_exam, grades_test, grades_quiz, notes, schedule, attendance, duties, photo)
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
                "announcements": row[11] if len(row) > 11 else "لا توجد إعلانات" # Added check for 'announcements' key
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
            "password": password  # أو أي معرف فريد موجود في الشيت
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
    elif data == "notes": # Added handling for 'notes' button
        await query.edit_message_text(f"✅ ملاحظات: {student['notes']}", reply_markup=reply_markup)
    elif data == "attendance": # Added handling for 'attendance' button
        await query.edit_message_text(f"✅ نسبة الحضور: {student['attendance']}", reply_markup=reply_markup)
    elif data == "announcements":
        await query.edit_message_text(f"📢 الإعلانات: {student['announcements']}", reply_markup=reply_markup) # Fixed KeyError
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
            [InlineKeyboardButton(subj, callback_data=f"{data}:{subj}")]
            for subj in grades
        ]
        await query.edit_message_text(f"📚 اختر المادة ({grade_type}):", reply_markup=InlineKeyboardMarkup(keyboard))
    elif ":" in data and data.startswith("grades_"):
        type_key, subject = data.split(":")
        grade_type = {"grades_exam": "امتحان", "grades_test": "مذاكرة", "grades_quiz": "سبر"}.get(type_key, "غير معروف")
        grade = student['grades'].get(grade_type, {}).get(subject)
        if grade is not None:
            await query.edit_message_text(f"📌 علامتك في {subject} ({grade_type}): {grade}" , reply_markup=reply_markup)
        else:
            await query.edit_message_text(f"❌ لا توجد علامة في {subject} ({grade_type})", reply_markup=reply_markup)
    elif data == "photo":
        try:
            await query.edit_message_text(f"{student['photo']}", reply_markup=reply_markup)
        except Exception as e: # Catch specific exception if possible, otherwise a general one
            print("Error sending photo:", e)
            await query.edit_message_text("⚠️ تعذر إرسال الصورة.", reply_markup=reply_markup)
    elif data == "worksheets":
        base_path = "worksheets"
        if not os.path.exists(base_path):
            await query.edit_message_text("⚠️ مجلد أوراق العمل غير موجود.", reply_markup=reply_markup)
            return
        subjects = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
        if not subjects:
            await query.edit_message_text("⚠️ لا توجد مواد في أوراق العمل.", reply_markup=reply_markup)
            return

        keyboard = [[InlineKeyboardButton(subj, callback_data=f"worksheet_subject:{subj}")] for subj in subjects]
        await query.edit_message_text("اختر المادة:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("worksheet_subject:"):
        subject = data.split(":", 1)[1]
        subject_path = os.path.join("worksheets", subject)
        if not os.path.exists(subject_path):
            await query.edit_message_text(f"⚠️ لم أجد ملفات لمادة {subject}.", reply_markup=reply_markup)
            return
        files = [f for f in os.listdir(subject_path) if f.endswith(".pdf")]
        if not files:
            await query.edit_message_text(f"⚠️ لا توجد ملفات PDF لمادة {subject}.", reply_markup=reply_markup)
            return

        keyboard = [[InlineKeyboardButton(f, callback_data=f"worksheet_file:{subject}:{f}")] for f in files]
        await query.edit_message_text(f"اختر ملف أوراق العمل للمادة {subject}:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("worksheet_file:"):
        parts = data.split(":", 2)
        if len(parts) < 3:
            await query.edit_message_text("⚠️ خطأ في اختيار الملف.", reply_markup=reply_markup)
            return
        subject = parts[1]
        filename = parts[2]
        file_path = os.path.join("worksheets", subject, filename)

        if not os.path.exists(file_path):
            await query.edit_message_text("⚠️ الملف غير موجود.", reply_markup=reply_markup)
            return
        try:
            with open(file_path, "rb") as pdf_file:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=InputFile(pdf_file),
                    filename=filename , reply_markup=reply_markup
                )

        except Exception as e:
            print("Error sending file:", e)
            await query.edit_message_text("⚠️ فشل إرسال الملف.", reply_markup=reply_markup)

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
