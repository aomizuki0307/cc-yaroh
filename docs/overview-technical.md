# @cc_yaroh X 成長パイプライン — 技術概要

## 概要

Claude Code を使って X アカウント (@cc_yaroh) の運用を全自動化するシステム。  
GitHub Actions + Python + X API v2 + Anthropic API (Haiku) で構成され、**1日10本の投稿・週次スレッド・KPI自動記録・エンゲージメント下書き生成**を無人で行う。

プロジェクト開始: 2026-05-18 / リポジトリ: `aomizuki0307/cc-yaroh` (private)

---

## アーキテクチャ

```
GitHub Actions (cron)
        │
        ▼
x_growth/runner.py  ──pillar──▶  source_collector.py
                                         │
                          ┌──────────────┼──────────────┐
                          ▼              ▼               ▼
                   rss_collector   git log parse    (revenue固定)
                    (RSS/HTML)      (commits)
                          │
                          ▼
                   prompt_builder.py
                          │
                          ▼
                  Anthropic Haiku API
                          │
                          ▼
                   publisher.py  ──▶  X API v2 POST /2/tweets
```

サブシステム:
- `kpi_updater.py` — 毎日フォロワー数を取得して `docs/x-growth/kpi.csv` に自動コミット
- `engagement_collector.py` — #ClaudeCode ツイートを検索し返信下書きを生成
- `weekly_thread.py` — 週次まとめスレッドをリプライチェーンで投稿

---

## ディレクトリ構成

```
cc-yaroh/
├── .github/workflows/          # GitHub Actions (13本)
│   ├── x-growth-0600-trend.yml
│   ├── x-growth-0730-trend.yml
│   ├── x-growth-0900-trend.yml
│   ├── x-growth-1130-trend.yml
│   ├── x-growth-1230-devlog.yml
│   ├── x-growth-1730-devlog.yml
│   ├── x-growth-1900-devlog.yml
│   ├── x-growth-2030-devlog.yml
│   ├── x-growth-2200-revenue.yml
│   ├── x-growth-2330-revenue.yml
│   ├── x-growth-kpi-update.yml
│   ├── x-growth-weekly-thread.yml
│   └── x-growth-engagement-draft.yml
├── x_growth/
│   ├── runner.py               # エントリポイント (--pillar trend|devlog|revenue)
│   ├── source_collector.py     # ピラー別コンテンツ収集
│   ├── rss_collector.py        # RSS/HTML フェッチ + 重複除去
│   ├── prompt_builder.py       # プロンプト組み立て
│   ├── publisher.py            # X API v2 投稿 (リプライチェーン対応)
│   ├── kpi_updater.py          # KPI CSV 自動更新
│   ├── weekly_thread.py        # 週次スレッド生成・投稿
│   └── engagement_collector.py # エンゲージメント下書き生成
├── prompts/x_growth/
│   ├── tier1_trend.md          # trend ピラー用システムプロンプト
│   ├── tier2_devlog.md         # devlog ピラー用
│   ├── tier3_revenue.md        # revenue ピラー用
│   └── weekly_thread.md        # 週次スレッド用
├── docs/x-growth/kpi.csv       # KPI 記録 (毎日自動更新)
├── out/x-growth/               # 生成ドラフト・アーティファクト (gitignore)
│   └── seen_headlines.json     # 重複除去キャッシュ (7日間)
└── requirements.txt
```

---

## コンテンツ生成パイプライン

### 3つのピラー

| ピラー | ソース | ハッシュタグ | 投稿数/日 |
|--------|--------|-------------|----------|
| trend | RSS/HTML フェッチ (Zenn・Qiita・TechCrunch・Google AI・Anthropic) | `#ClaudeCode #生成AI` | 4本 |
| devlog | `git log --since=24h` の最新コミット | `#ClaudeCode #buildinpublic` | 4本 |
| revenue | 固定コンテキスト (副業・フリーランス) | `#ClaudeCode #AI副業` | 2本 |

### RSS 重複除去キャッシュ

`out/x-growth/seen_headlines.json` にタイトルの MD5 ハッシュ (先頭16桁) を日付キーで保存。7日以内に取得済みのヘッドラインは自動スキップし、同一ニュースの連投を防ぐ。

### 捏造統計防止

Haiku は根拠のない数値 ("80%削減" など) を生成しやすいため、全プロンプトに以下のルールを明示している:

```
★ 数字・パーセンテージ・効果量は入力ソースに明示されたもの以外絶対に使用禁止
★ 固有名詞・製品名・バージョン番号も入力ソースにないものは作らない
```

---

## GitHub Actions スケジュール

| ワークフロー | UTC cron | JST 実績目安 |
|---|---|---|
| 0600-trend | `0 21 * * *` | ~09:00 |
| 0900-trend | `0 0 * * *` | ~09:00 |
| 0730-trend | `30 22 * * *` | ~10:30 |
| 1130-trend | `30 1 * * *` | ~11:00 |
| 1230-devlog | `0 3 * * *` | ~14:30 |
| 1730-devlog | `0 8 * * *` | ~19:50 |
| 1900-devlog | `0 10 * * *` | ~21:00 |
| 2030-devlog | `30 11 * * *` | ~22:30 |
| 2200-revenue | `0 8 * * *` | ~19:50 |
| 2330-revenue | `30 12 * * *` | ~21:30 |
| kpi-update | `0 22 * * *` | ~07:00 |
| engagement-draft | `0 23 * * *` | ~08:00 |
| weekly-thread | `0 10 * * 0` | 日曜~19:00 |

> GitHub Actions 共有インフラは平均 2〜3h の遅延があるため、UTC cron と JST 実績にズレが生じる。

---

## X API 認証・投稿

- **認証**: OAuth 1.0a (`requests-oauthlib`)
- **投稿**: `POST /2/tweets` — ペイロードに `"reply": {"in_reply_to_tweet_id": id}` を含めることでスレッド投稿に対応
- **KPI取得**: `GET /2/users/me?user.fields=public_metrics`
- **ツイート検索**: `GET /2/tweets/search/recent` (エンゲージメント下書き用)
- **認証情報**: GitHub Secrets 経由 (`X_OAUTH_CONSUMER_KEY` 等4点 + `ANTHROPIC_API_KEY`)

---

## KPI・モニタリング

- `docs/x-growth/kpi.csv` に日次でフォロワー数・投稿数を記録 (Actions が自動コミット)
- 各ワークフローは `out/x-growth/` 以下のドラフトを artifact として3〜7日保持
- エンゲージメント下書きは `out/x-growth/engagement/YYYY-MM-DD.md` に保存

---

## 技術スタック

| 用途 | ライブラリ/サービス |
|---|---|
| LLM 生成 | `anthropic` SDK / claude-haiku-4-5-20251001 |
| X API 認証 | `requests-oauthlib` |
| RSS パース | `feedparser>=6.0.11` |
| HTML スクレイピング | `beautifulsoup4>=4.12` |
| 環境変数 | `python-dotenv` |
| CI/CD | GitHub Actions |
