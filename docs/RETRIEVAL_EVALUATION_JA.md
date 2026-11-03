# 検索手法のoffline評価

固定したExperimentalClaimとfile単位の正解ラベルを使い、既存baseline / weighted lexical retrievalを比較します。Gemini、claim extraction、mapping、PDF parsingは呼びません。ローカルrepoだけを読み、外部データのdownloadやネット接続は不要です。

## 実行と出力

既存環境（`uv sync`済み）で実行できます。API keyは不要です。

```bash
uv run --offline python scripts/evaluate_retrieval.py \
  --dataset evals/retrieval_sample/dataset.json \
  --top-k 1 3 5 10 \
  --output outputs/retrieval-sample
```

`--top-k`の既定値は`1 3 5 10`。正の整数を空白区切りで指定し、重複は除いて昇順に整理します。`--output`の既定値は`outputs/retrieval-evaluation`です。

- `evaluation.json`: query別の順位付きpath、正解との一致、各kの指標、macro平均、coverage、警告、計測時間。
- `evaluation.md`: 同じ情報を集計表とquery別ランキング表で表示。指標は小数4桁、時間は小数6桁で表示し、JSONは丸めません。
- 標準出力: query数、label種別、coverage、出力先。未インデックスの正解は標準エラーにも警告します。

出力先は評価対象repoの外、またはloaderが除外する`outputs/`配下にしてください。比較中はrepoを変更せず、同じrevisionを使います。

## 評価セットJSON

```json
{
  "schema_version": 1,
  "label_type": "synthetic",
  "description": "架空の最小例。研究結果ではない。",
  "queries": [
    {
      "query_id": "decoder-config",
      "repository": "repository",
      "claim": {
        "statement": "The decoder configuration uses training inputs for CometSet.",
        "dataset": "CometSet",
        "metric": "score",
        "reported_value": "12.0"
      },
      "relevant_paths": ["configs/decoder.yaml", "data/decoder.txt"]
    }
  ]
}
```

`repository`は**評価JSONのdirectory基準**で解決するローカルpathです。絶対pathも使えます。`repository`と`./repository`など同じrepoへの参照はresolveしたpathで共通化し、文書を一度だけ読みます。URL、`~`や環境変数のshell展開、Windows形式は扱いません。出力にresolve済みrepo pathと入力JSONのpathが残ります。

`relevant_paths`は**repo root基準**のcase-sensitiveなPOSIX relative file pathsです。先頭`/`、空文字、`.`、`..`、重複slash、末尾slash、backslash、colon、制御文字、前後whitespaceは禁止です。実在してもloaderが読まないfileはcoverage欠落になります。

`claim`は既存ExperimentalClaimを使います。`statement`は必須、`dataset`・`metric`・`reported_value`は省略またはnullにできます。`evidence`は省略時に空listで、検索評価ではPDF evidenceを検証しません。重複query ID、重複正解path、空の正解集合、空のquery集合、未知field、不正なpath形式は入力エラーです。不正JSON、存在しないrepo、読込みエラーはCLIの終了code 2になります。

## 指標とcoverage

各queryの正解集合をG、上位kに現れる正解file数をhとします。pathの完全一致で採点します。

| 指標 | 計算 |
|---|---|
| Recall@k | h / 全正解file数 |
| Precision@k | h / k |
| RR@k | 上位kの最初の正解順位の逆数。正解なしは0 |
| macro Recall@k / Precision@k | query別値の算術平均 |
| MRR@k | query別RR@kの算術平均 |

**k件未満しか返らなくてもPrecisionの分母はk固定**で、未返却枠は不正解です。正解2件のうち1件をrank 2で取得し3件返った場合、k=5ではRecall=1/2、Precision=1/5、RR=1/2です。zero retrieval queryも0で平均に含めます。queryごとの重みは一律で、正解数やrepoサイズによる重み付けはありません。

正解pathがindexになくても正解集合から除外しません。query別`missing_paths`と警告を出し、Recallの分母に残します。coverageは`indexed_relevant_count / total_relevant_count`で、**query-fileの組の数**です。同じfileが2 queriesの正解なら2件と数えます。不存在、非対応拡張子、binary、サイズ制限、loader除外directory等は全て「indexにない」と報告し、原因の自動分類は行いません。

