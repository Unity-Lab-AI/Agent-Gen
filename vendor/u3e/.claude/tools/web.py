"""Plain HTTP access with zero dependencies - fetch, read, parse, download (stdlib only).

    python .claude/tools/web.py get  https://example.com [--max 20000]   # readable text
    python .claude/tools/web.py raw  https://example.com                 # body as sent
    python .claude/tools/web.py json https://api.example.com/x [--path a.b.0]
    python .claude/tools/web.py links https://example.com [--filter substring]
    python .claude/tools/web.py head https://example.com                 # status + headers
    python .claude/tools/web.py dl   https://example.com/f.zip [out]
    python .claude/tools/web.py post https://api.x/y '{"a":1}' [--json|--form]

Flags (any command):
    -H "Name: value"        repeatable extra header
    --ua "..."              override User-Agent
    --timeout 30            seconds
    --cookies cookies.json  cookie jar exported by `browser.py cookies --out`
    --insecure              skip TLS verification

Use this when a page or API is reachable without a browser - it is the fastest
and cheapest option. If the content needs JavaScript or a login session, use
browser.py (and hand its cookies here with --cookies).
"""
import gzip, json, os, re, ssl, sys, urllib.error, urllib.parse, urllib.request, zlib

try:  # pages are full of non-Latin text; cp1252 stdout would crash on them
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")


def arg_val(a, flag, default=None):
    return a[a.index(flag) + 1] if flag in a and len(a) > a.index(flag) + 1 else default


def build_opts(a):
    headers = {"User-Agent": arg_val(a, "--ua", UA), "Accept": "*/*",
               "Accept-Encoding": "gzip, deflate", "Accept-Language": "en-US,en;q=0.9"}
    for i, x in enumerate(a):
        if x == "-H" and i + 1 < len(a) and ":" in a[i + 1]:
            k, v = a[i + 1].split(":", 1)
            headers[k.strip()] = v.strip()
    jar = arg_val(a, "--cookies")
    if jar and os.path.exists(jar):
        ck = json.loads(open(jar, encoding="utf-8").read())
        pairs = [f"{c['name']}={c['value']}" for c in ck if isinstance(c, dict) and "name" in c]
        if pairs:
            headers["Cookie"] = "; ".join(pairs)
    ctx = None
    if "--insecure" in a:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return headers, float(arg_val(a, "--timeout", "30")), ctx


def fetch(url, a, data=None, method=None):
    headers, timeout, ctx = build_opts(a)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    except urllib.error.HTTPError as e:
        r = e  # still readable: let the caller see the error body
    body = r.read()
    enc = (r.headers.get("Content-Encoding") or "").lower()
    if enc == "gzip":
        body = gzip.decompress(body)
    elif enc == "deflate":
        body = zlib.decompress(body, -zlib.MAX_WBITS)
    return r, body


def decode(r, body):
    m = re.search(r"charset=([\w-]+)", r.headers.get("Content-Type", ""), re.I)
    for cs in ([m.group(1)] if m else []) + ["utf-8", "cp1252", "latin-1"]:
        try:
            return body.decode(cs)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", "replace")


BLOCK = r"p|div|br|tr|li|h[1-6]|section|article|header|footer|blockquote|pre|table"


def html_to_text(html):
    t = re.sub(r"(?is)<(script|style|noscript|svg|head|template)\b.*?</\1>", " ", html)
    t = re.sub(r"(?is)<!--.*?-->", " ", t)
    t = re.sub(rf"(?i)</?({BLOCK})\b[^>]*>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    import html as _h
    t = _h.unescape(t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t)
    return "\n".join(line.strip() for line in t.splitlines()).strip()


def dig(obj, path):
    for part in path.split("."):
        obj = obj[int(part)] if part.isdigit() and isinstance(obj, list) else obj[part]
    return obj


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help", "help"):
        sys.exit(__doc__)
    c, url = a[0], (a[1] if len(a) > 1 else "")
    mx = int(arg_val(a, "--max", "20000"))

    if c == "get":
        r, body = fetch(url, a)
        txt = decode(r, body)
        out = html_to_text(txt) if "<" in txt[:2000] else txt
        print(f"[{r.status}] {r.url}\n")
        print(out[:mx] + (f"\n... [{len(out) - mx} more chars]" if len(out) > mx else ""))
    elif c == "raw":
        r, body = fetch(url, a)
        sys.stdout.write(decode(r, body)[:mx])
    elif c == "json":
        r, body = fetch(url, a)
        obj = json.loads(decode(r, body) or "null")
        p = arg_val(a, "--path")
        print(json.dumps(dig(obj, p) if p else obj, indent=2)[:mx])
    elif c == "head":
        r, _ = fetch(url, a, method="HEAD")
        print(f"[{r.status}] {r.url}")
        for k, v in r.headers.items():
            print(f"{k}: {v}")
    elif c == "links":
        r, body = fetch(url, a)
        html = decode(r, body)
        sub = arg_val(a, "--filter")
        seen = set()
        for m in re.finditer(r"(?is)<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", html):
            href = urllib.parse.urljoin(r.url, m.group(1))
            text = html_to_text(m.group(2))[:80].replace("\n", " ")
            if href in seen:
                continue
            seen.add(href)
            if not sub or sub.lower() in (href + text).lower():
                print(f"{text or '-'}\t{href}")
    elif c == "dl":
        out = a[2] if len(a) > 2 and not a[2].startswith("--") else \
            (os.path.basename(urllib.parse.urlparse(url).path) or "download.bin")
        r, body = fetch(url, a)
        with open(out, "wb") as f:
            f.write(body)
        print(f"[{r.status}] {len(body):,} bytes -> {os.path.abspath(out)}")
    elif c == "post":
        payload = a[2] if len(a) > 2 else ""
        if "--form" in a:
            data = urllib.parse.urlencode(json.loads(payload)).encode()
            a += ["-H", "Content-Type: application/x-www-form-urlencoded"]
        else:
            data = payload.encode()
            a += ["-H", "Content-Type: application/json"]
        r, body = fetch(url, a, data=data, method="POST")
        print(f"[{r.status}] {r.url}\n")
        print(decode(r, body)[:mx])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
