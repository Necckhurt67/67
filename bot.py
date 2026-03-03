import os
import asyncio
import platform
import psutil
import speedtest
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode

# ═══════════════════════════════════════════════════════════════
# НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = "8677838013:AAHExkHjhIUDl14j2q3O-Dh2lf08RCCHDt8"
ADMIN_ID = 7928368527

# ═══════════════════════════════════════════════════════════════


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def bytes_to_human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def get_uptime() -> str:
    boot = datetime.fromtimestamp(psutil.boot_time())
    delta = datetime.now() - boot
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days}д {hours}ч {minutes}м {seconds}с"


# ─── Клавиатуры ─────────────────────────────────────────────────
def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статус", callback_data="status"),
            InlineKeyboardButton(text="💾 Память", callback_data="memory"),
        ],
        [
            InlineKeyboardButton(text="💽 Диск", callback_data="disk"),
            InlineKeyboardButton(text="🔧 CPU", callback_data="cpu"),
        ],
        [
            InlineKeyboardButton(text="⚡ Speedtest", callback_data="speedtest"),
            InlineKeyboardButton(text="📋 Процессы", callback_data="processes"),
        ],
        [
            InlineKeyboardButton(text="🌐 Сеть", callback_data="network"),
            InlineKeyboardButton(text="🖥 Система", callback_data="sysinfo"),
        ],
    ])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu")]
    ])


