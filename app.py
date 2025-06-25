from flask import Flask, render_template, request, send_file, abort
import pandas as pd
import os
from io import BytesIO

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

latest_result_df = None  # to store result for download

@app.route('/', methods=['GET', 'POST'])
def upload_files():
    global latest_result_df
    summary = None

    if request.method == 'POST':
        master_file = request.files['master_sheet']
        lsp_file = request.files['lsp_sheet']

        master_path = os.path.join(app.config['UPLOAD_FOLDER'], 'master.xlsx')
        lsp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'lsp.xlsx')

        master_file.save(master_path)
        lsp_file.save(lsp_path)

        result, summary = process_files(master_path, lsp_path)
        latest_result_df = result  # store result globally

        return render_template('index.html',
                               tables=[result.to_html(classes='table', index=False)],
                               titles=[''],
                               summary=summary)

    return render_template('index.html', summary=None)

@app.route('/download')
def download_report():
    global latest_result_df
    if latest_result_df is not None:
        try:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                latest_result_df.to_excel(writer, index=False, sheet_name='Reconciliation')
            output.seek(0)
            return send_file(
                output,
                download_name='Reconciliation_Report.xlsx',
                as_attachment=True,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        except Exception as e:
            print("Download Error:", e)
            return abort(500)
    return abort(404)

def process_files(master_path, lsp_path):
    master_df = pd.read_excel(master_path)
    lsp_df = pd.read_excel(lsp_path)

    merged_df = lsp_df.merge(master_df, on='Order ID', suffixes=('_LSP', '_Master'), how='left')

    def match_status(row):
        if pd.isna(row['Amount_Master']):
            return '⚠️ Not Matched (Order ID Missing)'
        elif row['LSP Name_LSP'] != row['LSP Name_Master']:
            return '⚠️ Not Matched (LSP Name Mismatch)'
        elif row['Amount_LSP'] == row['Amount_Master']:
            return '✅ Matched'
        elif row['Amount_LSP'] > row['Amount_Master']:
            return '⬆️ Amount Greater than Master Sheet'
        elif row['Amount_LSP'] < row['Amount_Master']:
            return '⬇️ Amount Lower than Master Sheet'
        else:
            return '⚠️ Not Matched'

    merged_df['Status'] = merged_df.apply(match_status, axis=1)

    final_df = merged_df[['Order ID', 'LSP Name_Master', 'LSP Name_LSP', 'Amount_Master', 'Amount_LSP', 'Status']]
    final_df.columns = ['Order ID', 'LSP Name (Master Sheet)', 'LSP Name (LSP Sheet)', 'Amount (Master)', 'Amount (LSP)', 'Status']

    # summary counts
    summary_counts = final_df['Status'].value_counts().to_dict()

    return final_df, summary_counts

# Important for Render to detect open port
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10001)
