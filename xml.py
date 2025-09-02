import os
from flask import Flask, request, render_template_string
import zipfile
import lxml.etree as ET
import shutil

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
EXTRACTED_FOLDER = 'extracted_resources'
ALLOWED_EXTENSIONS = {'apk'}

# フォルダが存在しない場合は作成
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(EXTRACTED_FOLDER):
    os.makedirs(EXTRACTED_FOLDER)

# ファイルの拡張子をチェック
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# XMLをHTMLに変換する関数
def convert_xml_to_html(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        html_body = ""
        # この部分に、XMLの各要素をHTMLに変換するロジックを実装
        # 簡易的な例として、TextViewとButtonを変換
        for elem in root.findall('.//{http://schemas.android.com/apk/res/android}TextView'):
            text = elem.attrib.get('{http://schemas.android.com/apk/res/android}text', '')
            html_body += f'<p style="color: blue;">{text}</p>'
        for elem in root.findall('.//{http://schemas.android.com/apk/res/android}Button'):
            text = elem.attrib.get('{http://schemas.android.com/apk/res/android}text', '')
            html_body += f'<button style="background-color: green; color: white;">{text}</button>'
        return html_body
    except Exception as e:
        return f'<p style="color: red;">XML変換エラー: {e}</p>'

# ファイルアップロードフォームを表示するルート
@app.route('/')
def upload_form():
    return render_template_string("""
    <!doctype html>
    <html>
    <head><title>APK Res Converter</title></head>
    <body>
    <h1>APKファイルアップロード</h1>
    <p>APKファイルをアップロードすると、resフォルダ内のXMLがHTMLに変換されます。</p>
    <form method="post" action="/upload" enctype="multipart/form-data">
      <input type="file" name="file">
      <input type="submit" value="Upload">
    </form>
    </body>
    </html>
    """)

# ファイルをアップロードし、処理を実行するルート
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'ファイルがありません'
    file = request.files['file']
    if file.filename == '':
        return 'ファイルが選択されていません'
    if file and allowed_file(file.filename):
        # 既存の抽出フォルダをクリーンアップ
        if os.path.exists(EXTRACTED_FOLDER):
            shutil.rmtree(EXTRACTED_FOLDER)
        os.makedirs(EXTRACTED_FOLDER)

        # ファイルを一時的に保存
        apk_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(apk_path)

        # APKを解凍し、resフォルダを抽出
        with zipfile.ZipFile(apk_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.startswith('res/') and not member.endswith('/'):
                    # 抽出パスを作成
                    dest_path = os.path.join(EXTRACTED_FOLDER, os.path.basename(member))
                    # ファイルを抽出
                    with open(dest_path, 'wb') as outfile:
                        outfile.write(zip_ref.read(member))

        # 抽出したファイルを処理
        html_output = ""
        for filename in os.listdir(EXTRACTED_FOLDER):
            if filename.endswith('.xml'):
                xml_path = os.path.join(EXTRACTED_FOLDER, filename)
                html_output += f'<h2>{filename}</h2>'
                html_output += convert_xml_to_html(xml_path)
                html_output += '<hr>'
            # 画像やJSONも同様に処理可能
            # elif filename.endswith(('.png', '.jpg', '.jpeg')):
            #    html_output += f'<h2>{filename}</h2><img src="/static/{filename}">'

        # 変換結果を表示
        return render_template_string(f"""
        <!doctype html>
        <html>
        <head><title>Conversion Result</title></head>
        <body>
        <h1>変換結果</h1>
        {html_output}
        <a href="/">別のファイルをアップロード</a>
        </body>
        </html>
        """)
    return '不正なファイル形式です'

if __name__ == '__main__':
    app.run(debug=True)

