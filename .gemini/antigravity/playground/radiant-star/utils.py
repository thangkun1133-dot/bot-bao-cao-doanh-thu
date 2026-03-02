import os
import logging
from datetime import datetime, timedelta
from typing import List

import pandas as pd
from models import Revenue

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── Gemini Vision — Đọc bill banking ───────────────────────────────────────
def scan_bill_with_gemini(image_path: str) -> dict:
    """
    Dùng Gemini Vision để nhận diện số tiền từ ảnh bill/chuyển khoản.
    Trả về dict: {"amount": float|None, "info": str}
    """
    try:
        from config import Config
        import google.generativeai as genai
        from PIL import Image

        if not Config.GEMINI_API_KEY:
            return {"amount": None, "info": "Chưa cấu hình GEMINI_API_KEY"}

        genai.configure(api_key=Config.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        img = Image.open(image_path)

        prompt = """Đây là ảnh bill/biên lai chuyển khoản ngân hàng Việt Nam.
Hãy trích xuất thông tin sau và trả lời CHÍNH XÁC theo định dạng JSON:
{
  "so_tien": <số tiền giao dịch, chỉ số, không có đơn vị>,
  "ngan_hang": "<tên ngân hàng nếu có>",
  "noi_dung": "<nội dung chuyển khoản nếu có>",
  "trang_thai": "<thành công/thất bại/không rõ>"
}
Nếu không tìm thấy số tiền, trả về "so_tien": null.
Chỉ trả về JSON, không giải thích thêm."""

        response = model.generate_content([prompt, img])
        text = response.text.strip()

        # Parse JSON từ response
        import json, re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            amount = data.get("so_tien")
            if amount:
                amount = float(str(amount).replace(",", "").replace(".", "").replace(" ", ""))
            bank = data.get("ngan_hang", "")
            note = data.get("noi_dung", "")
            status = data.get("trang_thai", "")
            info = f"🏦 {bank} | 📝 {note} | ✅ {status}" if bank else note
            return {"amount": amount, "info": info}

    except Exception as e:
        logger.error(f"Lỗi Gemini Vision: {e}")

    return {"amount": None, "info": ""}



# ─── Excel ───────────────────────────────────────────────────────────────────
def generate_revenue_excel(revenues: list, filename: str = "report.xlsx") -> str:
    data = []
    for r in revenues:
        data.append(
            {
                "ID": r.id,
                "Ngày": r.date.strftime("%Y-%m-%d %H:%M:%S"),
                "Số tiền": r.amount,
                "Ghi chú": r.note or "",
                "Người nhập": r.full_name or r.username or "N/A",
                "Nguồn": "📸 Hóa đơn" if r.source == "invoice" else "✏️ Thủ công",
                "Nhóm ID": r.group_id or "Chat riêng",
            }
        )
    df = pd.DataFrame(data)
    filepath = os.path.join(os.getcwd(), filename)
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Doanh Thu")
        ws = writer.sheets["Doanh Thu"]
        # Tự động chỉnh độ rộng cột
        for col in ws.columns:
            max_len = max((len(str(cell.value)) for cell in col if cell.value), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)
    return filepath


# ─── Formatting ──────────────────────────────────────────────────────────────
def format_currency(amount: float) -> str:
    return "{:,.0f} VNĐ".format(amount)


def build_leaderboard_text(results, title: str) -> str:
    """Tạo bảng xếp hạng đẹp."""
    if not results:
        return "📭 Chưa có dữ liệu doanh thu trong nhóm này."

    lines = [f"👥 *{title}*\n"]
    lines.append("```")
    lines.append(f"{'#':<4} {'Tên':<22} {'Doanh Thu':>14}")
    lines.append("─" * 42)

    total = 0
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(results):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = (row.full_name or row.username or "Ẩn danh")[:20]
        amount_str = f"{row.total:,.0f}"
        lines.append(f"{medal:<4} {name:<22} {amount_str:>12}")
        total += row.total

    lines.append("─" * 42)
    lines.append(f"{'🎯 TỔNG NHÓM':<26} {total:>12,.0f}")
    lines.append("```")
    return "\n".join(lines)
