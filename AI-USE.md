AI Use Policy

Tools Used:
- Copilot
- GLM 5.3 Flash

Scope & Purpose of Use:
- Use AI to assist with brainstorming, code explanations, debugging, summarization, and drafting project documentation.
- Use AI as a support tool, not as the final decision-maker for technical or academic work.
- Review all AI-generated output for correctness, relevance, safety, and compliance before relying on it.
- Keep AI usage focused on tasks that improve productivity, learning, and quality.

Human Critical Input:
- All important decisions should be checked by a human.
- Validate code, facts, citations, and assumptions before submission or deployment.
- Do not rely on AI outputs for security-sensitive, privacy-sensitive, or high-risk decisions without human review.
- Update this file from time to time as the toolset, workflow, or project requirements change.

Sample Prompts:
- "Explain this error and suggest a minimal fix for the root cause."
- "Summarize the project structure and identify the main files involved in this feature."
- "Draft a concise README section for the current assignment or tool workflow."
- "Review this code for logic issues, edge cases, and maintainability improvements."
- "Generate a checklist for validating the change before submission."
- "Create a analysis.py and record all the steps beginning from now. Install opencc, jieba, qhchina. Convert 明史.txt to simplified Chinese characters with opencc. Split the content of data.txt into sentences based on punctuation. each line per sentence, no space between words, at least 5 words in a sentence. Create data.txt under data folder, use plain-text UTF-8. Loads a user dictionary for jieba from userdict.txt (one word per line); create this file with the target words I care about: 倭 plus related names and official titles. create a index.csv with the 卷 number and title for each line of data.txt. prints 20 random segmented sentences that contain one of my target words, so I can check the segmentation by eye."

## Record of AI Use (2026-10-07)

What the AI did:
1. Updated `analysis.py` to assign years to sentences using Ming reign-year expressions and carry the latest dated year forward within each 卷, so an event sentence without its own year can still be placed in a phase.
2. Added collocate analyses for 倭 using `find_collocates` and the `zh_cl_sim` stopword list:
   - Window method with horizons 5 and 10, and sentence method.
   - Added `log_likelihood` and `logDice`; applied Benjamini-Hochberg FDR correction.
   - Required collocate tokens to be at least two characters long, excluded classical Chinese stopwords, and kept adjusted p-values below 0.05.
   - Sorted by logDice, printed up to 20 collocates per phase, and saved each analysis run in `output/`.
3. The supplied Early and Middle Ming ranges both include 1523; sentences dated to 1523 are included in both phases as specified by those ranges.

4. Added exact jieba-token frequency counts for 倭 and the 26 supplied 倭-related terms, divided among the three phases. The CSV includes a total-frequency column summing only the phase counts, omits terms with zero counts in every phase, and is saved as `output/target_word_frequencies_by_phase.csv`.
5. Added generation of `output/results.html` from the collocation and word-frequency CSVs. The standalone English report has a cover, three collocation views (window horizon 5, window horizon 10, and sentence method), a target-word frequency view, and an interactive comparison view. Collocation tables show observed/expected statistics and raw/adjusted p-values; every table supports sorting by clicking its column headers.
6. Updated report navigation labels to “5-Word,” “10-Word,” and “Word Frequency,” and updated the page titles for the three collocation analyses and related-word frequency view.
7. Added Page 6 as a direct comparison dashboard. It places the Early, Middle, and Late Ming phase values side by side for one selected method (5-Word, 10-Word, or Sentence). Controls select the method and statistic, search collocates, and sort table columns. A missing result is identified as not present among the selected method’s significant top-20 results for that phase, rather than shown as a zero.
8. Made the report navigation fixed to the top of the viewport while scrolling, with content spacing to keep page headings visible below the bar.
9. Set the report cover and document title to “Collocation Analysis of Ming-Japan Relation Shift throughout Different Periods of Ming Dynasty.”
10. Searched both `data/data.txt` and the source `data/明史.txt` for 倭刀, 倭王, 倭变/倭變, 伐倭, and 拒倭. None appeared literally in either text; related separate-character wording was not counted as exact terms.
11. Added a standalone `output/kwic.html` report using `kwic` from `qhchina.analytics.collocations`. It has a cover page and separate Early Ming, Middle Ming, and Late Ming pages; each phase shows up to 10 passages for each supplied collocate at 5-token, 10-token, and full-sentence horizons. When `data/index.csv` exists, each passage includes its 卷 number and title.
12. Added a Cover button to the KWIC navigation and displayed each passage’s matching collocation-result statistics: observed and expected frequencies, observed/expected ratio, log-likelihood, logDice, raw p-value, and adjusted p-value. Statistics unavailable because a collocate is absent from that method’s significant top-20 results are labeled as unavailable, not zero.
13. Renamed the KWIC context headings to “5-Word Analysis,” “10-Word Analysis,” and “Sentence Analysis.”
14. Kept the Cover link and fixed top navigation available throughout both standalone HTML reports, and updated 5/10-word horizon labels to “5-Word” and “10-Word.”
15. Replaced the Early Ming KWIC collocate 登岸 with 沿海; the Early Ming concordance page now uses 海上, 出海, and 沿海.

The main HTML report is rebuilt from the existing CSVs by `generate_results_html()` in `analysis.py`. The KWIC report is generated by `generate_kwic_html()` from the corpus rows and optional index. Rerunning the script refreshes the collocation CSVs, frequency CSV, and both reports.

Human verification:
- Review the phase-year assignments and the generated collocate tables before drawing historical conclusions.
- The current `data/userdict.txt` already contains all 27 requested frequency terms; the script preserves any extra existing dictionary entries.

## Record of AI Use (2026-10-06)

What the AI did:
1. Installed opencc, jieba, qhchina (Python 3.14).
2. Wrote analysis.py implementing the full pipeline:
   - Load data/明史.txt (traditional Chinese, 3.28M chars, 328 juans)
   - OpenCC t2s conversion to simplified Chinese
   - Parse juan structure (卷X headers + -- rules), Chinese numerals -> int
   - Sentence split on 。！？；… (closing quotes absorbed; not split on ，)
   - Filter sentences >= 5 chars, strip whitespace and footnote markers
   - Write data/data.txt (169,926 lines, one sentence per line, UTF-8)
   - Write data/index.csv (line, juan, title for every line)
   - Write data/userdict.txt (117 target words: 倭 + related names + official titles)
   - Load userdict into jieba
   - Print 20 random segmented sentences containing core target words
   - Print target-word frequency report (top 30)
3. Iterated on sentence-splitting logic so no sentence starts with ，.
4. Adjusted the sample check to prioritize 倭-specific words over generic titles.

Human verification:
- Eyeballed the 20 random segmented samples for segmentation quality.
- Checked data.txt, index.csv, userdict.txt contents and line counts.