# ─── Команды ────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён")
        return
    
    await message.answer(
        "🖥 *Панель управления сервером*\n\nВыбери действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )


@dp.message(Command("shell", "sh"))
async def cmd_shell(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    # Получаем команду после /shell
    command = message.text.split(maxsplit=1)
    if len(command) < 2:
        await message.answer("Использование: `/shell <команда>`", parse_mode=ParseMode.MARKDOWN)
        return
    
    command = command[1]
    msg = await message.answer(f"⏳ Выполняю: `{command}`", parse_mode=ParseMode.MARKDOWN)
    
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        
        output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
        if not output.strip():
            output = "✅ Выполнено (нет вывода)"
        
        if len(output) > 4000:
            output = output[:4000] + "\n... (обрезано)"
        
        await msg.edit_text(f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    except asyncio.TimeoutError:
        await msg.edit_text("❌ Таймаут (60 сек)")
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: `{e}`", parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    text = """
🖥 *Команды:*

/start — главное меню
/shell `<команда>` — выполнить shell
/sh `<команда>` — то же самое
/help — эта справка

*Быстрый shell:*
Просто напиши команду начиная с `$`
Пример: `$ ls -la`
"""
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)


# ─── Быстрый shell через $ ──────────────────────────────────────
@dp.message(F.text.startswith("$"))
async def quick_shell(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    command = message.text[1:].strip()
    if not command:
        return
    
    msg = await message.answer(f"⏳ `{command}`", parse_mode=ParseMode.MARKDOWN)
    
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        
        output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
        if not output.strip():
            output = "✅ OK"
        
        if len(output) > 4000:
            output = output[:4000] + "\n..."
        
        await msg.edit_text(f"```\n{output}\n```", parse_mode=ParseMode.MARKDOWN)
    except asyncio.TimeoutError:
        await msg.edit_text("❌ Таймаут")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


# ─── Кнопки ─────────────────────────────────────────────────────
@dp.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🖥 *Панель управления сервером*\n\nВыбери действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "status")
async def cb_status(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
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
        f"📥 Получено: `{bytes_to_human(net.bytes_recv)}`\n"
        f"📊 Процессов: `{len(psutil.pids())}`"
    )
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "memory")
async def cb_memory(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    def bar(percent):
        filled = int(percent / 10)
        return "█" * filled + "░" * (10 - filled)
    
    text = (
        "💾 *Память*\n\n"
        "*RAM:*\n"
        f"```\n"
        f"Всего:    {bytes_to_human(mem.total)}\n"
        f"Занято:   {bytes_to_human(mem.used)}\n"
        f"Свободно: {bytes_to_human(mem.available)}\n"
        f"[{bar(mem.percent)}] {mem.percent}%\n"
        f"```\n\n"
        "*Swap:*\n"
        f"```\n"
        f"Всего:    {bytes_to_human(swap.total)}\n"
        f"Занято:   {bytes_to_human(swap.used)}\n"
        f"[{bar(swap.percent)}] {swap.percent}%\n"
        f"```"
    )
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "disk")
async def cb_disk(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    text = "💽 *Диски*\n\n"
    
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            filled = int(usage.percent / 10)
            bar = "█" * filled + "░" * (10 - filled)
            text += (
                f"📁 `{part.mountpoint}`\n"
                f"   {bytes_to_human(usage.used)} / {bytes_to_human(usage.total)}\n"
                f"   [{bar}] {usage.percent}%\n\n"
            )
        except:
            pass
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "cpu")
async def cb_cpu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    cpu = psutil.cpu_percent(interval=1)
    cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
    freq = psutil.cpu_freq()
    
    text = f"🔧 *CPU*\n\n"
    text += f"Общая нагрузка: `{cpu}%`\n"
    text += f"Ядер: `{psutil.cpu_count()}`\n"
    
    if freq:
        text += f"Частота: `{freq.current:.0f} MHz`\n"
    
    try:
        load1, load5, load15 = os.getloadavg()
        text += f"Load: `{load1:.2f}` / `{load5:.2f}` / `{load15:.2f}`\n"
    except:
        pass
    
    text += "\n*По ядрам:*\n```\n"
    for i, p in enumerate(cpu_per_core):
        bar = "█" * int(p / 10) + "░" * (10 - int(p / 10))
        text += f"Core {i}: [{bar}] {p:5.1f}%\n"
    text += "```"
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "network")
async def cb_network(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    net = psutil.net_io_counters()
    
    text = (
        "🌐 *Сеть*\n\n"
        f"📤 Отправлено: `{bytes_to_human(net.bytes_sent)}`\n"
        f"📥 Получено: `{bytes_to_human(net.bytes_recv)}`\n"
        f"📦 Пакетов отпр: `{net.packets_sent:,}`\n"
        f"📦 Пакетов получ: `{net.packets_recv:,}`\n"
        f"❌ Ошибок: `{net.errin + net.errout}`\n"
    )
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "sysinfo")
async def cb_sysinfo(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    uname = platform.uname()
    
    text = (
        "🖥 *Система*\n\n"
        f"💻 ОС: `{uname.system} {uname.release}`\n"
        f"🏗 Архитектура: `{uname.machine}`\n"
        f"🖥 Хост: `{uname.node}`\n"
        f"🐍 Python: `{platform.python_version()}`\n"
        f"📋 Платформа: `{platform.platform()}`\n"
    )
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "speedtest")
async def cb_speedtest(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    await callback.message.edit_text(
        "⚡ *Speedtest запущен...*\n\nПодожди 20-30 секунд",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()
    
    try:
        # Способ 1: через fast.com (Netflix)
        proc = await asyncio.create_subprocess_shell(
            "curl -s https://raw.githubusercontent.com/sivel/speedtest-cli/master/speedtest.py | python3 - --simple",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stdout.decode().strip()
        
        if output and "Ping:" in output:
            # Парсим вывод: Ping: X ms / Download: X Mbit/s / Upload: X Mbit/s
            lines = output.split("\n")
            text = "⚡ *Speedtest результаты:*\n\n"
            for line in lines:
                if "Ping:" in line:
                    text += f"📡 {line}\n"
                elif "Download:" in line:
                    text += f"📥 {line}\n"
                elif "Upload:" in line:
                    text += f"📤 {line}\n"
        else:
            # Способ 2: простой тест через curl
            text = await simple_speed_test()
        
        await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard())
        
    except asyncio.TimeoutError:
        await callback.message.edit_text(
            "❌ Таймаут (тест занял больше 2 минут)",
            reply_markup=back_keyboard()
        )
    except Exception as e:
        # Fallback на простой тест
        try:
            text = await simple_speed_test()
            await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard())
        except:
            await callback.message.edit_text(
                f"❌ Ошибка: `{e}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_keyboard()
            )


async def simple_speed_test() -> str:
    """Простой тест скорости через скачивание файла"""
    import time
    
    test_urls = [
        ("Cloudflare", "https://speed.cloudflare.com/__down?bytes=10000000"),  # 10MB
        ("Hetzner", "https://speed.hetzner.de/1MB.bin"),
    ]
    
    text = "⚡ *Speedtest (простой):*\n\n"
    
    for name, url in test_urls:
        try:
            start = time.time()
            proc = await asyncio.create_subprocess_shell(
                f"curl -s -o /dev/null -w '%{{size_download}}' {url}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            elapsed = time.time() - start
            
            size = int(stdout.decode().strip())
            speed_mbps = (size * 8) / elapsed / 1_000_000
            
            text += f"📥 {name}: `{speed_mbps:.2f} Mbps`\n"
        except:
            text += f"📥 {name}: ❌ ошибка\n"
    
    # Пинг
    try:
        proc = await asyncio.create_subprocess_shell(
            "ping -c 3 8.8.8.8 | tail -1 | awk -F '/' '{print $5}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        ping = stdout.decode().strip()
        if ping:
            text += f"\n📡 Ping (Google): `{ping} 

@dp.callback_query(F.data == "processes")
async def cb_processes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except:
            pass
    
    procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)
    top = procs[:10]
    
    text = "📋 *Топ-10 процессов*\n\n```\n"
    text += f"{'Имя':<15} {'CPU':>6} {'MEM':>6}\n"
    text += "-" * 30 + "\n"
    
    for p in top:
        name = (p.get("name") or "?")[:15]
        cpu = p.get("cpu_percent") or 0
        mem = p.get("memory_percent") or 0
        text += f"{name:<15} {cpu:>5.1f}% {mem:>5.1f}%\n"
    
    text += "```"
    
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard())
    await callback.answer()


# ─── Запуск ─────────────────────────────────────────────────────
async def main():
    print("🚀 Бот запускается...")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    print("✅ Запуск бота...")
    asyncio.run(main())

