import logging
import os
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from sqlalchemy import func
from database import SessionLocal
from models import Revenue, Group
from utils import (
    generate_revenue_excel,
    format_currency,
    build_leaderboard_text,
)
from config import Config

logger = logging.getLogger(__name__)

# ─── Conversation states ──────────────────────────────────────────────────────
(
    AWAITING_AMOUNT,
    AWAITING_NOTE,
    AWAITING_INVOICE_CONFIRM,
    AWAITING_MANUAL_AMOUNT_AFTER_OCR,
) = range(4)

os.makedirs("invoices", exist_ok=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def main_menu_keyboard(is_group: bool = False):
    keyboard = [
        [
            InlineKeyboardButton("➕ Thêm Doanh Thu", callback_data="add_revenue"),
            InlineKeyboardButton("📊 Báo Cáo Cá Nhân", callback_data="personal_report"),
        ],
        [
            InlineKeyboardButton("📥 Xuất Excel", callback_data="export_excel"),
            InlineKeyboardButton("📈 Báo Cáo", callback_data="view_report"),
        ],
    ]
    if is_group:
        keyboard.append(
            [InlineKeyboardButton("👥 Thống Kê Nhóm", callback_data="group_stats")]
        )
    return InlineKeyboardMarkup(keyboard)


def get_user_info(user):
    full_name = (user.first_name or "") + (" " + user.last_name if user.last_name else "")
    return full_name.strip(), user.username


# ─── /start & Main Menu ───────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    is_group = chat.type in ("group", "supergroup")

    text = (
        "✨ *Bot Báo Cáo Doanh Thu* ✨\n\n"
        "Chào mừng! Chọn tính năng bên dưới:"
    )
    markup = main_menu_keyboard(is_group)

    if update.message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")


# ─── Bot added to group ───────────────────────────────────────────────────────
async def handle_bot_added(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = update.my_chat_member
    if member.new_chat_member.user.id != context.bot.id:
        return
    if member.new_chat_member.status not in ("member", "administrator"):
        return

    chat = update.effective_chat
    db = SessionLocal()
    existing = db.query(Group).filter_by(group_id=chat.id).first()
    if not existing:
        db.add(Group(group_id=chat.id, name=chat.title))
        db.commit()
        logger.info(f"Bot được thêm vào nhóm: {chat.title} ({chat.id})")
    db.close()

    await context.bot.send_message(
        chat_id=chat.id,
        text=(
            "👋 Xin chào mọi người!\n\n"
            "Tôi là *Bot Báo Cáo Doanh Thu* 🤖\n\n"
            "📌 Tính năng:\n"
            "• ➕ Thêm doanh thu (thủ công)\n"
            "• 📸 Gửi ảnh hóa đơn → tự nhận diện số tiền\n"
            "• 📊 Báo cáo cá nhân\n"
            "• 👥 Thống kê & bảng xếp hạng nhóm\n\n"
            "Gõ /start để bắt đầu!",
        ),
        parse_mode="Markdown",
    )


# ─── Add Revenue Flow ─────────────────────────────────────────────────────────
async def add_revenue_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💰 Nhập *số tiền* doanh thu (VD: 500000):",
        parse_mode="Markdown",
    )
    return AWAITING_AMOUNT


async def process_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(".", "").replace(",", "").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
        context.user_data["temp_amount"] = amount
        context.user_data["temp_source"] = "manual"
        context.user_data["temp_invoice_path"] = None
        await update.message.reply_text(
            f"✅ Số tiền: *{format_currency(amount)}*\n\nNhập *ghi chú* (hoặc /skip để bỏ qua):",
            parse_mode="Markdown",
        )
        return AWAITING_NOTE
    except ValueError:
        await update.message.reply_text("❌ Số không hợp lệ. Nhập lại (VD: 500000):")
        return AWAITING_AMOUNT


async def process_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text
    if note.startswith("/skip"):
        note = "Không có ghi chú"

    amount = context.user_data.get("temp_amount")
    source = context.user_data.get("temp_source", "manual")
    invoice_path = context.user_data.get("temp_invoice_path")
    user = update.effective_user
    chat = update.effective_chat
    full_name, username = get_user_info(user)

    db = SessionLocal()
    db.add(
        Revenue(
            amount=amount,
            note=note,
            user_id=user.id,
            username=username,
            full_name=full_name,
            date=datetime.now(),
            group_id=chat.id if chat.type in ("group", "supergroup") else None,
            source=source,
            invoice_path=invoice_path,
        )
    )
    db.commit()
    db.close()

    source_icon = "📸" if source == "invoice" else "✏️"
    await update.message.reply_text(
        f"✅ *Đã lưu!*\n\n"
        f"💰 Số tiền: *{format_currency(amount)}*\n"
        f"📝 Ghi chú: {note}\n"
        f"{source_icon} Nguồn: {'Hóa đơn' if source == 'invoice' else 'Thủ công'}\n"
        f"📅 Ngày: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Menu chính", callback_data="main_menu")]]
        ),
    )
    return ConversationHandler.END


