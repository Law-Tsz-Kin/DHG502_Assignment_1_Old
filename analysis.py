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
 10. Count exact target-word tokens by Ming-period phase, omit terms with
     zero counts in every phase, and write a phase/total frequency CSV.
 11. Find significant collocates for 倭 in three Ming-period phases and
     save window-5, window-10, and sentence results under output/.
 12. Build a standalone six-page HTML report from the output CSVs, including
     sortable collocation/frequency tables and a cross-phase comparison tool.
 13. Export KWIC passages for the supplied phase-specific collocates to CSV.
 14. Build a three-page KWIC report for the supplied phase-specific collocates.
"""

import csv
import html
import json
import random
import re
from pathlib import Path

import jieba
import opencc
import pandas as pd
from qhchina import load_stopwords
from qhchina.analytics.collocations import find_collocates, kwic

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_FILE = DATA_DIR / "明史.txt"
CLEAN_FILE = DATA_DIR / "data.txt"
INDEX_FILE = DATA_DIR / "index.csv"
USERDICT_FILE = DATA_DIR / "userdict.txt"
OUTPUT_DIR = ROOT / "output"
RESULTS_HTML_FILE = OUTPUT_DIR / "results.html"
KWIC_HTML_FILE = OUTPUT_DIR / "kwic.html"
KWIC_CSV_FILE = OUTPUT_DIR / "kwic.csv"

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
FREQUENCY_WORDS = (
    "倭", "倭寇", "倭人", "倭奴", "倭酋", "倭将", "倭兵", "倭船", "倭刀",
    "倭国", "倭王", "倭情", "倭变", "倭患", "倭乱", "备倭", "平倭", "御倭",
    "防倭", "征倭", "剿倭", "讨倭", "伐倭", "击倭", "拒倭", "导倭", "通倭",
)

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
    "零": 0, "〇": 0, "元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
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
    existing_words = []
    if USERDICT_FILE.exists():
        existing_words = [
            word.strip()
            for word in USERDICT_FILE.read_text(encoding="utf-8").splitlines()
            if word.strip()
        ]
    if all(word in existing_words for word in TARGET_WORDS):
        print(f"[7a] Existing user dictionary already contains all target words")
        return
    words = list(dict.fromkeys([*TARGET_WORDS, *existing_words]))
    with USERDICT_FILE.open("w", encoding="utf-8") as f:
        for w in words:
            f.write(w + "\n")
    print(f"[7a] Wrote {len(words)} dictionary words -> "
          f"{USERDICT_FILE.relative_to(ROOT)}")


def load_userdict():
    jieba.setLogLevel(60)
    jieba.load_userdict(str(USERDICT_FILE))
    word_count = sum(
        1 for line in USERDICT_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    print(f"[7b] Loaded user dictionary into jieba "
          f"({word_count} words)")


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
# Step 10 — period-specific collocation analysis
# --------------------------------------------------------------------------
MING_ERA_STARTS = {
    "洪武": 1368,
    "建文": 1399,
    "永乐": 1403,
    "洪熙": 1425,
    "宣德": 1426,
    "正统": 1436,
    "景泰": 1450,
    "天顺": 1457,
    "成化": 1465,
    "弘治": 1488,
    "正德": 1506,
    "嘉靖": 1522,
    "隆庆": 1567,
    "万历": 1573,
    "泰昌": 1620,
    "天启": 1621,
    "崇祯": 1628,
}
ERA_PATTERN = "|".join(sorted(MING_ERA_STARTS, key=len, reverse=True))
DATE_RE = re.compile(
    rf"^(?P<era>{ERA_PATTERN})?"
    r"(?P<year>元|[一二三四五六七八九十百千零〇]+|[0-9]+)年"
)
BARE_DATE_SUFFIX_RE = re.compile(
    r"^(?:春|夏|秋|冬|闰|閏|正月|[一二三四五六七八九十]+月|"
    r"[甲乙丙丁戊己庚辛壬癸]|[，,])"
)

MING_PHASES = [
    ("Early Ming (1368-1522)", 1368, 1522),
    ("Middle Ming (1523-1567)", 1523, 1567),
    ("Late Ming (1568-1644)", 1568, 1644),
]

COLLOCATION_RUNS = [
    ("window_h5", "window", 5),
    ("window_h10", "window", 10),
    ("sentence", "sentence", None),
]
KWIC_COLLOCATES = {
    "Early Ming (1368-1522)": ("海上", "出海", "沿海"),
    "Middle Ming (1523-1567)": ("江北", "东南", "官军"),
    "Late Ming (1568-1644)": ("朝鲜", "釜山", "平壤"),
}


def extract_dated_sentences(rows):
    """Carry dated Ming-era years forward through each juan's sentences."""
    active_era = None
    current_year = None
    previous_juan = None
    dated_rows = []

    for juan_num, _, sentence in rows:
        if juan_num != previous_juan:
            current_year = None
            previous_juan = juan_num

        match = DATE_RE.match(sentence)
        if match:
            era = match.group("era")
            year_text = match.group("year")
            suffix = sentence[match.end():]

            if era or BARE_DATE_SUFFIX_RE.match(suffix):
                year_number = cn_to_int(year_text)
                if era:
                    active_era = era
                if active_era:
                    current_year = MING_ERA_STARTS[active_era] + year_number - 1

        dated_rows.append((current_year, sentence))

    return dated_rows


