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
