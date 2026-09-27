# Genie応募向け: Paper2Reproの事実メモ

完成した応募文ではなく、repositoryとSoccerMaster development runから説明に使える事実をまとめた素材です。実際に提出する際は本人の経験・担当範囲に合うよう書き直してください。

## ① 背景・目的

- ML論文の再現情報は、論文本文とREADME、config、script、checkpoint、environmentなど複数の場所に分散している。
- 論文の実験claimごとに、公式repository内のどの情報が対応するか、再現に必要な情報がどこまで見つかるかを監査する小規模prototypeとしてPaper2Reproを開発。
- 学習・推論を実行して結果を再現するsystemではなく、根拠へのtraceabilityとartifact availabilityを調べるのがv0.1の範囲。

## ② 取り組み内容

- pypdfでローカルPDFをページ番号付きテキストへ変換。
- Gemini structured outputをPydantic schemaへ変換し、主要な量的experimental claimとpaper evidenceを抽出。
- paper evidence excerptが指定PDF pageのtextにanchorできるかをdeterministicに検証。
- repository inventoryとbounded text loaderでREADME、config、script、environment等を整理。
- dataset / metric / reported valueを用いる小さなkeyword retrieval baselineでclaim関連候補を抽出。
- Geminiでclaimと取得文書を対応付け、dataset preparation、model config、checkpoint、command、environment、random seed、evaluation protocolの7項目を監査。
- repository evidenceのpathとexcerptをdeterministicに検証し、anchorできないevidenceに依存するstatusをdowngrade。
- JSON / Markdown report、CLI、FastAPIの最小scaffold、Dockerfile、GitHub Actions CIを整備。
- Geminiの実APIを使わないpytestではfake clientを使う。

## ③ 技術・本人の役割

**確認できる技術:** Python 3.11、Pydantic、pypdf、Google GenAI SDK、FastAPI、pytest、uv、Docker、GitHub Actions、Git。

**本人が行った作業として説明できること:**

- プロジェクトの問題設定と方向性を決定。
- repository inventoryの初期実装。
- lexical retrieval baselineの中心である `score_document()` と `retrieve_documents()` を実装。
- 実際のPDFと公式GitHub repositoryを使ったdevelopment runを実行。
- zero retrievalや無関係な上位候補などのfailure modeを観察し、statement語を含める次の改善課題を定めた。

ほかの実装はrepositoryを確認して具体的な担当を説明してください。「すべてを一人で手書きした」とする根拠はありません。必要に応じて、AI支援を受けながら設計・実装・reviewを進めたと事実に即して説明してください。

## ④ 成果・学び

保存されているSoccerMasterの**1回のdevelopment run**では次の出力を得た:

- 9 claimsを抽出。
- paper evidence 21/21件が指定pageのPDF textにanchor。
- 9 claims中4件が`SUPPORTED`または`PARTIALLY_SUPPORTED`のmapping status。
- auditは`PRESENT=5`、`AMBIGUOUS=9`、`NOT_FOUND=49`。
- repository inventory 740 artifacts、text loader 621 documents。
- Claim 4とClaim 8でzero retrieval。Claim 2と9で同一の無関係候補が上位に並ぶfailureも確認。

これらは**一つのdevelopment runにおけるシステム出力で、正式なquality score、accuracy、一般化性能ではない**。21/21はこのrunのextracted evidenceのanchor結果であり、claimのsemantic truthを示さない。4/9はmappingの正答率ではない。`NOT_FOUND`は取得・検査した文書内で見つからなかったことを指し、repository全体に存在しない証明ではない。

## 説明時に強調できる学び

- LLMに根拠文やpathを生成させるだけでは信頼性を確保できず、出力を元PDF/repository textに照合するdeterministic checkが必要。
- evidenceが実在することと、claimを意味的に支持することは別問題。
- retrievalが空または誤ると後段auditも誤読され得るため、audit statusには検索範囲の明示が必要。
- 一度の実runでpaper evidence anchoringが機能した一方、simple lexical retrievalに目立つ失敗があると把握。次は人手review setを作り、baselineとの比較を通じて改善する段階。

## 応募時に確認する項目

- 実際に本人が書いた範囲、AI支援を受けた範囲、reviewした範囲を分けて説明する。
- 1回のdevelopment runと正式評価を混同しない。
- `SUPPORTED`等を「再現できた」と言い換えない。Paper2Reproは学習・推論を実行していない。
- 数字の背景として、Claim 4/8のzero retrievalと`NOT_FOUND`の範囲を説明できるようにする。