# ─── Personal Report ──────────────────────────────────────────────────────────
async def personal_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("📅 Hôm nay", callback_data="my_today"),
            InlineKeyboardButton("🗓️ Tháng này", callback_data="my_month"),
        ],
        [InlineKeyboardButton("📋 Lịch sử gần đây", callback_data="my_history")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "📊 *Báo Cáo Cá Nhân* — Chọn loại:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_personal_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    full_name, _ = get_user_info(user)

    db = SessionLocal()
    now = datetime.now()

    if query.data == "my_today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        label = "Hôm nay"
    elif query.data == "my_month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        label = "Tháng này"
    else:  # my_history
        start_date = now - timedelta(days=30)
        label = "30 ngày qua"

    revenues = (
        db.query(Revenue)
        .filter(Revenue.user_id == user.id, Revenue.date >= start_date)
        .order_by(Revenue.date.desc())
        .all()
    )
    total = sum(r.amount for r in revenues)
    db.close()

    text = (
        f"📊 *Báo cáo của {full_name}*\n"
        f"📅 Kỳ: {label}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔢 Số giao dịch: *{len(revenues)}*\n"
        f"💰 Tổng: *{format_currency(total)}*\n\n"
    )

    if revenues:
        text += "📝 *Giao dịch gần đây:*\n"
        for r in revenues[:8]:
            icon = "📸" if r.source == "invoice" else "✏️"
            text += f"{icon} {format_currency(r.amount)} — {r.note or '—'} `({r.date.strftime('%d/%m %H:%M')})`\n"
        if len(revenues) > 8:
            text += f"_... và {len(revenues) - 8} giao dịch khác_"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Quay lại", callback_data="personal_report")]]
        ),
    )


# ─── Group Stats ──────────────────────────────────────────────────────────────
async def group_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("📅 Hôm nay", callback_data="gs_today"),
            InlineKeyboardButton("🗓️ Tháng này", callback_data="gs_month"),
        ],
        [InlineKeyboardButton("🏆 Tất cả thời gian", callback_data="gs_all")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "👥 *Thống Kê Nhóm* — Chọn kỳ:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_group_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat = update.effective_chat

    now = datetime.now()
    if query.data == "gs_today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        label = "Hôm nay"
    elif query.data == "gs_month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        label = "Tháng này"
    else:
        start_date = datetime(2000, 1, 1)
        label = "Tất cả thời gian"

    db = SessionLocal()
    results = (
        db.query(
            Revenue.user_id,
            Revenue.username,
            Revenue.full_name,
            func.sum(Revenue.amount).label("total"),
        )
        .filter(Revenue.group_id == chat.id, Revenue.date >= start_date)
        .group_by(Revenue.user_id, Revenue.username, Revenue.full_name)
        .order_by(func.sum(Revenue.amount).desc())
        .all()
    )
    db.close()

    text = build_leaderboard_text(results, f"THỐNG KÊ NHÓM — {label.upper()}")
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Quay lại", callback_data="group_stats")]]
        ),
    )


