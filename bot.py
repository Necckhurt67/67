import os
import asyncio
import platform
import psutil
import speedtest
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ═══════════════════════════════════════════════════════════════
# НАСТРОЙКИ - ВПИШИ СЮДА СВОИ ДАННЫЕ
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = "8677838013:AAHExkHjhIUDl14j2q3O-Dh2lf08RCCHDt8"
ADMIN_ID = 7928368527  # Твой Telegram ID

# ═══════════════════════════════════════════════════════════════


def is_admin(user_id):
    return user_id == ADMIN_ID


def bytes_to_human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def get_uptime():
    boot = datetime.fromtimestamp(psutil.boot_time())
    delta = datetime.now() - boot
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days}д {hours}ч {minutes}м {seconds}с"


# ─── Клавиатура ─────────────────────────────────────────────────
def main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📊 Статус", callback_data="status"),
            InlineKeyboardButton("💾 Память", callback_data="memory"),
        ],
        [
            InlineKeyboardButton("💽 Диск", callback_data="disk"),
            InlineKeyboardButton("🔧 CPU", callback_data="cpu"),
        ],
        [
            InlineKeyboardButton("⚡ Speedtest", callback_data="speedtest"),
            InlineKeyboardButton("📋 Процессы", callback_data="processes"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="menu")]])


# ─── Команды ────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    await update.message.reply_text(
        "🖥 *Панель управления сервером*\n\nВыбери действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


async def cmd_shell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /shell <команда>")
        return
    
    command = " ".join(context.args)
    msg = await update.message.reply_text(f"⏳ Выполняю: `{command}`", parse_mode="Markdown")
    
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        
        output = stdout.decode() + stderr.decode()
        if not output:
            output = "✅ Выполнено (нет вывода)"
        
        if len(output) > 4000:
            output = output[:4000] + "\n... (обрезано)"
        
        await msg.edit_text(f"```\n{output}\n```", parse_mode="Markdown")
    except asyncio.TimeoutError:
        await msg.edit_text("❌ Таймаут команды")
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")


# ─── Кнопки ─────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        return
    
    data = query.data
    
    if data == "menu":
        await query.edit_message_text(
            "🖥 *Панель управления сервером*\n\nВыбери действие:",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    
    elif data == "status":
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        
        text = (
            "📊 *Статус системы*\n\n"
            f"🖥 Хост: `{platform.node()}`\n"
            f"⏱ Uptime: `{get_uptime()}`\n\n"
            f"🔧 CPU: `{cpu}%`\n"
            f"💾 RAM: `{mem.percent}%` ({bytes_to_human(mem.used)}/{bytes_to_human(mem.total)})\n"
            f"💽 Диск: `{disk.percent}%` ({bytes_to_human(disk.used)}/{bytes_to_human(disk.total)})\n\n"
            f"📤 Отправлено: `{bytes_to_human(net.bytes_sent)}`\n"
            f"📥 Получено: `{bytes_to_human(net.bytes_recv)}`"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
    
    elif data == "memory":
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        text = (
            "💾 *Память*\n\n"
            "*RAM:*\n"
            f"  Всего: `{bytes_to_human(mem.total)}`\n"
            f"  Занято: `{bytes_to_human(mem.used)}` ({mem.percent}%)\n"
            f"  Свободно: `{bytes_to_human(mem.available)}`\n\n"
            "*Swap:*\n"
            f"  Всего: `{bytes_to_human(swap.total)}`\n"
            f"  Занято: `{bytes_to_human(swap.used)}` ({swap.percent}%)"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
    
    elif data == "disk":
        disk = psutil.disk_usage("/")
        
        text = (
            "💽 *Диск*\n\n"
            f"Всего: `{bytes_to_human(disk.total)}`\n"
            f"Занято: `{bytes_to_human(disk.used)}` ({disk.percent}%)\n"
            f"Свободно: `{bytes_to_human(disk.free)}`"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
    
    elif data == "cpu":
        cpu = psutil.cpu_percent(interval=1)
        cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
        freq = psutil.cpu_freq()
        
        text = f"🔧 *CPU*\n\n"
        text += f"Общая нагрузка: `{cpu}%`\n"
        text += f"Ядер: `{psutil.cpu_count()}`\n"
        
        if freq:
            text += f"Частота: `{freq.current:.0f} MHz`\n"
        
        text += "\n*По ядрам:*\n"
        for i, p in enumerate(cpu_per_core):
            bar = "█" * int(p / 10) + "░" * (10 - int(p / 10))
            text += f"  {i}: [{bar}] {p}%\n"
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
    
    elif data == "speedtest":
        await query.edit_message_text("⚡ *Запуск Speedtest...*\n\nПодожди 30-60 секунд", parse_mode="Markdown")
        
        try:
            loop = asyncio.get_event_loop()
            
            def run_test():
                st = speedtest.Speedtest()
                st.get_best_server()
                st.download()
                st.upload()
                return st.results.dict()
            
            results = await loop.run_in_executor(None, run_test)
            
            download = results["download"] / 1_000_000
            upload = results["upload"] / 1_000_000
            ping = results["ping"]
            
            text = (
                "⚡ *Speedtest*\n\n"
                f"📥 Download: `{download:.2f} Mbps`\n"
                f"📤 Upload: `{upload:.2f} Mbps`\n"
                f"📡 Ping: `{ping:.1f} ms`"
            )
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}", reply_markup=back_keyboard())
    
    elif data == "processes":
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except:
                pass
        
        procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)
        top = procs[:10]
        
        text = "📋 *Топ процессов*\n\n```\n"
        for p in top:
            name = (p.get("name") or "?")[:15]
            cpu = p.get("cpu_percent") or 0
            mem = p.get("memory_percent") or 0
            text += f"{name:15} CPU:{cpu:5.1f}% MEM:{mem:5.1f}%\n"
        text += "```"
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard())


# ─── Запуск ─────────────────────────────────────────────────────
def main():
    print("🚀 Бот запускается...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("shell", cmd_shell))
    app.add_handler(CommandHandler("sh", cmd_shell))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Бот запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
