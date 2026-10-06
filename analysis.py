# -*- coding: utf-8 -*-
"""
analysis.py — 《明史》各卷「倭」字頻率分佈分析
================================================

研究問題:明代中日關係之共現分析
(Collocation analysis of Ming-Japan relation shift throughout
 different periods of Ming Dynasty)

資料來源:張廷玉等《明史》數位文本
(data/明史.txt,約 9.7 MB,43,178 行,UTF-8 編碼)

=====================================================================
分析步驟記錄 (Step-by-step record)
=====================================================================

Step 1  讀取 data/明史.txt(UTF-8)。
        檔案開頭為書名「明史」與「==」標題線,其後才是卷一。

Step 2  觀察檔案結構:每卷以「卷X」單獨一行開頭,
        下一行為「--」(或「------」)底線標記,例如:
            卷一
            --
            太祖開天行道肇紀...
        卷與卷之間以 50 個「=」分隔線隔開。

Step 3  發現雜訊:各卷之間夾有維基文庫版權聲明
        「本清朝作品在全世界都屬於公有領域,因為作者逝世已經超過100年。」
        (全書共 312 處),統計前必須清除,否則會污染字數計算。

Step 4  以正規表示式 ^卷[一二三四五六七八九十百千零〇]+$ 逐卷切分。
        注意:部分卷號使用「〇」(如 卷一百〇一),不可遺漏。

Step 5  將中文數字卷號轉為阿拉伯數字(支援 一/十/百/千 與「〇/零」)。

Step 6  驗證切分結果:
        - 共找到 328 個卷標題,卷號涵蓋 1–332,無重複;
        - 卷 102、107、110、112 在此數位化版本中整卷缺失
          (此四卷為「表」類:諸王世表四、功臣世表三、
           宰輔年表、七卿年表,數位化時表格內容被省略);
        - 卷 101 亦僅存標題,無實質內容。
        → 分析時將缺失卷標記為 missing,避免誤判為「倭字出現 0 次」。

Step 7  統計每卷:
        - 「倭」字出現次數 (wo_count);
        - 卷內漢字總字數 (han_chars,僅計 CJK 漢字,
          剔除標點、空白、腳註標記 [1] 等,供標準化之用);
        - 每千字「倭」字頻率 (wo_per_1000_chars)。

Step 8  輸出 results/wo_frequency_by_juan.csv,並於終端機列印摘要。

執行方式:  python3 analysis.py
=====================================================================
"""

import csv
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "data" / "明史.txt"
OUTPUT_DIR = BASE_DIR / "results"
OUTPUT_PATH = OUTPUT_DIR / "wo_frequency_by_juan.csv"

TARGET_CHAR = "倭"          # 分析目標字
TOTAL_JUAN = 332            # 《明史》全書共 332 卷

# 版權版權聲明(維基文庫頁尾雜訊)
COPYRIGHT_RE = re.compile(
    r"本清朝作品在全世界都屬於公有領域，因為作者逝世已經超過\s*100\s*年。"
)

# 卷標題:單獨一行,僅含「卷」+ 中文數字(含「〇」「零」)
JUAN_TITLE_RE = re.compile(r"^卷[一二三四五六七八九十百千零〇]+$", re.M)

# 漢字範圍(用於計算總字數;不含標點、空白、ASCII、腳註數字)
HAN_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")

# 腳註標記,如 [1]、[23]
FOOTNOTE_RE = re.compile(r"\[\d+\]")


def cn_num_to_int(cn: str) -> int:
    """將中文數字(一/十/百/千,含〇、零)轉為整數。

    例:卷一→1、卷二十→20、卷一百〇一→101、卷三百三十二→332
    """
    s = cn[1:]  # 去掉「卷」字
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000}

    # 個位數直接回傳
    if len(s) == 1 and s in digits:
        return digits[s]

    total, current = 0, 0
    for ch in s:
        if ch in digits:
            current = digits[ch]
        elif ch in units:
            unit = units[ch]
            if current == 0:
                current = 1          # 處理「十」= 10、「十X」= 1X
            total += current * unit
            current = 0
    return total + current


def load_text(path: Path) -> str:
    """Step 1:讀取原始文本。"""
    with path.open(encoding="utf-8") as f:
        return f.read()


def clean_text(text: str) -> str:
    """Step 3:清除版權聲明雜訊。"""
    cleaned, n = COPYRIGHT_RE.subn("", text)
    print(f"[Step 3] 已清除版權聲明 {n} 處")
    return cleaned