# ─── Revenue Report (quick) ───────────────────────────────────────────────────
async def view_report_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("📅 Hôm nay", callback_data="report_today"),
            InlineKeyboardButton("🗓️ Tháng này", callback_data="report_month"),
        ],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "📈 *Báo Cáo Tổng* — Chọn kỳ:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    now = datetime.now()

    if query.data == "report_today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        title = "Hôm nay"
    else:
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        title = "Tháng này"

    db = SessionLocal()
    revenues = db.query(Revenue).filter(Revenue.date >= start_date).all()
    total = sum(r.amount for r in revenues)
    db.close()

    text = (
        f"📊 *Báo cáo {title}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔢 Số giao dịch: *{len(revenues)}*\n"
        f"💰 Tổng doanh thu: *{format_currency(total)}*\n\n"
    )
    if revenues:
        text += "📝 *Chi tiết gần đây:*\n"
        for r in revenues[-5:]:
            icon = "📸" if r.source == "invoice" else "✏️"
            text += f"{icon} {format_currency(r.amount)} — {r.note or '—'} `({r.date.strftime('%H:%M')})`\n"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Quay lại", callback_data="view_report")]]
        ),
    )


# ─── Export Excel ─────────────────────────────────────────────────────────────
async def export_excel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Đang tạo file Excel...")

    db = SessionLocal()
    revenues = db.query(Revenue).order_by(Revenue.date.desc()).all()
    db.close()

    if not revenues:
        await query.edit_message_text("❌ Chưa có dữ liệu để xuất.")
        return

    filepath = generate_revenue_excel(revenues)
    with open(filepath, "rb") as f:
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=f,
            filename=f"Bao_Cao_Doanh_Thu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            caption=f"📂 Báo cáo doanh thu — {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                    f"📊 Tổng: *{len(revenues)}* giao dịch",
            parse_mode="Markdown",
        )


# ─── Invoice / Photo Scanning ─────────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user
    chat = update.effective_chat

    # Tải ảnh về làm chứng cứ
    photo = msg.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    os.makedirs("invoices", exist_ok=True)
    file_path = os.path.join("invoices", f"{photo.file_id}.jpg")
    await tg_file.download_to_drive(file_path)

    full_name, _ = get_user_info(user)
    context.user_data["temp_invoice_path"] = file_path
    context.user_data["temp_source"] = "invoice"
    context.user_data["temp_group_id"] = chat.id if chat.type in ("group", "supergroup") else None

    await msg.reply_text(
        "📸 *Đã nhận ảnh hóa đơn!*\n\n"
        "💰 Nhập *số tiền* trên hóa đơn (VD: 350000):",
        parse_mode="Markdown",
    )
    return AWAITING_AMOUNT



async def invoice_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    detected = context.user_data.get("temp_invoice_detected")
    context.user_data["temp_amount"] = detected

    await query.edit_message_text(
        f"✅ Đã xác nhận *{format_currency(detected)}*\n\nNhập *ghi chú* cho hóa đơn (hoặc /skip):",
        parse_mode="Markdown",
    )
    return AWAITING_NOTE


async def invoice_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✏️ Nhập *số tiền* hóa đơn (VD: 350000):", parse_mode="Markdown")
    return AWAITING_AMOUNT


# ─── Daily Report Job ─────────────────────────────────────────────────────────
async def daily_report_job(context: ContextTypes.DEFAULT_TYPE):
    if not Config.REPORT_CHANNEL_ID:
        return
    db = SessionLocal()
    yesterday = datetime.now() - timedelta(days=1)
    start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    total = (
        db.query(func.sum(Revenue.amount))
        .filter(Revenue.date >= start, Revenue.date < end)
        .scalar() or 0
    )
    count = db.query(Revenue).filter(Revenue.date >= start, Revenue.date < end).count()
    db.close()

    await context.bot.send_message(
        chat_id=Config.REPORT_CHANNEL_ID,
        text=(
            f"📢 *BÁO CÁO DOANH THU TỰ ĐỘNG*\n"
            f"📅 Ngày: {start.strftime('%d/%m/%Y')}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔢 Giao dịch: *{count}*\n"
            f"💰 Tổng cộng: *{format_currency(total)}*"
        ),
        parse_mode="Markdown",
    )


# ─── Cancel ───────────────────────────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Đã hủy.")
    return ConversationHandler.END
