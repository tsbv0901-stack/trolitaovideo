import os, asyncio, uuid, subprocess, shutil
from pathlib import Path
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler

BOT_TOKEN = os.getenv("BOT_TOKEN", "DAN_TOKEN_CUA_ANH_VAO_DAY")
DATA_DIR = Path("data_user")
DATA_DIR.mkdir(exist_ok=True)
CHO_ANH_1, CHO_ANH_2, CHO_VIDEO_FLOW, CHO_TEXT = range(4)
W, H = 1080, 1920
PART1_DURATION = 9.0
BANNER_H = 580
VOICE = "vi-VN-NamMinhNeural"

def run_cmd(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:2000])
    return r

def wrap_text(text, max_chars=26):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur + " " + w) > max_chars:
            lines.append(cur.strip()); cur = w
        else:
            cur = cur + " " + w
    if cur: lines.append(cur.strip())
    return lines

async def create_voiceover(text, out_mp3):
    cmd = ["edge-tts", "--voice", VOICE, "--file", str(out_mp3), "--text", text]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        from gtts import gTTS
        gTTS(text=text, lang='vi').save(out_mp3)
    return out_mp3

def make_part1(img1_path, img2_path, hook_text, out_mp4, voice_mp3):
    tmpdir = Path(f"/tmp/{uuid.uuid4().hex}")
    tmpdir.mkdir(parents=True, exist_ok=True)
    left = tmpdir / "left.jpg"; right = tmpdir / "right.jpg"
    run_cmd(["ffmpeg","-y","-i",str(img1_path),"-vf","scale=540:1340:force_original_aspect_ratio=increase,crop=540:1340","-q:v","2",str(left)])
    run_cmd(["ffmpeg","-y","-i",str(img2_path),"-vf","scale=540:1340:force_original_aspect_ratio=increase,crop=540:1340","-q:v","2",str(right)])
    top = tmpdir / "top.jpg"
    run_cmd(["ffmpeg","-y","-i",str(left),"-i",str(right),"-filter_complex","[0:v][1:v]hstack=inputs=2[v]","[v]","-frames:v","1",str(top)])
    from PIL import Image, ImageDraw, ImageFont
    banner = Image.new("RGB", (W, BANNER_H), (139, 0, 0))
    draw = ImageDraw.Draw(banner)
    try:
        font = ImageFont.truetype("fonts/BeVietnamPro-Bold.ttf", 52)
    except:
        font = ImageFont.load_default()
    lines = wrap_text(hook_text.upper(), 26)
    draw.line([(60, 60), (60, BANNER_H-60)], fill="white", width=4)
    y = 70
    for line in lines:
        draw.text((100, y), line, font=font, fill="white")
        y += 75
    banner_path = tmpdir / "banner.jpg"; banner.save(banner_path)
    frame = tmpdir / "frame.jpg"
    run_cmd(["ffmpeg","-y","-i",str(top),"-i",str(banner_path),"-filter_complex","[0:v][1:v]vstack=inputs=2[v]","[v]","-frames:v","1",str(frame)])
    run_cmd(["ffmpeg","-y","-loop","1","-i",str(frame),"-i",str(voice_mp3),"-filter_complex","[0:v]scale=1080:1920,zoompan=z='min(zoom+0.0008,1.08)':d=225:s=1080x1920:fps=25[v]","-map","[v]","-map","1:a","-t",str(PART1_DURATION),"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(out_mp4)])
    shutil.rmtree(tmpdir, ignore_errors=True)
    return out_mp4

def make_final_video(part1_mp4, flow_video_path, out_final):
    tmpdir = Path(f"/tmp/{uuid.uuid4().hex}"); tmpdir.mkdir(parents=True, exist_ok=True)
    p2 = tmpdir / "part2.mp4"
    run_cmd(["ffmpeg","-y","-i",str(flow_video_path),"-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920","-t","10","-c:v","libx264","-pix_fmt","yuv420p","-an",str(p2)])
    concat_list = tmpdir / "list.txt"
    concat_list.write_text(f"file '{Path(part1_mp4).resolve()}'\nfile '{p2.resolve()}'\n")
    run_cmd(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat_list),"-c","copy",str(out_final)])
    shutil.rmtree(tmpdir, ignore_errors=True)
    return out_final

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Chao anh! Em la Tro Ly Tao Video.\n\nDe em lam video giong y khuon video kinh, anh gui cho em:\n1. Anh 1: Mau deo\n2. Anh 2: San pham\n3. Video Flow 10s\n4. Cau gioi thieu\n\nAnh gui Anh 1 cho em truoc nhe!")
    return CHO_ANH_1

async def nhan_anh_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    udir = DATA_DIR / str(update.effective_user.id); udir.mkdir(parents=True, exist_ok=True)
    f = await update.message.photo[-1].get_file(); p = udir / "anh1.jpg"; await f.download_to_drive(p)
    context.user_data["anh1"] = str(p)
    await update.message.reply_text("Em nhan Anh 1 roi. Anh gui tiep Anh 2 nhe!")
    return CHO_ANH_2

async def nhan_anh_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    udir = DATA_DIR / str(update.effective_user.id)
    f = await update.message.photo[-1].get_file(); p = udir / "anh2.jpg"; await f.download_to_drive(p)
    context.user_data["anh2"] = str(p)
    await update.message.reply_text("Em nhan Anh 2 roi. Anh gui tiep Video Flow 10s nhe!")
    return CHO_VIDEO_FLOW

async def nhan_video_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    udir = DATA_DIR / str(update.effective_user.id)
    vid = update.message.video or update.message.document
    f = await vid.get_file(); p = udir / "flow.mp4"; await f.download_to_drive(p)
    context.user_data["flow"] = str(p)
    await update.message.reply_text("Em nhan Video Flow roi. Cuoi cung anh nhan cau gioi thieu cho em nhe!")
    return CHO_TEXT

async def nhan_text_va_lam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text; context.user_data["text"] = text
    await update.message.reply_text("Em nhan du roi, em dang lam video cho anh, anh cho em 2 phut nhe...")
    udir = DATA_DIR / str(update.effective_user.id); uid = uuid.uuid4().hex[:8]
    out_dir = udir / uid; out_dir.mkdir(parents=True, exist_ok=True)
    parts = text.split(".")
    hook = (parts[0] + "." if parts else text)[:120]
    try:
        voice_full = out_dir / "voice_full.mp3"; await create_voiceover(text, voice_full)
        voice_hook = out_dir / "voice_hook.mp3"; await create_voiceover(hook, voice_hook)
        part1 = out_dir / "part1.mp4"
        await asyncio.to_thread(make_part1, context.user_data["anh1"], context.user_data["anh2"], hook, part1, voice_hook)
        final = out_dir / f"video_hoan_chinh_{uid}.mp4"
        await asyncio.to_thread(make_final_video, part1, context.user_data["flow"], final)
        await update.message.reply_video(video=InputFile(final), caption="Em lam xong roi, video cua anh day a!")
    except Exception as e:
        await update.message.reply_text(f"Em bi loi: {e}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Em huy roi, anh go /start de lam lai nhe.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(entry_points=[CommandHandler("start", start)], states={CHO_ANH_1: [MessageHandler(filters.PHOTO, nhan_anh_1)], CHO_ANH_2: [MessageHandler(filters.PHOTO, nhan_anh_2)], CHO_VIDEO_FLOW: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, nhan_video_flow)], CHO_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, nhan_text_va_lam)]}, fallbacks=[CommandHandler("cancel", cancel)])
    app.add_handler(conv); print("Bot dang chay..."); app.run_polling()

if __name__ == "__main__":
    main()
