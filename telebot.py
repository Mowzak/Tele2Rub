import os
import re
import json
from pathlib import Path
from typing import Optional
import random
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import yt_dlp
import pyzipper
import subprocess


load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
QUEUE_DIR = BASE_DIR / "queue"
QUEUE_FILE = QUEUE_DIR / "tasks.jsonl"
#cache for saving url to download
CACHE  = QUEUE_DIR / "cache.json"

#saving users info (may be unnecessary)
SAVE = QUEUE_DIR / "saver.json"

#to keep users password
ZIP =  QUEUE_DIR / "zip.json"


SPLIT_SIZE = QUEUE_DIR / "split.json" # -> in Megabyte

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

open(CACHE , "w").write("{}")
open(SAVE , "w").write("{}")
open(ZIP , "w").write("{}")
open(QUEUE_FILE , "w").write("{}")
open(SPLIT_SIZE , "w").write("{}")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise RuntimeError("Please set API_ID, API_HASH and BOT_TOKEN in .env")

app = Client(
    "tel2rub",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


def safe_filename(name: Optional[str]) -> str:
    name = (name or "file.bin").strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    name = name.rstrip(". ")
    return name[:200] or "file.bin"


def split_name(filename: str) -> tuple[str, str]:
    path = Path(filename)
    return path.stem, path.suffix


def get_media(message: Message):
    media_types = [
        ("document", message.document),
        ("video", message.video),
        ("audio", message.audio),
        ("voice", message.voice),
        ("photo", message.photo),
        ("animation", message.animation),
        ("video_note", message.video_note),
        ("sticker", message.sticker),
    ]

    for media_type, media in media_types:
        if media:
            return media_type, media

    return None, None


def build_download_filename(message: Message, media_type: str, media) -> str:
    original_name = getattr(media, "file_name", None)

    if not original_name:
        file_unique_id = getattr(media, "file_unique_id", None) or "file"

        default_extensions = {
            "document": ".bin",
            "video": ".mp4",
            "audio": ".mp3",
            "voice": ".ogg",
            "photo": ".jpg",
            "animation": ".mp4",
            "video_note": ".mp4",
            "sticker": ".webp",
        }

        original_name = f"{file_unique_id}{default_extensions.get(media_type, '.bin')}"

    original_name = safe_filename(original_name)
    stem, suffix = split_name(original_name)

    unique_name = f"{stem}_{message.id}{suffix or '.bin'}"
    return safe_filename(unique_name)


def append_task(task: dict) -> None:
    with open(QUEUE_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(task, ensure_ascii=False) + "\n")


#progress message in downloading
async def prog(c,total,t,client,user_id):                                   
    #this function show the progress of downlaoing
    #to prevent error of fast editing i made random system to update the progres                                                                            
    try:                                                                    
        alf = random.randint(1,100)                                         
        # print(alf)   
        if c==total:
            await client.edit_message_text(                                 
            chat_id=t.chat.id,                                                          
            message_id=t.id,
            text=f"در حال دانلود {(c*100)/total:.1f}%"
        )                                        
        
        elif alf==50:                                                         
                                                                            
            await client.edit_message_text(                                 
            chat_id=t.chat.id,                                                          
            message_id=t.id,
            text=f"در حال دانلود {(c*100)/total:.1f}%"
        )
    except Exception as e:
        print(e)
        pass
    


@app.on_message(filters.private & filters.command("start"))
async def start_handler(client: Client, message: Message):

    start_message = """فایل رو بفرست
    برای دانلود از لینک از دستور /link <url> استفاده کن.
    برای زیپ کردن /zip
    برای پارتیشن بندی و ارسال /split"""
    await message.reply_text(start_message)


@app.on_message(
    filters.private
    & (
        filters.document
        | filters.video
        | filters.audio
        | filters.voice
        | filters.photo
        | filters.animation
        | filters.video_note
        | filters.sticker
    )
)
async def media_handler(client: Client, message: Message):
    media_type, media = get_media(message)
    if not media:
        await message.reply_text("فایل قابل پردازش نیست.")
        return

    download_name = build_download_filename(message, media_type, media)
    download_path = DOWNLOAD_DIR / download_name

    password = json.load(open(ZIP ,"r",encoding="UTF-8")).get(str(message.from_user.id),"")
    zip_size = json.load(open(SPLIT_SIZE,"r",encoding="utf-8")).get(str(message.from_user.id),400)

    sending_tx = f"""فایل رفت توی صف پردازش.
    وضعیت زیپ: {"/zip قابلیت زیپ کردن خاموش است" if password=="" else password}
    پارت بندی: {zip_size}"""
    status = await message.reply_text(sending_tx)
    try:
        downloaded = await client.download_media(
            message,
            file_name=str(download_path),
            progress=prog,progress_args= (status,client,message.from_user.id)
        )

        if not downloaded:
            await status.edit_text("مشکلی در دانلود فایل پیش آمد \n{downloaded}")
            raise RuntimeError("Download failed.")


        download_path = Path(download_path)
        zip_name = download_path.with_suffix(".zip")
        


        path_list = [str(download_path)]

        if not password == "":
            await status.edit_text("zipping...")
            with pyzipper.AESZipFile(zip_name, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(password.encode())
                zf.write(download_path, arcname=download_path.name)
            download_path = zip_name
            path_list = [str(download_path)]

            # Path to rar (usually in PATH; otherwise specify full path e.g. /usr/bin/rar)
            size_bytes = os.path.getsize(download_path)

            
            if (size_bytes / (1024*1024)) > zip_size:
                await status.edit_text("parting...")

                
                output_archive = download_path.with_suffix(".zip")
                name_output = Path(output_archive).with_suffix('')

                part_size = zip_size * 1024 * 1024
                path_list = []
                with open(download_path, "rb") as f:
                    part = 1
                    while True:
                        chunk = f.read(part_size)
                        if not chunk:
                            break
                        with open(f"{name_output}.part{part}", "wb") as out:
                            out.write(chunk)
                        path_list.append(f"{name_output}.part{part}")

                        part += 1






        await status.edit_text("فایل از تلگرام با موفقیت دانلود شد.")


        


        task = {
            "type": "local_file",
            "path": path_list,
            "caption": message.caption or "",
            "chat_id": message.chat.id,
            "status_message_id": status.id,
        }

        infos = [message.from_user.id,message.from_user.username,message.chat.id]
        save_user(str(path_list),infos)
        append_task(task)

    except Exception as e:
        await status.edit_text(f"خطا: {str(e)}")



#########################################################################
#download link section  
def add_cache(id,url):

    with open(CACHE ,"r",encoding="UTF-8") as f:
        data = json.load(f)
    
    data[id] = url
    with open(CACHE , "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data

def read_cache():

    with open(CACHE ,"r",encoding="UTF-8") as f:
        data = json.load(f)

    return data

def save_user(path, info):
    with open(SAVE,"r",encoding="UTF-8") as f:
        data = json.load(f)
    
    data[path] = info
    with open(SAVE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_formats(url):
    ydl_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []
    for f in info["formats"]:
        if f.get("ext") and f.get("format_id"):
            formats.append({
                "id": f["format_id"],
                "ext": f["ext"],
                "res": f.get("format_note") or f.get("height") or f.get("format") or f.get("resolution"),
                "url":f.get("url")
            })
    return formats


@app.on_message(filters.command("link"))
async def link_handler(client, message):
    url = message.command[1].strip()

    try:
        formats = get_formats(url)
    except:
        await message.reply("Failed to read video.")
        return
    
    add_cache(message.id,url)

    buttons = []
    urls = "لینک‌ها به‌ترتیب همراه با دکمه‌ها قرار داده شده‌اند:\n"
    for f in formats:
        urls += f["url"]+"\n"
        label = f'{f["res"]}--{f["ext"]}'
        data = f"{message.id}|{f['id']}|{f['ext']}"
        buttons.append([InlineKeyboardButton(label, callback_data=data)])

    await message.reply(urls)
    await message.reply(
        "Select format:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_callback_query()
async def callback_handler(client, callback_query):
    msg_id, format_id,ext = callback_query.data.split("|")
    url_cache = read_cache()

    url = url_cache.get(msg_id)

    if not url:
        await callback_query.answer("Expired.")
        return


    filename = f"download_{msg_id}_{format_id}.{ext}"
    ydl_opts = {
        "format": format_id,
        "outtmpl": filename
    }
    await callback_query.message.edit_text("در حال دانلود...")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)

    await callback_query.message.edit_text("درحال ارسال...")
    
    await client.send_document(
        chat_id=callback_query.message.chat.id,
        document=file_path,
        caption=filename,
        reply_to_message_id=callback_query.message.id
    )
    

    os.remove(filename)

################################
#zip files

def update_zip(state,user,password):
    user = str(user)
    with open(ZIP ,"r",encoding="UTF-8") as f:
        data = json.load(f)

    print(data)
    print(data.get(user,None))
    if not data.get(user,None):
        data[user] = ""
    if state:
        data[user] = password
    else:
        data[user] = ""

    with open(ZIP , "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@app.on_message(filters.command("zip"))
def ask_file(client, message):
    parts = message.text.split()




    if len(parts) == 1: 
        update_zip(False,message.from_user.id,"")
        message.reply("قابلیت زیب کردن خاموش شد.")
        return
    if len(parts) == 2:
        password = parts[1]
        update_zip(True,message.from_user.id,password)
        message.reply("پسورد ذخیره شد، فایل را ارسال کنید")
    else:
        txt = """
        فرمت صحیح به صورت:
        /zip <password>"""
        message.reply(txt)



#######################

def update_size(message,size):
    with open(SPLIT_SIZE,"r",encoding="utf-8") as f:
        data = json.load(f)

    data[str(message.from_user.id)] = int(size)

    with open(SPLIT_SIZE , "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@app.on_message(filters.command("split"))
def split(client, message):
    parts = message.text.split()
    
    if len(parts) == 2:
        size = parts[1]
        if size.isnumeric():

            update_size(message,size)


            message.reply(f"پارتیشن سایز: {size}")
        else:
            message.reply(f"عدد بده!")
    else:
        txt = """
        فرمت صحیح به صورت:
        /split <size>"""
        message.reply(txt)

if __name__ == "__main__":
    app.run()
