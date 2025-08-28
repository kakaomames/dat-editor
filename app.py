import os
import nbtlib
import json
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 【変更点1】 アップロードフォルダを /tmp に設定
# Vercelのサーバーレス環境では /tmp のみが書き込み可能
app.config['UPLOAD_FOLDER'] = '/tmp'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ['dat']

@app.route('/')
def index():
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
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return "許可されていないファイル形式です。datファイルをアップロードしてください。", 400

    filename = secure_filename(file.filename)
    # 【変更点2】 ファイルパスを /tmp に設定
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    return redirect(url_for('edit_file', filename=filename))

@app.route('/edit/<filename>', methods=['GET'])
def edit_file(filename):
    # 【変更点3】 ファイルパスを /tmp に設定
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
    try:
        edited_json = request.form['edited_data']
        filename = request.form['filename']

        edited_data = json.loads(edited_json)
        nbt_data = nbtlib.File.from_json_obj(edited_data)
        
        # 【変更点4】 ファイルパスを /tmp に設定
        output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], "converted_" + secure_filename(filename))
        
        nbt_data.save(output_filepath)
        
        return send_file(output_filepath, as_attachment=True)

    except Exception as e:
        return f"変換中にエラーが発生しました: {e}"
    finally:
        # 【変更点5】 ファイルパスを /tmp に設定
        uploaded_filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if os.path.exists(uploaded_filepath):
            os.remove(uploaded_filepath)
        if 'output_filepath' in locals() and os.path.exists(output_filepath):
            os.remove(output_filepath)

# 【変更点6】 Vercelでは不要な os.makedirs を削除
# if not os.path.exists(app.config['UPLOAD_FOLDER']):
#     os.makedirs(app.config['UPLOAD_FOLDER'])

if __name__ == '__main__':
    app.run(debug=True)
