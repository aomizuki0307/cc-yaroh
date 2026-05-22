# X Growth — CCやろー運用ドキュメント

Claude Code 特化の新規 X ハンドル「CCやろー」の運用・証跡・KPI を管理するディレクトリ。

## 概要

| 項目 | 値 |
|---|---|
| ハンドル | `@cc_yaroh`（Claude Code やろー）候補 |
| 開始日 | 2026-05-18 (W0) |
| 目標 | 3か月で 10K followers / 月50万円相当の収益 |
| 戦略 | ぱうう @09pauai 型: Claude Code 全自動 × 1日10投稿 × build in public |
| プラン詳細 | [docs/ai/x-growth-plan.md](../ai/x-growth-plan.md) |
| 実装記録 | [docs/ai/decisions.md](../ai/decisions.md) ADR-005 |

## ディレクトリ構造

```
docs/x-growth/
├── README.md          ← このファイル
├── kpi.csv            ← 日次KPI（フォロワー / インプ / 収益）
├── evidence/
│   └── day-0/         ← Day0 スクショ（X参加日 / フォロワー0証跡）
└── weekly/
    ├── W00.md         ← Week 0 仕込みログ
    ├── W01.md
    └── ...
```

## KPI 目標

| Week | フォロワー目標 | 備考 |
|---|---|---|
| W1 | 50 | 1日3投稿でスタート |
| W4 | 500 | **Go/No-Go ゲート** |
| W6 | 1,000 | 収益化申請の中間ゲート |
| W12 | 10,000 | 3か月チャレンジ |

Xクリエイター収益配分の参加資格は変わる可能性があるため、最新条件は公式ヘルプで確認する。2026-05-20確認時点では、Premium系サブスクリプション、過去3か月500万以上のオーガニックインプレッション、500人以上の認証済みフォロワーなどが必要。

## コンテンツピラー（最大1日10投稿）

| Pillar | 本数 | 内容 |
|---|---|---|
| Trend | 4 | Claude/AI ニュース解説 |
| Devlog | 4 | Claude Code で作ったものの実況 |
| Revenue | 2 | 収益進捗 + アフィ導線 |

## 投稿自動化パイプライン

```
x_growth collect → pillar_router (時間帯判定) → tier prompt生成 → publish_guard (フィルタ) → publish_to_x
```

実装: `x_growth/`  
スケジューラ: `.github/workflows/x-growth-*.yml`（W1前半は3本のみcron有効）

## コスト前提

X APIはPay-per-use。2026-05-20確認時点の公式価格では、投稿作成は通常 $0.015/request、URL付き投稿は $0.200/request。300投稿/月ならURLなしで約 $4.50 から。実コストはDeveloper Consoleで確認する。

## らたろー.T との分離ポリシー

- GitHub `aomizuki0307` のみ共有（プロファイル top リンク）
- 本名・フリーランス受注導線・書籍販促は混ぜない
- X 収益 + アフィ収益のみ公開（フリーランス売上は出さない）
