# -*- coding: utf-8 -*-
"""
analysis.py — DHG 502 Assignment 1
Corpus preparation and target-word frequency analysis of the Ming shi 明史.

Pipeline (recorded step by step):
  1. Load the raw traditional-Chinese text (data/明史.txt).
  2. Convert the whole text to simplified Chinese with OpenCC (t2s).
  3. Parse the 卷 (juan) structure: each "卷X" line is followed by a
     "-----" rule; the text between rules belongs to that juan.
  4. Split each juan's text into sentences on Chinese punctuation
     (。！？；… and closing brackets/quotes that end a sentence).
  5. Keep sentences with at least 5 characters (words), strip spaces,
     one sentence per line -> data/data.txt (plain UTF-8).
  6. Build data/index.csv mapping each line of data.txt to its 卷
     number and title.
  7. Load data/userdict.txt into jieba (one word per line).
  8. Print 20 random segmented sentences containing a target word so
     the segmentation can be checked by eye.
  9. Generate a target word frequency report.
"""

import csv
import random
import re
from pathlib import Path

import jieba
import opencc

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_FILE = DATA_DIR / "明史.txt"
CLEAN_FILE = DATA_DIR / "data.txt"
INDEX_FILE = DATA_DIR / "index.csv"
USERDICT_FILE = DATA_DIR / "userdict.txt"

# --------------------------------------------------------------------------
# Step 0 — target words (simplified forms) for the user dictionary
# --------------------------------------------------------------------------
TARGET_WORDS = [
    # core
    "倭", "倭寇", "倭人", "倭奴", "倭酋", "倭将", "倭兵", "倭船", "倭刀",
    "倭国", "倭王", "倭情", "倭变", "倭患", "倭乱", "备倭", "平倭", "御倭",
    "防倭", "征倭", "剿倭", "讨倭", "伐倭", "击倭", "拒倭", "导倭", "通倭",
    # related names
    "日本", "丰臣秀吉", "丰臣", "平秀吉", "关白", "足利", "源义满", "源义持",
    "源义政", "义满", "义政", "义晴", "大内", "细川", "宗设", "谦道", "素卿",
    "宋素卿", "瑞佐", "汪直", "王直", "徐海", "陈璘", "邓子龙", "李如松",
    "杨镐", "麻贵", "邢玠", "沈惟敬", "石星", "宋应昌", "赵文华", "朱纨",
    "张经", "戚继光", "胡宗宪", "俞大猷", "刘江", "李舜臣", "朝鲜", "对马",
    "萨摩", "宁波", "定海", "昌国", "桃渚", "望海埚",
    # official titles
    "国王", "将军", "征夷大将军", "都督", "总兵", "总兵官", "备倭总兵官",
    "都指挥", "都指挥使", "指挥", "指挥使", "把总", "备倭把总", "游击",
    "游击将军", "参将", "副将", "总督", "总督备倭", "巡抚", "提督", "经略",
    "赞画", "兵部尚书", "尚书", "侍郎", "主事", "郎中", "员外郎",
    "给事中", "御史", "巡按", "市舶司", "市舶", "海禁", "朝贡", "入贡",
    "来贡", "贡使", "贡船", "勘合", "册封", "封贡",
]

# --------------------------------------------------------------------------
# Step 1 — load raw text
# --------------------------------------------------------------------------
def load_raw() -> str:
    text = RAW_FILE.read_text(encoding="utf-8")
    print(f"[1] Loaded raw text: {len(text):,} characters")
    return text


# --------------------------------------------------------------------------
# Step 2 — convert to simplified Chinese
# --------------------------------------------------------------------------
def to_simplified(text: str) -> str:
    converter = opencc.OpenCC("t2s")
    simplified = converter.convert(text)
    print(f"[2] Converted to simplified Chinese with OpenCC (t2s)")
    return simplified


# --------------------------------------------------------------------------
# Step 3 — parse juan structure
# --------------------------------------------------------------------------
JUAN_RE = re.compile(r"^卷([一二三四五六七八九十百千零〇]+)$")

CN_NUM = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "百": 100, "千": 1000,
}


def cn_to_int(cn: str) -> int:
    """Convert a Chinese numeral string like 三百三十二 to an int."""
    if cn.isdigit():
        return int(cn)
    total, temp = 0, 0
    for ch in cn:
        val = CN_NUM.get(ch)
        if val is None:
            continue
        if val >= 10:
            if temp == 0:
                temp = 1
            if val == 10 and temp >= 10:
                total += temp * val
                temp = 0
            else:
                total += temp * val
                temp = 0
        else:
            temp = temp * 10 + val
    return total + temp


