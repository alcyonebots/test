import os
import random
import asyncio
import re
from pathlib import Path

from telethon import TelegramClient, functions, types
from telethon.errors.rpcerrorlist import FloodWaitError
from telethon.network import proxy

from colorama import Fore, Style, init as colorama_init

# Initialize colorama for colored terminal output
colorama_init(autoreset=True)

# API credentials
API_ID = 29872536
API_HASH = '65e1f714a47c0879734553dc460e98d6'

# Paths
SESSIONS_DIR = Path(__file__).parent / 'sessions'
PROXY_FILE = Path(__file__).parent / 'proxy.txt'

# Report reasons mapping to Telethon types
REASONS = {
    "Pornography": types.ReportReasonPornography(),
    "Spam": types.ReportReasonSpam(),
    "Violence": types.ReportReasonViolence(),
    "Child Abuse": types.ReportReasonChildAbuse(),
    "Other": types.ReportReasonOther()
}


def banner():
    print(Fore.CYAN + "="*50)
    print(Fore.GREEN + "     Telegram Report Automation Tool     ")
    print(Fore.CYAN + "="*50)


def load_sessions():
    if not SESSIONS_DIR.exists():
        print(Fore.RED + f"[!] Sessions directory '{SESSIONS_DIR}' not found.")
        return []
    session_files = list(SESSIONS_DIR.glob('*.session'))
    if not session_files:
        print(Fore.RED + f"[!] No .session files found in '{SESSIONS_DIR}'.")
        return []
    return session_files


