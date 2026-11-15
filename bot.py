import os, re, json, html
from datetime import datetime, timedelta, timezone
import requests
from PIL import Image, ImageDraw, ImageFont, ImageColor

CHANNELS = [
    ("bbcrussian", "BBC", "#bb1919"),
    ("meduzalive", "Медуза", "#2f7bd9"),
    ("astrapress", "ASTRA", "#e0861a"),
]
TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MAX_NEWS = 10
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]
MSK = timezone(timedelta(hours=3))
SKIP = ("http", "Подробнее", "Открыть", "Фото", "Видео",
        "Защитить себя", "Please open", "VIEW IN")
FD = "/usr/share/fonts/truetype/dejavu/"
PAPER, INK, GRAY = (244, 239, 225), (30, 30, 30), (95, 95, 95)
RW, RH, HH = 1080, 205, 200
ROWS = 6


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


def make_widget_json(posts):
    data = {}
    for i in range(1, 7):
        if i <= len(posts):
            p = posts[i - 1]
            data[f"time{i}"] = p["time"].astimezone(MSK).strftime("%H:%M")
            data[f"src{i}"] = p["src"]
            data[f"title{i}"] = short(p["title"], 110)
            data[f"url{i}"] = p["url"]
        else:
            data[f"time{i}"] = data[f"src{i}"] = data[f"title{i}"] = data[f"url{i}"] = ""
    data["count"] = str(len(posts))
    return json.dumps(data, ensure_ascii=False, indent=1)


def make_text(news):
    now = datetime.now(MSK)
    out = f"📰 <b>Новости</b> · {now.strftime('%H:%M')}\n"
    for n in news:
        t = n["time"].astimezone(MSK).strftime("%H:%M")
        block = (f"\n<b>{t} · {html.escape(n['src'])}</b>\n"
                 f'<a href="{html.escape(n["url"])}">{html.escape(n["title"])}</a>\n')
        if n["summary"]:
            block += html.escape(short(n["summary"], 110)) + "\n"
        if len(out) + len(block) > 3800:
            break
        out += block
    return out


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


def fit_lines(d, text, font, width, max_lines):
    lines = wrap(d, text, font, width)
    if len(lines) <= max_lines:
        return lines
    lines = lines[:max_lines]
    last = lines[-1]
    while last and d.textlength(last + "…", font=font) > width:
        last = last[:-1]
    lines[-1] = last.rstrip() + "…"
    return lines


def save_small(img, path):
    img.quantize(colors=32).save(path, optimize=True)


def make_head():
    img = Image.new("RGB", (RW, HH), PAPER)
    d = ImageDraw.Draw(img)
    title_f = F("DejaVuSerif-Bold.ttf", 62)
    date_f = F("DejaVuSans.ttf", 26)
    t = "НОВОСТНАЯ ГАЗЕТА"
    d.text(((RW - d.textlength(t, font=title_f)) / 2, 26), t, font=title_f, fill=INK)
    d.line((40, 118, RW - 40, 118), fill=INK, width=5)
    d.line((40, 128, RW - 40, 128), fill=INK, width=2)
    now = datetime.now(MSK)
    names = " · ".join(c[1] for c in CHANNELS)
    sub = f"{now.day} {MONTHS[now.month - 1]} {now.year} · {names}"
    d.text(((RW - d.textlength(sub, font=date_f)) / 2, 146), sub, font=date_f, fill=GRAY)
    d.line((40, HH - 4, RW - 40, HH - 4), fill=INK, width=2)
    return img


def make_row(p):
    img = Image.new("RGB", (RW, RH), PAPER)
    d = ImageDraw.Draw(img)
    if p:
        lbl_f = F("DejaVuSans-Bold.ttf", 24)
        head_f = F("DejaVuSerif-Bold.ttf", 34)
        d.rectangle((0, 12, 14, RH - 12), fill=ImageColor.getrgb(p["color"]))
        tm = p["time"].astimezone(MSK).strftime("%H:%M")
        d.text((44, 16), f"{tm} · {p['src']}", font=lbl_f, fill=GRAY)
        y = 56
        for line in fit_lines(d, p["title"], head_f, RW - 44 - 40, 3):
            d.text((44, y), line, font=head_f, fill=INK)
            y += 44
    d.line((30, RH - 3, RW - 30, RH - 3), fill=(190, 185, 170), width=2)
    return img


def make_redirect(url):
    u = html.escape(url)
    return ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0; url={u}">'
            '<title>Открываю…</title></head><body>'
            f'<script>location.replace({json.dumps(url)})</script>'
            f'<p><a href="{u}">Открыть новость</a></p></body></html>')


def write_widget_files(posts):
    save_small(make_head(), "head.png")
    for i in range(1, ROWS + 1):
        p = posts[i - 1] if i <= len(posts) else None
        save_small(make_row(p), f"row{i}.png")
        target = p["url"] if p else "index.html"
        with open(f"r{i}.html", "w", encoding="utf-8") as f:
            f.write(make_redirect(target))


def main():
    posts = get_day_posts()
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(make_page(posts))
    with open("news.json", "w", encoding="utf-8") as f:
        f.write(make_widget_json(posts))
    write_widget_files(posts)
    print("Новостей за сегодня:", len(posts))

    if os.environ.get("SEND") != "true":
        return
    now = datetime.now(timezone.utc)
    fresh = [p for p in posts if now - p["time"] < timedelta(hours=4, minutes=30)]
    news = fresh[:MAX_NEWS]
    if not news:
        print("Новых новостей для бота нет")
        return
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": make_text(news), "parse_mode": "HTML",
              "disable_web_page_preview": "true"},
        timeout=60,
    )
    print("Телеграм ответил:", r.status_code)
    if not r.ok:
        raise SystemExit(1)


main()
