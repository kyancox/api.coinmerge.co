from flask import Flask, request, jsonify, abort, send_file, render_template, url_for, redirect, current_app
import pandas as pd
from io import BytesIO
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# Import for Coinbase
from cb import coinbasePortfolio

# Import for Gemini
from gemini import geminiPortfolio

# Import for Ledger
from ledger import ledgerPortfolio

from portfolioClass import Portfolio, MasterPortfolio


app = Flask(__name__)

'''
Methods:

POST: API Key
w/ API Key and API Secret

POST: Ledger CSV

GET: Json with Portfolio data 

GET: Excel File with Data
https://chat.openai.com/c/9daee5bd-d674-40a5-a31d-dd6929e2ea5f
- send_file() using Flask

GET: total balance
'''

api_keys = {}

# Global variables for exchange Portfolio classes
coinbase = None
gemini = None
ledger = None
master = None
accounts = []

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' 
db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(50))
    data = db.Column(db.LargeBinary)

class ApiKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(50), nullable=False)  # 'Coinbase', 'Gemini', etc.
    api_key = db.Column(db.String(200), nullable=False)
    api_secret = db.Column(db.String(200), nullable=False)

@app.route('/api/coinbase/keys', methods=['POST'])
def set_coinbase_keys():
    data = request.get_json()
    print(data)

    # Check if data is None or if 'api_key' and 'api_secret' are present in the data
    if data is None or 'api_key' not in data or 'api_secret' not in data:
        return jsonify({'error': 'Invalid request format. Please provide "api_key" and "api_secret" in the request body.'}), 400

    # api_keys['Coinbase'] = {
    #     'api_key': data['api_key'],
    #     'api_secret': data['api_secret']
    # }

    key = data['api_key']
    secret = data['api_secret']

    coinbase_keys = ApiKey.query.filter_by(service='Coinbase').first()

    if coinbase_keys:
        coinbase_keys.api_key = key
        coinbase_keys.api_secret = secret
    else:
        new_coinbase_keys = ApiKey(service='Coinbase', api_key=key, api_secret=secret)
        db.session.add(new_coinbase_keys)
    db.session.commit()

    # print(api_keys)
    init_coinbase()
    return jsonify({'message':'Coinbase keys updated successfully'}), 201

def init_coinbase():
    global coinbase

    # api_key = api_keys['Coinbase']['api_key']
    # api_secret = api_keys['Coinbase']['api_secret']

    coinbase_keys = ApiKey.query.filter_by(service='Coinbase').first()

    if coinbase_keys and coinbase_keys.api_key and coinbase_keys.api_secret:

        key = coinbase_keys.api_key
        secret = coinbase_keys.api_secret

        try:
            coinbase = coinbasePortfolio(key, secret)
            print('Coinbase portfolio initialized successfully')
        except RequestsJSONDecodeError:
            #return jsonify({'message':'api_key or api_secret for Coinbase was invalid.'}), 404
            abort(404, 'api_key or api_secret for Coinbase was invalid.')
        
        global accounts
        accounts.append(coinbase)
        print("coinbase account appended to accounts")
    else:
        abort(404, 'api_key or api_secret for Coinbase was not uploaded.')


@app.route('/api/gemini/keys', methods=['POST'])
def set_gemini_keys():
    data = request.get_json()

    # Check if data is None or if 'api_key' and 'api_secret' are present in the data
    if data is None or 'api_key' not in data or 'api_secret' not in data:
        return jsonify({'error': 'Invalid request format. Please provide "api_key" and "api_secret" in the request body.'}), 400
    
    api_keys['Gemini'] = {
        'api_key': data['api_key'],
        'api_secret': data['api_secret']
    }

    print(api_keys)
    init_gemini()
    return jsonify({'message':'Gemini keys updated successfully'}), 201

def init_gemini():
    global gemini

    api_key = api_keys['Gemini']['api_key']
    api_secret = api_keys['Gemini']['api_secret']

    try:
        gemini = geminiPortfolio(api_key, api_secret)
        print('Gemini portfolio initialized successfully')
    except Exception:
        #return jsonify({'message':'api_key or api_secret for Gemini was invalid.'}), 404
        abort(404, 'api_key or api_secret for Gemini was invalid.')
    
    global accounts
    accounts.append(gemini)
    print("gemini account appended to accounts")


