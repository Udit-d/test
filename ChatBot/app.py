from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, send_from_directory
import pyrebase
import os
import boto3
from botocore.exceptions import NoCredentialsError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


app = Flask(__name__)

# AWS S3 Config
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
S3_BUCKET = os.getenv('S3_BUCKET')

s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)

# Firebase configuration
firebase_config = {
    "apiKey": "AIzaSyAlbv1kT3_HlTU8Z55JX4o6BZt-amXaE6E",
    "authDomain": "chatbot-42205.firebaseapp.com",
    "projectId": "chatbot-42205",
    "storageBucket": "chatbot-42205.appspot.com",
    "messagingSenderId": "663825317294",
    "appId": "1:663825317294:web:46038722e7af28a31b1c3f",
    "measurementId": "G-J03MBEYSZL",
    "databaseURL": ""
}

def handle_user_message(user_message):
    if user_message.lower() == 'hello':
        return 'Hi there!'
    elif user_message.lower() == 'bye':
        return 'Goodbye!'
    elif user_message.lower() == 'upload':
        return 'Please upload a file.'
    else:
        return 'I did not understand that. How can I assist you?'

# Initialize Firebase with pyrebase
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()

app.secret_key = 'secret'

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return 'hi ' + session['user']

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Sign in with email and password
            user = auth.sign_in_with_email_and_password(email, password)
            session['user'] = email
            return redirect(url_for('hi'))
        except:
            flash('Authentication failed')

    return render_template('login.html')

@app.route('/index', methods=['GET', 'POST'])
def hi():
    if 'user' in session:
        if request.method == 'POST':
            user_message = request.form.get('user_message')
            bot_response = handle_user_message(user_message)
            return render_template('chat.html', user=session['user'], bot_response=bot_response)

        return render_template('chat.html', user=session['user'])
    else:
        return redirect(url_for('login'))
    
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

def allowed_file(filename):
    return True

@app.route('/upload', methods=['POST'])
def upload_file():
    uploaded_file = request.files.get('file')
    print(f'File name: {uploaded_file.filename}')

    if uploaded_file and allowed_file(uploaded_file.filename):
        try:
            print("Uploading file to S3...")
            s3.upload_fileobj(uploaded_file, S3_BUCKET, uploaded_file.filename)
            print(f'File "{uploaded_file.filename}" uploaded successfully to S3!')
        except Exception as e:
            print(f'Error uploading file to S3: {e}')
    else:
        print('No valid file selected for upload.')

    return redirect(url_for('hi'))



@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if request.method == 'POST':
        session.pop('user', None)
        flash('You have been logged out.')
        return redirect(url_for('login'))
    else:
        # Handle GET request if needed (optional)
        return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True, port=5000)
