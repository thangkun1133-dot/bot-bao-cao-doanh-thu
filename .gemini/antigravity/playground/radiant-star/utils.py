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
