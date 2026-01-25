📄 AI文書管理システム：自動仕分け＆版管理ボット

このプロジェクトは、Azure Blob Storage にアップロードされた PDF 文書を AI（GPT-4o）が解析し、「会社名」「文書種別」「最新日付」に基づいて自動的に整理・データベース化するシステムです。


🌟 主な機能

・自動検知・OCR解析:

 mof2-blob-new コンテナへのアップロードをトリガーに、冒頭と末尾のテキスト、および1ページ目の画像を解析します。

 
・インテリジェント仕分け:

 AI が文書種別を 4 つのカテゴリ（契約書、就業規則、職務権限基準、その他）に分類します。


・自社規定の名寄せ:

 就業規則や職務権限基準は、会社名を一律で 「自社」 として集約します。


・自動版管理（バージョンコントロール）:

 同じ文書の新しい日付が来たら、既存ファイルを mof2-blob-old（過去分）へ退避。

 mof2-blob-all には常に 「最新版」 のみが残るよう管理されます。


・常時稼働 (Health Check):

 Flask を使用して Azure App Service からの生存確認に応答し、スリープを防ぎます。


🏗 システム構成図


🚀 セットアップ（共同編集者向け）


1. 必須となる環境変数

Azure App Service の「環境変数（構成）」に以下の値を設定してください。

| 変数名 | 内容 | 参照ファイル |

| AZURE_STORAGE_CONNECTION_STRING | ストレージアカウントの接続文字列 | main_app.py, blob_organizer.py |

| AZURE_OPENAI_ENDPOINT | Azure OpenAI のエンドポイント URL | ai_judge.py | 

| AZURE_OPENAI_API_KEY | Azure OpenAI の API キー | ai_judge.py |


3. ファイル構成

・main_app.py:

 メインプログラム。Flask サーバーと監視ループをスレッド分離して実行。


・ai_judge.py:

 GPT-4o へのプロンプト指示。仕分けルールの中枢。


・pdf_analyzer.py:

 PDF からのテキスト・画像抽出処理。


・blob_organizer.py:

 ストレージ間のファイル移動と DB（Table Storage）更新。


🛠 カスタマイズ方法

・文書の分類ルールを変えたい場合

ai_judge.py 内の 【厳格ルール】 と 【出力要件】 の JSON 構造を修正してください。

例:「見積書」をカテゴリに追加したい場合は、プロンプトの選択肢に「見積書」を追記します。


・監視の間隔を変えたい場合

main_app.py 内の time.sleep(10) の数値を調整してください。


⚠️ 運用上の注意点

Always On: App Service の設定で Always On を必ず オン にしてください。

スタートアップコマンド: python3 main_app.py を設定する必要があります。

DBのリセット: 名寄せルールを大幅に変えた後は、LatestDocumentDB テーブルを一度クリアすることをお勧めします。
