import os
import nbtlib
import json
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
# ユーザーがアップロードするファイルの容量を制限（例: 16MB）
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
# アップロードフォルダを指定
app.config['UPLOAD_FOLDER'] = 'uploads/'

# アップロードフォルダが存在しない場合は作成
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    """
    許可されたファイル形式か確認
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ['dat']

@app.route('/')
def index():
    """
    ファイルアップロード用のフォームを表示する
    """
    return """
    <!doctype html>
    <title>Minecraft Dat File Converter</title>
    <h1>dat ファイルをアップロード</h1>
    <form method=post enctype=multipart/form-data action="/upload">
      <input type=file name=file accept=".dat">
      <input type=submit value=Upload>
    </form>
    """

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    アップロードされたファイルを処理し、編集画面にリダイレクトする
    """
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return "許可されていないファイル形式です。datファイルをアップロードしてください。", 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    return redirect(url_for('edit_file', filename=filename))

@app.route('/edit/<filename>', methods=['GET'])
def edit_file(filename):
    """
    datファイルの内容をJSONとして読み込み、編集フォームを表示する
    """
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    if not os.path.exists(filepath):
        return "ファイルが見つかりません。", 404
    
    try:
        nbt_file = nbtlib.load(filepath)
        nbt_data_json = json.dumps(nbt_file.json_obj(), indent=4)
        
        return render_template('editor.html', nbt_data_json=nbt_data_json, filename=filename)
    except Exception as e:
        return f"エラーが発生しました: {e}"
        
@app.route('/convert', methods=['POST'])
def convert_file():
    """
    編集されたJSONデータを受け取り、NBTファイルに変換してダウンロードさせる
    """
    try:
        # JSONデータを取得
        edited_json = request.form['edited_data']
        filename = request.form['filename']

        # JSON文字列をPythonの辞書に変換
        edited_data = json.loads(edited_json)

        # 辞書をNBTオブジェクトに変換
        # nbtlibの内部的なデータ型（Int, Stringなど）を自動で推測
        nbt_data = nbtlib.File.from_json_obj(edited_data)
        
        # 変換後のファイルのパス
        output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], "converted_" + secure_filename(filename))
        
        # NBTファイルを保存
        nbt_data.save(output_filepath)
        
        # ファイルをダウンロードとして送信
        return send_file(output_filepath, as_attachment=True)

    except Exception as e:
        return f"変換中にエラーが発生しました: {e}"
    finally:
        # 処理が終わったら一時ファイルを削除
        uploaded_filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if os.path.exists(uploaded_filepath):
            os.remove(uploaded_filepath)
        if 'output_filepath' in locals() and os.path.exists(output_filepath):
            os.remove(output_filepath)

if __name__ == '__main__':
    app.run(debug=True)
