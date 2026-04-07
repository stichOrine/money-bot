import json
import os
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATA_FILE = "money_data.json"

CHOOSING_ACTION, ENTERING_AMOUNT, CHOOSING_CATEGORY = range(3)


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_user_id(update: Update) -> str:
    return str(update.effective_user.id)


def ensure_user(data, user_id):
    if user_id not in data:
        data[user_id] = []


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["➕ Доход", "➖ Расход"],
            ["📊 Баланс", "📜 История"],
            ["📅 Сегодня", "🗓 Месяц"],
            ["↩️ Удалить последнюю", "🗑 Очистить"],
            ["❌ Отмена"],
        ],
        resize_keyboard=True,
    )


def get_income_categories():
    return ReplyKeyboardMarkup(
        [
            ["💼 Зарплата", "🎁 Подарок"],
            ["💰 Подработка", "📦 Другое"],
            ["❌ Отмена"],
        ],
        resize_keyboard=True,
    )


def get_expense_categories():
    return ReplyKeyboardMarkup(
        [
            ["🍔 Еда", "🚕 Транспорт"],
            ["🛍 Покупки", "🏠 Дом"],
            ["🎉 Развлечения", "💊 Здоровье"],
            ["📦 Другое"],
            ["❌ Отмена"],
        ],
        resize_keyboard=True,
    )


def calculate_balance(items):
    return sum(item["amount"] for item in items)


def calculate_income(items):
    return sum(item["amount"] for item in items if item["amount"] > 0)


def calculate_expenses(items):
    return sum(-item["amount"] for item in items if item["amount"] < 0)


def filter_today(items):
    today = datetime.now().strftime("%Y-%m-%d")
    return [item for item in items if item["date"].startswith(today)]


def filter_month(items):
    current_month = datetime.now().strftime("%Y-%m")
    return [item for item in items if item["date"].startswith(current_month)]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Привет! Я бот учета денег.\n\nВыбери действие:",
        reply_markup=get_main_keyboard(),
    )
    return CHOOSING_ACTION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Действие отменено.",
        reply_markup=get_main_keyboard(),
    )
    return CHOOSING_ACTION


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "➕ Доход":
        context.user_data["type"] = "income"
        await update.message.reply_text("Введи сумму дохода числом.\nНапример: 5000")
        return ENTERING_AMOUNT

    if text == "➖ Расход":
        context.user_data["type"] = "expense"
        await update.message.reply_text("Введи сумму расхода числом.\nНапример: 300")
        return ENTERING_AMOUNT

    if text == "📊 Баланс":
        await show_balance(update, context)
        return CHOOSING_ACTION

    if text == "📜 История":
        await show_history(update, context)
        return CHOOSING_ACTION

    if text == "📅 Сегодня":
        await show_today_stats(update, context)
        return CHOOSING_ACTION

    if text == "🗓 Месяц":
        await show_month_stats(update, context)
        return CHOOSING_ACTION

    if text == "↩️ Удалить последнюю":
        await delete_last_operation(update, context)
        return CHOOSING_ACTION

    if text == "🗑 Очистить":
        await clear_data(update, context)
        return CHOOSING_ACTION

    if text == "❌ Отмена":
        return await cancel(update, context)

    await update.message.reply_text(
        "Пожалуйста, выбери кнопку из меню.",
        reply_markup=get_main_keyboard(),
    )
    return CHOOSING_ACTION


async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "❌ Отмена":
        return await cancel(update, context)

    try:
        amount = int(text)
        if amount <= 0:
            await update.message.reply_text("Сумма должна быть больше нуля. Попробуй ещё раз.")
            return ENTERING_AMOUNT
    except ValueError:
        await update.message.reply_text("Нужно ввести только число. Например: 500")
        return ENTERING_AMOUNT

    context.user_data["amount"] = amount

    if context.user_data.get("type") == "income":
        await update.message.reply_text(
            "Выбери категорию дохода:",
            reply_markup=get_income_categories(),
        )
    else:
        await update.message.reply_text(
            "Выбери категорию расхода:",
            reply_markup=get_expense_categories(),
        )

    return CHOOSING_CATEGORY


