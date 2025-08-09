import os
import boto3
import psycopg2
from flask import Flask, request, jsonify, Response

# --- Configuration ---
app = Flask(__name__)
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
AWS_REGION = os.environ.get('AWS_REGION')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_HOST = os.environ.get('DB_HOST') # Kubernetes service name for Postgres
DB_NAME = os.environ.get('DB_NAME')

# --- Database Helper ---
def get_db_connection():
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

# Initialize S3 client using boto3
s3_client = boto3.client('s3', region_name=AWS_REGION)

# --- API Endpoints ---
@app.route("/up", methods=['GET'])
def health_check():
    """Health probe endpoint."""
    return "OK", 200

@app.route("/upload", methods=['POST'])
def upload_file():
    """Accepts a file and saves it to an S3 bucket."""
    if 'file' not in request.files:
        return "No file part in the request", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    try:
        s3_client.upload_fileobj(file, S3_BUCKET_NAME, file.filename)
        
        # Log the upload to PostgreSQL
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute('CREATE TABLE IF NOT EXISTS uploads (id SERIAL PRIMARY KEY, filename VARCHAR(255) NOT NULL, upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP);')
            cur.execute('INSERT INTO uploads (filename) VALUES (%s);', (file.filename,))
            conn.commit()
            cur.close()
            conn.close()
        
        return jsonify({"status": "success", "bucket": S3_BUCKET_NAME, "key": file.filename}), 200
    except Exception as e:
        return f"An error occurred: {e}", 500

@app.route("/file/<filename>", methods=['GET'])
def get_file(filename):
    """Streams a file from S3."""
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=filename)
        return Response(response['Body'].read(), mimetype=response['ContentType'])
    except s3_client.exceptions.NoSuchKey:
        return "File not found", 404
    except Exception as e:
        return f"An error occurred: {e}", 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