def parse_juans(text: str):
    """
    Return a list of (juan_number, juan_title, juan_text).
    Structure in the raw file:
        卷一
        --
        <text of juan 1>
        ==================================================
        卷二
        ...
    """
    juans = []
    current = None  # (num, title, [lines])
    for line in text.splitlines():
        stripped = line.strip()
        m = JUAN_RE.match(stripped)
        if m:
            if current:
                juans.append(current)
            num = cn_to_int(m.group(1))
            current = (num, stripped, [])
            continue
        if current is None:
            continue  # skip the file header (明史 ==)
        if set(stripped) <= {"-", "="} and stripped:
            continue  # separator rules
        current[2].append(line)
    if current:
        juans.append(current)
    print(f"[3] Parsed {len(juans)} juans")
    return juans


# --------------------------------------------------------------------------
# Step 4 — sentence splitting
# --------------------------------------------------------------------------
SENT_END = "。！？；…"    # characters that end a sentence
CLOSERS = "」』】》〉"      # closing quotes/brackets absorbed into the sentence


def split_sentences(text: str):
    """Split a block of text into sentences on Chinese punctuation.

    A sentence ends at 。！？；… ; any closing quotes/brackets right after
    the end mark stay with the sentence. Closing marks alone (e.g. 」
    followed by ，) do NOT end a sentence, so no sentence starts with ，.
    """
    text = re.sub(r"\[\d+\]", "", text)    # drop footnote markers like [2]
    text = re.sub(r"\s+", "", text)        # no spaces between words
    sentences, buf = [], ""
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        buf += ch
        if ch in SENT_END:
            while i + 1 < n and text[i + 1] in CLOSERS:
                i += 1
                buf += text[i]
            if buf.strip():
                sentences.append(buf.strip())
            buf = ""
        i += 1
    if buf.strip():
        sentences.append(buf.strip())
    return sentences


MIN_LEN = 5  # at least 5 words (characters) per sentence


# --------------------------------------------------------------------------
# Step 5 + 6 — write data.txt and index.csv
# --------------------------------------------------------------------------
def build_corpus(juans):
    rows = []  # (line_no, juan_num, juan_title, sentence)
    for num, title, lines in juans:
        for sent in split_sentences("\n".join(lines)):
            if len(sent) >= MIN_LEN:
                rows.append((num, title, sent))

    with CLEAN_FILE.open("w", encoding="utf-8") as f:
        for _, _, sent in rows:
            f.write(sent + "\n")

    with INDEX_FILE.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "juan", "title"])
        for i, (num, title, _) in enumerate(rows, start=1):
            w.writerow([i, num, title])

    print(f"[5] Wrote {len(rows):,} sentences -> {CLEAN_FILE.relative_to(ROOT)}")
    print(f"[6] Wrote index -> {INDEX_FILE.relative_to(ROOT)}")
    return rows


# --------------------------------------------------------------------------
# Step 7 — user dictionary for jieba
# --------------------------------------------------------------------------
def write_userdict():
    with USERDICT_FILE.open("w", encoding="utf-8") as f:
        for w in TARGET_WORDS:
            f.write(w + "\n")
    print(f"[7a] Wrote {len(TARGET_WORDS)} target words -> "
          f"{USERDICT_FILE.relative_to(ROOT)}")


def load_userdict():
    jieba.setLogLevel(60)
    jieba.load_userdict(str(USERDICT_FILE))
    print(f"[7b] Loaded user dictionary into jieba "
          f"({len(TARGET_WORDS)} words)")


# --------------------------------------------------------------------------
# Step 8 — random sample for eyeball check
# --------------------------------------------------------------------------
def sample_check(rows, n=20, seed=42):
    # Prefer sentences containing 倭-specific words (not generic titles)
    core = [w for w in TARGET_WORDS if "倭" in w or w in
            ("日本", "丰臣秀吉", "关白", "汪直", "王直", "戚继光", "朝鲜")]
    hits = [s for _, _, s in rows if any(t in s for t in core)]
    rng = random.Random(seed)
    sample = rng.sample(hits, min(n, len(hits)))
    print(f"\n[8] {len(hits):,} sentences contain a core target word; "
          f"showing {len(sample)} random samples (segmented):\n")
    for i, sent in enumerate(sample, 1):
        seg = " / ".join(jieba.cut(sent))
        print(f"{i:2d}. {seg}")
    return sample


# --------------------------------------------------------------------------
# Step 9 — target word frequency report
# --------------------------------------------------------------------------
def frequency_report(rows):
    counts = {}
    for _, _, s in rows:
        for w in TARGET_WORDS:
            if w in s:
                counts[w] = counts.get(w, 0) + 1
    print(f"\n[9] Target word frequency (sentences containing each word):")
    for w, c in sorted(counts.items(), key=lambda x: -x[1])[:30]:
        print(f"    {w}: {c:,}")
    return counts


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    raw = load_raw()                    # step 1
    simplified = to_simplified(raw)     # step 2
    juans = parse_juans(simplified)     # step 3
    rows = build_corpus(juans)          # steps 4-6
    write_userdict()                    # step 7a
    load_userdict()                     # step 7b
    sample_check(rows)                  # step 8
    frequency_report(rows)              # step 9


if __name__ == "__main__":
    main()
