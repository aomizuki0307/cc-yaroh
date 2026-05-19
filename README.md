# cc-yaroh — Claude Code × X 全自動投稿ボット

[@cc_yaroh](https://x.com/cc_yaroh) の X 投稿を Claude Code で全自動化するプロジェクト。

**ゴール**: 新規X参入 → 3ヶ月で1万フォロワー & 月50万円

## 構成

```
x_growth/          # 投稿パイプライン（Python）
prompts/x_growth/  # LLMプロンプト（3ピラー）
.github/workflows/ # GitHub Actions cron（10スロット/日）
docs/x-growth/     # KPI・週次レポート
```

## 3ピラー × 1日10投稿

| Pillar | 投稿数/日 | 時間帯 (JST) |
|---|---|---|
| Trend（AI技術ニュース解説） | 4 | 6:00 / 7:30 / 9:00 / 11:30 |
| Devlog（開発実況・build in public） | 4 | 12:30 / 17:30 / 19:00 / 20:30 |
| Revenue（収益・KPI公開） | 2 | 22:00 / 23:30 |

## セットアップ

```bash
pip install -r requirements.txt
```

GitHub Secrets に以下を登録:
- `X_OAUTH_CONSUMER_KEY`
- `X_OAUTH_CONSUMER_SECRET`
- `X_OAUTH_ACCESS_TOKEN`
- `X_OAUTH_ACCESS_TOKEN_SECRET`
- `ANTHROPIC_API_KEY`

## ローカルテスト

```bash
# dry-run（投稿しない）
python -m x_growth.runner --pillar devlog

# 実際に投稿
python -m x_growth.runner --pillar devlog --live
```

## KPI

→ [docs/x-growth/kpi.csv](docs/x-growth/kpi.csv)

---

*built with [Claude Code](https://claude.ai/claude-code)*
