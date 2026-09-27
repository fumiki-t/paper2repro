# SoccerMaster retrieval failure analysis

## Scope and evidence

This is an offline inspection of the saved one-run report at `outputs/soccermaster/report.json` and the local public SoccerMaster clone. No Gemini request was made for this analysis. Retrieved files below are the run's candidates, not gold relevance labels. Candidate files from repository text search also require human review.

The baseline `score_document()` checks only `claim.dataset`, `claim.metric`, and `claim.reported_value` as case-insensitive literal substrings of `path + content`. Each matching field adds one point. `claim.statement` is not searched, and a field gets no credit when its full phrase does not occur literally. `retrieve_documents()` drops score-zero files and returns up to `top_k` results by score.

## Run-level observations

- The run returned documents for 7 of 9 claims; Claims 4 and 8 had an empty result.
- The report says 4/9 mappings were `PARTIALLY_SUPPORTED` and 5/9 `UNSUPPORTED`. This is model output after evidence grounding, not a retrieval accuracy measurement.
- Claims 2 and 9 share the same five top files, despite asking about different athlete-detection results. These include calibration, game-state, TrackLab, PoseTrack21, and SAM 2 material. This is a visible false-positive pattern for the user's intended tasks, though relevance still needs human labels.
- The seven audit checks are evaluated only on retrieved documents. A `NOT_FOUND` result after empty retrieval is not evidence that the information is absent from the repository.
- Offline review of the saved report found that each of its 9 `AMBIGUOUS` audit items has at least one anchored excerpt. The stricter policy added now would not change those saved statuses. It downgrades an `AMBIGUOUS` item to `NOT_FOUND` only when none of its excerpts anchors to any retrieved document; the report retains a note when documents were retrieved but the cited evidence failed validation.

## Claims 2, 4, 8, and 9

| Claim | Baseline output | Offline diagnosis | Human-review candidates |
|---|---|---|---|
| 2: athlete detection, AP@50 91.5 / mAP 49.5 | Five files: `codes/SoccerMaster/sn_calibration/README.md`, `codes/sn-gamestate/README.md`, `codes/tracklab/README.md`, `codes/tracklab/plugins/eval/PoseTrack21/README.md`, `codes/sam2/sam2/configs/sam2.1/sam2.1_hiera_b+.yaml`; mapping `UNSUPPORTED` | `dataset` is empty, so only `mAP` and `49.5` are searched. `mAP` occurs in 166 loaded files. The literal `49.5` also matches inside `349.51` in an unrelated PoseTrack21 coordinate test at `codes/tracklab/plugins/eval/PoseTrack21/posetrack21_mot/posetrack21_mot/motmetrics/tests/test_io.py`. A separate repository-wide search found `91.5` as a speed value (FPS) in `codes/sam2/README.md`, not as the SoccerMaster athlete-detection score. The baseline ignores the task phrase and AP@50. | `codes/SoccerMaster/data/soccernet_gsr_detection.py`, `codes/SoccerMaster/configs/default.yaml`, `codes/SoccerMaster/train.py`; these are detection/config/training candidates, not verified support for the reported result. |
| 4: vision-language retrieval, top-1 accuracy 39.0% | `retrieved_documents = []`; mapping `UNSUPPORTED` | The claim has no dataset field. The exact phrase `top-1 accuracy` has zero matches, while the repository spells its metric key `top_1_accuracy` in one loaded file. The exact value `39.0%` also has zero matches. The statement terms `vision-language` and `retrieval` are ignored. | `codes/SoccerMaster/models/video_caption.py` contains `top_1_accuracy` and retrieval metric bookkeeping; `codes/SoccerMaster/configs/default.yaml` has the video-caption task and batch settings. These are candidates for review, not gold evidence for 39.0%. |
| 8: SN-Caption-test-align commentary generation, CIDEr 38.6 | `retrieved_documents = []`; mapping `UNSUPPORTED` | The full `dataset` phrase `SN-Caption-test-align benchmark` has zero matches, while the base phrase `SN-Caption-test-align` appears in one loaded file. `CIDEr` and `38.6` each have zero matches. Statement terms such as `commentary generation` are ignored. | `codes/SoccerMaster/data/video_caption.py`, `codes/SoccerMaster/models/video_caption.py`, `codes/SoccerMaster/models/caption_classification.py`, `codes/SoccerMaster/configs/default.yaml`, `codes/SoccerMaster/configs/pretrain.yaml`, `codes/SoccerMaster/train.py`. The data loader references `SN-Caption-test-align`; none of these is confirmed as evidence for the reported CIDEr result. |
| 9: SoccerFactory spatial data; athlete-detection mAP 30.2 → 37.5 | The same five unrelated candidates as Claim 2; mapping `UNSUPPORTED` | `dataset` is empty. `mAP` occurs in 166 loaded files, while `37.5` has zero matches. The statement terms `SoccerFactory`, `spatial data`, `compact training`, and `athlete detection` are ignored, so broad mAP matches fill the top-k. | `codes/SoccerMaster/configs/pretrain.yaml`, `codes/SoccerMaster/configs/default.yaml`, `codes/SoccerMaster/data/soccernet_gsr_detection.py`, `codes/SoccerMaster/train.py`. These are broad data/config/training candidates; simple text search did not establish the claimed data augmentation or metric values. |

The six files explicitly checked by name in the task are present in the local clone: `models/video_caption.py`, `data/video_caption.py`, `models/caption_classification.py`, `configs/default.yaml`, `configs/pretrain.yaml`, and `train.py`. Presence alone does not show that a file supports a particular number.

## Where the baseline appears useful

Claims 1, 3, 5, and 6 returned at least some plausible domain-matching files and received `PARTIALLY_SUPPORTED` in this run. Examples include SoccerNet-GSR docs/configs for Claim 1 and camera-calibration code for Claims 5 and 6. Treat these as candidate successes only: there is no human gold set yet, and a non-empty result or partial mapping status does not establish retrieval correctness.

## Next steps

For a small next experiment, include selected task/action terms from `claim.statement` in a weighted lexical query, preserve dataset/metric/value signals, and optionally score path matches slightly above body-text matches. Keep this deterministic, record per-term contributions, and compare the new ranking with this unchanged baseline on human-reviewed examples. The implementation exercise is intentionally left in `docs/NEXT_RETRIEVAL_TASK_JA.md`.

Do not interpret empty retrieval as repository-wide absence. Candidate paths should be reviewed against the paper and repository before being used as evaluation labels.
