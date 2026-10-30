"""Drive the separate Twitch browser window (Playwright Chromium, profile .local/twitch-profile,
CDP port 9333) -- never the owner's own Chrome.

    python .local/twitch/tw.py shot [out.png]            screenshot the active tab
    python .local/twitch/tw.py url                       print the active tab's URL
    python .local/twitch/tw.py goto URL
    python .local/twitch/tw.py click "visible text" [n]  click the n-th element showing that text
    python .local/twitch/tw.py clicksel "css selector"
    python .local/twitch/tw.py button "Exact Name"         click a button by its accessible name
    python .local/twitch/tw.py choose "Exact text" FILE   click it, answer the file chooser with FILE
    python .local/twitch/tw.py fill "css selector" "text"
    python .local/twitch/tw.py upload "css selector" FILE   set a file input (no OS dialog)
    python .local/twitch/tw.py texts                     list visible buttons/links/labels
    python .local/twitch/tw.py chat "message"              post in the channel's own Twitch chat (popout tab)
"""
import sys
from playwright.sync_api import sync_playwright

def page_of(b):
    pages = [p for c in b.contexts for p in c.pages]
    tw = [p for p in pages if "twitch.tv" in p.url]
    return (tw or pages)[-1]

def main():
    a = sys.argv[1:]
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        pg = page_of(b)
        cmd = a[0]
        if cmd == "shot":
            out = a[1] if len(a) > 1 else ".local/twitch/shot.png"
            pg.screenshot(path=out); print(out, pg.url)
        elif cmd == "url":
            print(pg.url)
        elif cmd == "goto":
            pg.goto(a[1], wait_until="domcontentloaded"); pg.wait_for_load_state("networkidle", timeout=20000); print(pg.url)
        elif cmd == "click":
            n = int(a[2]) if len(a) > 2 else 0
            pg.get_by_text(a[1], exact=False).nth(n).click(timeout=10000); print("clicked", a[1])
        elif cmd == "clicksel":
            pg.locator(a[1]).first.click(timeout=10000); print("clicked", a[1])
        elif cmd == "button":
            pg.get_by_role("button", name=a[1], exact=True).first.click(timeout=10000); print("pressed", a[1])
        elif cmd == "choose":   # click something that opens a file chooser, answer it with FILE
            with pg.expect_file_chooser(timeout=15000) as fc:
                pg.get_by_text(a[1], exact=True).first.click(timeout=10000)
            fc.value.set_files(a[2]); print("chose", a[2])
        elif cmd == "fill":
            pg.locator(a[1]).first.fill(a[2], timeout=10000); print("filled", a[1])
        elif cmd == "upload":
            pg.locator(a[1]).first.set_input_files(a[2], timeout=10000); print("uploaded", a[2])
        elif cmd == "chat":   # owner-approved lines only (links he gave, replies to viewers)
            cp = next((x for c in b.contexts for x in c.pages if "/popout/" in x.url and "/chat" in x.url), None)
            if not cp:
                cp = b.contexts[0].new_page(); cp.goto("https://www.twitch.tv/popout/unityplaysrimworld/chat", wait_until="domcontentloaded")
            box = cp.locator('[data-a-target="chat-input"]').first
            box.click(timeout=15000); cp.keyboard.type(a[1], delay=15); cp.keyboard.press("Enter"); print("sent")
        elif cmd == "texts":
            for el in pg.locator("button, a, label, h2, h3, input, textarea").all()[:200]:
                try:
                    if not el.is_visible(): continue
                    t = (el.inner_text() or el.get_attribute("placeholder") or el.get_attribute("aria-label") or "").strip()
                    tag = el.evaluate("e => e.tagName + (e.type ? ':' + e.type : '') + (e.id ? '#' + e.id : '')")
                    if t or tag.startswith("INPUT") or tag.startswith("TEXTAREA"):
                        print(tag, "|", t[:80].replace("\n", " "))
                except Exception:
                    pass

if __name__ == "__main__":
    main()
