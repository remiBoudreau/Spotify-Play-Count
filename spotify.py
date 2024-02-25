import os
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_limiter import Limiter
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from get_artists_data import main

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize Limiter to limit the number of requests
limiter = Limiter(
    app,
    default_limits=["200 per day", "50 per hour"]  # Default rate limit
)

# Load Spotify API credentials from environment variables
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Allowed file extensions for uploaded files
ALLOWED_EXTENSIONS = {'csv'}

@app.route('/', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # Rate limit applied to this route
def index():
    # Handle file upload
    if request.method == 'POST':
        try:
            artists_data = handle_uploaded_file(request)
            return render_template('results.html', results=artists_data)
        except ValueError as e:
            flash(str(e), "error")
        except Exception as e:
            flash("An error occurred while processing the file. Please try again.", "error")
        return redirect(url_for('index'))
    return render_template('index.html')

def allowed_file(filename):
    """
    Check if the uploaded file has a valid extension.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def handle_uploaded_file(request):
    """
    Handle the uploaded file, process it, and return the result.
    """
    csv_file = request.files.get('file')
    if not csv_file or csv_file.filename == '':
        raise ValueError('No file selected')
    if not allowed_file(csv_file.filename):
        raise ValueError('Invalid file format. Please upload a CSV file.')
    filename = secure_filename(csv_file.filename)
    csv_file.save(filename)
    artists_data = main(filename, CLIENT_ID, CLIENT_SECRET)
    os.remove(filename)  # Delete the uploaded file after processing
    return artists_data

if __name__ == '__main__':
    app.run(debug=True)
