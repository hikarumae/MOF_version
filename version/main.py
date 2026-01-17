# main.py
import version_manager
import version_manager_ai_azure
import file_organizer
import time

def run_pipeline():
    print("=== [1/3] OCR処理を開始します ===")
    version_manager.process_pdfs()
    
    # 少し間を置いて確実にファイルが作成されるのを待ちます
    time.sleep(2)
    
    print("\n=== [2/3] Azure OpenAIによる最新版判定を開始します ===")
    version_manager_ai_azure.run_ai_judgment()
    
    time.sleep(2)
    
    print("\n=== [3/3] ファイルの仕分け（最新・アーカイブ）を開始します ===")
    file_organizer.organize_files()
    
    print("\n🎉 すべての工程が正常に完了しました！")

if __name__ == "__main__":
    run_pipeline()