def phase_for_year(year):
    """Return the Ming phase containing a year, or None if it is out of range."""
    return next(
        (
            phase_name
            for phase_name, start_year, end_year in MING_PHASES
            if start_year <= year <= end_year
        ),
        None,
    )


def run_collocation_analysis(rows):
    """Run the three collocation configurations and save their CSVs."""
    phase_sentences = {name: [] for name, _, _ in MING_PHASES}
    for year, sentence in extract_dated_sentences(rows):
        if year is None:
            continue
        phase_name = phase_for_year(year)
        if phase_name is not None:
            phase_sentences[phase_name].append(sentence)

    stopwords = sorted(load_stopwords("zh_cl_sim"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {run_name: [] for run_name, _, _ in COLLOCATION_RUNS}

    for phase_name, _, _ in MING_PHASES:
        sentences = phase_sentences[phase_name]
        tokenized = [jieba.lcut(sentence, HMM=False) for sentence in sentences]
        target_sentence_count = sum("倭" in tokens for tokens in tokenized)
        print(
            f"\n[10] {phase_name}: {len(sentences):,} dated sentences; "
            f"{target_sentence_count:,} contain 倭"
        )

        for run_name, method, horizon in COLLOCATION_RUNS:
            kwargs = {
                "method": method,
                "measures": ["log_likelihood", "logDice"],
                "correction": "fdr_bh",
                "filters": {"stopwords": stopwords, "min_word_length": 2},
                "sort_by": "log_dice",
                "ascending": False,
                "return_type": "dataframe",
            }
            if horizon is not None:
                kwargs["horizon"] = horizon

            results = find_collocates(
                sentences=tokenized,
                target_words="倭",
                **kwargs,
            )
            significant = results.loc[
                results["adjusted_p_value"] < 0.05
            ].sort_values("log_dice", ascending=False).head(20).copy()
            significant.insert(0, "phase", phase_name)
            outputs[run_name].append(significant)

            print(f"\n[10] {run_name} — {phase_name}: top 20 by logDice")
            if significant.empty:
                print("(no collocates passed the filters)")
            else:
                print(significant.to_string(index=False))

    for run_name, _, _ in COLLOCATION_RUNS:
        output_file = OUTPUT_DIR / f"collocates_{run_name}.csv"
        pd.concat(outputs[run_name], ignore_index=True).to_csv(
            output_file, index=False, encoding="utf-8"
        )
        print(f"\n[10] Wrote collocates -> {output_file.relative_to(ROOT)}")


def load_corpus_index():
    """Return line-to-volume metadata when the optional corpus index exists."""
    if not INDEX_FILE.exists():
        return None

    with INDEX_FILE.open(encoding="utf-8-sig", newline="") as csv_file:
        return {
            int(record["line"]): {
                "juan": record["juan"],
                "title": record["title"],
            }
            for record in csv.DictReader(csv_file)
        }


def generate_kwic_html(rows):
    """Write KWIC passages for each phase collocate and context horizon."""
    phase_entries = {phase_name: [] for phase_name, _, _ in MING_PHASES}
    for line_number, (year, sentence) in enumerate(
        extract_dated_sentences(rows), start=1
    ):
        if year is None:
            continue
        phase_name = phase_for_year(year)
        if phase_name is not None:
            phase_entries[phase_name].append((line_number, year, sentence))

    index = load_corpus_index()
    horizons = (("5", 5), ("10", 10), ("Sentence", None))
    horizon_titles = {
        "5": "5-Word Analysis",
        "10": "10-Word Analysis",
        "Sentence": "Sentence Analysis",
    }
    stats_by_run = {}
    for run_name, _, _ in COLLOCATION_RUNS:
        stats_path = OUTPUT_DIR / f"collocates_{run_name}.csv"
        with stats_path.open(encoding="utf-8-sig", newline="") as csv_file:
            stats_by_run[run_name] = {
                (record["phase"], record["collocate"]): record
                for record in csv.DictReader(csv_file)
            }

    statistic_fields = (
        ("obs_local", "Observed"),
        ("exp_local", "Expected"),
        ("ratio_local", "Observed / expected"),
        ("log_likelihood", "Log-likelihood"),
        ("log_dice", "logDice"),
        ("p_value", "p-value"),
        ("adjusted_p_value", "Adjusted p-value"),
    )
    run_by_horizon = {
        "5": "window_h5",
        "10": "window_h10",
        "Sentence": "sentence",
    }
    phase_results = {}

    for phase_name, _, _ in MING_PHASES:
        entries = phase_entries[phase_name]
        tokenized = [jieba.lcut(sentence, HMM=False) for _, _, sentence in entries]
        sentence_horizon = max((len(sentence) for sentence in tokenized), default=1)
        results_by_horizon = {}

        for horizon_name, horizon_size in horizons:
            concordance = kwic(
                sentences=tokenized,
                target="倭",
                horizon=horizon_size or sentence_horizon,
                sort_by="position",
                separator="",
                return_type="dataframe",
                max_sentence_length=None,
            )
            if not isinstance(concordance, pd.DataFrame):
                raise TypeError("kwic did not return a pandas DataFrame")
            concordance_records = concordance.to_dict(orient="records")
            matches_by_collocate = {}
            for collocate in KWIC_COLLOCATES[phase_name]:
                matches = []
                for record in concordance_records:
                    left = record["left"]
                    right = record["right"]
                    if collocate not in left and collocate not in right:
                        continue

                    source_line, year, _ = entries[record["doc_index"]]
                    metadata = index[source_line] if index is not None else None
                    stats = stats_by_run[run_by_horizon[horizon_name]].get(
                        (phase_name, collocate)
                    )
                    matches.append({
                        "phase": phase_name,
                        "year": year,
                        "line": source_line,
                        "horizon": horizon_name,
                        "collocate": collocate,
                        "left": left,
                        "node": record["node"],
                        "right": right,
                        "juan": metadata["juan"] if metadata else "",
                        "title": metadata["title"] if metadata else "",
                        "stats": stats,
                    })
                    if len(matches) == 10:
                        break
                matches_by_collocate[collocate] = matches
            results_by_horizon[horizon_name] = matches_by_collocate

        phase_results[phase_name] = results_by_horizon

    kwic_fields = [
        "phase", "year", "method", "horizon", "collocate", "match_number",
        "corpus_line", "juan", "title", "left", "node", "right", "context",
        "target", "exp_local", "obs_local", "ratio_local", "obs_global",
        "p_value", "log_likelihood", "log_dice", "adjusted_p_value",
    ]
    with KWIC_CSV_FILE.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=kwic_fields)
        writer.writeheader()
        for phase_name, _, _ in MING_PHASES:
            for horizon_name, _ in horizons:
                for collocate in KWIC_COLLOCATES[phase_name]:
                    passages = phase_results[phase_name][horizon_name][collocate]
                    for match_number, passage in enumerate(passages, start=1):
                        stats = passage["stats"] or {}
                        writer.writerow({
                            "phase": phase_name,
                            "year": passage["year"],
                            "method": run_by_horizon[horizon_name],
                            "horizon": horizon_name,
                            "collocate": collocate,
                            "match_number": match_number,
                            "corpus_line": passage["line"],
                            "juan": passage["juan"],
                            "title": passage["title"],
                            "left": passage["left"],
                            "node": passage["node"],
                            "right": passage["right"],
                            "context": (
                                passage["left"] + passage["node"] + passage["right"]
                            ),
                            "target": "倭",
                            **{
                                field: stats.get(field, "")
                                for field in kwic_fields
                                if field in {
                                    "exp_local", "obs_local", "ratio_local",
                                    "obs_global", "p_value",
                                    "log_likelihood", "log_dice",
                                    "adjusted_p_value",
                                }
                            },
                        })
    print(f"[13] Wrote KWIC CSV -> {KWIC_CSV_FILE.relative_to(ROOT)}")

    def context_html(context, collocate):
        pieces = re.split(f"({re.escape(collocate)})", context)
        return "".join(
            f"<mark>{html.escape(piece)}</mark>"
            if piece == collocate
            else html.escape(piece)
            for piece in pieces
        )

    phase_pages = []
    for phase_name, _, _ in MING_PHASES:
        collocate_sections = []
        for collocate in KWIC_COLLOCATES[phase_name]:
            horizon_sections = []
            for horizon_name, _ in horizons:
                passages = phase_results[phase_name][horizon_name][collocate]
                if passages:
                    passage_items = []
                    for passage in passages:
                        source = ""
                        if index is not None:
                            source = (
                                '<span class="source">'
                                f"卷 {html.escape(passage['juan'])} · "
                                f"{html.escape(passage['title'])}</span>"
                            )
                        if passage["stats"] is None:
                            stats_html = (
                                '<span class="stats-unavailable">'
                                "Statistics unavailable: collocate is not in this "
                                "method’s significant top-20 results.</span>"
                            )
                        else:
                            stat_items = []
                            for field, label in statistic_fields:
                                raw_value = passage["stats"].get(field, "")
                                try:
                                    number = float(raw_value)
                                    value = (
                                        f"{number:.3g}"
                                        if field in {"p_value", "adjusted_p_value"}
                                        else f"{number:,.4g}"
                                    )
                                except (TypeError, ValueError):
                                    value = raw_value or "—"
                                stat_items.append(
                                    f'<span><strong>{html.escape(label)}:</strong> '
                                    f"{html.escape(value)}</span>"
                                )
                            stats_html = (
                                f'<span class="passage-stats">'
                                f"{''.join(stat_items)}</span>"
                            )
                        passage_items.append(
                            '<li class="passage">'
                            f"{context_html(passage['left'], collocate)}"
                            f'<mark class="node">{html.escape(passage["node"])}</mark>'
                            f"{context_html(passage['right'], collocate)}"
                            f"{stats_html}"
                            f"{source}</li>"
                        )
                    passage_content = f"<ol>{''.join(passage_items)}</ol>"
                else:
                    passage_content = '<p class="empty">No passages found.</p>'
                horizon_sections.append(
                    '<section class="horizon">'
                    f"<h4>{horizon_titles[horizon_name]}</h4>"
                    f"{passage_content}</section>"
                )
            collocate_sections.append(
                '<section class="collocate">'
                f"<h3>{html.escape(collocate)}</h3>"
                f"{''.join(horizon_sections)}</section>"
            )
        phase_id = phase_name.split()[0].lower() + "-ming"
        phase_pages.append(
            f'<section class="page" id="page-{phase_id}" hidden>'
            f"<h2>{html.escape(phase_name)}</h2>"
            '<p class="intro">Up to 10 concordance passages per collocate and '
            "context horizon. The target 倭 is bold; the requested collocate "
            "is highlighted.</p>"
            f"{''.join(collocate_sections)}</section>"
        )

    title = (
        "KWIC: Collocation Analysis of Ming-Japan Relation Shift "
        "throughout Different Periods of Ming Dynasty"
    )
    navigation = "".join(
        f'<a class="nav-link" href="#{phase_name.split()[0].lower()}-ming" '
        f'data-page="{phase_name.split()[0].lower()}-ming">'
        f"{phase_name.split()[0]} Ming</a>"
        for phase_name, _, _ in MING_PHASES
    )
    navigation = (
        '<a class="nav-link" href="#cover" data-page="cover">Cover</a>'
        + navigation
    )
    html_document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: light; --ink: #172c3b; --muted: #617381; --accent: #246b75; --paper: #f4f7f6; --line: #dce5e3; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }}
.topbar {{ position: fixed; inset: 0 0 auto; z-index: 10; display: flex; gap: .5rem; overflow-x: auto; padding: .8rem max(1rem, calc((100vw - 1100px) / 2)); background: #142b39; box-shadow: 0 3px 12px #142b3940; }}
.nav-link {{ flex: 0 0 auto; padding: .55rem .8rem; border: 1px solid #516673; border-radius: .45rem; color: #f4f8f7; text-decoration: none; }}
.nav-link:hover, .nav-link[aria-current="page"] {{ background: var(--accent); border-color: #76b4b3; }}
main {{ max-width: 1100px; margin: auto; padding: 5.5rem 1rem 4rem; }}
.page[hidden] {{ display: none; }}
.cover {{ min-height: 72vh; display: flex; flex-direction: column; justify-content: center; padding: clamp(1rem, 6vw, 5rem); border: 1px solid var(--line); border-radius: 1rem; background: linear-gradient(145deg, #fff, #e7f0ed); }}
.cover h1 {{ max-width: 850px; font: 700 clamp(2.2rem, 6vw, 4.4rem)/1.15 Georgia, "Times New Roman", serif; }}
.eyebrow {{ color: var(--accent); font-size: .8rem; font-weight: 750; letter-spacing: .12em; }}
.intro, .source {{ color: var(--muted); }}
.collocate {{ margin: 2rem 0; padding: 1rem 1.25rem; border: 1px solid var(--line); border-radius: .7rem; background: white; }}
.horizon {{ margin: 1.3rem 0; }}
.passage {{ margin: .55rem 0; padding: .7rem; border-bottom: 1px solid var(--line); }}
.source {{ display: block; margin-top: .25rem; font-size: .85rem; }}
.passage-stats {{ display: flex; flex-wrap: wrap; gap: .25rem .85rem; margin-top: .4rem; color: #344f5d; font-size: .82rem; }}
.stats-unavailable {{ display: block; margin-top: .4rem; color: var(--muted); font-size: .82rem; font-style: italic; }}
mark {{ border-radius: .2rem; background: #fff0b5; color: inherit; }}
mark.node {{ background: #b9e4dc; font-weight: 800; }}
.empty {{ color: var(--muted); font-style: italic; }}
@media (max-width: 700px) {{ main {{ padding: 5rem .65rem 3rem; }} .topbar {{ padding: .6rem; }} .collocate {{ padding: .7rem; }} }}
</style>
</head>
<body>
<nav class="topbar" aria-label="Ming period pages">{navigation}</nav>
<main>
<section class="page cover" id="page-cover">
<p class="eyebrow">KEYWORD IN CONTEXT · 明史</p>
<h1>{html.escape(title)}</h1>
<p>Concordance passages for 倭 and the supplied collocates in the Early, Middle, and Late Ming phases.</p>
<p class="intro">Use the navigation bar to open a period. Each collocate is shown with 5-Word Analysis, 10-Word Analysis, and Sentence Analysis contexts.</p>
</section>
{''.join(phase_pages)}
</main>
<script>
(() => {{
  const links = [...document.querySelectorAll('.nav-link')];
  const pages = [...document.querySelectorAll('.page')];
  function showPage() {{
    const requested = location.hash.slice(1) || 'cover';
    const pageId = document.getElementById('page-' + requested) ? requested : 'cover';
    for (const page of pages) page.hidden = page.id !== 'page-' + pageId;
    for (const link of links) {{
      if (link.dataset.page === pageId) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }}
    window.scrollTo(0, 0);
  }}
  window.addEventListener('hashchange', showPage);
  showPage();
}})();
</script>
</body>
</html>
"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    KWIC_HTML_FILE.write_text(html_document, encoding="utf-8")
    print(f"[14] Wrote KWIC report -> {KWIC_HTML_FILE.relative_to(ROOT)}")
    return KWIC_HTML_FILE


def run_target_word_frequencies(rows):
    """Count exact target tokens by phase and omit terms absent from all phases."""
    phase_counts = {
        phase_name: {word: 0 for word in FREQUENCY_WORDS}
        for phase_name, _, _ in MING_PHASES
    }

    for year, sentence in extract_dated_sentences(rows):
        if year is None:
            continue
        phase_name = phase_for_year(year)
        if phase_name is not None:
            for token in jieba.lcut(sentence, HMM=False):
                if token in phase_counts[phase_name]:
                    phase_counts[phase_name][token] += 1

    table = pd.DataFrame.from_dict(phase_counts, orient="index").transpose()
    table.index.name = "word"
    table = table.reset_index()
    phase_columns = [phase_name for phase_name, _, _ in MING_PHASES]
    table = table.loc[table[phase_columns].sum(axis=1) > 0].copy()
    table["Total frequency"] = table[phase_columns].sum(axis=1)
    output_file = OUTPUT_DIR / "target_word_frequencies_by_phase.csv"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_file, index=False, encoding="utf-8")

    print("\n[11] Exact target-word token frequencies by phase")
    print(table.to_string(index=False))
    print(f"\n[11] Wrote frequencies -> {output_file.relative_to(ROOT)}")
    return table


def render_sortable_table(rows, columns, numeric_columns=()):
    """Render CSV records as a sortable, accessible HTML table."""
    header_cells = "".join(
        "<th scope=\"col\"><button type=\"button\" class=\"sort-button\" "
        f"data-type=\"{'number' if column in numeric_columns else 'text'}\">"
        f"{html.escape(label)}<span class=\"sort-indicator\" aria-hidden=\"true\"></span>"
        "</button></th>"
        for column, label in columns
    )
    body_rows = []
    for row in rows:
        cells = []
        for column, _ in columns:
            value = row.get(column, "")
            raw_value = str(value)
            display_value = raw_value
            if column in numeric_columns and raw_value:
                try:
                    number = float(raw_value)
                    if column in {"p_value", "adjusted_p_value"}:
                        display_value = f"{number:.3g}"
                    elif column in {"log_likelihood", "log_dice"}:
                        display_value = f"{number:.3f}"
                    elif column in {"exp_local", "ratio_local"}:
                        display_value = f"{number:.4g}"
                except ValueError:
                    display_value = raw_value
            cells.append(
                f"<td data-value=\"{html.escape(raw_value, quote=True)}\" "
                f"title=\"{html.escape(raw_value, quote=True)}\">"
                f"{html.escape(display_value)}</td>"
            )
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return (
        '<div class="table-wrap"><table class="sortable">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table></div>"
    )


def generate_results_html():
    """Build a standalone six-view report from the output CSV files."""
    collocation_runs = [
        (
            "window-h5",
            "Page 2 · 5-Word Collocation Analysis",
            "collocates_window_h5.csv",
            "Window method, horizon = 5",
        ),
        (
            "window-h10",
            "Page 3 · 10-Word Collocation Analysis",
            "collocates_window_h10.csv",
            "Window method, horizon = 10",
        ),
        (
            "sentence",
            "Page 4 · Sentence Collocation Analysis",
            "collocates_sentence.csv",
            "Sentence method",
        ),
    ]
    phases = [phase_name for phase_name, _, _ in MING_PHASES]
    comparison_methods = [
        ("window_h5", "5-Word", "collocates_window_h5.csv"),
        ("window_h10", "10-Word", "collocates_window_h10.csv"),
        ("sentence", "Sentence", "collocates_sentence.csv"),
    ]
    collocation_columns = [
        ("phase", "Phase"),
        ("target", "Target"),
        ("collocate", "Collocate"),
        ("exp_local", "Expected"),
        ("obs_local", "Observed"),
        ("ratio_local", "Observed / expected"),
        ("obs_global", "Global frequency"),
        ("p_value", "p-value"),
        ("adjusted_p_value", "Adjusted p-value"),
        ("log_likelihood", "Log-likelihood"),
        ("log_dice", "logDice"),
    ]
    numeric_collocation_columns = {
        "exp_local", "obs_local", "ratio_local", "obs_global",
        "p_value", "adjusted_p_value", "log_likelihood", "log_dice",
    }
    pages = []
    comparison_data = {}

    for page_id, page_title, filename, method_label in collocation_runs:
        csv_path = OUTPUT_DIR / filename
        with csv_path.open(encoding="utf-8", newline="") as csv_file:
            records = list(csv.DictReader(csv_file))
        run_key = next(
            key for key, _, run_filename in comparison_methods
            if run_filename == filename
        )
        for record in records:
            phase = record["phase"]
            collocate = record["collocate"]
            comparison_row = comparison_data.setdefault(collocate, {}).setdefault(
                phase, {}
            )
            comparison_row[run_key] = {
                key: record.get(key, "")
                for key in (
                    "log_dice", "log_likelihood", "obs_local", "exp_local",
                    "ratio_local", "obs_global", "p_value", "adjusted_p_value",
                )
            }
        phase_tables = []
        for phase in phases:
            phase_rows = [record for record in records if record["phase"] == phase]
            phase_tables.append(
                f"<section class=\"phase-block\"><h3>{html.escape(phase)}</h3>"
                f"{render_sortable_table(phase_rows, collocation_columns, numeric_collocation_columns)}"
                "</section>"
            )
        pages.append(
            f'<section class="page" id="page-{page_id}" hidden>'
            f"<h2>{html.escape(page_title)}</h2>"
            f'<p class="method-note">{html.escape(method_label)} · '
            "Benjamini–Hochberg adjusted p-value and raw p-value shown. "
            "Click any column heading to sort.</p>"
            f"{''.join(phase_tables)}</section>"
        )

    frequency_path = OUTPUT_DIR / "target_word_frequencies_by_phase.csv"
    with frequency_path.open(encoding="utf-8", newline="") as csv_file:
        frequency_records = list(csv.DictReader(csv_file))
    frequency_columns = [
        ("word", "Word"),
        (phases[0], phases[0]),
        (phases[1], phases[1]),
        (phases[2], phases[2]),
        ("Total frequency", "Total frequency"),
    ]
    frequency_numeric_columns = set(phases) | {"Total frequency"}
    pages.append(
        '<section class="page" id="page-frequency" hidden>'
        "<h2>Page 5 · Other Related Word Frequency</h2>"
        '<p class="method-note">Exact token counts by phase. Click any column heading to sort.</p>'
        f"{render_sortable_table(frequency_records, frequency_columns, frequency_numeric_columns)}"
        "</section>"
    )

    comparison_columns = [
        ("collocate", "Collocate"),
        (phases[0], phases[0]),
        (phases[1], phases[1]),
        (phases[2], phases[2]),
    ]
    comparison_table = render_sortable_table(
        [], comparison_columns, set(phases)
    )
    comparison_controls = (
        '<div class="comparison-controls">'
        '<label>Method <select id="comparison-method">'
        '<option value="window_h5">5-Word</option>'
        '<option value="window_h10">10-Word</option>'
        '<option value="sentence">Sentence</option>'
        '</select></label>'
        '<label>Statistic <select id="comparison-stat">'
        '<option value="log_dice">logDice</option>'
        '<option value="log_likelihood">Log-likelihood</option>'
        '<option value="obs_local">Observed frequency</option>'
        '<option value="exp_local">Expected frequency</option>'
        '<option value="ratio_local">Observed / expected</option>'
        '<option value="obs_global">Global frequency</option>'
        '<option value="p_value">p-value</option>'
        '<option value="adjusted_p_value">Adjusted p-value</option>'
        '</select></label>'
        '<label>Find collocate <input id="comparison-search" type="search" '
        'placeholder="Type a word"></label>'
        "</div>"
        '<p class="method-note" id="comparison-count" aria-live="polite"></p>'
    )
    pages.append(
        '<section class="page" id="page-compare" hidden>'
        "<h2>Page 6 · Interactive Comparison</h2>"
        '<p class="method-note">Compare the three Ming phases side by side. '
        "Choose 5-Word, 10-Word, or Sentence to compare a method across phases, "
        "select a statistic, and optionally search for a collocate. Click a column "
        "heading to sort. A dash means the collocate is not present in the selected "
        "method’s significant top-20 results for that phase; it is not a measured zero.</p>"
        f"{comparison_controls}{comparison_table}"
        "</section>"
    )
    comparison_json = json.dumps(
        comparison_data, ensure_ascii=False, separators=(",", ":")
    ).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    nav_items = [
        ("cover", "Cover · Page 1"),
        ("window-h5", "5-Word · Page 2"),
        ("window-h10", "10-Word · Page 3"),
        ("sentence", "Sentence · Page 4"),
        ("frequency", "Word Frequency · Page 5"),
        ("compare", "Compare · Page 6"),
    ]
    navigation = "".join(
        f'<a class="nav-link" href="#{page_id}" data-page="{page_id}">'
        f"{html.escape(label)}</a>"
        for page_id, label in nav_items
    )
    title = "Collocation Analysis of Ming-Japan Relation Shift throughout Different Periods of Ming Dynasty"
    cover = (
        '<section class="page cover" id="page-cover">'
        '<p class="eyebrow">DHG 502 · DIGITAL HISTORICAL RESEARCH</p>'
        f"<h1>{html.escape(title)}</h1>"
        '<p class="cover-copy">Collocates of 倭 and related target-word frequencies '
        "across three Ming-period phases.</p>"
        '<p class="cover-phases">Early Ming (1368–1522) · Middle Ming (1523–1567) · '
        "Late Ming (1568–1644)</p>"
        '<p class="cover-hint">Use the navigation bar above to open each analysis page.</p>'
        "</section>"
    )
    html_document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: light; --ink: #172c3b; --muted: #617381; --accent: #246b75; --paper: #f4f7f6; --line: #dce5e3; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }}
.topbar {{ position: fixed; inset: 0 0 auto; z-index: 10; display: flex; gap: .5rem; overflow-x: auto; padding: .8rem max(1rem, calc((100vw - 1200px) / 2)); background: #142b39; box-shadow: 0 3px 12px #142b3940; }}
.nav-link {{ flex: 0 0 auto; padding: .55rem .8rem; border: 1px solid #516673; border-radius: .45rem; color: #f4f8f7; text-decoration: none; font-size: .9rem; }}
.nav-link:hover, .nav-link[aria-current="page"] {{ background: var(--accent); border-color: #76b4b3; }}
main {{ max-width: 1200px; margin: 0 auto; padding: 5.5rem 1rem 5rem; }}
.page {{ animation: appear .18s ease-out; }}
.page[hidden] {{ display: none; }}
h1, h2, h3 {{ line-height: 1.2; }}
h2 {{ margin: 0 0 1rem; font-size: clamp(1.6rem, 3vw, 2.25rem); }}
h3 {{ margin: 1.5rem 0 .65rem; }}
.cover {{ min-height: 72vh; display: flex; flex-direction: column; justify-content: center; padding: clamp(1rem, 6vw, 5rem); border: 1px solid var(--line); border-radius: 1rem; background: linear-gradient(145deg, #fff, #e7f0ed); }}
.cover h1 {{ max-width: 880px; margin: .5rem 0 1rem; font-family: Georgia, "Times New Roman", serif; font-size: clamp(2.3rem, 6vw, 4.6rem); }}
.eyebrow {{ color: var(--accent); font-size: .8rem; font-weight: 750; letter-spacing: .12em; }}
.cover-copy {{ max-width: 650px; color: #344f5d; font-size: 1.2rem; }}
.cover-phases, .cover-hint, .method-note {{ color: var(--muted); }}
.method-note {{ margin: 0 0 1rem; }}
.phase-block {{ margin: 1.75rem 0 2.5rem; }}
.table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: .65rem; background: white; box-shadow: 0 4px 14px #172c3b0a; }}
table {{ width: 100%; border-collapse: collapse; font-size: .9rem; white-space: nowrap; }}
th, td {{ padding: .65rem .75rem; border-bottom: 1px solid var(--line); text-align: left; }}
th {{ position: sticky; top: 0; background: #e8f0ee; color: #183846; }}
tbody tr:nth-child(even) {{ background: #f8faf9; }}
tbody tr:hover {{ background: #edf6f4; }}
.sort-button {{ display: inline-flex; align-items: center; gap: .35rem; padding: 0; border: 0; background: none; color: inherit; font: inherit; font-weight: 700; cursor: pointer; }}
.sort-button:hover {{ color: var(--accent); }}
.sort-indicator {{ min-width: .6rem; color: var(--accent); }}
.comparison-controls {{ display: flex; flex-wrap: wrap; gap: 1rem; margin: 1rem 0; }}
.comparison-controls label {{ display: grid; gap: .3rem; color: var(--muted); font-size: .9rem; font-weight: 650; }}
.comparison-controls select, .comparison-controls input {{ min-width: 12rem; padding: .55rem .65rem; border: 1px solid #bdcdca; border-radius: .4rem; background: white; color: var(--ink); font: inherit; }}
footer {{ margin-top: 3rem; color: var(--muted); font-size: .85rem; }}
@keyframes appear {{ from {{ opacity: .5; transform: translateY(3px); }} to {{ opacity: 1; transform: translateY(0); }} }}
@media (max-width: 700px) {{ main {{ padding: 5rem .65rem 3rem; }} .topbar {{ padding: .6rem; }} th, td {{ padding: .55rem; }} }}
</style>
</head>
<body>
<nav class="topbar" aria-label="Report pages">{navigation}</nav>
<main>
{cover}
{''.join(pages)}
<footer>Collocation statistics are shown with the raw and adjusted p-values. Select a column heading to compare rankings.</footer>
</main>
<script>
const comparisonData = {comparison_json};
(() => {{
  const links = [...document.querySelectorAll('.nav-link')];
  const pages = [...document.querySelectorAll('.page')];
  function showPage() {{
    const requested = location.hash.slice(1) || 'cover';
    const pageId = document.getElementById('page-' + requested) ? requested : 'cover';
    for (const page of pages) page.hidden = page.id !== 'page-' + pageId;
    for (const link of links) {{
      if (link.dataset.page === pageId) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }}
    document.title = (pageId === 'cover' ? '' : document.querySelector('#page-' + pageId + ' h2')?.textContent + ' · ') + {json.dumps(title)};
    window.scrollTo(0, 0);
  }}
  window.addEventListener('hashchange', showPage);
  function enableSorting(table) {{
    if (table.dataset.sortReady) return;
    table.dataset.sortReady = 'true';
    table.querySelectorAll('thead th').forEach((header, columnIndex) => {{
      const button = header.querySelector('button');
      button.addEventListener('click', () => {{
        const body = table.tBodies[0];
        const ascending = button.dataset.direction !== 'asc';
        const type = button.dataset.type;
        const rows = [...body.rows];
        rows.sort((left, right) => {{
          const a = left.cells[columnIndex].dataset.value || '';
          const b = right.cells[columnIndex].dataset.value || '';
          const result = type === 'number'
            ? (Number(a) || 0) - (Number(b) || 0)
            : a.localeCompare(b, undefined, {{ numeric: true, sensitivity: 'base' }});
          return (ascending ? 1 : -1) * result;
        }});
        for (const row of rows) body.appendChild(row);
        table.querySelectorAll('.sort-button').forEach(other => {{
          other.dataset.direction = '';
          other.querySelector('.sort-indicator').textContent = '';
          other.removeAttribute('aria-sort');
        }});
        button.dataset.direction = ascending ? 'asc' : 'desc';
        button.querySelector('.sort-indicator').textContent = ascending ? '▲' : '▼';
        header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
      }});
    }});
  }}
  document.querySelectorAll('table.sortable').forEach(enableSorting);

  const methodSelect = document.getElementById('comparison-method');
  const statisticNames = {{
    log_dice: 'logDice',
    log_likelihood: 'Log-likelihood',
    obs_local: 'Observed frequency',
    exp_local: 'Expected frequency',
    ratio_local: 'Observed / expected',
    obs_global: 'Global frequency',
    p_value: 'p-value',
    adjusted_p_value: 'Adjusted p-value'
  }};
  const comparisonTable = document.querySelector('#page-compare table');
  const comparisonBody = comparisonTable.tBodies[0];
  const statSelect = document.getElementById('comparison-stat');
  const searchInput = document.getElementById('comparison-search');
  const resultCount = document.getElementById('comparison-count');

  function formatStat(value, statistic) {{
    if (value === undefined || value === '') return '—';
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    if (statistic === 'p_value' || statistic === 'adjusted_p_value') {{
      return number === 0 ? '0' : number.toExponential(3);
    }}
    if (statistic === 'obs_local' || statistic === 'obs_global') {{
      return number.toLocaleString();
    }}
    return number.toFixed(3);
  }}

  function addCell(row, value) {{
    const cell = row.insertCell();
    cell.textContent = value;
    cell.dataset.value = value;
  }}

  function renderComparison() {{
    const method = methodSelect.value;
    const statistic = statSelect.value;
    const query = searchInput.value.trim().toLocaleLowerCase();
    const rows = [];
    for (const [collocate, phases] of Object.entries(comparisonData)) {{
      if (query && !collocate.toLocaleLowerCase().includes(query)) continue;
      rows.push({{ collocate, phases }});
    }}
    rows.sort((left, right) => left.collocate.localeCompare(
      right.collocate, undefined, {{ numeric: true }}
    ));
    comparisonBody.replaceChildren();
    for (const item of rows) {{
      const row = comparisonBody.insertRow();
      addCell(row, item.collocate);
      for (const phase of {json.dumps(phases, ensure_ascii=False)}) {{
        const rawValue = item.phases[phase]?.[method]?.[statistic];
        const displayValue = formatStat(rawValue, statistic);
        const cell = row.insertCell();
        cell.textContent = displayValue;
        cell.dataset.value = rawValue === undefined || rawValue === ''
          ? ''
          : String(Number(rawValue));
        cell.title = rawValue === undefined || rawValue === ''
          ? 'Not present in the selected method’s significant top-20 results for this phase'
          : `${{statisticNames[statistic]}}: ${{rawValue}}`;
      }}
    }}
    resultCount.textContent = `${{rows.length}} collocates · ${{methodSelect.options[methodSelect.selectedIndex].text}} · showing ${{statisticNames[statistic]}} across all three phases`;
  }}
  methodSelect.addEventListener('change', renderComparison);
  statSelect.addEventListener('change', renderComparison);
  searchInput.addEventListener('input', renderComparison);
  renderComparison();
  showPage();
}})();
</script>
</body>
</html>
"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_HTML_FILE.write_text(html_document, encoding="utf-8")
    print(f"[12] Wrote interactive results report -> {RESULTS_HTML_FILE.relative_to(ROOT)}")
    return RESULTS_HTML_FILE


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
    run_target_word_frequencies(rows)   # step 10
    run_collocation_analysis(rows)      # step 11
    generate_results_html()             # step 12
    generate_kwic_html(rows)            # steps 13-14


if __name__ == "__main__":
    main()
