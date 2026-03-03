# bot.py

import os
import sys
import asyncio
import platform
import subprocess
import shutil
import time
import socket
import psutil
import speedtest
import logging
from datetime import datetime, timedelta
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# ─── Логирование ────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Конфигурация ───────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))  # через запятую
COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "60"))

if not BOT_TOKEN:
    logger.error("BOT_TOKEN не установлен!")
    sys.exit(1)

if not ADMIN_IDS or ADMIN_IDS == [0]:
    logger.error("ADMIN_IDS не установлен!")
    sys.exit(1)


# ─── Декоратор авторизации ──────────────────────────────────────
def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.effective_message.reply_text(
                "🚫 *Доступ запрещён!*\n"
                f"Ваш ID: `{user_id}`\n"
                "Обратитесь к администратору.",
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.warning(f"Попытка доступа от {user_id}")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


# ─── Утилиты ────────────────────────────────────────────────────
def bytes_to_human(n: int) -> str:
    """Конвертация байт в человекочитаемый формат."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def seconds_to_human(seconds: int) -> str:
    """Конвертация секунд в человекочитаемый формат."""
    delta = timedelta(seconds=seconds)
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    if minutes:
        parts.append(f"{minutes}м")
    parts.append(f"{secs}с")
    return " ".join(parts)


async def run_shell(command: str, timeout: int = COMMAND_TIMEOUT) -> tuple[str, str, int]:
    """Асинхронное выполнение shell-команды."""
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            process.returncode,
        )
    except asyncio.TimeoutError:
        process.kill()
        return "", "⏰ Команда превысила таймаут!", -1
    except Exception as e:
        return "", str(e), -1


def truncate(text: str, max_len: int = 4000) -> str:
    """Обрезка текста до допустимой длины Telegram."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 20] + "\n\n... (обрезано)"


# ─── Главное меню ────────────────────────────────────────────────
def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📊 Статус системы", callback_data="status"),
            InlineKeyboardButton("💾 Память", callback_data="memory"),
        ],
        [
            InlineKeyboardButton("💽 Диски", callback_data="disk"),
            InlineKeyboardButton("🔧 CPU", callback_data="cpu"),
        ],
        [
            InlineKeyboardButton("🌐 Сеть", callback_data="network"),
            InlineKeyboardButton("⚡ Speedtest", callback_data="speedtest"),
        ],
        [
            InlineKeyboardButton("📋 Процессы", callback_data="processes"),
            InlineKeyboardButton("🖥 Системная инфо", callback_data="sysinfo"),
        ],
        [
            InlineKeyboardButton("🔄 Перезагрузка", callback_data="reboot_confirm"),
            InlineKeyboardButton("📡 Ping", callback_data="ping"),
        ],
        [
            InlineKeyboardButton("🐍 Python Info", callback_data="python_info"),
            InlineKeyboardButton("🌍 IP Info", callback_data="ip_info"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ─── Команды ────────────────────────────────────────────────────
@admin_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню."""
    await update.message.reply_text(
        "🖥 *Railway Server Manager*\n\n"
        "Добро пожаловать в панель управления сервером!\n"
        "Выберите действие из меню ниже:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


@admin_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам."""
    help_text = """
🖥 *Railway Server Manager — Справка*

*Меню (кнопки):*
• 📊 Статус — общая информация
• 💾 Память — RAM и swap
• 💽 Диски — использование дисков
• 🔧 CPU — нагрузка процессора
• 🌐 Сеть — сетевые интерфейсы
• ⚡ Speedtest — скорость интернета
• 📋 Процессы — топ процессов
• 🖥 Системная инфо — детали ОС
• 🔄 Перезагрузка — рестарт
• 📡 Ping — проверка хоста
• 🐍 Python Info — версия Python
• 🌍 IP Info — внешний IP

*Текстовые команды:*
/start — главное меню
/help — эта справка
/shell `<команда>` — выполнить shell-команду
/exec `<код>` — выполнить Python-код
/upload — ответить на файл для загрузки
/download `<путь>` — скачать файл с сервера
/env — переменные окружения
/logs `<N>` — последние N строк логов
/install `<пакет>` — pip install
/menu — показать меню
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню кнопок."""
    await update.message.reply_text(
        "📋 *Выберите действие:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


@admin_only
async def cmd_shell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполнить shell-команду."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Использование: `/shell <команда>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    command = " ".join(context.args)
    msg = await update.message.reply_text(
        f"⏳ Выполняю: `{command}`...",
        parse_mode=ParseMode.MARKDOWN,
    )

    stdout, stderr, code = await run_shell(command)

    result = f"🖥 *Shell:* `{command}`\n"
    result += f"📟 *Код выхода:* `{code}`\n\n"

    if stdout:
        result += f"*Вывод:*\n```\n{truncate(stdout, 3500)}\n```\n"
    if stderr:
        result += f"*Ошибки:*\n```\n{truncate(stderr, 1000)}\n```"

    if not stdout and not stderr:
        result += "_Нет вывода_"

    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_exec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполнить Python-код."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Использование: `/exec <код>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    code = " ".join(context.args)
    msg = await update.message.reply_text("⏳ Выполняю Python-код...")

    old_stdout = sys.stdout
    sys.stdout = mystdout = __import__("io").StringIO()

    try:
        exec_globals = {"__builtins__": __builtins__}
        exec(code, exec_globals)
        output = mystdout.getvalue()
        result = f"🐍 *Python:*\n```python\n{code}\n```\n\n"
        if output:
            result += f"*Вывод:*\n```\n{truncate(output, 3500)}\n```"
        else:
            result += "_Нет вывода_"
    except Exception as e:
        result = f"🐍 *Python:*\n```python\n{code}\n```\n\n"
        result += f"❌ *Ошибка:*\n```\n{str(e)}\n```"
    finally:
        sys.stdout = old_stdout

    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_env(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать переменные окружения (без секретов)."""
    env_vars = dict(os.environ)

    # Скрываем чувствительные переменные
    sensitive = ["TOKEN", "KEY", "SECRET", "PASSWORD", "PASS", "AUTH"]
    for key in env_vars:
        for s in sensitive:
            if s in key.upper():
                env_vars[key] = "***HIDDEN***"

    text = "🔐 *Переменные окружения:*\n\n```\n"
    for key, value in sorted(env_vars.items()):
        text += f"{key}={value}\n"
    text = truncate(text, 3900) + "\n```"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скачать файл с сервера."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Использование: `/download <путь к файлу>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    filepath = " ".join(context.args)

    if not os.path.exists(filepath):
        await update.message.reply_text(f"❌ Файл не найден: `{filepath}`", parse_mode=ParseMode.MARKDOWN)
        return

    file_size = os.path.getsize(filepath)
    if file_size > 50 * 1024 * 1024:  # 50MB лимит Telegram
        await update.message.reply_text("❌ Файл слишком большой (>50MB)")
        return

    await update.message.reply_document(
        document=open(filepath, "rb"),
        filename=os.path.basename(filepath),
        caption=f"📁 `{filepath}`\n💾 {bytes_to_human(file_size)}",
        parse_mode=ParseMode.MARKDOWN,
    )


@admin_only
async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Загрузить файл на сервер."""
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text(
            "⚠️ Ответьте на сообщение с файлом командой `/upload [путь]`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    document = update.message.reply_to_message.document

    # Определяем путь для сохранения
    save_path = "/tmp/"
    if context.args:
        save_path = " ".join(context.args)
        os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
    else:
        save_path = os.path.join("/tmp/", document.file_name)

    file = await document.get_file()
    await file.download_to_drive(save_path)

    await update.message.reply_text(
        f"✅ Файл загружен!\n"
        f"📁 Путь: `{save_path}`\n"
        f"💾 Размер: {bytes_to_human(document.file_size)}",
        parse_mode=ParseMode.MARKDOWN,
    )


@admin_only
async def cmd_install(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить Python-пакет через pip."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Использование: `/install <пакет>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    package = " ".join(context.args)
    msg = await update.message.reply_text(f"⏳ Устанавливаю `{package}`...", parse_mode=ParseMode.MARKDOWN)

    stdout, stderr, code = await run_shell(f"pip install {package}", timeout=120)

    if code == 0:
        result = f"✅ *Пакет `{package}` установлен!*\n\n```\n{truncate(stdout, 3500)}\n```"
    else:
        result = f"❌ *Ошибка установки `{package}`*\n\n```\n{truncate(stderr, 3500)}\n```"

    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


@admin_only
async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последние строки логов."""
    lines = 50
    if context.args:
        try:
            lines = int(context.args[0])
        except ValueError:
            pass

    # Попытка прочитать разные лог-файлы
    log_files = ["/var/log/syslog", "/var/log/messages", "/tmp/app.log"]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            stdout, _, _ = await run_shell(f"tail -n {lines} {log_file}")
            if stdout:
                await update.message.reply_text(
                    f"📋 *Логи ({log_file}, последние {lines} строк):*\n\n```\n{truncate(stdout, 3800)}\n```",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

    # Если логов нет — показываем dmesg
    stdout, _, _ = await run_shell(f"dmesg | tail -n {lines}")
    if stdout:
        await update.message.reply_text(
            f"📋 *dmesg (последние {lines} строк):*\n\n```\n{truncate(stdout, 3800)}\n```",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("❌ Логи не найдены")


# ─── Обработчики кнопок ─────────────────────────────────────────
@admin_only
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на inline-кнопки."""
    query = update.callback_query
    await query.answer()

    data = query.data
    handlers = {
        "status": handle_status,
        "memory": handle_memory,
        "disk": handle_disk,
        "cpu": handle_cpu,
        "network": handle_network,
        "speedtest": handle_speedtest,
        "processes": handle_processes,
        "sysinfo": handle_sysinfo,
        "reboot_confirm": handle_reboot_confirm,
        "reboot_yes": handle_reboot,
        "reboot_no": handle_reboot_cancel,
        "ping": handle_ping_menu,
        "python_info": handle_python_info,
        "ip_info": handle_ip_info,
        "back_menu": handle_back_menu,
    }

    handler = handlers.get(data)
    if handler:
        await handler(query, context)


async def handle_status(query, context):
    """Общий статус системы."""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = seconds_to_human(int((datetime.now() - boot_time).total_seconds()))

    # Сетевые счётчики
    net = psutil.net_io_counters()

    text = (
        "📊 *Статус системы*\n\n"
        f"🖥 *Хост:* `{platform.node()}`\n"
        f"⏱ *Uptime:* `{uptime}`\n"
        f"🕐 *Время:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
        f"🔧 *CPU:* `{cpu_percent}%` ({psutil.cpu_count()} ядер)\n"
        f"💾 *RAM:* `{memory.percent}%` ({bytes_to_human(memory.used)}/{bytes_to_human(memory.total)})\n"
        f"💽 *Диск:* `{disk.percent}%` ({bytes_to_human(disk.used)}/{bytes_to_human(disk.total)})\n\n"
        f"📤 *Отправлено:* `{bytes_to_human(net.bytes_sent)}`\n"
        f"📥 *Получено:* `{bytes_to_human(net.bytes_recv)}`\n"
        f"📊 *Процессов:* `{len(psutil.pids())}`"
    )

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_memory(query, context):
    """Детальная информация о памяти."""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Прогресс-бар
    def bar(percent):
        filled = int(percent / 10)
        return "█" * filled + "░" * (10 - filled)

    text = (
        "💾 *Оперативная память (RAM)*\n\n"
        f"```\n"
        f"Всего:     {bytes_to_human(mem.total)}\n"
        f"Доступно:  {bytes_to_human(mem.available)}\n"
        f"Занято:    {bytes_to_human(mem.used)}\n"
        f"Процент:   {mem.percent}%\n"
        f"[{bar(mem.percent)}] {mem.percent}%\n"
        f"```\n\n"
        f"🔄 *Swap*\n\n"
        f"```\n"
        f"Всего:     {bytes_to_human(swap.total)}\n"
        f"Занято:    {bytes_to_human(swap.used)}\n"
        f"Свободно:  {bytes_to_human(swap.free)}\n"
        f"Процент:   {swap.percent}%\n"
        f"[{bar(swap.percent)}] {swap.percent}%\n"
        f"```"
    )

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_disk(query, context):
    """Информация о дисках."""
    partitions = psutil.disk_partitions()
    text = "💽 *Дисковые разделы*\n\n"

    for p in partitions:
        try:
            usage = psutil.disk_usage(p.mountpoint)
            filled = int(usage.percent / 10)
            bar = "█" * filled + "░" * (10 - filled)
            text += (
                f"📁 *{p.mountpoint}*\n"
                f"  Устройство: `{p.device}`\n"
                f"  ФС: `{p.fstype}`\n"
                f"  Всего: `{bytes_to_human(usage.total)}`\n"
                f"  Занято: `{bytes_to_human(usage.used)}`\n"
                f"  Свободно: `{bytes_to_human(usage.free)}`\n"
                f"  [{bar}] `{usage.percent}%`\n\n"
            )
        except PermissionError:
            text += f"📁 *{p.mountpoint}* — доступ запрещён\n\n"

    # IO статистика
    io = psutil.disk_io_counters()
    if io:
        text += (
            f"📊 *Дисковый I/O:*\n"
            f"  Прочитано: `{bytes_to_human(io.read_bytes)}`\n"
            f"  Записано: `{bytes_to_human(io.write_bytes)}`"
        )

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(truncate(text), parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_cpu(query, context):
    """Информация о CPU."""
    cpu_freq = psutil.cpu_freq()
    cpu_percent_per_core = psutil.cpu_percent(interval=1, percpu=True)
    cpu_times = psutil.cpu_times_percent(interval=0)

    text = "🔧 *Процессор (CPU)*\n\n"
    text += (
        f"📊 *Общая нагрузка:* `{psutil.cpu_percent()}%`\n"
        f"🧮 *Ядер (логич.):* `{psutil.cpu_count()}`\n"
        f"🧮 *Ядер (физ.):* `{psutil.cpu_count(logical=False) or 'N/A'}`\n"
    )

    if cpu_freq:
        text += (
            f"⚡ *Частота:*\n"
            f"  Текущая: `{cpu_freq.current:.0f} MHz`\n"
            f"  Мин: `{cpu_freq.min:.0f} MHz`\n"
            f"  Макс: `{cpu_freq.max:.0f} MHz`\n"
        )

    text += f"\n📊 *Нагрузка по ядрам:*\n```\n"
    for i, percent in enumerate(cpu_percent_per_core):
        filled = int(percent / 10)
        bar = "█" * filled + "░" * (10 - filled)
        text += f"Core {i}: [{bar}] {percent:5.1f}%\n"
    text += "```\n"

    text += (
        f"\n⏱ *Время CPU:*\n"
        f"  User: `{cpu_times.user}%`\n"
        f"  System: `{cpu_times.system}%`\n"
        f"  Idle: `{cpu_times.idle}%`"
    )

    # Load average
    try:
        load1, load5, load15 = os.getloadavg()
        text += (
            f"\n\n📈 *Load Average:*\n"
            f"  1 мин: `{load1:.2f}`\n"
            f"  5 мин: `{load5:.2f}`\n"
            f"  15 мин: `{load15:.2f}`"
        )
    except OSError:
        pass

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(truncate(text), parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_network(query, context):
    """Информация о сети."""
    net_io = psutil.net_io_counters()
    interfaces = psutil.net_if_addrs()

    text = "🌐 *Сетевая информация*\n\n"
    text += (
        f"📊 *Общий трафик:*\n"
        f"  📤 Отправлено: `{bytes_to_human(net_io.bytes_sent)}`\n"
        f"  📥 Получено: `{bytes_to_human(net_io.bytes_recv)}`\n"
        f"  📦 Пакетов отпр.: `{net_io.packets_sent:,}`\n"
        f"  📦 Пакетов получ.: `{net_io.packets_recv:,}`\n"
        f"  ❌ Ошибок: `{net_io.errin + net_io.errout}`\n\n"
    )

    text += "🔌 *Интерфейсы:*\n"
    for iface, addrs in interfaces.items():
        text += f"\n  📡 *{iface}:*\n"
        for addr in addrs:
            if addr.family == socket.AF_INET:
                text += f"    IPv4: `{addr.address}`\n"
            elif addr.family == socket.AF_INET6:
                text += f"    IPv6: `{addr.address[:30]}...`\n"

    # Активные соединения
    try:
        connections = psutil.net_connections(kind="inet")
        established = len([c for c in connections if c.status == "ESTABLISHED"])
        listening = len([c for c in connections if c.status == "LISTEN"])
        text += (
            f"\n🔗 *Соединения:*\n"
            f"  Установлено: `{established}`\n"
            f"  Слушает: `{listening}`\n"
            f"  Всего: `{len(connections)}`"
        )
    except (psutil.AccessDenied, PermissionError):
        pass

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(truncate(text), parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_speedtest(query, context):
    """Тест скорости интернета."""
    await query.edit_message_text(
        "⚡ *Запуск Speedtest...*\n\n"
        "⏳ Это может занять 30-60 секунд.\n"
        "Пожалуйста, подождите...",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        loop = asyncio.get_event_loop()

        def run_speedtest():
            st = speedtest.Speedtest()
            st.get_best_server()
            st.download()
            st.upload()
            return st.results.dict()

        results = await loop.run_in_executor(None, run_speedtest)

        download = results["download"] / 1_000_000  # Mbps
        upload = results["upload"] / 1_000_000  # Mbps
        ping = results["ping"]
        server = results["server"]

        text = (
            "⚡ *Результаты Speedtest*\n\n"
            f"📥 *Download:* `{download:.2f} Mbps`\n"
            f"📤 *Upload:* `{upload:.2f} Mbps`\n"
            f"📡 *Ping:* `{ping:.1f} ms`\n\n"
            f"🏢 *Сервер:*\n"
            f"  Имя: `{server.get('sponsor', 'N/A')}`\n"
            f"  Город: `{server.get('name', 'N/A')}`\n"
            f"  Страна: `{server.get('country', 'N/A')}`\n\n"
            f"🌐 *ISP:* `{results.get('client', {}).get('isp', 'N/A')}`\n"
            f"📍 *IP:* `{results.get('client', {}).get('ip', 'N/A')}`"
        )
    except Exception as e:
        text = f"❌ *Ошибка Speedtest:*\n\n`{str(e)}`"

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_processes(query, context):
    """Топ процессов по использованию ресурсов."""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            processes.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Сортируем по CPU
    processes.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
    top = processes[:15]

    text = "📋 *Топ-15 процессов (по CPU):*\n\n```\n"
    text += f"{'PID':>7} {'CPU%':>6} {'MEM%':>6} {'Статус':>10}  Имя\n"
    text += "-" * 55 + "\n"

    for p in top:
        text += (
            f"{p.get('pid', 0):>7} "
            f"{(p.get('cpu_percent') or 0):>5.1f}% "
            f"{(p.get('memory_percent') or 0):>5.1f}% "
            f"{(p.get('status') or 'N/A'):>10}  "
            f"{(p.get('name') or 'N/A')[:20]}\n"
        )
    text += f"```\n\n📊 *Всего процессов:* `{len(processes)}`"

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(truncate(text), parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_sysinfo(query, context):
    """Системная информация."""
    uname = platform.uname()

    text = (
        "🖥 *Системная информация*\n\n"
        f"💻 *ОС:* `{uname.system} {uname.release}`\n"
        f"📦 *Версия:* `{uname.version[:60]}`\n"
        f"🏗 *Архитектура:* `{uname.machine}`\n"
        f"🖥 *Имя хоста:* `{uname.node}`\n"
        f"🐍 *Python:* `{platform.python_version()}`\n"
        f"📋 *Платформа:* `{platform.platform()}`\n"
    )

    # Дополнительная информация через shell
    commands = {
        "Ядро": "uname -r",
        "Дистрибутив": "cat /etc/os-release 2>/dev/null | head -2",
    }

    for label, cmd in commands.items():
        stdout, _, _ = await run_shell(cmd, timeout=5)
        if stdout:
            text += f"📌 *{label}:* `{stdout.strip()[:100]}`\n"

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(truncate(text), parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_reboot_confirm(query, context):
    """Подтверждение перезагрузки."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, перезагрузить", callback_data="reboot_yes"),
            InlineKeyboardButton("❌ Отмена", callback_data="reboot_no"),
        ]
    ])
    await query.edit_message_text(
        "🔄 *Вы уверены, что хотите перезагрузить сервер?*\n\n"
        "⚠️ Все текущие процессы будут остановлены!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def handle_reboot(query, context):
    """Перезагрузка сервера."""
    await query.edit_message_text(
        "🔄 *Перезагрузка сервера...*\n\nБот будет недоступен некоторое время.",
        parse_mode=ParseMode.MARKDOWN,
    )
    # На Railway перезагрузка через завершение процесса (Railway перезапустит)
    await run_shell("kill 1 2>/dev/null; exit 0", timeout=5)
    os._exit(0)


async def handle_reboot_cancel(query, context):
    """Отмена перезагрузки."""
    await query.edit_message_text(
        "✅ *Перезагрузка отменена.*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


async def handle_ping_menu(query, context):
    """Ping меню — пинг популярных хостов."""
    hosts = {
        "Google DNS": "8.8.8.8",
        "Cloudflare": "1.1.1.1",
        "Google": "google.com",
        "GitHub": "github.com",
        "Railway": "railway.app",
    }

    text = "📡 *Ping результаты:*\n\n"

    for name, host in hosts.items():
        stdout, _, code = await run_shell(f"ping -c 3 -W 2 {host}", timeout=15)
        if code == 0:
            # Парсим среднее время
            lines = stdout.strip().split("\n")
            for line in lines:
                if "avg" in line or "rtt" in line:
                    parts = line.split("=")[-1].strip().split("/")
                    if len(parts) >= 2:
                        avg = parts[1]
                        text += f"✅ *{name}* (`{host}`): `{avg} ms`\n"
                        break
            else:
                text += f"✅ *{name}* (`{host}`): OK\n"
        else:
            text += f"❌ *{name}* (`{host}`): Недоступен\n"

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_python_info(query, context):
    """Информация о Python."""
    text = (
        "🐍 *Python Information*\n\n"
        f"📦 *Версия:* `{sys.version}`\n"
        f"📁 *Путь:* `{sys.executable}`\n"
        f"📋 *Платформа:* `{sys.platform}`\n"
        f"📊 *Макс. рекурсия:* `{sys.getrecursionlimit()}`\n"
        f"📐 *Макс. int:* `{sys.maxsize}`\n\n"
    )

    # Установленные пакеты
    stdout, _, _ = await run_shell("pip list --format=columns 2>/dev/null | head -20", timeout=10)
    if stdout:
        text += f"📦 *Установленные пакеты (первые 20):*\n```\n{stdout}\n```"

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(truncate(text), parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_ip_info(query, context):
    """Информация о внешнем IP."""
    await query.edit_message_text("🌍 *Определяю IP...*", parse_mode=ParseMode.MARKDOWN)

    # Пробуем через curl
    stdout, _, code = await run_shell("curl -s https://ipinfo.io/json", timeout=10)

    if code == 0 and stdout:
        try:
            import json
            data = json.loads(stdout)
            text = (
                "🌍 *Информация об IP*\n\n"
                f"📍 *IP:* `{data.get('ip', 'N/A')}`\n"
                f"🏙 *Город:* `{data.get('city', 'N/A')}`\n"
                f"🗺 *Регион:* `{data.get('region', 'N/A')}`\n"
                f"🌐 *Страна:* `{data.get('country', 'N/A')}`\n"
                f"📮 *Индекс:* `{data.get('postal', 'N/A')}`\n"
                f"🏢 *Организация:* `{data.get('org', 'N/A')}`\n"
                f"🕐 *Часовой пояс:* `{data.get('timezone', 'N/A')}`\n"
                f"📌 *Координаты:* `{data.get('loc', 'N/A')}`"
            )
        except Exception:
            text = f"🌍 *IP Info (raw):*\n```\n{stdout}\n```"
    else:
        # Fallback
        stdout2, _, _ = await run_shell("curl -s https://api.ipify.org", timeout=10)
        text = f"🌍 *Внешний IP:* `{stdout2.strip() if stdout2 else 'Не определён'}`"

    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]])
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb)


async def handle_back_menu(query, context):
    """Возврат в главное меню."""
    await query.edit_message_text(
        "🖥 *Railway Server Manager*\n\nВыберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


# ─── Обработка произвольных сообщений (quick shell) ─────────────
@admin_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Если сообщение начинается с $, выполнить как shell-команду."""
    text = update.message.text

    if text.startswith("$ "):
        command = text[2:]
        msg = await update.message.reply_text(
            f"⏳ `{command}`...",
            parse_mode=ParseMode.MARKDOWN,
        )
        stdout, stderr, code = await run_shell(command)

        result = ""
        if stdout:
            result += f"```\n{truncate(stdout, 3800)}\n```\n"
        if stderr:
            result += f"⚠️ ```\n{truncate(stderr, 500)}\n```"
        if not result:
            result = f"✅ Выполнено (код: {code})"

        await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ─── Обработка ошибок ───────────────────────────────────────────
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок."""
    logger.error(f"Exception: {context.error}", exc_info=context.error)
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"❌ *Произошла ошибка:*\n`{str(context.error)[:500]}`",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass


# ─── Запуск ─────────────────────────────────────────────────────
def main():
    """Запуск бота."""
    logger.info("🚀 Запуск Railway Server Manager Bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("shell", cmd_shell))
    app.add_handler(CommandHandler("sh", cmd_shell))
    app.add_handler(CommandHandler("exec", cmd_exec))
    app.add_handler(CommandHandler("env", cmd_env))
    app.add_handler(CommandHandler("download", cmd_download))
    app.add_handler(CommandHandler("upload", cmd_upload))
    app.add_handler(CommandHandler("install", cmd_install))
    app.add_handler(CommandHandler("logs", cmd_logs))

    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler))

    # Текстовые сообщения (quick shell с $)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Ошибки
    app.add_error_handler(error_handler)

    # Запуск
    logger.info("✅ Бот запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()