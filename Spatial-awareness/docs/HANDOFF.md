# Spatial Awareness - 後継者向け引き継ぎプロンプト

以下をそのまま新しいClaudeセッションに貼り付けてください。

---

## プロンプト

```
あなたは「Spatial Awareness」プロジェクトの開発を引き継ぎます。
このプロジェクトは、スマートフォンで撮影した一般的な動画/画像から、工場内の間取り・機械配置を3Dモデルとして復元するシステムです。

### リポジトリ
https://github.com/ymneco/AI/ の Spatial-awareness/ ディレクトリ

### 現在のシステム構成
- **フレーム抽出**: FFmpegで動画からフレーム抽出（uniform/keyframe/adaptive）
- **Sparse復元**: COLMAP 4.0.2 (CUDA) でSfM
- **Dense復元**: COLMAP patch_match_stereo + stereo_fusion → 色付き点群
- **メッシュ生成**: Poisson / Delaunay meshing
- **Web 3Dビューア**: Three.js + FastAPI (http://localhost:8889)
- **CLI**: `python main.py reconstruct|view|serve|info`

### 環境要件
- Python 3.11+, NVIDIA GPU (CUDA), FFmpeg, COLMAP 4.0.2
- COLMAP 4.0.2はオプション名がv3と異なる（FeatureExtraction.use_gpu, FeatureMatching.use_gpu, TwoViewGeometry.min_num_inliers等）
- COLMAPバイナリは vendor/colmap/ に配置（gitignore済み、`python scripts/install_colmap.py` でダウンロード可能）

### 完了済みの作業
1. フレーム抽出パイプライン（FFmpeg）
2. COLMAP Sparse Reconstruction（マルチモデル対応、ベストモデル自動選択）
3. Dense Reconstruction（マルチモデル統合対応）
4. Poisson / Delaunay メッシュ生成
5. Web 3Dビューア（Three.js + FastAPI、プロジェクト一覧・ファイル選択・PLY表示）
6. SIFTパラメータチューニング（壁面等の特徴が少ないシーン対応）
   - sift_max_features: 16384, peak_threshold: 0.004, edge_threshold: 16
   - これにより登録率が35%→96%に改善
7. カメラ軌跡からの部屋サイズ推定（歩行速度ベース・天井高ベース）
8. 撮影ガイド（docs/shooting_guide.md）

### 最重要の未解決課題
**メッシュの品質が「部屋に見えない」**

テスト動画（会議室を壁に沿って1周する51秒の4K動画）で試したところ:
- Sparse: 148/154フレーム登録、20,200点 → 良好
- Dense: 2,688,734点（色付き） → 良好
- **Mesh: 部屋に見えない。バラバラなポリゴンの集まりになる。**

ただし、初期テスト(test_003)でSparse 36画像/Dense 431K点から生成したPoissonメッシュ(depth=13, trim=10)は
壁面・窓・自販機のロゴまで読めるレベルで再現できていた。
つまり**密度の高い局所的な領域では良いメッシュが作れるが、部屋全体を覆うと品質が落ちる**。

### 具体的に取り組むべきこと

1. **「部屋に見えるメッシュ」の生成**
   - カメラのループ軌跡は検出済み（始点と終点の距離≈0）
   - Dense点群(2.7M点)は十分ある
   - Poissonメッシュのtrimパラメータ、Delaunayメッシャーのパラメータ調整
   - または Open3D の BallPivoting / Alpha Shape 等、別のメッシュ化手法を試す
   - テクスチャマッピング（MVS-Texturing等）で映像の色をメッシュに貼り付ける

2. **品質チェックのループ**
   - ユーザーの指示: 「フェーズ完了ごとにスクリーンショットで自律チェックし、"部屋に見えるか"を重視」
   - Webビューアでメッシュを表示→スクリーンショット→判定→調整のループを回す

3. **ユーザーの作業スタイル**
   - フェーズ進行の確認は不要。100%問題ない状態になったら自律で次へ進む
   - 日本語でコミュニケーション
   - GPUあり（NVIDIA RTX 4060 Laptop, 8GB VRAM）

### テストデータ
- video/20260326_100634.mp4 (338MB, 4K HEVC, 51秒) — gitignore済み、ローカルに存在
- data/projects/test_003/ — 初期テスト結果（最も視覚品質が良いmesh.plyがここにある）
- data/projects/test_005/ — 改善SIFT設定でのテスト結果（148画像登録、2.7M点Dense）

### 主要ファイル
- spatial/sfm/colmap_runner.py — COLMAP操作（Sparse/Dense/Mesh全て）
- spatial/pipeline/runner.py — パイプライン統括
- spatial/viewer/server.py — Web 3Dビューア
- spatial/cli.py — CLIコマンド
- config.py — 設定

### Webビューア起動方法
python main.py serve --port 8889
→ http://localhost:8889 でアクセス
```
