## 📘 プロジェクト概要（短く・読みやすく）
**MOF_version** は、Azure Blob にアップロードされた PDF を自動で解析・仕分けし、最新版管理（アーカイブ更新）や検索用インデックス作成を行う小さなドキュメント管理ツールです。  
AI（OpenAI）を使い文書種別や対象組織名、日付を抽出して自動処理します。

---

## 🔧 主な機能
- PDF のテキストと1ページ目の画像を抽出（OCRの代わりに画像を解析用に利用）  
- AI（gpt-4o）で「文書タイプ」「対象組織」「日付」を判定（`ai_judge.py`）  
- 判定結果に従い最新版判定・移動・テーブル更新（Table Storage）を実施（`blob_organizer.py`）  
- RAG 用のインデックス作成・検索 API（`app/`：FastAPI）  

---

## 📁 ファイル構成
- `main_app.py` — Azure Blob を監視し、検出した PDF を処理するメイン（Flaskでヘルスチェック、監視はスレッド）  
- `pdf_analyzer.py` — PyMuPDF を用いてテキスト（先頭/末尾）と1ページ目の画像を抽出  
- `ai_judge.py` — AI に渡すプロンプト／判定ロジック（出力は指定の JSON 形式）  
- `blob_organizer.py` — Blob と Table Storage を使った保存・アーカイブ・DB更新のロジック  

-（以下はまーP作）
- `app/` — RAG（インデックス作成と検索）用の FastAPI サービス  
  - `app/main.py` — インデックス作成・検索の API エンドポイント  
  - `app/blob.py` — Blob から PDF を読み込むユーティリティ  
  - `app/embedding.py` — Embedding 取得（OpenAI）  
  - `app/search.py` — Azure Search にインデックス登録、ベクトル検索  

---

## ⚙️ 必要な環境変数（主要なもの）
```bash
AZURE_STORAGE_CONNECTION_STRING
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_API_KEY
AZURE_OPENAI_API_VERSION
AZURE_OPENAI_EMBEDDING_DEPLOYMENT
AZURE_SEARCH_ENDPOINT
AZURE_SEARCH_INDEX_NAME
AZURE_SEARCH_API_KEY
PORT  # (例: 8000)
```

---

## 🚀 ローカルでのセットアップ
1. Python を用意（推奨: 3.10+）  
2. リポジトリをクローン／配置  
3. 仮想環境を作る（推奨）
   - Windows PowerShell の例:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     pip install -r requirements.txt
     ```
4. 必要な環境変数を `.env` に記載（または PowerShell で設定）  
5. 監視＋ヘルスサーバーを起動（簡単な方法）
   ```powershell
   python main_app.py
   ```
6. RAG API を使うとき（インデックス作成・検索用）
   ```bash
   uvicorn app.main:app --reload --port 8001
   ```

---

## 🧪 使い方
- PDF を `mof2-blob-new` コンテナにアップロードすると、`main_app.py` の監視で検出→処理されます。  
- RAG API
  - インデックス作成: POST `/index` に `{ "container": "your-container", "prefix": "optional/prefix" }`
  - 検索: POST `/search` に `{ "question": "質問文", "k": 5 }`

---

## 💡 開発メモ
- 文書判定ルールは `ai_judge.py` のプロンプトで編集可能（カテゴリ追加など）  
- 監視間隔は `main_app.py` の `time.sleep(10)` を調整  
- Table/Blob の処理は `blob_organizer.py` にまとまっている（保存先コンテナ名やテーブル名を変更可能）  

---

## ⚠️ 注意点・トラブルシューティング
- 環境変数が未設定だと動作しません（ログを確認）  
- PyMuPDF や pypdf のインストールに失敗する場合、事前にビルドツールや C ライブラリが必要なことがあります  
- Azure の権限／接続文字列に注意（読み込み・書き込み許可を確認）

---

## 📌 デプロイのヒント
- Azure App Service などにデプロイする際は、環境変数を正しく登録してください  
- コード変更後は App Service を一度停止してからデプロイする運用が推奨（現状 README に記載あり）  



