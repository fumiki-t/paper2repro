# 次の課題: statement語を使うweighted lexical retriever

目安は30分です。現行の `score_document()` / `retrieve_documents()` はそのまま残し、新しい関数を別に作って比較できるようにしてください。完成コードや正解rankingはここには用意していません。

## なぜ失敗するか

現在のbaselineが見るのは `dataset`、`metric`、`reported_value` の完全な部分文字列だけです。SoccerMasterのClaim 4では本文に `vision-language` や `retrieval` がある候補を見つけられず、Claim 8では `SN-Caption-test-align benchmark` と `SN-Caption-test-align` の表記差を許容できません。Claim 2と9ではstatementにある「athlete detection」「SoccerFactory」「spatial data」を無視するため、一般的な `mAP` の記述が同じ候補を上位にしやすくなっています。

## 入出力の候補

- 入力: `ExperimentalClaim` と `RepoDocument`。既存の型を再利用します。
- 出力: integer score、または `document + score + matched terms` の小さな結果型。
- 新しいquery helper候補: `build_query_terms(claim) -> list[WeightedTerm]`。
- retriever候補: `retrieve_documents_weighted(claim, documents, top_k=5)`。
- どの語が何点加算されたかを確認できると、誤rankingの調査がしやすくなります。

## 最初に試すweight案

値は仮説です。人間が見た少数例で調整してください。

| 情報源 | 初期weight案 |
|---|---:|
| dataset | 4 |
| metric | 3 |
| reported_value | 2 |
| statementから抽出した意味語 | 1 |

同じ語が重複して何度も加点されないようにする方法を決めます。ファイルpath内のmatchはbody内のmatchより少し強く、例えばpath multiplierを1.2程度にする案があります。実装ではfloat scoreを使うか、整数へ換算するかを自分で選んでください。

## Stopwordとtie-break

- `the`, `on`, `achieves`, `using` など一般語は候補から除けます。
- `SoccerFactory`, `SN-Caption`, `athlete`, `retrieval`, `caption` などtaskを区別する語は残したいところです。
- 最初は依存追加をせず、小さな明示的stopword集合と英数字tokenizationで十分です。
- 同じscoreの場合に順番が毎回変わらないtie-breakを決めます。例: score降順、path昇順。

## 最低限のtest

1. dataset / metric / value のweightが期待通りに反映される。
2. statementの意味語が関連文書を候補に上げる。
3. stopwordだけのstatementが全ファイルを同点上位にしない。
4. bodyよりpathのmatchを少し強く評価する。
5. 同じscoreの文書で決定的な順序になる。
6. `top_k` の件数を守り、score 0の文書は返さない。
7. 現行baselineのtestが引き続き通り、既存関数の出力は変わらない。

まずClaim 2、4、8、9のcandidate pathsを人間が見て、goldと呼ばずに小さなreview setとして比較してください。
