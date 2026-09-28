# Paper2Repro 概要

Paper2Reproは、機械学習論文の実験claimと公式repository内の情報を対応付け、再現に必要な情報を確認するための小規模な研究開発prototypeです。論文の結果を実際に再現するsystemではなく、根拠がどこに記載されているかを追跡しやすくすることを目指しています。

## 何を作ったか

ローカルPDFとローカルまたは公開GitHub repositoryを入力し、claimごとにpaper evidence、repository内の候補文書、mapping、再現性確認項目をまとめた`report.json`と`report.md`を生成します。

## 背景・目的

論文の実験結果を再現するための情報は、本文だけでなくREADME、config、script、checkpoint、environmentなどに分散しています。repository全体を一つの要約にするだけでは、ある数値やclaimをどのfileが支えるのか分かりにくくなります。

Paper2Reproではexperimental claimを分析単位にし、claimとpaperの該当page、claimとrepository内の候補文書を対応付けます。目的は情報の有無と根拠のtraceabilityを確認することで、trainingやevaluationを実行することではありません。

## 現在できること

- pypdfでselectable textを持つPDFからpage番号付きテキストを抽出する。
- Geminiのstructured outputで主要な実験claimとpaper evidenceを抽出する。保存済みreportからclaim setを再利用して、retriever比較時の抽出呼び出しを省略することもできる。
- baseline lexical retrievalを既定値としてrepository文書を取得する。experimental weighted lexical retrievalもCLIから選択できる。
- claimと取得文書をGeminiで対応付け、dataset preparation、model/config、checkpoint、command、environment、random seed、evaluation protocolの7項目を整理する。
- paper excerptを指定PDF pageに、repository evidenceを取得したfile pathとtextに照合する。
- JSON / Markdown reportを出力する。CLI、最小限のFastAPI endpoint、Dockerfile、GitHub Actions CIも用意している。

## 技術的な工夫

- claim単位で分析し、paper evidenceとrepository evidenceをreport内に残す。
- evidence validationはLLMの自己申告に任せず、page、path、excerptが入力データに存在するかdeterministicに確認する。
- PDFのUnicode、不可視文字、改行による単語分割、whitespaceの差を正規化する。一方、異なる数字や句読点をfuzzy matchingで同一視しない。
- `NOT_FOUND`は取得して検査した文書内で見つからなかった意味に限定する。repository全体に情報が存在しない証明とは扱わない。
- baselineとweightedのmapping cache versionを分け、異なるretrieverの結果が同じcache keyを使わないようにしている。

## 開発時の観察

保存されたSoccerMasterの一回のdevelopment runでは、9 claimsを抽出し、paper evidence 21/21件が指定pageのPDF textにanchorしました。mappingは4/9 claimsが`SUPPORTED`または`PARTIALLY_SUPPORTED`で、740 artifactsをinventoryし621 text documentsを読み込みました。これは一つのrunの出力であり、accuracyや正式なquality評価ではありません。mapping statusもgold labelとの比較ではありません。

baselineは同runでClaim 4とClaim 8に文書を返さず、Claim 2とClaim 9で似た無関係候補を上位に返す問題がありました。offline development comparisonではweighted版がClaim 4で`models/video_caption.py`、Claim 8で`data/video_caption.py`をそれぞれrank 1にしました。これは候補順位の一例であり、関連性の正しさやaccuracyを示すものではありません。詳細は[retrieval analysis](SOCCERMASTER_RETRIEVAL_ANALYSIS.md)を参照してください。

## 現在の限界

- OCRはなく、画像だけのPDFでは本文を抽出できないことがある。
- claim extractionとrepository mappingはGemini出力に依存し、runごとに変わる可能性がある。
- excerptが実在することは確認するが、その文章がclaimを意味的に支持するかは判定しない。
- retrievalはlexical方式で、関連fileを取りこぼしたり、無関係な候補を返すことがある。weighted版もexperimentalで、human-reviewedな複数論文評価はまだない。
- 大きなfile、binary、checkpoint、datasetはdocument contentとして読み込まない。
- training、inference、任意のrepository command、GPU jobを実行しない。
- repositoryの選択文書は設定されたGemini API providerに送信される。

## 今後の予定

- 複数論文とrepositoryに対するhuman-reviewed evaluation setを作る。
- baseline / weighted retrievalを人手で確認した例に対して比較し、必要に応じてBM25やembedding retrievalを評価する。
- 文書の分割やline locationを改善し、evidence validationのtraceabilityを高める。
- 実行可能性を調べる場合は、通常の情報有無監査と分けたcontrolled executionとして設計する。

## 実行方法

環境構築とCLIの例は[README](../README.md#quickstart)を参照してください。
