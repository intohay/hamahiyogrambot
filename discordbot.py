import instaloader
import os
import config
import asyncio
import discord
from moviepy.editor import VideoFileClip
from datetime import datetime, time, timedelta
import random


class CustomInstaloaderContext(instaloader.InstaloaderContext):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_headers = {
            'User-Agent': 'Instagram 343.0.0.23.93 (iPhone14,7; iOS 17_5_1; en_JP; en-JP; scale=3.00; 1170x2532; 629030903) AppleWebKit/420+',
        }

    def _send_request(self, req):
        for header, value in self.custom_headers.items():
            req.headers[header] = value
        return super()._send_request(req)

class CustomInstaloader(instaloader.Instaloader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = CustomInstaloaderContext(self)


# インスタンスを作成
L = instaloader.Instaloader()

# セッションファイルのパス
session_file = f"{config.USER_ID}_session"

def login():
    try:
        if os.path.exists(session_file):
            print("Loading session from file...")
            L.load_session_from_file(config.USER_ID, session_file)
        else:
            raise FileNotFoundError
    except (FileNotFoundError, instaloader.exceptions.ConnectionException):
        print("Logging in...")
        try:
            L.login(config.USER_ID, config.PASSWD)
            L.save_session_to_file(session_file)
        except instaloader.exceptions.LoginException as e:
            print(f"Login failed: {e}")
            exit(1)  # ログイン失敗時にプログラムを終了


login()

# Instagramのユーザー名
username = 'hiyotan928_official'

# プロファイルをダウンロード
profile = instaloader.Profile.from_username(L.context, username)


last_check_file = f"{username}_last_check.txt"
last_story_check_file = f"{username}_last_story_check.txt"

def load_last_check_time(file):
    if os.path.exists(file):
        with open(file, 'r') as f:
            timestamp = f.read().strip()
            return datetime.strptime(timestamp, '%Y-%m-%d_%H-%M-%S')
    return None

def save_last_check_time(timestamp, file):
    with open(file, 'w') as f:
        f.write(timestamp.strftime('%Y-%m-%d_%H-%M-%S'))


# Discord Botのセットアップ
intents = discord.Intents.all()
client = discord.Client(intents=intents)


async def download_and_post():
    await client.wait_until_ready()
    channel = client.get_channel(config.CHANNEL_ID)

    print("Checking posts...")
    while not client.is_closed():
        last_check_time = load_last_check_time(last_check_file)
        new_last_check_time = last_check_time

        post_dir = f"{username}_posts"

        print("Downloading posts...")
        posts = []

        for post in profile.get_posts():
            post_time = post.date_utc
            if last_check_time is None or post_time > last_check_time:
                if not os.path.exists(post_dir):
                    os.makedirs(post_dir)
                L.download_post(post, target=post_dir)
                posts.append(post)
                if new_last_check_time is None or post_time > new_last_check_time:
                    new_last_check_time = post_time
            else:
                break
        
        posts.reverse()
        for post in posts:
            await post_all_media_to_discord(channel, post_dir, post)
        
        if new_last_check_time:
            save_last_check_time(new_last_check_time, last_check_file)

        print("All content has been downloaded.")

        await asyncio.sleep(300)  # 5分ごとに実行

async def download_and_post_stories():
    await client.wait_until_ready()
    channel = client.get_channel(config.CHANNEL_ID)

    start_time = time(7, 0)  # 7:00 AM
    end_time = time(0, 0)    # 24:00 AM (midnight)

    print("Checking stories...")
    while not client.is_closed():
        now = datetime.now().time()
        if start_time <= now <= end_time:
            try:
                print("Checking stories...")
                print("Logging in...")
                login()  # ログインを再確認
                last_story_check_time = load_last_check_time(last_story_check_file)
                new_last_story_check_time = last_story_check_time

                story_dir = f"{username}_stories"

                print("Downloading stories...")
                stories = []

                for story in L.get_stories(userids=[profile.userid]):
                    for item in story.get_items():
                        item_time = item.date_utc
                        if last_story_check_time is None or item_time > last_story_check_time:
                            if not os.path.exists(story_dir):
                                os.makedirs(story_dir)
                            L.download_storyitem(item, target=story_dir)
                            stories.append(item)
                            if new_last_story_check_time is None or item_time > new_last_story_check_time:
                                new_last_story_check_time = item_time
                        else:
                            break
                
                stories.reverse()
                for story in stories:
                    await post_all_media_to_discord(channel, story_dir, story)

                if new_last_story_check_time:
                    save_last_check_time(new_last_story_check_time, last_story_check_file)

                print("All stories have been downloaded.")
            except instaloader.exceptions.ConnectionException as e:
                print(f"Connection error: {e}. Waiting before retrying...")
                await asyncio.sleep(600)  # 10分待機して再試行
                login()

            # 15〜25分のランダムな時間を待機
            wait_seconds = random.randint(15 * 60, 25 * 60)
            print(f"Waiting for {wait_seconds / 60:.2f} minutes before the next check.")
            await asyncio.sleep(wait_seconds)
        else:
            # 現在の時間が指定範囲外の場合、7時まで待機
            next_start = datetime.combine(datetime.today(), start_time)
            if now > start_time:
                next_start += timedelta(days=1)
            wait_seconds = (next_start - datetime.now()).total_seconds()
            print(f"Out of scheduled time range. Waiting for {wait_seconds / 3600:.2f} hours until 7:00 AM.")
            await asyncio.sleep(wait_seconds)

async def post_all_media_to_discord(channel, post_dir, post):
    post_timestamp = post.date_utc.strftime('%Y-%m-%d_%H-%M-%S')
    media_files = []

    for filename in os.listdir(post_dir):
        if filename.startswith(post_timestamp) and filename.endswith(('jpg', 'mp4')):
            file_path = os.path.join(post_dir, filename)
            if os.path.isfile(file_path):
                if file_path.endswith('.mp4') and os.path.getsize(file_path) > 8 * 1024 * 1024:
                    # 動画を圧縮
                    compressed_path = os.path.join(post_dir, f"compressed_{filename}")
                    compress_video(file_path, compressed_path)
                    file_path = compressed_path
                media_files.append(file_path)

    if media_files:
        files = [discord.File(fp, filename=os.path.basename(fp)) for fp in media_files]
        instagram_link = f"https://www.instagram.com/p/{post.shortcode}/"
        await channel.send(content=f"はまひよグラムが更新されました！\n{instagram_link}", files=files)


def compress_video(input_path, output_path):
    target_size = 8 * 1024 * 1024  # 8MB
    clip = VideoFileClip(input_path)
    clip_resized = clip.resize(width=480)  # サイズを小さくして圧縮

    # 初期ビットレートを計算
    duration = clip.duration
    initial_bitrate = 500 * 1024  # 500kbps in bits
    bitrate = initial_bitrate

    clip_resized.write_videofile(output_path, codec='libx264', audio_codec='aac', bitrate=f'{bitrate}k')

    while os.path.getsize(output_path) > target_size:
        # ビットレートを下げて再試行
        bitrate -= 50 * 1024  # 50kbps 減らす
        if bitrate <= 0:
            raise ValueError("Could not compress the video below 8MB")
        clip_resized.write_videofile(output_path, codec='libx264', audio_codec='aac', bitrate=f'{bitrate}k')

@client.event
async def on_ready():
    print(f'Logged in as {client.user.name}')
    client.loop.create_task(download_and_post())
    client.loop.create_task(download_and_post_stories())

# ボットを実行
client.run(config.DISCORD_TOKEN)
