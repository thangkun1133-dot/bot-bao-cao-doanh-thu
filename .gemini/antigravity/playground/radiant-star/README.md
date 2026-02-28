# 🤖 Bot Báo Cáo Doanh Thu (Telegram)

Bot quản lý doanh thu hàng ngày với giao diện menu thân thiện, hỗ trợ xuất báo cáo Excel và lưu trữ dữ liệu an toàn.

## ✨ Tính năng
- ✅ **Thêm doanh thu**: Nhập số tiền và ghi chú nhanh chóng.
- 📊 **Báo cáo chi tiết**: Xem tổng doanh thu ngày/tháng ngay trên Telegram.
- 📥 **Xuất Excel (XLSX)**: Tải file báo cáo đầy đủ về máy.
- 🗄️ **Cơ sở dữ liệu**: Mặc định dùng SQLite, có thể cấu hình sang MySQL.
- ⚙️ **Dễ cấu hình**: Quản lý qua file `.env`.

## 🛠️ Hướng dẫn cài đặt

### 1. Cài đặt Python
Đảm bảo máy bạn đã cài Python 3.10 trở lên.

### 2. Cài đặt thư viện
Chạy lệnh sau trong terminal:
```bash
pip install -r requirements.txt
```

### 3. Cấu hình Bot
1. Copy file `.env.example` thành `.env`.
2. Lấy **Bot Token** từ [@BotFather](https://t.me/BotFather) và dán vào `TELEGRAM_BOT_TOKEN`.
3. (Tùy chọn) Cấu hình `DATABASE_URL` nếu muốn dùng MySQL.

### 4. Chạy Bot
```bash
python main.py
```

## 📝 Sử dụng
- Gõ `/start` để mở Menu chính.
- Chọn **Thêm Doanh Thu** để nhập liệu.
- Chọn **Báo Cáo** để xem nhanh.
- Chọn **Xuất Excel** để lấy file.

---
Phát triển bởi **Antigravity AI**.
