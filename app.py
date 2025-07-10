import streamlit as st
import os
from dotenv import load_dotenv
import tempfile
import pandas as pd
import PyPDF2
import time
import re
import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta
import json
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq
import sqlite3
import hashlib
import uuid
from typing import Dict, List, Optional

# Load environment variables
load_dotenv()

# Updated Database setup function with better error handling
def init_database():
    """Initialize SQLite database with necessary tables and handle migrations."""
    conn = sqlite3.connect('cv_analyzer.db')
    cursor = conn.cursor()
    
    try:
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'candidate',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Jobs table - with all necessary columns
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                requirements TEXT NOT NULL,
                department TEXT,
                location TEXT,
                salary_range TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        ''')
        
        # Applications table - with enhanced columns for additional information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                candidate_id INTEGER,
                cv_text TEXT,
                match_score REAL,
                skills_score REAL,
                experience_score REAL,
                matched_skills TEXT,
                missing_skills TEXT,
                analysis_result TEXT,
                experience_summary TEXT,
                status TEXT DEFAULT 'pending',
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                -- New application form fields
                applicant_full_name TEXT,
                applicant_email TEXT,
                applicant_phone TEXT,
                current_salary TEXT,
                expected_salary TEXT,
                total_experience TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs (id),
                FOREIGN KEY (candidate_id) REFERENCES users (id)
            )
        ''')
        
        # Handle existing database migration
        # Check for missing columns and add them
        cursor.execute("PRAGMA table_info(applications)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        # Define all required columns for applications table
        required_columns = [
            ('skills_score', 'REAL'),
            ('experience_score', 'REAL'),
            ('matched_skills', 'TEXT'),
            ('missing_skills', 'TEXT'),
            ('analysis_result', 'TEXT'),
            ('experience_summary', 'TEXT'),
            ('applicant_full_name', 'TEXT'),
            ('applicant_email', 'TEXT'),
            ('applicant_phone', 'TEXT'),
            ('current_salary', 'TEXT'),
            ('expected_salary', 'TEXT'),
            ('total_experience', 'TEXT')
        ]
        
        # Add missing columns
        for column_name, column_type in required_columns:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE applications ADD COLUMN {column_name} {column_type}')
                    print(f"Added missing column: {column_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e):
                        print(f"Warning: Could not add column {column_name}: {e}")
        
        # Check jobs table for missing columns
        cursor.execute("PRAGMA table_info(jobs)")
        existing_job_columns = [column[1] for column in cursor.fetchall()]
        
        if 'created_by' not in existing_job_columns:
            try:
                cursor.execute('ALTER TABLE jobs ADD COLUMN created_by INTEGER')
                print("Added missing column: created_by to jobs table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    print(f"Warning: Could not add created_by column: {e}")
        
        if 'is_active' not in existing_job_columns:
            try:
                cursor.execute('ALTER TABLE jobs ADD COLUMN is_active BOOLEAN DEFAULT 1')
                print("Added missing column: is_active to jobs table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    print(f"Warning: Could not add is_active column: {e}")
        
        conn.commit()
        print("Database initialization completed successfully!")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

# Authentication functions
def hash_password(password: str) -> str:
    """Hash password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    return hash_password(password) == hashed

def create_user(username: str, email: str, password: str, full_name: str, role: str = 'candidate') -> bool:
    """Create a new user."""
    try:
        conn = sqlite3.connect('cv_analyzer.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, email, hash_password(password), full_name, role))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate user and return user data."""
    conn = sqlite3.connect('cv_analyzer.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, email, full_name, role FROM users 
        WHERE username = ? AND password_hash = ?
    ''', (username, hash_password(password)))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'full_name': user[3],
            'role': user[4]
        }
    return None

# Job functions
def get_all_jobs() -> List[Dict]:
    """Get all active jobs."""
    conn = sqlite3.connect('cv_analyzer.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT j.id, j.title, j.description, j.requirements, j.department, j.location, 
               j.salary_range, j.created_at, u.full_name as created_by_name
        FROM jobs j
        LEFT JOIN users u ON j.created_by = u.id
        WHERE j.is_active = 1 
        ORDER BY j.created_at DESC
    ''')
    jobs = cursor.fetchall()
    conn.close()
    
    return [{
        'id': job[0],
        'title': job[1],
        'description': job[2],
        'requirements': job[3],
        'department': job[4],
        'location': job[5],
        'salary_range': job[6],
        'created_at': job[7],
        'created_by_name': job[8]
    } for job in jobs]

def get_job_by_id(job_id: int) -> Optional[Dict]:
    """Get job by ID."""
    conn = sqlite3.connect('cv_analyzer.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT j.id, j.title, j.description, j.requirements, j.department, j.location, 
               j.salary_range, j.created_by, j.created_at, u.full_name as created_by_name
        FROM jobs j
        LEFT JOIN users u ON j.created_by = u.id
        WHERE j.id = ? AND j.is_active = 1
    ''', (job_id,))
    job = cursor.fetchone()
    conn.close()
    
    if job:
        return {
            'id': job[0],
            'title': job[1],
            'description': job[2],
            'requirements': job[3],
            'department': job[4],
            'location': job[5],
            'salary_range': job[6],
            'created_by': job[7],
            'created_at': job[8],
            'created_by_name': job[9]
        }
    return None

def create_job(title: str, description: str, requirements: str, department: str, location: str, salary_range: str, created_by: int) -> bool:
    """Create a new job posting."""
    try:
        conn = sqlite3.connect('cv_analyzer.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO jobs (title, description, requirements, department, location, salary_range, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, requirements, department, location, salary_range, created_by))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_jobs_by_creator(creator_id: int) -> List[Dict]:
    """Get jobs created by a specific HR user."""
    conn = sqlite3.connect('cv_analyzer.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, description, requirements, department, location, salary_range, created_at
        FROM jobs WHERE created_by = ? AND is_active = 1 ORDER BY created_at DESC
    ''', (creator_id,))
    jobs = cursor.fetchall()
    conn.close()
    
    return [{
        'id': job[0],
        'title': job[1],
        'description': job[2],
        'requirements': job[3],
        'department': job[4],
        'location': job[5],
        'salary_range': job[6],
        'created_at': job[7]
    } for job in jobs]

# Application functions
def submit_application(job_id: int, candidate_id: int, cv_text: str, analysis_result: Dict, 
                      applicant_info: Dict) -> bool:
    """Submit a job application with additional applicant information."""
    try:
        conn = sqlite3.connect('cv_analyzer.db')
        cursor = conn.cursor()
        
        # Check if user already applied for this job
        cursor.execute('''
            SELECT id FROM applications WHERE job_id = ? AND candidate_id = ?
        ''', (job_id, candidate_id))
        
        if cursor.fetchone():
            conn.close()
            return False  # Already applied
        
        cursor.execute('''
            INSERT INTO applications 
            (job_id, candidate_id, cv_text, match_score, skills_score, experience_score, 
             matched_skills, missing_skills, analysis_result, experience_summary, status,
             applicant_full_name, applicant_email, applicant_phone, current_salary, 
             expected_salary, total_experience)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_id, candidate_id, cv_text,
            analysis_result.get('score', 0),
            analysis_result.get('skills_match_score', 0),
            analysis_result.get('experience_relevance_score', 0),
            json.dumps(analysis_result.get('key_skills_matched', [])),
            json.dumps(analysis_result.get('missing_skills', [])),
            json.dumps(analysis_result),
            analysis_result.get('experience_summary', ''),
            'reviewed' if analysis_result.get('score', 0) >= 6 else 'rejected',
            applicant_info.get('full_name', ''),
            applicant_info.get('email', ''),
            applicant_info.get('phone', ''),
            applicant_info.get('current_salary', ''),
            applicant_info.get('expected_salary', ''),
            applicant_info.get('total_experience', '')
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error submitting application: {str(e)}")
        return False

def get_applications_for_hr(hr_id: int) -> List[Dict]:
    """Get applications for jobs created by specific HR user."""
    conn = sqlite3.connect('cv_analyzer.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.id, j.title, u.full_name, u.email, a.match_score, a.skills_score, 
               a.experience_score, a.status, a.applied_at, a.matched_skills, a.missing_skills,
               a.experience_summary, a.analysis_result, j.id as job_id,
               a.applicant_full_name, a.applicant_email, a.applicant_phone, 
               a.current_salary, a.expected_salary, a.total_experience
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        JOIN users u ON a.candidate_id = u.id
        WHERE j.created_by = ?
        ORDER BY a.applied_at DESC
    ''', (hr_id,))
    applications = cursor.fetchall()
    conn.close()
    
    return [{
        'id': app[0],
        'job_title': app[1],
        'candidate_name': app[2],
        'candidate_email': app[3],
        'match_score': app[4],
        'skills_score': app[5],
        'experience_score': app[6],
        'status': app[7],
        'applied_at': app[8],
        'matched_skills': json.loads(app[9]) if app[9] else [],
        'missing_skills': json.loads(app[10]) if app[10] else [],
        'experience_summary': app[11],
        'analysis_result': json.loads(app[12]) if app[12] else {},
        'job_id': app[13],
        'applicant_full_name': app[14] or app[2],  # Fallback to username if not provided
        'applicant_email': app[15] or app[3],      # Fallback to user email if not provided
        'applicant_phone': app[16] or 'Not provided',
        'current_salary': app[17] or 'Not provided',
        'expected_salary': app[18] or 'Not provided',
        'total_experience': app[19] or 'Not provided'
    } for app in applications]

def get_user_applications(user_id: int) -> List[Dict]:
    """Get applications for a specific user."""
    conn = sqlite3.connect('cv_analyzer.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT j.title, a.match_score, a.status, a.applied_at, a.skills_score, a.experience_score
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.candidate_id = ?
        ORDER BY a.applied_at DESC
    ''', (user_id,))
    applications = cursor.fetchall()
    conn.close()
    
    return [{
        'job_title': app[0],
        'match_score': app[1],
        'status': app[2],
        'applied_at': app[3],
        'skills_score': app[4],
        'experience_score': app[5]
    } for app in applications]

# CV Analysis functions
def extract_text_from_pdf(pdf_file):
    """Extract text content from a PDF file with robust error handling."""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error parsing PDF: {str(e)}")
        return f"[Error extracting PDF content: {str(e)}. Please check if this is a valid PDF file.]"

def extract_work_experience(cv_text, client):
    """Extract work experience durations from the CV text using Groq."""
    prompt = f"""
    Extract all work experience entries from the CV text below. For each position, identify the start and end dates.
    If the end date is "Present" or "Current", use today's date.
    
    CV text:
    {cv_text}
    
    Format your response as JSON with the following structure:
    {{
        "work_experience": [
            {{
                "position": "Job Title",
                "company": "Company Name",
                "start_date": "YYYY-MM",
                "end_date": "YYYY-MM or Present"
            }},
            ...
        ]
    }}
    Return only the JSON with no additional text.
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            temperature=0.2,
            max_tokens=1000
        )
        result = response.choices[0].message.content
        
        try:
            experience_data = json.loads(result)
            return experience_data
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return {"work_experience": []}
            
    except Exception as e:
        print(f"Error extracting work experience: {str(e)}")
        return {"work_experience": []}

def calculate_total_experience(work_experience):
    """Calculate total work experience in months and years from extracted work experience data."""
    today = datetime.datetime.now().date()
    total_months = 0
    
    for entry in work_experience.get("work_experience", []):
        try:
            start_date_str = entry.get("start_date")
            if not start_date_str:
                continue
                
            try:
                start_date = parser.parse(start_date_str).date()
            except:
                match = re.search(r'(\d{4})[-/]?(\d{1,2})', start_date_str)
                if match:
                    year, month = match.groups()
                    start_date = datetime.date(int(year), int(month), 1)
                else:
                    continue
            
            end_date_str = entry.get("end_date", "")
            if end_date_str.lower() in ["present", "current", "now"]:
                end_date = today
            else:
                try:
                    end_date = parser.parse(end_date_str).date()
                except:
                    match = re.search(r'(\d{4})[-/]?(\d{1,2})', end_date_str)
                    if match:
                        year, month = match.groups()
                        end_date = datetime.date(int(year), int(month), 1)
                    else:
                        continue
            
            delta = relativedelta(end_date, start_date)
            months = delta.years * 12 + delta.months
            total_months += months
            
        except Exception as e:
            print(f"Error calculating experience for entry {entry}: {str(e)}")
            continue
    
    years = total_months // 12
    remaining_months = total_months % 12
    
    return {
        "total_months": total_months,
        "years": years,
        "months": remaining_months,
        "formatted": f"{years} years, {remaining_months} months"
    }

def analyze_cv(cv_text, job_description, work_experience_data, client):
    """Use Groq to analyze a CV against a job description."""
    total_experience = calculate_total_experience(work_experience_data)
    
    prompt = f"""
    You are an AI HR assistant. You need to evaluate a candidate's CV against a job description.
    
    Job Description:
    {job_description}
    
    Candidate CV:
    {cv_text}
    
    Candidate's total work experience: {total_experience["formatted"]} ({total_experience["total_months"]} months total)
    
    Provide a numerical score from 1-10 for how well this candidate matches the job requirements.
    Consider both skills match AND the relevance and duration of work experience when scoring.
    
    Also provide a brief explanation (maximum 3 sentences) of the main strengths and weaknesses.
    
    Format your response as JSON with the following structure:
    {{
        "score": [1-10 integer],
        "experience_relevance_score": [1-10 integer],
        "skills_match_score": [1-10 integer],
        "explanation": "[brief explanation]",
        "key_skills_matched": ["skill1", "skill2", "skill3"],
        "missing_skills": ["skill1", "skill2"],
        "experience_summary": "[brief summary of relevant experience]"
    }}
    Return only the JSON with no additional text.
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            temperature=0.2,
            max_tokens=1000
        )
        result = response.choices[0].message.content
        
        try:
            json_result = json.loads(result)
            return json_result
        except json.JSONDecodeError:
            print(f"JSON decode error in analysis result: {result}")
            return {
                "score": 5,
                "experience_relevance_score": 5,
                "skills_match_score": 5,
                "explanation": "Unable to properly analyze this CV due to formatting issues.",
                "key_skills_matched": [],
                "missing_skills": [],
                "experience_summary": "Experience details could not be extracted accurately."
            }
            
    except Exception as e:
        print(f"Error analyzing CV: {str(e)}")
        return {
            "score": 5,
            "experience_relevance_score": 5,
            "skills_match_score": 5,
            "explanation": f"Error analyzing CV: {str(e)}",
            "key_skills_matched": [],
            "missing_skills": [],
            "experience_summary": "Analysis failed due to technical issues."
        }

# Custom CSS for better UI
def set_custom_styling():
    st.markdown("""
    <style>
    .stApp {
        background-color: #0f55b8;
        color: black;
    }
    .header-container {
        background-color: #1a62c5;
        padding: 1.5rem;
        border-radius: 10px;
        color: black;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .card {
        background-color: #1a62c5;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        margin-bottom: 1rem;
        color: black;
    }
    .job-card {
        background-color: #2570d4;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        margin-bottom: 1rem;
        color: black;
        border-left: 4px solid #4caf50;
    }
    .metric-container {
        background-color: #2570d4;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
        color: black;
    }
    .login-container {
        background-color: #1a62c5;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
        max-width: 400px;
        margin: 2rem auto;
        color: black;
    }
    .application-detail {
        background-color: #1a62c5;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
        margin: 1rem 0;
        color: black;
        border: 2px solid #4caf50;
    }
    .application-form {
        background-color: #1a62c5;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
        margin: 1rem 0;
        color: black;
        border: 2px solid #2196f3;
    }
    p, h1, h2, h3, h4, h5, h6, li, label, span {
        color: black !important;
    }
    .stButton>button {
        background-color: #ffffff;
        color: #0f55b8;
        border: none;
        font-weight: bold;
        border-radius: 5px;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #e6e6e6;
        color: #0f55b8;
    }
    .apply-button {
        background-color: #4caf50 !important;
        color: white !important;
    }
    .apply-button:hover {
        background-color: #45a049 !important;
    }
    .score-high {
        color: #4caf50 !important;
        font-weight: bold;
    }
    .score-medium {
        color: #ff9800 !important;
        font-weight: bold;
    }
    .score-low {
        color: #f44336 !important;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

def login_page():
    """Display login/registration page."""
    st.markdown('<div class="header-container"><h1>CV Analyzer Platform</h1><p>Login or Register to Continue</p></div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.subheader("Login")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                user = authenticate_user(username, password)
                if user:
                    st.session_state.user = user
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.subheader("Register")
        
        with st.form("register_form"):
            reg_username = st.text_input("Username", key="reg_username")
            reg_email = st.text_input("Email", key="reg_email")
            reg_full_name = st.text_input("Full Name", key="reg_full_name")
            reg_password = st.text_input("Password", type="password", key="reg_password")
            reg_confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password")
            role = st.selectbox("Role", ["candidate", "hr"])
            register = st.form_submit_button("Register")
            
            if register:
                if reg_password != reg_confirm_password:
                    st.error("Passwords do not match")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters")
                elif create_user(reg_username, reg_email, reg_password, reg_full_name, role):
                    st.success("Registration successful! Please login.")
                else:
                    st.error("Username or email already exists")
        st.markdown('</div>', unsafe_allow_html=True)

def job_detail_page(job):
    """Display detailed job information and application form."""
    st.markdown('<div class="application-detail">', unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back to Jobs", type="secondary"):
        if 'selected_job' in st.session_state:
            del st.session_state.selected_job
        st.rerun()
    
    st.markdown(f"# {job['title']}")
    st.markdown(f"**Department:** {job['department']}")
    st.markdown(f"**Location:** {job['location']}")
    st.markdown(f"**Salary Range:** {job['salary_range']}")
    st.markdown(f"**Posted by:** {job['created_by_name']}")
    st.markdown(f"**Posted on:** {job['created_at']}")
    
    st.markdown("---")
    
    st.markdown("## Job Description")
    st.markdown(job['description'])
    
    st.markdown("## Requirements")
    st.markdown(job['requirements'])
    
    st.markdown("---")
    
    # Application form
    st.markdown("## Apply for This Position")
    
    st.markdown('<div class="application-form">', unsafe_allow_html=True)
    
    with st.form("application_form"):
        st.markdown("### Personal Information")
        
        # Pre-fill with user data where available
        full_name = st.text_input("Full Name *", value=st.session_state.user.get('full_name', ''))
        email = st.text_input("Email Address *", value=st.session_state.user.get('email', ''))
        phone = st.text_input("Phone Number *", placeholder="e.g., +1-234-567-8900")
        
        st.markdown("### Professional Information")
        
        col1, col2 = st.columns(2)
        with col1:
            current_salary = st.text_input("Current Salary", placeholder="e.g., $50,000 or Not Applicable (if not currently employed)")
        with col2:
            expected_salary = st.text_input("Expected Salary", placeholder="e.g., $60,000")
        
        total_experience = st.text_input("Total Years of Experience *", placeholder="e.g., 3.5 years")
        
        st.markdown("### Upload Your CV")
        uploaded_file = st.file_uploader("Choose your CV file", type=['pdf', 'txt'])
        
        # Additional information
        st.markdown("### Additional Information (Optional)")
        cover_letter = st.text_area("Cover Letter / Additional Comments", 
                                   placeholder="Tell us why you're interested in this position...")
        
        submit_application = st.form_submit_button("Submit Application", type="primary")
        
        if submit_application:
            # Validation
            if not all([full_name, email, phone, total_experience, uploaded_file]):
                st.error("Please fill in all required fields (*) and upload your CV.")
            else:
                # Process the CV
                with st.spinner("Processing your application..."):
                    try:
                        # Initialize Groq client
                        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                        
                        # Extract text from uploaded file
                        if uploaded_file.type == "application/pdf":
                            cv_text = extract_text_from_pdf(uploaded_file)
                        else:
                            cv_text = str(uploaded_file.read(), "utf-8")
                        
                        # Extract work experience
                        work_experience_data = extract_work_experience(cv_text, client)
                        
                        # Analyze CV
                        job_requirements = f"{job['description']}\n\nRequirements:\n{job['requirements']}"
                        analysis_result = analyze_cv(cv_text, job_requirements, work_experience_data, client)
                        
                        # Prepare applicant information
                        applicant_info = {
                            'full_name': full_name,
                            'email': email,
                            'phone': phone,
                            'current_salary': current_salary,
                            'expected_salary': expected_salary,
                            'total_experience': total_experience,
                            'cover_letter': cover_letter
                        }
                        
                        # Submit application
                        if submit_application_db(job['id'], st.session_state.user['id'], 
                                               cv_text, analysis_result, applicant_info):
                            st.success("Application submitted successfully!")
                            st.balloons()
                            
                            # Show analysis results
                            
                    except Exception as e:
                        st.error(f"Error processing application: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def submit_application_db(job_id, candidate_id, cv_text, analysis_result, applicant_info):
    """Submit application to database - wrapper function for better error handling"""
    return submit_application(job_id, candidate_id, cv_text, analysis_result, applicant_info)

def candidate_dashboard():
    """Display candidate dashboard with job listings and applications."""
    st.markdown('<div class="header-container"><h1>Welcome, ' + st.session_state.user['full_name'] + '</h1><p>Find your dream job</p></div>', unsafe_allow_html=True)
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Select Page", ["Browse Jobs", "My Applications", "Profile"])
    
    if page == "Browse Jobs":
        st.markdown("## Available Jobs")
        
        # Get all jobs
        jobs = get_all_jobs()
        
        if not jobs:
            st.info("No jobs available at the moment.")
            return
        
        # Display jobs in a grid
        for job in jobs:
            st.markdown('<div class="job-card">', unsafe_allow_html=True)
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"### {job['title']}")
                st.markdown(f"**{job['department']} | {job['location']}**")
                st.markdown(f"**Salary:** {job['salary_range']}")
                st.markdown(f"**Description:** {job['description'][:200]}...")
                st.markdown(f"*Posted by: {job['created_by_name']} on {job['created_at'][:10]}*")
            
            with col2:
                if st.button(f"View Details", key=f"view_{job['id']}"):
                    st.session_state.selected_job = job['id']
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    elif page == "My Applications":
        st.markdown("## My Applications")
        
        applications = get_user_applications(st.session_state.user['id'])
        
        if not applications:
            st.info("You haven't applied to any jobs yet.")
            return
        
        # Display applications
        for app in applications:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**{app['job_title']}**")
                st.markdown(f"Applied on: {app['applied_at'][:10]}")
            
            with col2:
                score_class = "score-high" if app['match_score'] >= 7 else "score-medium" if app['match_score'] >= 5 else "score-low"
                st.markdown(f'<p class="{score_class}">Match: {app["match_score"]}/10</p>', unsafe_allow_html=True)
            
            with col3:
                status_color = "🟢" if app['status'] == 'reviewed' else "🔴" if app['status'] == 'rejected' else "🟡"
                st.markdown(f"{status_color} {app['status'].title()}")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    elif page == "Profile":
        st.markdown("## My Profile")
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**Full Name:** {st.session_state.user['full_name']}")
            st.markdown(f"**Username:** {st.session_state.user['username']}")
            st.markdown(f"**Email:** {st.session_state.user['email']}")
        
        with col2:
            st.markdown(f"**Role:** {st.session_state.user['role'].title()}")
            
            # Application stats
            apps = get_user_applications(st.session_state.user['id'])
            st.markdown(f"**Total Applications:** {len(apps)}")
            
            if apps:
                reviewed = sum(1 for app in apps if app['status'] == 'reviewed')
                rejected = sum(1 for app in apps if app['status'] == 'rejected')
                st.markdown(f"**Reviewed:** {reviewed}")
                st.markdown(f"**Rejected:** {rejected}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Handle job detail view
    if 'selected_job' in st.session_state:
        job = get_job_by_id(st.session_state.selected_job)
        if job:
            job_detail_page(job)

def hr_dashboard():
    """Display HR dashboard with job management and applications."""
    st.markdown('<div class="header-container"><h1>HR Dashboard</h1><p>Welcome, ' + st.session_state.user['full_name'] + '</p></div>', unsafe_allow_html=True)
    
    # Sidebar navigation
    st.sidebar.title("HR Navigation")
    page = st.sidebar.selectbox("Select Page", ["Dashboard", "Create Job", "My Jobs", "All Applications", "Analytics"])
    
    if page == "Dashboard":
        st.markdown("## Dashboard Overview")
        
        # Get statistics
        user_jobs = get_jobs_by_creator(st.session_state.user['id'])
        applications = get_applications_for_hr(st.session_state.user['id'])
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f'<div class="metric-container"><h4>Total Jobs</h4><h2>{len(user_jobs)}</h2></div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown(f'<div class="metric-container"><h4>Total Applications</h4><h2>{len(applications)}</h2></div>', unsafe_allow_html=True)
        
        with col3:
            reviewed = sum(1 for app in applications if app['status'] == 'reviewed')
            st.markdown(f'<div class="metric-container"><h4>Reviewed</h4><h2>{reviewed}</h2></div>', unsafe_allow_html=True)
        
        with col4:
            if applications:
                avg_score = sum(app['match_score'] for app in applications) / len(applications)
                st.markdown(f'<div class="metric-container"><h4>Avg Score</h4><h2>{avg_score:.1f}/10</h2></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="metric-container"><h4>Avg Score</h4><h2>N/A</h2></div>', unsafe_allow_html=True)
        
        # Recent applications
        st.markdown("## Recent Applications")
        
        if applications:
            recent_apps = applications[:5]  # Show last 5
            
            for app in recent_apps:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.markdown(f"**{app['candidate_name']}**")
                    st.markdown(f"Applied for: {app['job_title']}")
                    st.markdown(f"Email: {app['candidate_email']}")
                
                with col2:
                    score_class = "score-high" if app['match_score'] >= 7 else "score-medium" if app['match_score'] >= 5 else "score-low"
                    st.markdown(f'<p class="{score_class}">Score: {app["match_score"]}/10</p>', unsafe_allow_html=True)
                
                with col3:
                    status_color = "🟢" if app['status'] == 'reviewed' else "🔴" if app['status'] == 'rejected' else "🟡"
                    st.markdown(f"{status_color} {app['status'].title()}")
                
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No applications yet.")
    
    elif page == "Create Job":
        st.markdown("## Create New Job Posting")
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        with st.form("create_job_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                title = st.text_input("Job Title *")
                department = st.text_input("Department")
                location = st.text_input("Location")
            
            with col2:
                salary_range = st.text_input("Salary Range", placeholder="e.g., $50,000 - $70,000")
            
            description = st.text_area("Job Description *", height=200)
            requirements = st.text_area("Requirements *", height=200)
            
            submit_job = st.form_submit_button("Create Job Posting")
            
            if submit_job:
                if not all([title, description, requirements]):
                    st.error("Please fill in all required fields (*)")
                else:
                    if create_job(title, description, requirements, department, location, 
                                salary_range, st.session_state.user['id']):
                        st.success("Job posting created successfully!")
                        st.balloons()
                    else:
                        st.error("Failed to create job posting")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    elif page == "My Jobs":
        st.markdown("## My Job Postings")
        
        jobs = get_jobs_by_creator(st.session_state.user['id'])
        
        if not jobs:
            st.info("You haven't created any job postings yet.")
            return
        
        for job in jobs:
            st.markdown('<div class="job-card">', unsafe_allow_html=True)
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"### {job['title']}")
                st.markdown(f"**{job['department']} | {job['location']}**")
                st.markdown(f"**Salary:** {job['salary_range']}")
                st.markdown(f"**Posted on:** {job['created_at'][:10]}")
                st.markdown(f"**Description:** {job['description'][:200]}...")
            
            with col2:
                # Get application count for this job
                job_applications = [app for app in get_applications_for_hr(st.session_state.user['id']) 
                                  if app['job_id'] == job['id']]
                st.markdown(f"**Applications:** {len(job_applications)}")
                
                if job_applications:
                    avg_score = sum(app['match_score'] for app in job_applications) / len(job_applications)
                    st.markdown(f"**Avg Score:** {avg_score:.1f}/10")
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    elif page == "All Applications":
        st.markdown("## All Applications")
        
        applications = get_applications_for_hr(st.session_state.user['id'])
        
        if not applications:
            st.info("No applications received yet.")
            return
        
        # Filter options
        col1, col2 = st.columns(2)
        
        with col1:
            status_filter = st.selectbox("Filter by Status", ["All", "reviewed", "rejected", "pending"])
        
        with col2:
            job_titles = list(set([app['job_title'] for app in applications]))
            job_filter = st.selectbox("Filter by Job", ["All"] + job_titles)
        
        # Apply filters
        filtered_apps = applications
        if status_filter != "All":
            filtered_apps = [app for app in filtered_apps if app['status'] == status_filter]
        if job_filter != "All":
            filtered_apps = [app for app in filtered_apps if app['job_title'] == job_filter]
        
        # Display applications
        for app in filtered_apps:
            st.markdown('<div class="application-detail">', unsafe_allow_html=True)
            
            # Header
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"### {app['applicant_full_name']}")
                st.markdown(f"**Position:** {app['job_title']}")
                st.markdown(f"**Email:** {app['applicant_email']}")
                st.markdown(f"**Phone:** {app['applicant_phone']}")
            
            with col2:
                score_class = "score-high" if app['match_score'] >= 7 else "score-medium" if app['match_score'] >= 5 else "score-low"
                st.markdown(f'<p class="{score_class}">Overall: {app["match_score"]}/10</p>', unsafe_allow_html=True)
                st.markdown(f"Skills: {app['skills_score']}/10")
                st.markdown(f"Experience: {app['experience_score']}/10")
            
            with col3:
                status_color = "🟢" if app['status'] == 'reviewed' else "🔴" if app['status'] == 'rejected' else "🟡"
                st.markdown(f"{status_color} **{app['status'].title()}**")
                st.markdown(f"Applied: {app['applied_at'][:10]}")
            
            # Expandable details
            with st.expander("View Details"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Professional Info:**")
                    st.markdown(f"- Total Experience: {app['total_experience']}")
                    st.markdown(f"- Current Salary: {app['current_salary']}")
                    st.markdown(f"- Expected Salary: {app['expected_salary']}")
                
                with col2:
                    st.markdown("**Skills Analysis:**")
                    if app['matched_skills']:
                        st.markdown(f"- Matched Skills: {', '.join(app['matched_skills'])}")
                    if app['missing_skills']:
                        st.markdown(f"- Missing Skills: {', '.join(app['missing_skills'])}")
                
                if app['experience_summary']:
                    st.markdown("**Experience Summary:**")
                    st.markdown(app['experience_summary'])
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    elif page == "Analytics":
        st.markdown("## Analytics Dashboard")
        
        applications = get_applications_for_hr(st.session_state.user['id'])
        
        if not applications:
            st.info("No data available for analytics.")
            return
        
        # Create charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Application status distribution
            status_counts = {}
            for app in applications:
                status = app['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            fig_status = px.pie(
                values=list(status_counts.values()),
                names=list(status_counts.keys()),
                title="Application Status Distribution"
            )
            st.plotly_chart(fig_status, use_container_width=True)
        
        with col2:
            # Score distribution
            scores = [app['match_score'] for app in applications]
            fig_scores = px.histogram(
                x=scores,
                nbins=10,
                title="Match Score Distribution",
                labels={'x': 'Match Score', 'y': 'Count'}
            )
            st.plotly_chart(fig_scores, use_container_width=True)
        
        # Applications over time
        df_apps = pd.DataFrame(applications)
        df_apps['applied_date'] = pd.to_datetime(df_apps['applied_at']).dt.date
        apps_by_date = df_apps.groupby('applied_date').size().reset_index(name='count')
        
        fig_timeline = px.line(
            apps_by_date,
            x='applied_date',
            y='count',
            title="Applications Over Time"
        )
        st.plotly_chart(fig_timeline, use_container_width=True)

def main():
    """Main application function."""
    st.set_page_config(page_title="CV Analyzer", page_icon="📄", layout="wide")
    
    # Initialize database
    init_database()
    
    # Set custom styling
    set_custom_styling()
    
    # Check if user is logged in
    if 'user' not in st.session_state:
        login_page()
    else:
        # Display appropriate dashboard based on user role
        if st.session_state.user['role'] == 'hr':
            hr_dashboard()
        else:
            candidate_dashboard()
        
        # Logout button in sidebar
        st.sidebar.markdown("---")
        if st.sidebar.button("Logout"):
            # Clear session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()