import os, re, io, json, html
from datetime import datetime, timedelta, timezone
import requests
from PIL import Image, ImageDraw, ImageFont

CHANNELS = [
    ("bbcrussian", "BBC", "#bb1919"),
    ("meduzalive", "Медуза", "#2f7bd9"),
    ("astrapress", "ASTRA", "#e0861a"),
]
TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MAX_NEWS = 10
W, M = 1080, 60
FD = "/usr/share/fonts/truetype/dejavu/"
PAPER, INK, GRAY = (244, 239, 225), (30, 30, 30), (95, 95, 95)
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]
MSK = timezone(timedelta(hours=3))
SKIP = ("http", "Подробнее", "Открыть", "Фото", "Видео",
        "Защитить себя", "Please open", "VIEW IN")


def F(name, size):
    return ImageFont.truetype(FD + name, size)


def strip_junk(s):
    return re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f\u200d]", "", s).strip()


def is_junk(l):
    return (not l or l.startswith(SKIP) or "Сайт без VPN" in l
            or re.fullmatch(r"[—–\-_=*\s]+", l) is not None)


def short(s, n):
    if len(s) <= n:
        return s
    cut = s[:n]
    k = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:k + 1] if k > n * 0.4 else cut.rsplit(" ", 1)[0] + "…"


def parse_posts(text, ch):
    _, label, color = ch
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
        for x in t.split("\n"):
            l = strip_junk(x)
            if not is_junk(l):
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
            "src": label,
            "color": color,
        })
    return posts


def get_channel_posts(ch, day_start):
    found = {}
    url = f"https://t.me/s/{ch[0]}"
    last_before = None
    for _ in range(8):
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        page = parse_posts(r.text, ch)
        for p in page:
            found[p["url"]] = p
        if page and min(p["time"] for p in page) < day_start:
            break
        nums = [int(x) for x in re.findall(r"\?before=(\d+)", r.text)]
        if not nums:
            break
        nxt = min(nums)
        if last_before is not None and nxt >= last_before:
            break
        last_before = nxt
        url = f"https://t.me/s/{ch[0]}?before={nxt}"
    return [p for p in found.values() if p["time"] >= day_start]


def get_day_posts():
    day_start = datetime.now(MSK).replace(hour=0, minute=0, second=0, microsecond=0)
    allp, errors = [], 0
    for ch in CHANNELS:
        try:
            allp += get_channel_posts(ch, day_start)
        except Exception as e:
            errors += 1
            print("Канал не прочитался:", ch[0], type(e).__name__)
    if errors == len(CHANNELS):
        raise SystemExit(1)
    return sorted(allp, key=lambda p: p["time"], reverse=True)


CSS = """
:root{--bg:#f4efe1;--ink:#1e1e1e;--gray:#5f5f5f;--line:#cfc8b2;--card:#faf6ea}
@media (prefers-color-scheme:dark){:root{--bg:#15171c;--ink:#ece8da;--gray:#a9a597;--line:#33363e;--card:#1d2027}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Georgia,"DejaVu Serif",serif;padding:14px 14px 40px;max-width:760px;margin:0 auto}
header{text-align:center;border-top:4px double var(--ink);border-bottom:2px solid var(--ink);padding:12px 0 10px;margin-bottom:16px}
h1{margin:0;font-size:30px;letter-spacing:1px}
.sub{color:var(--gray);font-size:14px;margin-top:6px;font-family:Arial,sans-serif}
.item{display:block;text-decoration:none;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 12px 12px 14px;margin-bottom:10px}
.meta{font-family:Arial,sans-serif;font-weight:bold;font-size:13px;color:var(--gray);margin-bottom:5px}
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
            f'<a class="item" style="border-left:5px solid {p["color"]}" '
            f'href="{html.escape(p["url"])}">'
            f'<div class="meta">{t} · {html.escape(p["src"])}</div>'
            f'<h2>{html.escape(p["title"])}</h2>{summ}</a>'
        )
    body = "\n".join(items) if items else '<div class="empty">Пока новостей за сегодня нет</div>'
    date = f"{now.day} {MONTHS[now.month - 1]} {now.year}"
    names = " · ".join(c[1] for c in CHANNELS)
    return (
        '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Новостная газета</title><style>' + CSS + '</style></head><body>'
        '<header><h1>НОВОСТНАЯ ГАЗЕТА</h1>'
        f'<div class="sub">{date} · {names} · новостей: {len(posts)}</div>'
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
    img = Image.new("RGB", (W, 8000), PAPER)
    d = ImageDraw.Draw(img)
    title_f = F("DejaVuSerif-Bold.ttf", 66)
    date_f = F("DejaVuSans.ttf", 26)
    lbl_f = F("DejaVuSans-Bold.ttf", 24)
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
    names = " · ".join(c[1] for c in CHANNELS)
    sub = f"{now.day} {MONTHS[now.month - 1]} {now.year} · {names}"
    d.text(((W - d.textlength(sub, font=date_f)) / 2, y), sub, font=date_f, fill=GRAY)
    y += 50
    d.line((M, y, W - M, y), fill=INK, width=2)
    y += 30

    for i, n in enumerate(news, 1):
        tm = n["time"].astimezone(MSK).strftime("%H:%M")
        d.text((M, y), f"{n['src']} · {tm}", font=lbl_f, fill=GRAY)
        y += 36
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

    if os.environ.get("SEND") != "true":
        return
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
        name = f"{n['src']}: {n['title']}"
        if len(name) > 55:
            name = name[:55] + "…"
        kb.append([{"text": name, "url": n["url"]}])
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
