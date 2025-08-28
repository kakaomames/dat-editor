import os
import nbtlib
import json
import uuid
import base64
from flask import Flask, render_template, request, redirect, url_for, send_file
from werkzeug.utils import secure_filename
from github import Github, GithubException
import tempfile
import zipfile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 環境変数からGitHub APIキーとリポジトリ情報を取得
GITHUB_API_KEY = os.environ.get('GITHUB_API_KEY')
GITHUB_REPO_OWNER = os.environ.get('GITHUB_REPO_OWNER')
GITHUB_REPO_NAME = os.environ.get('GITHUB_REPO_NAME')

def get_github_repo():
    """GitHubリポジトリのインスタンスを取得する"""
    try:
        g = Github(GITHUB_API_KEY)
        return g.get_user(GITHUB_REPO_OWNER).get_repo(GITHUB_REPO_NAME)
    except Exception as e:
        return None

def save_to_github(filepath, github_path, commit_message):
    """ファイルをGitHubに保存する"""
    repo = get_github_repo()
    if not repo:
        return False, "GitHubリポジトリにアクセスできません。"
    
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
            encoded_content = base64.b64encode(content).decode('utf-8')
        
        # 既存ファイルがあるかチェック
        try:
            old_file = repo.get_contents(github_path, ref="main")
            repo.update_file(
                path=github_path,
                message=commit_message,
                content=base64.b64decode(encoded_content),
                sha=old_file.sha,
                branch="main"
            )
        except GithubException:
            # ファイルが存在しない場合は新規作成
            repo.create_file(
                path=github_path,
                message=commit_message,
                content=base64.b64decode(encoded_content),
                branch="main"
            )
        return True, "成功"
    except GithubException as e:
        return False, f"GitHubエラー: {e.data['message']}"
    except Exception as e:
        return False, f"予期せぬエラー: {e}"

def get_from_github(github_path):
    """GitHubからファイルをダウンロードしてローカルパスを返す"""
    repo = get_github_repo()
    if not repo:
        return None, "GitHubリポジトリにアクセスできません。"
    
    try:
        file_content = repo.get_contents(github_path, ref="main")
        
        # 一時ファイルを作成
        temp_dir = tempfile.gettempdir()
        temp_filepath = os.path.join(temp_dir, os.path.basename(github_path))
        
        with open(temp_filepath, 'wb') as f:
            f.write(base64.b64decode(file_content.content))
            
        return temp_filepath, "成功"
    except GithubException as e:
        return None, f"GitHubエラー: {e.data['message']}"
    except Exception as e:
        return None, f"予期せぬエラー: {e}"

@app.route('/')
def index():
    return """
    <!doctype html>
    <title>Minecraft Dat File Converter</title>
    <h1>Minecraftファイルをアップロード</h1>
    <form method=post enctype=multipart/form-data action="/upload">
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
    
    # 【変更点1】 アップロードされたファイルを一時的に /tmp に保存
    temp_filepath = os.path.join('/tmp', original_filename)
    file.save(temp_filepath)
    
    # バージョン判別ロジック
    version = "unknown"
    if original_filename.endswith('.dat'):
        version = 'Java'
    elif original_filename.endswith(('.zip', '.mcworld')):
        try:
            with zipfile.ZipFile(temp_filepath, 'r') as z:
                file_list = z.namelist()
                if any('db/' in f for f in file_list):
                    version = 'Bedrock'
                else:
                    version = 'Java'
        except zipfile.BadZipFile:
            os.remove(temp_filepath)
            return "アップロードされたZIPファイルが破損しています。", 400
            
    github_path = f"original/{version}/{unique_id}-{original_filename}"

    # 【変更点2】 GitHubにファイルを保存
    success, message = save_to_github(temp_filepath, github_path, f"Uploaded {original_filename}")
    os.remove(temp_filepath) # 一時ファイルを削除

    if not success:
        return f"GitHubへの保存に失敗しました: {message}", 500

    # 【変更点3】 edit_fileにUUIDとバージョンを渡す
    return redirect(url_for('edit_file', unique_id=unique_id, version=version))

# ... app.pyの既存のコードは省略 ...

@app.route('/edit/<unique_id>/<version>', methods=['GET'])
def edit_file(unique_id, version):
    """
    GitHubからファイルを読み込み、JSONとして編集フォームを表示する
    """
    if not all([GITHUB_API_KEY, GITHUB_REPO_OWNER, GITHUB_REPO_NAME]):
        return "GitHubの環境変数が設定されていません。", 500
    
    # GitHubからオリジナルファイルをダウンロード
    github_path = f"original/{version}/{unique_id}-level.dat"
    local_filepath, message = get_from_github(github_path)

    if not local_filepath:
        return f"ファイルが見つかりません: {message}", 404
        
    try:
        # 【修正点1】 nbtlib.load()が直接Compoundを返すように変更されたため、.rootを削除
        nbt_data = nbtlib.load(local_filepath)
        
        # 【修正点2】 json_obj()を直接呼び出す
        nbt_data_json = json.dumps(nbt_data.json_obj(), indent=4)
        
        return render_template('editor.html', nbt_data_json=nbt_data_json, unique_id=unique_id, version=version)
    except Exception as e:
        return f"エラーが発生しました: {e}"
    finally:
        # 処理が終わったら一時ファイルを削除
        if os.path.exists(local_filepath):
            os.remove(local_filepath)

# ... app.pyの残りのコードは省略 ...
            
@app.route('/convert', methods=['POST'])
def convert_file():
    """
    編集されたJSONデータを受け取り、NBTファイルに変換してGitHubに保存する
    """
    if not all([GITHUB_API_KEY, GITHUB_REPO_OWNER, GITHUB_REPO_NAME]):
        return "GitHubの環境変数が設定されていません。", 500
        
    try:
        edited_json = request.form['edited_data']
        unique_id = request.form['unique_id']
        version = request.form['version']

        # 【変更点6】 JSON文字列をNBTオブジェクトに変換
        edited_data = json.loads(edited_json)
        nbt_data = nbtlib.File.from_json_obj(edited_data)
        
        # 【変更点7】 変換後のファイルを一時的に /tmp に保存
        output_filepath = os.path.join('/tmp', f"{unique_id}-edited.dat")
        nbt_data.save(output_filepath)

        # 【変更点8】 GitHubへの保存パスを決定
        github_path = f"processed/{version}/{unique_id}-level.dat"
        
        # 【変更点9】 GitHubにファイルをアップロード
        success, message = save_to_github(output_filepath, github_path, f"Edited and saved {unique_id}")
        
        # 【変更点10】 一時ファイルを削除
        os.remove(output_filepath)
        
        if not success:
            return f"GitHubへの保存に失敗しました: {message}", 500

        return "変更が適用され、GitHubに保存されました！<br><a href=\"/\">ホームに戻る</a>"
        
    except Exception as e:
        return f"変換中にエラーが発生しました: {e}"

if __name__ == '__main__':
    app.run(debug=True)
