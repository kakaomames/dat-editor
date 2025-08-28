import os
import nbtlib
import json
import uuid
import base64
from flask import Flask, render_template, request, redirect, url_for, send_file
from werkzeug.utils import secure_filename
from github import Github, GithubException

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 【変更点1】 環境変数からGitHub APIキーとリポジトリ情報を取得
GITHUB_API_KEY = os.environ.get('GITHUB_API_KEY')
GITHUB_REPO_OWNER = os.environ.get('GITHUB_REPO_OWNER')
GITHUB_REPO_NAME = os.environ.get('GITHUB_REPO_NAME')

def allowed_file(filename):
    """
    許可されたファイル形式か確認
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ['dat', 'zip', 'mcworld']

def save_to_github(filepath, github_path, commit_message):
    """
    ファイルをGitHubに保存する
    """
    try:
        g = Github(GITHUB_API_KEY)
        repo = g.get_user(GITHUB_REPO_OWNER).get_repo(GITHUB_REPO_NAME)
        
        with open(filepath, 'rb') as f:
            content = f.read()
            encoded_content = base64.b64encode(content).decode('utf-8')

        repo.create_file(
            path=github_path,
            message=commit_message,
            content=base64.b64decode(encoded_content),
            branch="main" # または任意のブランチ名
        )
        return True, "成功"
    except GithubException as e:
        return False, f"GitHubエラー: {e.data['message']}"
    except Exception as e:
        return False, f"予期せぬエラー: {e}"

@app.route('/')
def index():
    return """
    <!doctype html>
    <title>Minecraft Dat File Converter</title>
    <h1>Minecraftファイルをアップロード</h1>
    <form method=post enctype=multipart/form-data action="./upload">
      <input type=file name=file accept=".dat,.zip,.mcworld">
      <input type=submit value=Upload>
    </form>
    """

@app.route('/upload', methods=['POST'])
def upload_file():
    if not all([GITHUB_API_KEY, GITHUB_REPO_OWNER, GITHUB_REPO_NAME]):
        return "GitHubの環境変数が設定されていません。", 500

    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return "許可されていないファイル形式です。", 400

    original_filename = secure_filename(file.filename)
    unique_id = uuid.uuid4()
    
    # 【変更点2】 ファイルを一時的に /tmp に保存
    temp_filepath = os.path.join('/tmp', original_filename)
    file.save(temp_filepath)
    
    # 【変更点3】 ファイルのバージョンを判別
    file_extension = original_filename.rsplit('.', 1)[1].lower()
    if file_extension in ['zip', 'mcworld']:
        # zipまたはmcworldの判別ロジックをここに実装
        # 例: zipfileで解凍して中身をチェック
        # version = 'Java' if 'level.dat' in zipfile else 'Bedrock'
        version = 'Java' # 仮の判別
    else:
        version = 'Java' # datファイルはJava版と仮定
        
    github_path = f"original/{version}/{unique_id}-{original_filename}"

    # 【変更点4】 GitHubにファイルを保存
    success, message = save_to_github(temp_filepath, github_path, f"Uploaded {original_filename}")
    os.remove(temp_filepath) # 一時ファイルを削除

    if not success:
        return f"GitHubへの保存に失敗しました: {message}", 500

    # 【変更点5】 ここから編集画面へ
    return redirect(url_for('edit_file', file_path=github_path))

# ... edit_file と convert_file 関数はGitHubからのダウンロードとアップロードに修正が必要 ...
# ... send_file は直接GitHubからファイルを送るように修正が必要 ...

if __name__ == '__main__':
    app.run(debug=True)
