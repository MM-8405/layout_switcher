<div align="center">

<img src="assets/logo.png" width="120" alt="LayoutSwitcher">

# LayoutSwitcher — تبدیل زبان کیبورد

**متنِ اشتباه تایپ‌شده را با یک کلید میانبر درست کن.**

فارسی ⇄ انگلیسی، بدون کپی‌کردن دستی و بدون بازکردن برنامه.

[**⬇️ دانلود آخرین نسخه (LayoutSwitcher.exe)**](https://github.com/MM-8405/layout_switcher/raw/main/dist/LayoutSwitcher.exe)

</div>

---

## 😩 مشکل چیه؟

می‌خوای «سلام» بنویسی، ولی یادت رفته زبان عوض کنی و این تایپ شده:

```
sghl
```

حالا باید متن رو پاک کنی، زبان رو عوض کنی و دوباره تایپ کنی. **LayoutSwitcher** این کار رو با یک کلید انجام می‌دهد.

## ✨ چه کارهایی می‌کند؟

- 🔁 تبدیل متن بین **فارسی** و **انگلیسی** (`sghl` → `سلام` و برعکس).
- ⌨️ کلید میانبر پیش‌فرض: **`Ctrl + Alt + Space`** (قابل تغییر).
- 🖱️ حالت‌های جایگزین میانبر: **دوبار فشردن Ctrl/Shift/Alt** یا **دکمه‌ی کناری ماوس**.
- ✅ اگر متنی انتخاب نشده باشد، خودش انتخاب می‌کند: **کل متن / خط جاری / آخرین کلمه**.
- 🌐 بعد از تبدیل، **زبان کیبورد سیستم** را هم به زبان مقصد عوض می‌کند.
- 🎨 پوسته‌ی روشن/تیره/سیستم.
- 🚀 **بدون نیاز به نصب پایتون**؛ یک فایل exe مستقل.

## ⬇️ نصب و اجرا

1. فایل [`dist/LayoutSwitcher.exe`](dist/LayoutSwitcher.exe) را دانلود کنید (یا از دکمه‌ی بالای صفحه).
2. آن را هرجایی که خواستید کپی کنید و دابل‌کلیک کنید. همین!
3. برنامه در **تسک‌بار** می‌ماند و با `Ctrl + Alt + Space` کار می‌کند.

> **نکته‌ی ویندوز:** چون فایل امضای دیجیتال ندارد، ممکن است SmartScreen هشدار بدهد.
> روی **More info → Run anyway** بزنید.

- فقط یک نسخه از برنامه هم‌زمان اجرا می‌شود.
- تنظیمات در `%APPDATA%\LayoutSwitcher\config.json` ذخیره می‌شود.

## 🕹️ طریقه‌ی استفاده

| مرحله | کار |
|------|-----|
| 1 | متن اشتباه را تایپ کنید (یا متن موجود را انتخاب کنید) |
| 2 | `Ctrl + Alt + Space` را بزنید |
| 3 | متن تبدیل‌شده جای‌گزین می‌شود و زبان سیستم هم عوض می‌شود |

## 🗂️ ساختار پروژه

```
layout_switcher/
├─ layout_switcher.py      ← سورس اصلی برنامه
├─ build.bat               ← ساخت فایل exe با یک دابل‌کلیک
├─ assets/
│  ├─ icon.ico             ← آیکون برنامه (خودکار از لوگو ساخته می‌شود)
│  └─ logo.png             ← لوگو
└─ dist/
   └─ LayoutSwitcher.exe   ← خروجی آماده برای اجرا ⬅️ همین را دانلود کنید
```

## 🛠️ ساخت exe از سورس

پیش‌نیاز: Python 3.10+ روی ویندوز.

```bat
build.bat
```

اسکریپت به‌ترتیب وابستگی‌ها را نصب می‌کند، آیکون را از لوگوی برنامه می‌سازد و خروجی را در `dist\LayoutSwitcher.exe` می‌گذارد.

یا به‌صورت دستی:

```bat
pip install customtkinter pyperclip pillow pyinstaller
python layout_switcher.py --make-icon
pyinstaller --noconfirm --clean --onefile --noconsole --name LayoutSwitcher ^
  --icon assets\icon.ico --collect-all customtkinter layout_switcher.py
```

### اجرا بدون ساخت exe

```bat
pip install customtkinter pyperclip pillow
python layout_switcher.py
```

## 🌍 افزودن زبان جدید

در فایل `layout_switcher.py`، دیکشنری `LAYOUTS` را ببینید:

```python
LAYOUTS = {
    "en": {"name": "English", "lang": 0x09, "chars": KEYS},
    "fa": {"name": "فارسی", "lang": 0x29, "chars": "ضصثقفغعهخحجچ..."},
}
```

- `lang` = کد زبان اصلی ویندوز (Primary Language ID): `en=0x09`، `fa=0x29`، `ar=0x01`، `ru=0x19` ...
- `chars` = کاراکتر هر کلید، دقیقاً هم‌طول و هم‌ترتیب با رشته‌ی `KEYS`.

## 📋 نیازمندی‌ها

| مورد | نسخه |
|------|------|
| ویندوز | 10 / 11 |
| پایتون (فقط برای ساخت) | 3.10+ |
| customtkinter | 5+ / 6 |
| pyperclip | 1.8+ |
| pillow | 10+ |

## ⚠️ محدودیت‌ها

- فقط برای **ویندوز** است (از Win32 API استفاده می‌کند).
- در برنامه‌هایی که کپی/چسباندن را مسدود می‌کنند (بعضی فیلدهای رمز) کار نمی‌کند.
- روی برخی برنامه‌های اجراشده با دسترسی Administrator، باید LayoutSwitcher را هم Run as administrator اجرا کنید.
