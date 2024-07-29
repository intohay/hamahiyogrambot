import instaloader
import os
import config
import asyncio
import discord
from moviepy.editor import VideoFileClip
from datetime import datetime
# インスタンスを作成
L = instaloader.Instaloader()

L.login(config.USER_ID, config.PASSWD)

# Instagramのユーザー名
username = 'hiyotan928_official'

# プロファイルをダウンロード
profile = instaloader.Profile.from_username(L.context, username)


last_check_file = f"{username}_last_check.txt"

def load_last_check_time():
    if os.path.exists(last_check_file):
        with open(last_check_file, 'r') as file:
            timestamp = file.read().strip()
            return datetime.strptime(timestamp, '%Y-%m-%d_%H-%M-%S')
    return None

def save_last_check_time(timestamp):
    with open(last_check_file, 'w') as file:
        file.write(timestamp.strftime('%Y-%m-%d_%H-%M-%S'))

# Discord Botのセットアップ
intents = discord.Intents.all()
client = discord.Client(intents=intents)


async def download_and_post():
    await client.wait_until_ready()
    channel = client.get_channel(config.CHANNEL_ID)

    while not client.is_closed():
        last_check_time = load_last_check_time()
        new_last_check_time = last_check_time

        print("Downloading posts...")
        for post in profile.get_posts():
            post_time = post.date_utc
            if last_check_time is None or post_time > last_check_time:
                post_dir = f"{username}_posts"
                if not os.path.exists(post_dir):
                    os.makedirs(post_dir)
                L.download_post(post, target=post_dir)
                await post_all_media_to_discord(channel, post_dir, post)
                if new_last_check_time is None or post_time > new_last_check_time:
                    new_last_check_time = post_time
            else:
                break
        
        # print("Downloading reels...")
        # for reel in profile.get_igtv_posts():
        #     reel_time = reel.date_utc
        #     if last_check_time is None or reel_time > last_check_time:
        #         reel_dir = f"{username}_reels"
        #         if not os.path.exists(reel_dir):
        #             os.makedirs(reel_dir)
        #         L.download_post(reel, target=reel_dir)
        #         await post_all_media_to_discord(channel, reel_dir, reel)
        #         if new_last_check_time is None or reel_time > new_last_check_time:
        #             new_last_check_time = reel_time
        
        print("Downloading stories...")
        for story in L.get_stories(userids=[profile.userid]):
            for item in story.get_items():
                item_time = item.date_utc
                if last_check_time is None or item_time > last_check_time:
                    story_dir = f"{username}_stories"
                    if not os.path.exists(story_dir):
                        os.makedirs(story_dir)
                    L.download_storyitem(item, target=story_dir)
                    await post_all_media_to_discord(channel, story_dir, item)
                    if new_last_check_time is None or item_time > new_last_check_time:
                        new_last_check_time = item_time
                else:
                    break

        if new_last_check_time:
            save_last_check_time(new_last_check_time)

        print("All content has been downloaded.")

        await asyncio.sleep(60) # 1分ごとに実行

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
        await channel.send(content=f"New post from {username}:\n{instagram_link}", files=files)


def compress_video(input_path, output_path):
    clip = VideoFileClip(input_path)
    clip_resized = clip.resize(width=480)  # サイズを小さくして圧縮
    clip_resized.write_videofile(output_path, codec='libx264', audio_codec='aac', bitrate='500k')


@client.event
async def on_ready():
    print(f'Logged in as {client.user.name}')
    client.loop.create_task(download_and_post())

# ボットを実行
client.run(config.DISCORD_TOKEN)
