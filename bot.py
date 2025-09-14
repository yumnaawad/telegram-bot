import os
import json
import pandas as pd
import time
import threading
import random
import asyncio
import nest_asyncio
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

nest_asyncio.apply()

from server import keep_alive
keep_alive()  # يشغّل السيرفر على Repl.it أو غيره

TOKEN = "PUT_YOUR_BOT_TOKEN"
LOGIN = 1

STUDENT_DATA_FILE = "STUDENT_DATA_FILE.xlsx"
SESSIONS_FILE = "sessions.json"

# لوحة الأزرار الرئيسية
keyboard = [
    [InlineKeyboardButton("حول مدرسة الأفق الجديد", callback_data="about")],
    [InlineKeyboardButton("🗓️ برنامج الدوام", callback_data="schedule")],
    [InlineKeyboardButton("🗓️الواجبات", callback_data="duties")],
    [InlineKeyboardButton("📄 أوراق العمل", callback_data="worksheets")],
    [InlineKeyboardButton("📢 الإعلانات", callback_data="announcements")],
    [InlineKeyboardButton("📊العلامات", callback_data="grades")],
    [InlineKeyboardButton("📝 الملاحظات", callback_data="notes")],
    [InlineKeyboardButton("📸 الصور", callback_data="photo")],
]
reply_markup = InlineKeyboardMarkup(keyboard)

# تحميل الجلسات السابقة
try:
    with open(SESSIONS_FILE, "r") as f:
        logged_in_users = json.load(f)
except FileNotFoundError:
    logged_in_users = {}

# تحميل ملف Excel الخاص بالأهالي
def load_data():
    return pd.read_excel("parents.xlsx")

def save_data(df):
    df.to_excel("parents.xlsx", index=False)

# استقبال رقم الهاتف وإعطاء كلمة المرور
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.contact.phone_number
    df = load_data()

    row = df[df['phone'] == phone]

    if not row.empty:
        if pd.notna(row.iloc[0]['password']):
            password = row.iloc[0]['password']
        else:
            password = str(random.randint(100000, 999999))
            df.loc[df['phone'] == phone, 'password'] = password
            save_data(df)

        await update.message.reply_text(
            f"✅ تم التحقق من رقمك.\nكلمة المرور الخاصة بك: {password}\n\n"
            "استخدم /login لإدخال كلمة المرور والدخول للنظام."
        )
    else:
        await update.message.reply_text("❌ رقمك غير موجود في سجلات المدرسة. تواصل مع الإدارة.")

# تحميل بيانات الطلاب
def load_student_data():
    df = pd.read_excel(STUDENT_DATA_FILE)
    data = {}
    for _, row in df.iterrows():
        data[str(row['password'])] = {
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
            "announcements": row.get('announcements', "لا توجد إعلانات")
        }
    return data

# ربط chat_id بالطالب
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

# keep_alive في خيط منفصل
def keep_alive_thread():
    while True:
        print("البوت يعمل...")
        time.sleep(60)

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    if user_id in logged_in_users:
        student = get_student_by_chat_id(update.effective_chat.id)
        if student:
            await show_main_menu(update, context, student)
        else:
            await update.message.reply_text("⚠️ حدث خطأ أثناء جلب البيانات. أعد تسجيل الدخول.")
    else:
        button = KeyboardButton("📱 شارك رقم هاتفك", request_contact=True)
        kb = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("مرحباً! شارك رقم هاتفك للتسجيل:", reply_markup=kb)

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
        await query.edit_message_text("مدرسة الأفق الجديد... للتواصل: 0947180707", reply_markup=reply_markup)
    elif data == "schedule":
        await query.edit_message_text(f"✅ برنامج الدوام: {student['schedule']}", reply_markup=reply_markup)
    elif data == "duties":
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"✅ واجباتك لليوم: {student['duties']}", reply_markup=reply_markup)
    elif data == "notes":
        await query.edit_message_text(f"✅ ملاحظات: {student['notes']}", reply_markup=reply_markup)
    elif data == "announcements":
        await query.edit_message_text(f"📢 الإعلانات: {student['announcements']}", reply_markup=reply_markup)
    # باقي الحالات مثل grades / worksheets / photo تقدر تبقيها كما هي عندك...

# تشغيل البوت
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    login_conv = ConversationHandler(
        entry_points=[CommandHandler("login", login)],
        states={LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(login_conv)
    app.add_handler(CallbackQueryHandler(handle_button))

    await app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=keep_alive_thread, daemon=True).start()
    asyncio.run(main())
