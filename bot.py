import os, re, io, json, html
from datetime import datetime, timedelta, timezone
import requests
from PIL import Image, ImageDraw, ImageFont

CHANNEL = "bbcrussian"
TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MAX_NEWS = 6
W, M = 1080, 60
FD = "/usr/share/fonts/truetype/dejavu/"
PAPER, INK, GRAY = (244, 239, 225), (30, 30, 30), (95, 95, 95)
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def F(name, size):
    return ImageFont.truetype(FD + name, size)


def strip_junk(s):
    return re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f\u200d]", "", s).strip()


def get_posts():
    r = requests.get(f"https://t.me/s/{CHANNEL}",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    posts = []
    for part in r.text.split("tgme_widget_message_wrap")[1:]:
        m_id = re.search(r'data-post="([^"]+)"', part)
        m_tx = re.search(r'js-message_text[^>]*>(.*?)</div>', part, re.S)
        m_tm = re.search(r'<time[^>]*datetime="([^"]+)"', part)
        if not (m_id and m_tx and m_tm):
            continue
        t = re.sub(r"<br\s*/?>", "\n", m_tx.group(1))
        t = html.unescape(re.sub(r"<[^>]+>", "", t))
        lines = []
        for l in t.split("\n"):
            l = strip_junk(l)
            if (not l or l.startswith("http") or "Сайт без VPN" in l
                    or l.startswith("Подробнее")):
                continue
            lines.append(l)
        if not lines:
            continue
        title = re.sub(r"^[^\w«\"“(]+", "", lines[0])
        if len(title) < 10:
            continue
        rest = " ".join(lines[1:])
        if len(rest) > 200:
            cut = rest[:200]
            k = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
            rest = cut[:k + 1] if k > 80 else cut.rsplit(" ", 1)[0] + "…"
        posts.append({
            "title": title,
            "summary": rest,
            "url": "https://t.me/" + m_id.group(1),
            "time": datetime.fromisoformat(m_tm.group(1)),
        })
    return posts


def wrap(d, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        test = (cur + " " + w).strip()
        if d.textlength(test, font=font) <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_image(news):
    img = Image.new("RGB", (W, 6000), PAPER)
    d = ImageDraw.Draw(img)
    title_f = F("DejaVuSerif-Bold.ttf", 66)
    date_f = F("DejaVuSans.ttf", 26)
    head_f = F("DejaVuSerif-Bold.ttf", 36)
    body_f = F("DejaVuSerif.ttf", 28)

    y = 50
    t = "НОВОСТНАЯ ГАЗЕТА"
    d.text(((W - d.textlength(t, font=title_f)) / 2, y), t, font=title_f, fill=INK)
    y += 100
    d.line((M, y, W - M, y), fill=INK, width=4)
    y += 10
    d.line((M, y, W - M, y), fill=INK, width=1)
    y += 16
    now = datetime.now(timezone(timedelta(hours=3)))
    sub = f"{now.day} {MONTHS[now.month - 1]} {now.year} · BBC News Русская служба"
    d.text(((W - d.textlength(sub, font=date_f)) / 2, y), sub, font=date_f, fill=GRAY)
    y += 50
    d.line((M, y, W - M, y), fill=INK, width=2)
    y += 30

    for i, n in enumerate(news, 1):
        for line in wrap(d, f"{i}. {n['title']}", head_f, W - 2 * M):
            d.text((M, y), line, font=head_f, fill=INK)
            y += 48
        y += 4
        if n["summary"]:
            for line in wrap(d, n["summary"], body_f, W - 2 * M):
                d.text((M, y), line, font=body_f, fill=GRAY)
                y += 38
        y += 22
        d.line((M, y, W - M, y), fill=(190, 185, 170), width=1)
        y += 26
    return img.crop((0, 0, W, y + 20))


def main():
    posts = get_posts()
    now = datetime.now(timezone.utc)
    fresh = [p for p in posts if now - p["time"] < timedelta(hours=24)]
    news = list(reversed((fresh or posts)[-MAX_NEWS:]))
    if not news:
        print("Новостей не нашлось")
        return
    buf = io.BytesIO()
    make_image(news).save(buf, "PNG")
    kb = []
    for i, n in enumerate(news, 1):
        name = n["title"] if len(n["title"]) <= 50 else n["title"][:50] + "…"
        kb.append([{"text": f"{i}. {name}", "url": n["url"]}])
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
        data={"chat_id": CHAT_ID, "reply_markup": json.dumps({"inline_keyboard": kb})},
        files={"photo": ("gazeta.png", buf.getvalue(), "image/png")},
        timeout=60,
    )
    print(r.status_code, r.text[:300])
    if not r.ok:
        raise SystemExit(1)


main()
