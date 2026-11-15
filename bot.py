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
MSK = timezone(timedelta(hours=3))


def F(name, size):
    return ImageFont.truetype(FD + name, size)


def strip_junk(s):
    return re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f\u200d]", "", s).strip()


def short(s, n):
    if len(s) <= n:
        return s
    cut = s[:n]
    k = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:k + 1] if k > n * 0.4 else cut.rsplit(" ", 1)[0] + "…"


def parse_posts(text):
    posts = []
    for part in text.split("tgme_widget_message_wrap")[1:]:
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
        posts.append({
            "title": title,
            "summary": short(" ".join(lines[1:]), 300),
            "url": "https://t.me/" + m_id.group(1),
            "time": datetime.fromisoformat(m_tm.group(1)),
        })
    return posts


def get_day_posts():
    day_start = datetime.now(MSK).replace(hour=0, minute=0, second=0, microsecond=0)
    found = {}
    url = f"https://t.me/s/{CHANNEL}"
    for _ in range(8):
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        page = parse_posts(r.text)
        for p in page:
            found[p["url"]] = p
        if page and min(p["time"] for p in page) < day_start:
            break
        m = re.search(r"/s/" + CHANNEL + r"\?before=(\d+)", r.text)
        if not m:
            break
        url = f"https://t.me/s/{CHANNEL}?before={m.group(1)}"
    today = [p for p in found.values() if p["time"] >= day_start]
    return sorted(today, key=lambda p: p["time"], reverse=True)


CSS = """
:root{--bg:#f4efe1;--ink:#1e1e1e;--gray:#5f5f5f;--line:#cfc8b2;--card:#faf6ea}
@media (prefers-color-scheme:dark){:root{--bg:#15171c;--ink:#ece8da;--gray:#a9a597;--line:#33363e;--card:#1d2027}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Georgia,"DejaVu Serif",serif;padding:14px 14px 40px;max-width:760px;margin:0 auto}
header{text-align:center;border-top:4px double var(--ink);border-bottom:2px solid var(--ink);padding:12px 0 10px;margin-bottom:16px}
h1{margin:0;font-size:30px;letter-spacing:1px}
.sub{color:var(--gray);font-size:14px;margin-top:6px;font-family:Arial,sans-serif}
.item{display:flex;gap:12px;text-decoration:none;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:10px}
.time{font-family:Arial,sans-serif;font-weight:bold;font-size:15px;color:var(--gray);min-width:46px;padding-top:2px}
h2{margin:0 0 6px;font-size:19px;line-height:1.25}
p{margin:0;color:var(--gray);font-size:15px;line-height:1.4}
.empty{text-align:center;color:var(--gray);padding:40px 0}
"""


def make_page(posts):
    now = datetime.now(MSK)
    items = []
    for p in posts:
        t = p["time"].astimezone(MSK).strftime("%H:%M")
        summ = f"<p>{html.escape(p['summary'])}</p>" if p["summary"] else ""
        items.append(
            f'<a class="item" href="{html.escape(p["url"])}">'
            f'<div class="time">{t}</div>'
            f'<div><h2>{html.escape(p["title"])}</h2>{summ}</div></a>'
        )
    body = "\n".join(items) if items else '<div class="empty">Пока новостей за сегодня нет</div>'
    date = f"{now.day} {MONTHS[now.month - 1]} {now.year}"
    return (
        '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Новостная газета</title><style>' + CSS + '</style></head><body>'
        '<header><h1>НОВОСТНАЯ ГАЗЕТА</h1>'
        f'<div class="sub">{date} · BBC News Русская служба · новостей: {len(posts)} · обновлено {now.strftime("%H:%M")}</div>'
        '</header>' + body + '</body></html>'
    )


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
    now = datetime.now(MSK)
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
            for line in wrap(d, short(n["summary"], 200), body_f, W - 2 * M):
                d.text((M, y), line, font=body_f, fill=GRAY)
                y += 38
        y += 22
        d.line((M, y, W - M, y), fill=(190, 185, 170), width=1)
        y += 26
    return img.crop((0, 0, W, y + 20))


def main():
    posts = get_day_posts()
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(make_page(posts))
    print("Новостей за сегодня:", len(posts))

    now = datetime.now(timezone.utc)
    fresh = [p for p in posts if now - p["time"] < timedelta(hours=4, minutes=30)]
    news = fresh[:MAX_NEWS]
    if not news:
        print("Новых новостей для бота нет")
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
    print("Телеграм ответил:", r.status_code)
    if not r.ok:
        raise SystemExit(1)


main()