## 架空fixtureの例

同梱の`evals/retrieval_sample/`は4文書と3 queriesです。複数正解、statementのみのquery、0件ヒットを確認する人工例で、実論文の評価や検索手法の優劣を示す研究結果ではありません。

| Retriever | k | macro Recall@k | macro Precision@k | MRR@k |
|---|---:|---:|---:|---:|
| baseline | 1 | 0.0000 | 0.0000 | 0.0000 |
| baseline | 3 | 0.3333 | 0.2222 | 0.1667 |
| weighted | 1 | 0.5000 | 0.6667 | 0.6667 |
| weighted | 3 | 0.6667 | 0.3333 | 0.6667 |

最初のqueryのbaseline順位はREADME（不正解）、config（正解）、data（正解）で、Recall@3=1、Precision@3=2/3、RR@3=1/2です。macroでは正解を返さなかったqueryも含めて平均します。

## 時間計測

`perf_counter()`によるwall-clock秒を次の2区間に分けます。

- repo読込み: repoごとに`inventory_repository()`と`load_repository_documents()`を1回ずつ実行した区間。repo別秒数と合計を報告します。
- retrieval-only: 同じclaimと文書listを渡し、baseline、weightedの順で`max(k)`件を返す既存retriever呼び出しだけを計測。query・手法あたり1回で、他のkは同じランキングのprefixから計算します。

retrievalの集計は手法別の秒数合計とquery数で割った平均で、query別秒数はJSONに記録します。JSON parsing、path解決、coverage、指標計算、report出力は両区間から除外します。warm-up、反復測定、OS cache制御、統計的検定はなく、順序も固定なので、特にfixtureの時間差を実用速度の結論に使わないでください。

## gold / silver / syntheticと追加データ

- **gold**: 人が論文とrepoを確認し、関連性の基準に従ってreviewした正解。
- **silver**: heuristicや未review候補など、goldに達していない暫定ラベル。
- **synthetic**: 評価器検証用の架空文書・人工ラベル。同梱fixtureはこれに該当。

`label_type`はdataset全体に必須で、異なる種別は別JSONに分けます。このfieldは出自の自己申告で、toolがラベル品質を保証するものではありません。既存reportの`retrieved_documents`や`SUPPORTED`をそのままgoldに変換しないでください。今回AIによる実データのラベル作成は行っていません。

1. ローカルにあるpaper/repoと固定claim setを選び、人が関連性の定義を決めます。
2. claim、dataset/metric/valueを固定してJSONへ転記します。同じclaimとrepo revisionで両手法を比較します。
3. 上位候補だけに偏らずrepoを確認し、関連fileを列挙します。reviewer、repo commit SHA、理由は`description`または別のreview記録へ残します。
4. 不確かな候補はsilver datasetへ分けます。正解が分からないqueryは空集合にせず、評価前に保留します。
5. coverage警告がfile移動ならrevisionを再確認し、loader制約なら正解を消して見かけのscoreを上げず制約を記録します。
6. 開発用と評価用のqueriesを分け、同じJSONとコードrevisionで評価し、出力を比較・保管します。

## 限界と次の拡張

file単位の二値ラベルであり、claim extraction、semantic support、mapping/auditの正しさ、実験再現の可否は評価しません。未ラベルfileは不正解扱いなので、不完全な正解集合は指標を歪めます。少数queryや同じrepoへの多数queryから一般化性能を主張できません。

既存検索ロジックとpipelineは変更していません。次の候補は人手reviewした複数repoのデータ、revision/checksum記録、反復時間測定です。BM25・embedding・外部benchmarkのdownloadは含みません。

## 重要ロジックの読み順

1. `retrieval/evaluation.py`: `EvaluationSet` / `EvaluationQuery`で入力検証、`metrics_at_k()`で採点、`evaluate_retrieval()`で読込み・検索・集計、`render_evaluation_markdown()`で表示。
2. `scripts/evaluate_retrieval.py`: argparse、入力エラー処理、2種類のreport書込み。
3. `tests/test_retrieval_evaluation.py`: 手計算、macro平均、coverage、読込み回数、計測区間、入力検証、ネット接続を禁止したCLI実行を確認。
