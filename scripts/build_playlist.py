#!/usr/bin/env python3
import re
import urllib.request
from pathlib import Path

VN_URL = "https://iptv-org.github.io/iptv/countries/vn.m3u"
CN_CCTV_URL = "https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_cctv.m3u8"
CN_PROVINCE_URL = "https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_province.m3u8"

# Kênh Việt Nam muốn giữ lại cho APTV/CarPlay.
VN_VTV = [f"VTV{i}" for i in range(1, 10)]
VN_OTHER = ["HTV7", "HTV9", "THVL1", "THVL2"]

CN_PROVINCE_NAMES = {
    "北京卫视", "东方卫视", "湖南卫视", "浙江卫视", "江苏卫视",
    "广东卫视", "深圳卫视", "山东卫视", "辽宁卫视", "安徽卫视",
    "湖北卫视", "四川卫视",
}

def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (GitHub Actions APTV playlist builder)"}
    )
    with urllib.request.urlopen(req, timeout=45) as r:
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
    return extinf.rsplit(",", 1)[-1].strip()

def tvg_name(extinf):
    m = re.search(r'tvg-name="([^"]+)"', extinf, re.I)
    return m.group(1).strip() if m else ""

def set_group(extinf, group_title):
    extinf = re.sub(r'group-title="[^"]*"', "", extinf)
    extinf = re.sub(r"\s+", " ", extinf).replace(" ,", ",")
    if extinf.startswith("#EXTINF:-1"):
        extinf = extinf.replace(
            "#EXTINF:-1",
            f'#EXTINF:-1 group-title="{group_title}"',
            1
        )
    return extinf

def choose_one(entries, group_title):
    # Ưu tiên HTTPS nếu có; nếu không thì lấy stream đầu tiên.
    https = [e for e in entries if e[1].lower().startswith("https://")]
    chosen = https[0] if https else entries[0]
    return set_group(chosen[0], group_title), chosen[1]

def vn_match(extinf):
    # IPTV-org có nhiều kiểu tên: VTV1, VTV1 HD, VTV-1, VTV 1...
    # Kiểm tra cả tvg-name và tên hiển thị.
    names = " ".join([tvg_name(extinf), ext_name(extinf)]).upper()

    # Chuẩn hóa dấu cách/gạch để nhận VTV1, VTV-1, VTV 1...
    compact = re.sub(r"[\s_-]+", "", names)

    for channel in VN_VTV:
        if channel in compact:
            return channel

    # Các kênh ngoài VTV.
    for channel in VN_OTHER:
        if channel in compact:
            return channel

    # Một số nguồn dùng tên tiếng Việt đầy đủ.
    if "VTV CẦN THƠ" in names or "VTV CAN THO" in names:
        return "VTV Cần Thơ"

    return None

def collect_vn():
    entries = parse_m3u(fetch(VN_URL))
    wanted_order = VN_VTV + VN_OTHER + ["VTV Cần Thơ"]
    buckets = {name: [] for name in wanted_order}

    for extinf, url in entries:
        channel = vn_match(extinf)
        if channel and channel in buckets:
            buckets[channel].append((extinf, url))

    out = []
    for channel in wanted_order:
        if buckets[channel]:
            out.append(choose_one(buckets[channel], "🇻🇳 Việt Nam"))
    return out

def normalize_cctv(extinf):
    names = " ".join([tvg_name(extinf), ext_name(extinf)]).upper()
    names = names.replace(" ", "")

    m = re.search(r"CCTV-?([1-9]|1[0-7])(?:[^0-9]|$)", names)
    if m:
        return f"CCTV-{m.group(1)}"

    if "CCTV5+" in names or "CCTV-5+" in names or "CCTV5PLUS" in names:
        return "CCTV-5+"

    if "CCTV4K" in names or "CCTV-4K" in names:
        return "CCTV-4K"

    return None

def collect_cn_cctv():
    entries = parse_m3u(fetch(CN_CCTV_URL))
    buckets = {}

    for extinf, url in entries:
        channel = normalize_cctv(extinf)
        if channel:
            buckets.setdefault(channel, []).append((extinf, url))

    wanted_order = [f"CCTV-{i}" for i in range(1, 18)] + ["CCTV-5+", "CCTV-4K"]

    out = []
    for channel in wanted_order:
        if channel in buckets:
            out.append(choose_one(buckets[channel], "🇨🇳 CCTV"))
    return out

def collect_cn_province():
    entries = parse_m3u(fetch(CN_PROVINCE_URL))
    buckets = {name: [] for name in CN_PROVINCE_NAMES}

    for extinf, url in entries:
        display = ext_name(extinf)
        for target in CN_PROVINCE_NAMES:
            if display == target or target in display:
                buckets[target].append((extinf, url))
                break

    order = [
        "北京卫视", "东方卫视", "湖南卫视", "浙江卫视", "江苏卫视",
        "广东卫视", "深圳卫视", "山东卫视", "辽宁卫视", "安徽卫视",
        "湖北卫视", "四川卫视",
    ]

    return [
        choose_one(buckets[name], "🇨🇳 卫视")
        for name in order
        if buckets[name]
    ]

def main():
    vn = collect_vn()
    cctv = collect_cn_cctv()
    province = collect_cn_province()

    print(f"Generated {len(vn)} VN + {len(cctv)} CCTV + {len(province)} satellite channels.")

    # Không ghi đè playlist nếu nguồn VN/CN bất ngờ rỗng.
    if not vn:
        raise SystemExit("No Vietnam channels found; refusing to overwrite playlist.")
    if not cctv:
        raise SystemExit("No China CCTV channels found; refusing to overwrite playlist.")

    output = [
        "#EXTM3U",
        "#PLAYLIST: VN + China TV for APTV / CarPlay",
        "# Generated automatically by GitHub Actions.",
        "# Upstream: IPTV-org (VN) + best-fan/iptv-sources (CN).",
    ]

    for section in (vn, cctv, province):
        for extinf, url in section:
            output.extend([extinf, url])

    Path("VN_CN_APTV.m3u").write_text(
        "\n".join(output) + "\n",
        encoding="utf-8"
    )

if __name__ == "__main__":
    main()