def split_juan(text: str):
    """Step 4–5:切分各卷並轉換卷號。

    回傳 (juan_list, missing):
      juan_list = [(juan_no, title, body), ...]
      missing   = 缺失卷號清單
    """
    matches = list(JUAN_TITLE_RE.finditer(text))
    juan_list = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        title = m.group()
        juan_list.append((cn_num_to_int(title), title, body))

    found = {no for no, _, _ in juan_list}
    missing = [n for n in range(1, TOTAL_JUAN + 1) if n not in found]
    return juan_list, missing


def count_stats(body: str):
    """Step 7:統計單卷之「倭」字次數與漢字總字數。"""
    body = FOOTNOTE_RE.sub("", body)          # 移除腳註標記 [1]
    wo_count = body.count(TARGET_CHAR)
    han_chars = len(HAN_RE.findall(body))
    return wo_count, han_chars


def main() -> None:
    print("=" * 60)
    print("《明史》各卷「倭」字頻率分佈分析")
    print("=" * 60)

    # Step 1:讀取
    text = load_text(INPUT_PATH)
    print(f"[Step 1] 已讀取 {INPUT_PATH.name}({len(text):,} 字元)")

    # Step 3:清理
    text = clean_text(text)

    # Step 4–5:切分卷
    juan_list, missing = split_juan(text)
    print(f"[Step 4] 共切分出 {len(juan_list)} 卷")
    if missing:
        print(f"[Step 6] 缺失卷號(數位化版本無內容):{missing}")

    # Step 7:統計
    rows = []
    for juan_no, title, body in juan_list:
        wo_count, han_chars = count_stats(body)
        rows.append({
            "juan_no": juan_no,
            "juan_title": title,
            "wo_count": wo_count,
            "han_chars": han_chars,
            "wo_per_1000_chars": round(wo_count / han_chars * 1000, 4)
                                 if han_chars else 0.0,
            "has_content": han_chars > 0,
        })

    # 補上整卷缺失的卷號(102、107、110、112),標記 missing
    present = {r["juan_no"] for r in rows}
    for n in missing:
        rows.append({
            "juan_no": n,
            "juan_title": f"卷{cn_int_to_cn(n)}",
            "wo_count": "",
            "han_chars": "",
            "wo_per_1000_chars": "",
            "has_content": False,
        })
    rows.sort(key=lambda r: r["juan_no"])

    total_wo = sum(r["wo_count"] for r in rows if r["wo_count"] != "")
    juan_with_wo = sum(1 for r in rows if isinstance(r["wo_count"], int)
                       and r["wo_count"] > 0)
    print(f"[Step 7] 「{TARGET_CHAR}」全書共 {total_wo} 次,"
          f"出現於 {juan_with_wo} 卷")

    # Step 8:輸出 CSV
    OUTPUT_DIR.mkdir(exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["juan_no", "juan_title", "wo_count",
                        "han_chars", "wo_per_1000_chars", "has_content"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"[Step 8] 已輸出 {OUTPUT_PATH.relative_to(BASE_DIR)}")

    # 摘要:出現次數最多的前 15 卷
    print("\n「倭」字出現次數最多的前 15 卷:")
    print(f"{'卷號':>6}  {'次數':>4}  {'卷字數':>8}  {'每千字頻率':>10}")
    top = sorted((r for r in rows if isinstance(r["wo_count"], int)),
                 key=lambda r: r["wo_count"], reverse=True)[:15]
    for r in top:
        print(f"{r['juan_no']:>6}  {r['wo_count']:>4}  "
              f"{r['han_chars']:>8,}  {r['wo_per_1000_chars']:>10.4f}")


def cn_int_to_cn(n: int) -> str:
    """將整數轉回中文數字卷號(僅供缺失卷標題顯示用)。

    例:102 → 一百〇二、110 → 一百一十、112 → 一百一十二
    (與原書寫法一致:百位必帶「一」,十位 10–19 可省略「一」)
    """
    digits = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    units = [(1000, "千"), (100, "百"), (10, "十")]
    if n < 10:
        return digits[n]
    result = ""
    for value, name in units:
        if n >= value:
            count, n = divmod(n, value)
            # 「百」「千」必帶數字(一百、三百);「十」在 10–19 省略「一」
            if count > 1 or (count == 1 and value != 10):
                result += digits[count]
            result += name
        elif result:
            # 中間位為零(如 一百〇二 的十位)
            result += "〇"
    if n:
        result += digits[n]
    return result


if __name__ == "__main__":
    sys.exit(main())