async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "❌ Отмена":
        return await cancel(update, context)

    operation_type = context.user_data.get("type")
    amount = context.user_data.get("amount")

    if not operation_type or not amount:
        await update.message.reply_text(
            "Что-то сбилось. Нажми /start",
            reply_markup=get_main_keyboard(),
        )
        return CHOOSING_ACTION

    category = text
    signed_amount = amount if operation_type == "income" else -amount

    data = load_data()
    user_id = get_user_id(update)
    ensure_user(data, user_id)

    operation = {
        "amount": signed_amount,
        "category": category,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    data[user_id].append(operation)
    save_data(data)

    if operation_type == "income":
        await update.message.reply_text(
            f"✅ Доход добавлен\nСумма: {amount}\nКатегория: {category}",
            reply_markup=get_main_keyboard(),
        )
    else:
        await update.message.reply_text(
            f"✅ Расход добавлен\nСумма: {amount}\nКатегория: {category}",
            reply_markup=get_main_keyboard(),
        )

    context.user_data.clear()
    return CHOOSING_ACTION


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = get_user_id(update)
    ensure_user(data, user_id)

    items = data[user_id]
    balance = calculate_balance(items)
    income = calculate_income(items)
    expenses = calculate_expenses(items)

    text = (
        f"📊 Баланс: {balance}\n"
        f"➕ Доходы: {income}\n"
        f"➖ Расходы: {expenses}"
    )

    await update.message.reply_text(text, reply_markup=get_main_keyboard())


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = get_user_id(update)
    ensure_user(data, user_id)

    if not data[user_id]:
        await update.message.reply_text(
            "История пустая.",
            reply_markup=get_main_keyboard(),
        )
        return

    lines = ["📜 Последние операции:\n"]
    for item in data[user_id][-10:]:
        sign = "+" if item["amount"] > 0 else ""
        lines.append(f'{item["date"]} | {sign}{item["amount"]} | {item["category"]}')

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=get_main_keyboard(),
    )


async def show_today_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = get_user_id(update)
    ensure_user(data, user_id)

    today_items = filter_today(data[user_id])

    if not today_items:
        await update.message.reply_text(
            "📅 Сегодня операций пока нет.",
            reply_markup=get_main_keyboard(),
        )
        return

    balance = calculate_balance(today_items)
    income = calculate_income(today_items)
    expenses = calculate_expenses(today_items)

    text = (
        f"📅 Сегодня\n"
        f"📊 Баланс: {balance}\n"
        f"➕ Доходы: {income}\n"
        f"➖ Расходы: {expenses}"
    )

    await update.message.reply_text(text, reply_markup=get_main_keyboard())


async def show_month_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = get_user_id(update)
    ensure_user(data, user_id)

    month_items = filter_month(data[user_id])

    if not month_items:
        await update.message.reply_text(
            "🗓 В этом месяце операций пока нет.",
            reply_markup=get_main_keyboard(),
        )
        return

    balance = calculate_balance(month_items)
    income = calculate_income(month_items)
    expenses = calculate_expenses(month_items)

    text = (
        f"🗓 Этот месяц\n"
        f"📊 Баланс: {balance}\n"
        f"➕ Доходы: {income}\n"
        f"➖ Расходы: {expenses}"
    )

    await update.message.reply_text(text, reply_markup=get_main_keyboard())


async def delete_last_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = get_user_id(update)
    ensure_user(data, user_id)

    if not data[user_id]:
        await update.message.reply_text(
            "Удалять нечего, история пустая.",
            reply_markup=get_main_keyboard(),
        )
        return

    deleted = data[user_id].pop()
    save_data(data)

    sign = "+" if deleted["amount"] > 0 else ""
    text = (
        "↩️ Последняя операция удалена\n"
        f'{deleted["date"]} | {sign}{deleted["amount"]} | {deleted["category"]}'
    )
    await update.message.reply_text(text, reply_markup=get_main_keyboard())


async def clear_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = get_user_id(update)
    data[user_id] = []
    save_data(data)

    await update.message.reply_text(
        "🗑 Все записи удалены.",
        reply_markup=get_main_keyboard(),
    )


async def fallback_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Нажми /start и выбери кнопку.",
        reply_markup=get_main_keyboard(),
    )


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)
            ],
            ENTERING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)
            ],
            CHOOSING_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_category)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("balance", show_balance))
    app.add_handler(CommandHandler("history", show_history))
    app.add_handler(CommandHandler("clear", clear_data))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_message)
    )

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()