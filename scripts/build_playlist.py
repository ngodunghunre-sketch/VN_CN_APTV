#!/usr/bin/env python3
import re
import urllib.request
from pathlib import Path

VN_URL = "https://iptv-org.github.io/iptv/countries/vn.m3u"
CN_CCTV_URL = "https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_cctv.m3u8"
CN_PROVINCE_URL = "https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_province.m3u8"

# Keep the playlist compact for APTV / CarPlay.
VN_PATTERNS = [
    r"^VTV\s*1$", r"^VTV\s*2$", r"^VTV\s*3$", r"^VTV\s*4$", r"^VTV\s*5$",
    r"^VTV\s*6$", r"^VTV\s*7$", r"^VTV\s*8$", r"^VTV\s*9$",
    r"^VTV\s*Cần Thơ$", r"^VTV Can Tho$",
    r"^HTV7$", r"^HTV\s*7$", r"^HTV9$", r"^HTV\s*9$",
    r"^THVL1$", r"^THVL\s*1$", r"^THVL2$", r"^THVL\s*2$",
]

CN_CCTV_PATTERNS = [
    r"^CCTV[- ]?([1-9]|1[0-7])$",
    r"^CCTV5\+$", r"^CCTV-5\+$", r"^CCTV5Plus$",
    r"^CCTV[- ]?4K$", r"^CCTV4K$",
]

CN_PROVINCE_NAMES = {
    "北京卫视", "东方卫视", "湖南卫视", "浙江卫视", "江苏卫视",
    "广东卫视", "深圳卫视", "山东卫视", "辽宁卫视", "安徽卫视",
    "湖北卫视", "四川卫视",
}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def parse_m3u(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    out = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF:") and i + 1 < len(lines):
            out.append((lines[i], lines[i + 1]))
            i += 2
        else:
            i += 1
    return out

def ext_name(extinf):
    # Channel display name is the part after the last comma.
    return extinf.rsplit(",", 1)[-1].strip()

def tvg_name(extinf):
    m = re.search(r'tvg-name="([^"]+)"', extinf, re.I)
    return m.group(1).strip() if m else ext_name(extinf)

def normalize_vn(name):
    return re.sub(r"\s+", " ", name.replace("–", "-").replace("—", "-")).strip()

def choose_one(entries, group_title):
    # Prefer HTTPS, then first entry (the upstream CN project already checks/sorts sources).
    https = [e for e in entries if e[1].lower().startswith("https://")]
    chosen = https[0] if https else entries[0]
    extinf, url = chosen
    extinf = re.sub(r'group-title="[^"]*"', f'group-title="{group_title}"', extinf)
    if 'group-title=' not in extinf:
        extinf = extinf.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{group_title}"', 1)
    return extinf, url

def collect_vn():
    entries = parse_m3u(fetch(VN_URL))
    wanted = []
    seen = set()
    for extinf, url in entries:
        name = normalize_vn(ext_name(extinf))
        if any(re.fullmatch(p, name, re.I) for p in VN_PATTERNS):
            key = re.sub(r"\s+", "", name).lower()
            if key not in seen:
                wanted.append(choose_one([(extinf, url)], "🇻🇳 Việt Nam"))
                seen.add(key)
    return wanted

def collect_cn_cctv():
    entries = parse_m3u(fetch(CN_CCTV_URL))
    buckets = {}
    order = []
    for extinf, url in entries:
        name = tvg_name(extinf) or ext_name(extinf)
        n = name.upper().replace(" ", "")
        # Normalize common forms.
        m = re.fullmatch(r"CCTV[-]?([1-9]|1[0-7])", n)
        if m:
            key = f"CCTV-{m.group(1)}"
        elif n in {"CCTV5+", "CCTV-5+", "CCTV5PLUS"}:
            key = "CCTV-5+"
        elif n in {"CCTV4K", "CCTV-4K"}:
            key = "CCTV-4K"
        else:
            continue
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append((extinf, url))

    wanted_order = [f"CCTV-{i}" for i in range(1, 18)] + ["CCTV-5+", "CCTV-4K"]
    out = []
    for key in wanted_order:
        if key in buckets:
            out.append(choose_one(buckets[key], "🇨🇳 CCTV"))
    return out

def collect_cn_province():
    entries = parse_m3u(fetch(CN_PROVINCE_URL))
    buckets = {n: [] for n in CN_PROVINCE_NAMES}
    for extinf, url in entries:
        name = ext_name(extinf)
        for target in CN_PROVINCE_NAMES:
            if name == target or target in name:
                buckets[target].append((extinf, url))
                break
    out = []
    for name in [
        "北京卫视", "东方卫视", "湖南卫视", "浙江卫视", "江苏卫视",
        "广东卫视", "深圳卫视", "山东卫视", "辽宁卫视", "安徽卫视",
        "湖北卫视", "四川卫视",
    ]:
        if buckets[name]:
            out.append(choose_one(buckets[name], "🇨🇳 卫视"))
    return out

def main():
    vn = collect_vn()
    cctv = collect_cn_cctv()
    province = collect_cn_province()

    output = [
        "#EXTM3U",
        '#PLAYLIST: VN + China TV for APTV / CarPlay',
        "# This file is generated automatically by GitHub Actions.",
        "# Upstream sources: IPTV-org (VN) and best-fan/iptv-sources (CN).",
    ]

    for section in (vn, cctv, province):
        for extinf, url in section:
            output.extend([extinf, url])

    Path("VN_CN_APTV.m3u").write_text("\n".join(output) + "\n", encoding="utf-8")

    print(f"Generated {len(vn)} VN + {len(cctv)} CCTV + {len(province)} satellite channels.")
    if not cctv:
        raise SystemExit("No China CCTV channels found; refusing to overwrite playlist.")
    if not vn:
        raise SystemExit("No Vietnam channels found; refusing to overwrite playlist.")

if __name__ == "__main__":
    main()
