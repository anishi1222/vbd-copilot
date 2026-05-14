# Japanese AI Tells Checklist

Reference for detecting AI-generated Japanese prose in CSA-Copilot deliverables (slides, demo guides, hackathon docs, AI project READMEs/architecture docs).

Severity: 🔴 critical (kills credibility) / 🟡 medium (softens impact) / 🟢 minor (polish only).

This checklist applies when `OUTPUT_LANGUAGE: ja`. The English checklist in `ai-tells-checklist.md` does not apply to Japanese body text but DOES still apply to any English fragments (product names quoted, embedded English captions).

---

## 1. Hedging tails 🔴

Pattern: closing a statement with a softener so the model never commits to a claim.

| AI tell | Why it reads as AI | Rewrite |
|---|---|---|
| 〜と言えるでしょう | Hedges every assertion | State the claim directly: 「〜です」 |
| 〜と言っても過言ではありません | Self-aware hedge to sound balanced | Just say it: 「〜です」 |
| 〜と考えられます | Avoids ownership | 「〜です」 or 「〜と判断します」 |
| 〜の可能性が示唆されます | Academic dodge | 「〜の可能性があります」or name the source |
| 〜と思われます | Adds doubt for no reason | 「〜です」 |

## 2. Filler openers 🔴

Pattern: meta-statements about what the document is about to do, instead of doing it.

| AI tell | Rewrite |
|---|---|
| 〜について述べます | Drop. Just deliver the content. |
| 〜について解説します | Drop. |
| 〜についてご説明します | Drop. The reader already knows they're reading the section. |
| 本章では〜を扱います | Drop or replace with a concrete claim. |
| 以下では〜について見ていきます | Drop. |

## 3. Formal listing 🟡

| AI tell | Rewrite |
|---|---|
| 〜が挙げられます | Name them: 「主な選択肢は A、B、C の3つです」 |
| 〜などが代表的です | Drop 「など」 unless truly non-exhaustive |
| 様々な〜が存在します | Be specific: 「Azure では Container Apps と AKS の2つが利用可能です」 |

## 4. Translation tells 🔴

These are direct translations of English AI tells. They mark machine-translated content.

| AI Japanese | Natural Japanese |
|---|---|
| 〜することができます | 〜できます |
| 〜することが可能です | 〜できます |
| 〜を行う | 〜する (use the verb directly) |
| 〜を実施する | 〜する |
| 〜という形で | (drop) |
| 〜のような形で | (drop) |
| 〜に対して〜を行う | (rewrite with direct verb) |
| 〜することを目的として | 〜のために |
| 重要なのは〜です | (drop or replace with the actual point) |

## 5. Formal closer 🟡

Pattern: stiff academic transitions at every paragraph break.

| AI tell | Rewrite |
|---|---|
| 以上のことから〜 | Drop or use 「つまり」「結論として」 sparingly |
| したがいまして〜 | 「だから」「そのため」 once, not every paragraph |
| 結論として〜 | Use only at the actual conclusion |
| なお、〜 | Use sparingly; AI overuses |

## 6. Suffix stacking 🟡

| Pattern | Why | Fix |
|---|---|---|
| 〜的 stacking: 効率的に効果的に戦略的に | All three say roughly the same thing | Pick the one that adds information |
| 〜化 stacking: 最適化、効率化、自動化、可視化 in one sentence | Buzzword soup | Pick the one that matters; remove the rest |
| 〜性 stacking: 拡張性、柔軟性、信頼性、可用性、保守性 | All in one bullet | Choose 1-2 that the reader actually cares about |

## 7. Mixed registers 🔴

Within ONE slide, ONE section, or ONE paragraph, NEVER mix:

- **Polite** (です/ます/ました/でしょう) - default for customer-facing materials
- **Plain/declarative** (だ/である/だった) - acceptable for technical reference docs

Example failure (mixed in one slide):
> AKS は Kubernetes のマネージド サービスです。コントロール プレーンは Microsoft が運用する。月額コストは Standard SKU で約 $73 だ。

Fixed (consistent ですます):
> AKS は Kubernetes のマネージド サービスです。コントロール プレーンは Microsoft が運用します。月額コストは Standard SKU で約 $73 です。

## 8. Sentence rhythm 🟡

| Pattern | Fix |
|---|---|
| 3+ sentences ending in 「〜です」 in a row | Vary: 「〜できます」「〜が便利です」「〜を選びます」 |
| 3+ sentences with the same opener (例えば、また、さらに、) | Drop or vary |
| Uniform sentence length (all 30-40 chars) | Mix short (10 chars) and long (60 chars) |
| Every sentence is exactly one independent clause | Use 「〜が、〜」「〜ため、〜」compound structures occasionally |

## 9. Generic authority 🔴

| AI tell | Why | Fix |
|---|---|---|
| 一般的に〜と言われています | No source | Name the source or remove |
| 多くの企業では〜 | Generic claim | Name a specific industry, customer scenario, or remove |
| 業界標準として〜 | Vague | Cite the actual standard (ISO, NIST, etc.) |
| 近年〜が注目されています | Time-vague filler | Give a year, a metric, or remove |
| 様々な調査によれば〜 | No citation | Cite or remove |

## 10. Markdown tells 🟡

| Pattern | Fix |
|---|---|
| Triple bullet points where each restates the previous | Collapse to one |
| Tables with 「項目」「説明」「備考」 columns where 備考 is empty | Drop the empty column |
| Section headers ending in 「について」 (「セキュリティについて」) | Drop 「について」 |

---

## Self-Check Routine

After drafting Japanese content, re-read and ask:

1. Could ANY sentence appear unchanged in generic AI output about a different topic? Rewrite it to reference THIS specific scenario.
2. Is the register consistent throughout (all ですます or all だ/である)?
3. Count Japanese AI tells from categories 1-5 above. 3+ hits = rewrite the worst offenders.
4. Are product names, code, URLs, file paths, and SKU IDs in English (not transliterated to katakana)? If you wrote 「アジュール コンテナー アプリ」, change it back to 「Azure Container Apps」.
5. Does each paragraph open differently? If not, vary.

---

## Tooling

The `humanizer_scorer.py` script currently scores English content. For Japanese content, perform the self-check above manually until the scorer is extended for Japanese (tracked separately).

The QA scripts (pptx_qa_checks.py, demo_qa_checks.py, hackathon_qa_checks.py) accept `--language ja` and detect categories 1, 4, 5, and 7 automatically.
