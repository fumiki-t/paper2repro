# Paper2Repro v0.1 学習ノート

この文書は、完成コードを30〜60分で読み直すための案内です。先に`pipeline.py`を読み、そこから各部品へ移ると全体像をつかみやすくなります。

## 1. 全体のdata flow

**何か:** PDFとrepositoryを入力し、claim単位の監査reportを作る一連の流れです。

**なぜ使うか:** 「論文のどの結果」と「repositoryのどの情報」が対応しているかを追跡可能にするためです。処理順は、PDF parse → claim extraction → paper evidence検証 → repository inventory/load → keyword retrieval → mapping/audit → repo evidence検証 → reportです。

**見るfile:** `src/paper2repro/pipeline.py`、`scripts/analyze.py`

## 2. dataclassとPydantic

**何か:** dataclassはPython内の軽いデータ容器、Pydanticは外部入力やLLM出力を型とschemaで検証するモデルです。

**なぜ使うか:** `PaperChunk`はparser内部で作る単純な値なのでdataclassで十分です。`ExperimentalClaim`などはGeminiのstructured outputやJSON reportに使うためPydanticにしています。

**見るfile:** `src/paper2repro/models.py`

## 3. structured output

**何か:** LLMの返答を自由文ではなく、Pydanticから作ったJSON Schemaに従うJSONへ制約する方法です。

**なぜ使うか:** `statement`や`evidence`などの形を毎回そろえ、手書きのJSON parserを避けるためです。ただしschemaが正しくても内容が実在する保証はないため、後段の検証が必要です。

**見るfile:** `src/paper2repro/providers/gemini.py`、`src/paper2repro/llm.py`

## 4. evidence grounding

**何か:** claimや判定を、page/pathと原文excerptへ結び付けることです。

**なぜ使うか:** 読む人がLLMの結論を元資料まで戻って確認できるようにするためです。paper側はpage + excerpt、repository側はpath + artifact type + excerptを保持します。

**見るfile:** `src/paper2repro/models.py`、`src/paper2repro/mapping/prompts.py`

## 5. deterministic validation

**何か:** LLMを使わず、指定page/pathが存在しexcerptがその本文に含まれるかを文字列処理で確認することです。

**なぜ使うか:** LLMは存在しない引用や誤ったpageを返す可能性があります。Unicode、不可視文字、改行hyphen、空白だけを保守的に正規化し、数字や句読点の違いは許容しません。これはsemantic supportの判定ではなくanchorの確認です。

**見るfile:** `src/paper2repro/text.py`、`src/paper2repro/claims/evidence.py`、`src/paper2repro/repo/evidence.py`

## 6. repository inventory

**何か:** repositoryを再帰的に走査し、各fileをreadme/environment/config/script/otherへ分類する処理です。

**なぜ使うか:** 後段がどのartifactを発見したか把握し、text loaderへ渡す入口にするためです。分類は意図的に単純です。

**見るfile:** `src/paper2repro/repo/inventory.py`

## 7. RepoArtifactとRepoDocument

**何か:** `RepoArtifact`はpathと種類だけ、`RepoDocument`はretrieval用の本文contentも持ちます。

**なぜ使うか:** inventoryとfile読み込みの責務を分けるためです。loaderは対象拡張子、除外directory、UTF-8 decode、256 KB上限を確認し、読めないfileだけをskipします。

**見るfile:** `src/paper2repro/models.py`、`src/paper2repro/repo/loader.py`

## 8. keyword retrieval

**何か:** claimのdataset、metric、reported valueが`document.path + document.content`に何個含まれるかを数えるlexical baselineです。

**なぜ使うか:** 小規模v0.1で挙動を説明しやすくし、将来のBM25/embeddingと比較する基準を作るためです。score 0は除外し、上位`top_k`だけをLLMへ渡します。

**見るfile:** `src/paper2repro/retrieval/keyword.py`

## 9. RAGとの関係

**何か:** retrievalで関連文書を絞り、その文書をLLMのcontextとして渡す構成は小さなRAGです。

**なぜ使うか:** repository全体をpromptへ入れず、claimごとに候補を限定するためです。現在は生成回答よりもevidence選択と監査分類が目的です。

**見るfile:** `src/paper2repro/retrieval/keyword.py`、`src/paper2repro/mapping/assessor.py`

## 10. claim → repo mapping

**何か:** 1つのclaimについて、retrieved document内に再現に関連する情報があるかを`SUPPORTED`、`PARTIALLY_SUPPORTED`、`UNSUPPORTED`で表します。

**なぜ使うか:** repository全体の印象ではなくclaim単位で根拠を確認するためです。positive statusでも有効なexcerptがなければdeterministic codeが`UNSUPPORTED`へ下げます。`SUPPORTED`は再現成功を意味しません。

**見るfile:** `src/paper2repro/mapping/prompts.py`、`src/paper2repro/mapping/assessor.py`

## 11. reproducibility audit

**何か:** dataset、config、checkpoint、command、environment、seed、evaluationの7項目をclaimごとに点検します。

**なぜ使うか:** 「関連fileがある」だけでなく、再現に必要な情報の種類ごとに不足を見えるようにするためです。`NOT_FOUND`は調査範囲内で見つからなかったという意味です。`PRESENT`に有効なevidenceがなければ降格します。

**見るfile:** `src/paper2repro/models.py`、`src/paper2repro/mapping/assessor.py`

## 12. FastAPI

**何か:** Python関数をHTTP endpointとして呼べるようにするframeworkです。

**なぜ使うか:** v0.1では`/health`と、serverから見えるlocal PDF/repositoryまたはGitHub URLを受け取る同期`/analysis`を提供します。upload、queue、DBはまだありません。

**見るfile:** `src/paper2repro/api.py`、`tests/test_api.py`

## 13. pytest

**何か:** 小さな関数の期待動作とpipelineの接続を自動確認するtest runnerです。

**なぜ使うか:** 数値hallucination、誤ったpath、decode error、空retrievalなど重要なfailureを固定するためです。Geminiはmockし、CIで課金や外部API変動を発生させません。

**見るfile:** `tests/test_evidence.py`、`tests/test_repo_evidence.py`、`tests/test_repository_assessor.py`、`tests/test_pipeline.py`

## 14. Docker

**何か:** 実行環境とdependencyをimageとして固定する仕組みです。

**なぜ使うか:** Python 3.11、uv、project dependencyをまとめ、同じFastAPI起動方法を再現しやすくするためです。API keyやPDFはimageへcopyしません。

**見るfile:** `Dockerfile`、`.dockerignore`

## 15. CI

**何か:** pushやpull requestごとにGitHub上で自動検証するworkflowです。

**なぜ使うか:** testとDocker buildが新しい環境でも通ることを確認するためです。実Gemini APIは呼びません。

**見るfile:** `.github/workflows/ci.yml`

## 読む順番

1. `src/paper2repro/pipeline.py`
2. `src/paper2repro/models.py`
3. `src/paper2repro/claims/`と`src/paper2repro/text.py`
4. `src/paper2repro/repo/`と`src/paper2repro/retrieval/keyword.py`
5. `src/paper2repro/mapping/`と`src/paper2repro/report.py`

最後に`tests/test_pipeline.py`を読むと、外部APIなしで全体がどう接続されるか確認できます。