def load_proxies():
    proxies = []
    if not PROXY_FILE.exists():
        print(Fore.YELLOW + f"No proxy file '{PROXY_FILE}' found. Continuing without proxies.")
        return proxies

    with open(PROXY_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(':')
            if len(parts) == 2:
                # host:port
                host, port = parts
                proxies.append((host, int(port), None, None))
            elif len(parts) == 4:
                # host:port:user:pass
                host, port, user, pwd = parts
                proxies.append((host, int(port), user, pwd))
            else:
                print(Fore.YELLOW + f"Invalid proxy format skipped: {line}")
    return proxies


def get_telethon_proxy(proxy_tuple):
    if proxy_tuple is None:
        return None
    host, port, user, pwd = proxy_tuple
    # Telethon proxy tuple format:
    # (proxy_type, addr, port, rdns, username, password)
    # Using SOCKS5 proxy here:
    return (proxy.SOCKS5, host, port, True, user, pwd)


def parse_msg_link(link):
    """
    Parse Telegram message link to extract entity (username or peer id) and msg_id.
    Supports links in formats like:
    - https://t.me/username/123
    - https://t.me/c/123456789/123

    Returns tuple (entity, msg_id) or (None, None) on failure.
    """
    m = re.match(r"https?://t\.me/(c/)?([\w\d_]+)/(\d+)", link)
    if not m:
        return None, None

    is_private = m.group(1) == 'c/'
    channel_part = m.group(2)
    msg_id = int(m.group(3))

    if is_private:
        try:
            channel_id = int(channel_part)
            entity = int("-100" + str(channel_id))
        except:
            entity = channel_part
    else:
        entity = channel_part

    return entity, msg_id


async def send_report(client, entity, reason, message_text, msg_id=None):
    """
    Sends a report using the TelegramClient.

    Returns:
    - True if report sent successfully.
    - "flood" if FloodWaitError encountered.
    - False on other errors.
    """
    try:
        if msg_id:
            # Reporting a specific message
            await client(functions.messages.ReportRequest(
                peer=entity,
                id=[msg_id],
                reason=reason,
                message=message_text
            ))
        else:
            # Reporting user/channel/group
            await client(functions.account.ReportRequest(
                peer=entity,
                reason=reason,
                message=message_text
            ))
        return True

    except FloodWaitError as e:
        print(Fore.YELLOW + f"Flood limit hit, sleeping for {e.seconds} seconds.")
        await asyncio.sleep(e.seconds + 1)
        return "flood"

    except Exception as e:
        print(Fore.RED + f"Report failed with error: {e}")
        return False


async def main_menu():
    banner()

    sessions = load_sessions()
    if not sessions:
        return

    proxies = load_proxies()

    print(Fore.CYAN + f"🔐 Loaded sessions: {len(sessions)}")
    print(Fore.MAGENTA + f"🌐 Loaded proxies:  {len(proxies)}\n")

    report_per_session = input(Fore.GREEN + "💣 How many reports per session? ").strip()
    while not report_per_session.isdigit() or int(report_per_session) < 1:
        report_per_session = input("Enter a valid number (>=1): ").strip()
    report_per_session = int(report_per_session)

    print("\n🧭 What do you want to report?")
    print("1. Telegram User")
    print("2. Channel")
    print("3. Group")
    print("4. Specific Message")
    choice = input("🟢 Choice (1-4): ").strip()
    while choice not in {'1', '2', '3', '4'}:
        choice = input("Enter valid choice (1-4): ").strip()

    entity = None
    msg_id = None

    if choice == "4":
        msg_link = input("🔗 Enter full message link (public/private): ").strip()
        entity, msg_id = parse_msg_link(msg_link)
        if not entity:
            print(Fore.RED + "❌ Invalid message link. Aborting.")
            return
    else:
        entity = input("🔗 Enter username, ID or invite link: ").strip()
        if not entity:
            print(Fore.RED + "❌ Invalid input. Aborting.")
            return

    print("\n📚 Available reasons:")
    for i, key in enumerate(REASONS.keys(), 1):
        print(Fore.YELLOW + f"{i}. {key}")
    while True:
        r = input("➡ Select reason number: ").strip()
        if r.isdigit() and 1 <= int(r) <= len(REASONS):
            reason = list(REASONS.values())[int(r) - 1]
            reason_text = list(REASONS.keys())[int(r) - 1]
            break
        else:
            print("Invalid choice. Try again.")

    msg_text = input("📝 Enter report message: ").strip()
    if not msg_text:
        msg_text = "No additional message."

    print(Fore.CYAN + "\n🚀 Launching reports...\n")

    success, failed, flood = 0, 0, 0

    for idx, session_path in enumerate(sessions, 1):
        proxy_tuple = random.choice(proxies) if proxies else None
        proxy = get_telethon_proxy(proxy_tuple)

        session_name = session_path.stem

        client = TelegramClient(
            str(SESSIONS_DIR / session_name),
            API_ID,
            API_HASH,
            proxy=proxy,
        )

        try:
            await client.connect()

            if not await client.is_user_authorized():
                print(Fore.RED + f"[{idx}] Session '{session_name}' is not authorized. Skipping.")
                failed += report_per_session
                await client.disconnect()
                continue

            name = session_path.name

            for rpt in range(report_per_session):
                result = await send_report(client, entity, reason, msg_text, msg_id=msg_id)
                status = f"[{idx}:{rpt + 1}]"
                if result is True:
                    print(Fore.GREEN + f"{status} ✅ Report sent from {name}")
                    success += 1
                elif result == "flood":
                    print(Fore.YELLOW + f"{status} ⚠️ Flood limit hit from {name}. Skipping remaining reports for this session.")
                    flood += 1
                    break
                else:
                    print(Fore.RED + f"{status} ❌ Failed from {name}")
                    failed += 1

            await client.disconnect()

        except Exception as e:
            print(Fore.RED + f"[{idx}] ❌ Client error: {e}")
            failed += report_per_session

    total_attempts = len(sessions) * report_per_session
    print(Style.BRIGHT + "\n📊 Final Report Summary:")
    print(Fore.GREEN + f"✅ Successful: {success}")
    print(Fore.YELLOW + f"⚠️  FloodWaits:  {flood}")
    print(Fore.RED + f"❌ Failed:     {failed}")
    print(Fore.CYAN + f"🧮 Total Attempts: {total_attempts}")
    print(Fore.GREEN + "\n🎯 Done.\n")


if __name__ == "__main__":
    try:
        asyncio.run(main_menu())
    except KeyboardInterrupt:
        print(Fore.RED + "\n[!] Interrupted by user. Exiting...")
