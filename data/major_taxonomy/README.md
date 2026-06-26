# Major Taxonomy Database

This directory provides the static major taxonomy used by the Codex career-agent design. The goal is to avoid reclassifying Chinese engineering majors from scratch on every run.

## Files

- `engineering_official_majors_2026.zh-CN.json`
  - Cleaned extraction of the official `08 学科门类：工学` section from the Ministry of Education undergraduate major catalog.
  - Preserves official class code, official class name, major code, major name, and degree-award notes.

- `engineering_employment_clusters.zh-CN.json`
  - Employment-oriented clustering built on top of the official catalog.
  - Each major has exactly one `primary_cluster` to keep overlap between clusters low.
  - Each major may have multiple `cross_tags` for adjacent job families, learning-path recommendations, and transferable-skill analysis.

- `engineering_major_index.zh-CN.csv`
  - Flat index for quick lookup by major code or major name.

- `summary.json`
  - Counts by official class and employment cluster.

- `engineering_related_interdisciplinary_majors_2026.zh-CN.json`
  - Engineering-related majors from `14 学科门类：交叉学科`.
  - Includes majors such as `具身智能`, `未来机器人`, `工程互联网`, and `集成电路科学与工程`.
  - These are not part of `08 工学`, but many award an engineering bachelor's degree and are relevant to engineering job matching.

- `engineering_related_interdisciplinary_majors_2026.zh-CN.csv`
  - Flat lookup table for the interdisciplinary engineering-related majors.

## Source

- Title: `普通高等学校本科专业目录（2026年）`
- Publisher: `中华人民共和国教育部`
- Source page: `https://www.moe.gov.cn/srcsite/A08/moe_1034/s3882/202604/t20260427_1434931.html`
- PDF: `https://www.moe.gov.cn/srcsite/A08/moe_1034/s3882/202604/W020260427440749576927.pdf`
- Accessed on: `2026-06-26`

Additional source scope:

- `14 学科门类：交叉学科` majors that award engineering degrees or strongly map to engineering job families.

## Classification Policy

This database separates two concepts:

1. Official academic classification:
   - Uses the Ministry of Education catalog as the source of truth for official major code and official major class.

2. Employment-oriented classification:
   - Groups majors by job-market skill adjacency rather than only by official academic class.
   - Uses a low-overlap `primary_cluster`.
   - Adds `cross_tags` when a major can reasonably connect to multiple job families.

Example:

- `人工智能` is officially under `0807 电子信息类` in the source catalog.
- For employment matching, it is mapped to the primary cluster `计算机与 AI 软件类`.
- It also keeps cross-tags such as `电子信息`, `自动化控制`, and `数学建模`.

## Intended Use

The `MajorClusterClassifier` should:

1. Look up the user's normalized major in `engineering_major_index.zh-CN.csv` or `engineering_employment_clusters.zh-CN.json`.
2. If not found, also check `engineering_related_interdisciplinary_majors_2026.zh-CN.csv`.
3. Return the `primary_cluster`.
4. Return all `cross_tags`.
5. Use the primary cluster for low-overlap peer comparison.
6. Use cross-tags for adjacent job suggestions, learning recommendations, and personal-branding advice.

If a user's exact major is not found, the classifier should:

- Try fuzzy matching against major names.
- Ask for the college, curriculum, and direction if ambiguity remains.
- Use the closest official class only as a fallback.
