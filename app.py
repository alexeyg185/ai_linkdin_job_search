"""
Main application entry point for the LinkedIn Job Search Automation System.
This file initializes the Flask web application and configures routes.
"""

import atexit
import json
import logging
import sys
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, g
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect

from config import Config
# Import services
from services.orchestrator_service import OrchestratorService

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('application.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['WTF_CSRF_ENABLED'] = False

# Initialize Flask extensions
csrf = CSRFProtect(app)
bootstrap = Bootstrap5(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Initialize orchestrator (this also starts the scheduler)
orchestrator = OrchestratorService()


# Add mobile detection
@app.before_request
def detect_mobile():
    user_agent = request.headers.get('User-Agent', '').lower()
    g.is_mobile = any(device in user_agent for device in ['iphone', 'ipad', 'android', 'mobile'])


# User class for Flask-Login
class User:
    def __init__(self, user_data):
        self.id = user_data['user_id']
        self.username = user_data['username']
        self.email = user_data.get('email')
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False

    def get_id(self):
        return str(self.id)


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    user_data = orchestrator.user_service.get_user_by_id(int(user_id))
    if user_data:
        return User(user_data)
    return None


# Routes

@app.route('/')
def index():
    """Home page route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please enter both username and password', 'danger')
            return render_template('auth/login.html')

        user_data = orchestrator.user_service.authenticate(username, password)

        if user_data:
            user = User(user_data)
            login_user(user)
            next_page = request.args.get('next')
            if not next_page or next_page == '/logout':
                next_page = url_for('dashboard')
            return redirect(next_page)
        else:
            flash('Invalid username or password', 'danger')

    return render_template('auth/login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout route."""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard route."""
    dashboard_data = orchestrator.get_user_dashboard_data(current_user.id)
    return render_template('dashboard/index.html', data=dashboard_data)


@app.route('/jobs')
@login_required
def jobs():
    """Jobs listing route."""
    query = request.args.get('query', '')
    states = request.args.getlist('state')
    if not states:
        states = ['relevant', 'saved', 'applied', 'irrelevant']

    limit = int(request.args.get('limit', 20))
    offset = int(request.args.get('offset', 0))

    results = orchestrator.search_jobs(
        current_user.id, query, states, limit, offset
    )

    return render_template('jobs/list.html', results=results, query=query, states=states)


@app.route('/jobs/<job_id>')
@login_required
def job_detail(job_id):
    """Job detail route."""
    try:
        job_details = orchestrator.get_job_details(job_id, current_user.id)
        return render_template('jobs/detail.html', job=job_details)
    except ValueError:
        flash('Job not found', 'danger')
        return redirect(url_for('jobs'))


@app.route('/preferences')
@login_required
def preferences():
    """Preferences route."""
    all_prefs = orchestrator.pref_service.get_all_preferences(current_user.id)
    schedule = orchestrator.db_service.get_user_schedule(current_user.id)

    return render_template('preferences/settings.html', preferences=all_prefs, schedule=schedule)


@app.route('/api/update_preferences', methods=['POST'])
@login_required
def update_preferences():
    """API route to update preferences."""
    try:
        preferences = request.json
        orchestrator.update_user_preferences(current_user.id, preferences)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error updating preferences: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/api/update_job_state', methods=['POST'])
@login_required
def update_job_state():
    """API route to update job state."""
    try:
        job_id = request.json.get('job_id')
        new_state = request.json.get('state')
        notes = request.json.get('notes')

        result = orchestrator.update_job_state(job_id, current_user.id, new_state, notes)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error updating job state: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/api/run_job', methods=['POST'])
@login_required
def run_job():
    """API route to run a manual job."""
    try:
        result = orchestrator.run_manual_job(current_user.id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error running job: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/api/job_status/<job_id>')
@login_required
def job_status(job_id):
    """API route to get job status."""
    status = orchestrator.scheduler_service.get_job_status(job_id)
    if status:
        return jsonify(status)
    return jsonify({"status": "not_found"}), 404


@app.route('/api/reanalyze_job', methods=['POST'])
@login_required
def reanalyze_job():
    """API route to reanalyze a job."""
    try:
        job_id = request.json.get('job_id')
        result = orchestrator.reanalyze_job(job_id, current_user.id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error reanalyzing job: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/api/add_job_by_url', methods=['POST'])
@login_required
def add_job_by_url():
    """API route to add a job by URL."""
    try:
        # Check if this is a company jobs URL request
        if 'company_jobs_url' in request.json:
            logger.info(f"Received request to add job from company URL: {request.json.get('company_jobs_url')}")
            company_jobs_url = request.json.get('company_jobs_url')
            job_ids = request.json.get('job_ids', '').split()  # Split job IDs by spaces

            if not company_jobs_url:
                return jsonify({"status": "error", "message": "Company jobs URL is required"}), 400

            if not job_ids:
                return jsonify({"status": "error", "message": "Job IDs are required"}), 400

            logger.info(f"Starting scrape for job IDs: {job_ids}")
            # Use scraper to get jobs from company URL
            scrape_result = orchestrator.scraper_service.scrape_company_jobs(
                company_jobs_url, current_user.id, job_ids=job_ids, callback=None
            )
            logger.info(f"Scrape result: {scrape_result}")

            # Check for queued jobs directly instead of relying on scrape_result
            queued_jobs = orchestrator.db_service.get_jobs_by_state(
                current_user.id, "queued_for_analysis"
            )
            logger.info(f"Found {len(queued_jobs)} jobs queued for analysis")

            if queued_jobs:
                logger.info("Starting analysis of queued jobs")
                try:
                    # Run analysis
                    analyze_result = orchestrator.analysis_service.analyze_queued_jobs(
                        current_user.id, limit=len(queued_jobs)
                    )
                    logger.info(f"Analysis completed with result: {analyze_result}")
                    scrape_result["analysis_result"] = analyze_result
                except Exception as analysis_error:
                    logger.error(f"Error during analysis: {str(analysis_error)}")
                    scrape_result["analysis_error"] = str(analysis_error)
            else:
                logger.warning("No jobs queued for analysis after scraping")

            return jsonify(scrape_result)
    except Exception as e:
        logger.error(f"Error adding job by URL: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/add_job', methods=['GET'])
@login_required
def add_job_page():
    """Route for the add job page."""
    return render_template('jobs/add_job.html')


@app.route('/api/delete_job', methods=['POST'])
@login_required
def delete_job():
    """API route to permanently delete a job."""
    try:
        job_id = request.json.get('job_id')
        if not job_id:
            return jsonify({"status": "error", "message": "Job ID is required"}), 400

        result = orchestrator.delete_job(job_id, current_user.id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in delete_job route: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Setup route for first-time installation."""
    # Check if any users exist
    users = orchestrator.user_service.get_all_users()
    if users:
        flash('Setup has already been completed', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        if not username or not password:
            flash('Please enter both username and password', 'danger')
            return render_template('auth/setup.html')

        try:
            user_id = orchestrator.setup_new_installation(username, password, email)
            flash('Setup completed successfully. Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            logger.error(f"Error in setup: {str(e)}")
            flash(f'Error during setup: {str(e)}', 'danger')

    return render_template('auth/setup.html')


@app.after_request
def add_security_headers(response):
    # Prevent browsers from interpreting files as a different MIME type
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'

    # Enable browser XSS filtering
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # Enable Content Security Policy (CSP)
    response.headers[
        'Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com;"

    # Enable HTTP Strict Transport Security (HSTS)
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    return response


# JSON encoder for datetime objects
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


app.json_encoder = JSONEncoder


# Clean up on exit
def shutdown():
    """Shutdown hook to stop background services."""
    logger.info("Application shutting down")
    orchestrator.stop_services()


atexit.register(shutdown)

# Start the application
if __name__ == '__main__':
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