@app.route('/api/ledger/upload-csv', methods=['POST', 'GET'])
def upload_ledger_csv():
    if request.method == 'POST':
        # Check if the POST request has a file part
        if 'file' not in request.files:
            return {'error': 'No file part'}, 400

        file = request.files['file']

        # Check if the file is empty
        if file.filename == '':
            return {'error': 'No selected file'}, 400
        
        # Check if the file is an Excel file
        if not file.filename.endswith('.csv'):
            return {'error': 'Invalid file format. Please upload a CSV file (.csv)'}, 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            upload = Upload(filename = filename, data = file.read())
            db.session.add(upload)
            db.session.commit()

            init_ledger()
            return redirect(url_for('download_page'))
        
        return 'Upload failed.'
    
    return render_template('upload.html')

@app.route('/download', methods=['GET'])
def download_page():
    return render_template('download.html')

    
def init_ledger():
    upload = Upload.query.order_by(Upload.id.desc()).first()

    if upload is None:
        return jsonify({'error': 'No ledger file found'}), 404
    
    file_data = BytesIO(upload.data)
    
    global ledger
    try:
        ledger = ledgerPortfolio(file_data)
        print('Ledger portfolio initialized successfully')
    except Exception:
        abort(404, 'CSV file for Ledger was invalid.')
    
    global accounts
    accounts.append(ledger)
    print("ledger account appended to accounts")

def init_master():
    global master, accounts

    if len(accounts) == 0:
        return jsonify({'message':'Accounts are invalid...'}), 404

    master = MasterPortfolio(accounts)


@app.route('/api/coinbase/json', methods=['GET'])
def coinbase_json():
    if type(coinbase) == Portfolio:
        coinbase.loadData()
        return jsonify(coinbase.portfolio), 202
    
    return jsonify({'message':'Error returning Coinbase portfolio json...'}), 404

@app.route('/api/coinbase/total-balance', methods=['GET'])
def coinbase_total_balance():
    if type(coinbase) == Portfolio:
        coinbase.loadData()
        return jsonify({'balance':coinbase.totalBalance()}), 202

    return jsonify({'message':'Error returning Coinbase balance...'}), 404

@app.route('/api/gemini/json', methods=['GET'])
def gemini_json():
    if type(gemini) == Portfolio:
        gemini.loadData()
        return jsonify(gemini.portfolio), 202
    
    return jsonify({'message':'Error returning Gemini portfolio json...'}), 404

@app.route('/api/gemini/total-balance', methods=['GET'])
def gemini_total_balance():
    if type(gemini) == Portfolio:
        gemini.loadData()
        return jsonify({'balance':gemini.totalBalance()}), 202

    return jsonify({'message':'Error returning Gemini balance...'}), 404

@app.route('/api/ledger/json', methods=['GET'])
def ledger_json():
    if type(ledger) == Portfolio:
        ledger.loadData()
        return jsonify(ledger.portfolio), 202
    
    return jsonify({'message':'Error returning Ledger portfolio json...'}), 404

@app.route('/api/ledger/total-balance', methods=['GET'])
def ledger_total_balance():
    if type(ledger) == Portfolio:
        ledger.loadData()
        return jsonify(ledger.totalBalance()), 202
    
    return jsonify({'message':'Error returning Ledger balance...'}), 404

@app.route('/api/master/json', methods = ['GET'])
def master_json():
    init_master()

    if type(master) == MasterPortfolio:
        master.loadData()
        return jsonify(master.portfolio), 202
    
    return jsonify({'message':'Error returning Master portfolio json...'}), 404
    
@app.route('/api/master/total-balance', methods=['GET'])
def master_total_balance():
    init_master()

    if type(master) == MasterPortfolio:
        master.loadData()
        return jsonify({'balance':master.totalBalance()}), 202

    return jsonify({'message':'Error returning Master balance...'}), 404

@app.route('/api/master/download-xlsx', methods = ['GET'])
def download_master_xlsx():
    init_master()
    master.loadData()

    excel_file = master.pandasToExcel_api()

    current_time = datetime.now().strftime("%m-%d-%Y %H:%M")
    fileName = f'master_portfolio_{current_time}.xlsx'

    return send_file(excel_file, 
                     as_attachment=True, 
                     attachment_filename=fileName,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)