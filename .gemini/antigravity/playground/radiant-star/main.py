import logging
import threading
import os
from datetime import time

from flask import Flask
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

from config import Config
from database import init_db
import handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ── Health check server (để Render / UptimeRobot ping) ───────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "✅ Bot Báo Cáo Doanh Thu đang hoạt động!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)


def main():
    Config.validate()
    init_db()

    app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # ── Scheduled daily report ────────────────────────────────────────────────
    if Config.REPORT_CHANNEL_ID:
        app.job_queue.run_daily(handlers.daily_report_job, time=time(0, 1))

    # ── Revenue Conversation (thêm doanh thu thủ công) ────────────────────────
    revenue_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.add_revenue_start, pattern="^add_revenue$"),
        ],
        states={
            handlers.AWAITING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_amount),
                CallbackQueryHandler(handlers.invoice_manual, pattern="^invoice_manual$"),
            ],
            handlers.AWAITING_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_note),
                CommandHandler("skip", handlers.process_note),
            ],
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)],
        per_message=False,
    )

    # ── Invoice Conversation (quét hóa đơn → xác nhận → ghi chú) ────────────
    invoice_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO, handlers.handle_photo),
        ],
        states={
            handlers.AWAITING_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_note),
                CommandHandler("skip", handlers.process_note),
            ],
            handlers.AWAITING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_amount),
            ],
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)],
        per_message=False,
    )

    # ── Inline callback for invoice confirm ───────────────────────────────────
    invoice_confirm_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handlers.invoice_confirm, pattern="^invoice_confirm$"),
            CallbackQueryHandler(handlers.invoice_manual, pattern="^invoice_manual$"),
        ],
        states={
            handlers.AWAITING_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_note),
                CommandHandler("skip", handlers.process_note),
            ],
            handlers.AWAITING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.process_amount),
            ],
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)],
        per_message=False,
    )

    # ── Register handlers ──────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(ChatMemberHandler(handlers.handle_bot_added, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(revenue_conv)
    app.add_handler(invoice_conv)
    app.add_handler(invoice_confirm_conv)

    # Menu callbacks
    app.add_handler(CallbackQueryHandler(handlers.start,              pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(handlers.personal_report,    pattern="^personal_report$"))
    app.add_handler(CallbackQueryHandler(handlers.show_personal_report, pattern="^my_(today|month|history)$"))
    app.add_handler(CallbackQueryHandler(handlers.group_stats,        pattern="^group_stats$"))
    app.add_handler(CallbackQueryHandler(handlers.show_group_stats,   pattern="^gs_(today|month|all)$"))
    app.add_handler(CallbackQueryHandler(handlers.view_report_menu,   pattern="^view_report$"))
    app.add_handler(CallbackQueryHandler(handlers.show_report,        pattern="^report_(today|month)$"))
    app.add_handler(CallbackQueryHandler(handlers.export_excel_handler, pattern="^export_excel$"))

    print("🚀 Bot Báo Cáo Doanh Thu đang chạy...")
    app.run_polling(allowed_updates=["message", "callback_query", "my_chat_member"])


if __name__ == "__main__":
    # Chạy Flask server trong thread riêng để Render/UptimeRobot có thể ping
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    main()
