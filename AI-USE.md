Tools Used: Copilot, GLM 5.3 Flash

Scope & Purpose of Use:

Human Critical Input: 

Sample Prompts:

---

## Session Record — 2026-10-06

### Task 1: Frequency distribution of 倭 across each 卷 of 明史.txt

**Prompt:** "Create a analysis.py and record all the step beginning from now. Analysis the frequency distribution of word 倭 from each 卷 of 明史.txt, create a .csv file of the result"

**Steps taken by AI (analysis.py):**

1. **Data exploration** — Inspected `data/明史.txt` (9.7 MB, 43,178 lines, UTF-8). Found structure: each 卷 begins with a standalone line `卷X` followed by a `--` underline; juan sections separated by 50 `=` characters.
2. **Noise detection** — Found 312 occurrences of Wiki-source copyright boilerplate 「本清朝作品在全世界都屬於公有領域，因為作者逝世已經超過100年。」 between juan sections; removed before counting.
3. **Juan segmentation** — Split text with regex `^卷[一二三四五六七八九十百千零〇]+$` (note: some juan numbers use 〇, e.g. 卷一百〇一). Converted Chinese numerals to integers.
4. **Validation** — Found 328 juan headers covering numbers 1–332, no duplicates. **Juan 102, 107, 110, 112 are entirely missing** from this digitized edition (they are the 表-type juan: 諸王世表/功臣世表/宰輔年表/七卿年表 — table content was omitted during digitization). Juan 101 has a header but no body. These are flagged `has_content=False` in the CSV rather than being counted as 0.
5. **Counting** — Per juan: (a) count of 倭; (b) total CJK character count (excluding punctuation, whitespace, footnote markers `[1]`) for normalization; (c) frequency per 1,000 characters.
6. **Output** — `results/wo_frequency_by_juan.csv` (333 rows: header + 332 juan), UTF-8 with BOM for Excel compatibility.

**Key results:** 倭 appears 717 times across 99 juan. Top juan: 卷320 朝鮮傳 (79), 卷212 (66, 劉大夏/馮琦等傳), 卷322 日本傳 (63), 卷205 (49, 胡宗憲等傳), 卷18 (44, 世宗本紀二), 卷290 (37, 戚繼光傳), 卷238 (34, 李成梁傳), 卷91 兵志三 (29).

**Human review:** [pending]
