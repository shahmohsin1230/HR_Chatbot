import streamlit as st
import os
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
from openai import OpenAI

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
    .metric-container {
        background-color: #2570d4;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
        color: black;
    }
    .feedback-textarea {
        border: 1px solid #3a78d9;
        border-radius: 5px;
        padding: 10px;
        width: 100%;
        background-color: #1a62c5;
        color: black;
    }
    .skills-matched {
        color: #006400;
        font-weight: 500;
    }
    .skills-missing {
        color: #8b0000;
        font-weight: 500;
    }
    .chart-container {
        background-color: #2570d4;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
    }
    /* Make sure all text is black */
    p, h1, h2, h3, h4, h5, h6, li, label, span {
        color: black !important;
    }
    /* Make buttons more visible on blue background */
    .stButton>button {
        background-color: #ffffff;
        color: #0f55b8;
        border: none;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #e6e6e6;
        color: #0f55b8;
    }
    /* Style select boxes for better visibility */
    .stSelectbox [data-baseweb="select"] {
        background-color: #2570d4;
        color: black;
    }
    /* Style text inputs and text areas */
    .stTextInput>div>div>input, .stTextArea textarea {
        background-color: #2570d4;
        color: black;
        border: 1px solid #3a78d9;
    }
    /* Style dataframe for blue background */
    .dataframe {
        background-color: #2570d4;
        color: black;
    }
    .dataframe th {
        background-color: #1a62c5;
        color: black;
    }
    /* Style tabs for blue background */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #2570d4;
        color: black;
        border-radius: 4px 4px 0 0;
        padding: 10px 16px;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff;
        color: #0f55b8 !important;
    }
    /* API key input styling */
    .api-key-container {
        background-color: #1a62c5;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
    }
    </style>
    """, unsafe_allow_html=True)

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
        # Return a placeholder message if PDF parsing fails
        print(f"Error parsing PDF: {str(e)}")
        return f"[Error extracting PDF content: {str(e)}. Please check if this is a valid PDF file.]"

def extract_work_experience(cv_text, client):
    """Extract work experience durations from the CV text with improved error handling."""
    # Use OpenAI to extract work experience
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
            model="gpt-4o",
            temperature=0.2,
            max_tokens=1000,
            response_format={"type": "json_object"}  # Force JSON response format
        )
        result = response.choices[0].message.content
        
        # Ensure we have valid JSON
        try:
            experience_data = json.loads(result)
            return experience_data
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            # Fallback to empty work experience
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
            # Parse start date
            start_date_str = entry.get("start_date")
            if not start_date_str:
                continue
                
            # Try to parse the date
            try:
                start_date = parser.parse(start_date_str).date()
            except:
                # If parsing fails, try to extract year and month
                match = re.search(r'(\d{4})[-/]?(\d{1,2})', start_date_str)
                if match:
                    year, month = match.groups()
                    start_date = datetime.date(int(year), int(month), 1)
                else:
                    continue
            
            # Parse end date
            end_date_str = entry.get("end_date", "")
            if end_date_str.lower() in ["present", "current", "now"]:
                end_date = today
            else:
                try:
                    end_date = parser.parse(end_date_str).date()
                except:
                    # If parsing fails, try to extract year and month
                    match = re.search(r'(\d{4})[-/]?(\d{1,2})', end_date_str)
                    if match:
                        year, month = match.groups()
                        end_date = datetime.date(int(year), int(month), 1)
                    else:
                        continue
            
            # Calculate duration in months
            delta = relativedelta(end_date, start_date)
            months = delta.years * 12 + delta.months
            total_months += months
            
        except Exception as e:
            print(f"Error calculating experience for entry {entry}: {str(e)}")
            continue
    
    # Convert to years and months
    years = total_months // 12
    remaining_months = total_months % 12
    
    return {
        "total_months": total_months,
        "years": years,
        "months": remaining_months,
        "formatted": f"{years} years, {remaining_months} months"
    }

def analyze_cv(cv_text, job_description, work_experience_data, client):
    """Use OpenAI to analyze a CV against a job description, with improved error handling."""
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
            model="gpt-4o",
            temperature=0.2,
            max_tokens=1000,
            response_format={"type": "json_object"}  # Force JSON response format
        )
        result = response.choices[0].message.content
        
        # Validate JSON response
        try:
            json_result = json.loads(result)
            return json_result
        except json.JSONDecodeError:
            print(f"JSON decode error in analysis result: {result}")
            # Create a fallback response
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

def generate_personalized_feedback(cv_text, job_description, analysis_result, client):
    """Generate detailed personalized feedback for a specific CV."""
    try:
        # Ensure analysis_result is a dictionary
        if isinstance(analysis_result, str):
            try:
                analysis_result = json.loads(analysis_result)
            except json.JSONDecodeError:
                # If we can't parse it, create a minimal structure
                analysis_result = {
                    "score": 5,
                    "skills_match_score": 5,
                    "experience_relevance_score": 5,
                    "key_skills_matched": [],
                    "missing_skills": []
                }
        
        prompt = f"""
        You are an expert HR advisor. Based on the CV and job description below, provide personalized feedback to the candidate.
        
        Job Description:
        {job_description}
        
        Candidate CV:
        {cv_text}
        
        Analysis Results:
        - Match Score: {analysis_result.get('score', 'N/A')}/10
        - Skills Match Score: {analysis_result.get('skills_match_score', 'N/A')}/10
        - Experience Relevance Score: {analysis_result.get('experience_relevance_score', 'N/A')}/10
        - Matched Skills: {', '.join(analysis_result.get('key_skills_matched', []))}
        - Missing Skills: {', '.join(analysis_result.get('missing_skills', []))}
        
        Create personalized feedback with the following sections:
        1. Strengths: What makes this candidate suitable for the position
        2. Areas for Improvement: What skills or experiences they should develop
        3. Resume Enhancement Tips: How to better highlight their relevant experiences 
        4. Interview Preparation: Key points to emphasize during interviews
        
        Keep your response well-structured but conversational and constructive. Aim to be helpful and provide actionable advice.
        """
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.5,
            max_tokens=1500
        )
        result = response.choices[0].message.content
        return result
    except Exception as e:
        return f"Error generating personalized feedback: {str(e)}"

def create_gauge_chart(value, title, max_value=10):
    """Create a gauge chart for displaying scores."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'color': 'black', 'size': 16}},  # Changed color to black
        gauge={
            'axis': {'range': [0, max_value], 'tickcolor': 'black'},  # Changed color to black
            'bar': {'color': get_score_color(value)},
            'steps': [
                {'range': [0, 4], 'color': 'rgba(239, 83, 80, 0.2)'},
                {'range': [4, 7], 'color': 'rgba(255, 205, 86, 0.2)'},
                {'range': [7, 10], 'color': 'rgba(76, 175, 80, 0.2)'}
            ],
            'threshold': {
                'line': {'color': 'black', 'width': 4},  # Changed color to black
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    
    fig.update_layout(
        height=250, 
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': 'black'},  # Changed color to black
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return fig

def get_score_color(score):
    """Get color based on score value."""
    if score >= 8:
        return 'rgb(76, 175, 80)'  # Green
    elif score >= 6:
        return 'rgb(255, 205, 86)'  # Yellow
    else:
        return 'rgb(239, 83, 80)'   # Red

def create_radar_chart(candidate_data):
    """Create a radar chart showing candidate skills vs job requirements."""
    # Create data for radar chart
    categories = ['Overall Match', 'Skills Match', 'Experience Relevance']
    values = [
        candidate_data.get('score', 0),
        candidate_data.get('skills_match_score', 0),
        candidate_data.get('experience_relevance_score', 0)
    ]
    
    # Create radar chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name='Candidate',
        line_color='rgb(76, 175, 80)',
        fillcolor='rgba(76, 175, 80, 0.3)'
    ))
    
    fig.add_trace(go.Scatterpolar(
        r=[10, 10, 10],
        theta=categories,
        fill='toself',
        name='Ideal Candidate',
        line_color='rgba(0, 0, 0, 0.5)',  # Changed color to black
        fillcolor='rgba(0, 0, 0, 0.1)'  # Changed color to black
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                tickfont=dict(color='black')  # Changed color to black
            ),
            angularaxis=dict(
                tickfont=dict(color='black')  # Changed color to black
            )
        ),
        showlegend=True,
        legend=dict(font=dict(color='black')),  # Changed color to black
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=350,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    return fig

def create_skills_chart(matched_skills, missing_skills):
    """Create a horizontal bar chart showing matched vs missing skills."""
    all_skills = matched_skills + missing_skills
    
    # Handle the case with no skills identified
    if not all_skills:
        all_skills = ["No specific skills identified"]
        skill_status = ["Missing"]
    else:
        skill_status = ['Matched'] * len(matched_skills) + ['Missing'] * len(missing_skills)
    
    df = pd.DataFrame({
        'Skill': all_skills,
        'Status': skill_status,
        'Value': [1] * len(all_skills)  # Each skill has equal weight for visualization
    })
    
    # Create a color map
    color_map = {'Matched': '#4caf50', 'Missing': '#f44336'}
    
    fig = px.bar(
        df, 
        y='Skill', 
        x='Value', 
        color='Status',
        color_discrete_map=color_map,
        orientation='h',
        title='Skills Assessment',
        text='Status'
    )
    
    fig.update_layout(
        xaxis_title="",
        yaxis_title="",
        xaxis={'visible': False},
        showlegend=True,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': 'black'},  # Changed color to black
        height=max(250, 50 * len(all_skills)),  # Dynamic height based on number of skills
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    fig.update_traces(textposition='inside', textfont_color='white')
    
    return fig

def create_candidates_comparison_chart(results):
    """Create a horizontal bar chart comparing candidates by overall score."""
    # Check if results are empty
    if not results:
        # Create a placeholder chart
        fig = go.Figure()
        fig.add_annotation(
            text="No candidates to compare",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="black")
        )
        fig.update_layout(
            height=350,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig
    
    # Sort results by score
    sorted_results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)
    
    # Extract names and scores
    names = [f"#{i+1}: {r['filename'].split('.')[0]}" for i, r in enumerate(sorted_results)]
    scores = [r.get('score', 0) for r in sorted_results]
    skills_scores = [r.get('skills_match_score', 0) for r in sorted_results]
    exp_scores = [r.get('experience_relevance_score', 0) for r in sorted_results]
    
    fig = go.Figure()
    
    # Add overall score bars with consistent color
    fig.add_trace(go.Bar(
        y=names,
        x=scores,
        orientation='h',
        name='Overall Match',
        marker_color='rgb(76, 175, 80)',  # Fixed green color
        text=[f"{s}/10" for s in scores],
        textposition='auto',
    ))
    
    # Add skills score bars
    fig.add_trace(go.Bar(
        y=names,
        x=skills_scores,
        orientation='h',
        name='Skills Match',
        marker_color='rgba(33, 150, 243, 0.8)',  # Blue color
        text=[f"{s}/10" for s in skills_scores],
        textposition='auto',
    ))
    
    # Add experience score bars
    fig.add_trace(go.Bar(
        y=names,
        x=exp_scores,
        orientation='h',
        name='Experience',
        marker_color='rgba(255, 152, 0, 0.8)',  # Orange color
        text=[f"{s}/10" for s in exp_scores],
        textposition='auto',
    ))
    
    # Update layout
    fig.update_layout(
        title='Candidate Comparison',
        xaxis_title='Score (0-10)',
        yaxis_title='Candidates',
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': 'black'},  # Changed color to black
        legend={'font': {'color': 'black'}},  # Changed color to black
        height=max(350, 60 * len(names)),  # Dynamic height based on number of candidates
        margin=dict(l=20, r=20, t=50, b=20),
        xaxis=dict(range=[0, 10])
    )
    
    return fig

def create_top_candidates_pie_chart(results):
    """Create a pie chart showing top candidates distribution by category."""
    # Check if results are empty
    if not results:
        # Create a placeholder chart
        fig = go.Figure()
        fig.add_annotation(
            text="No candidates to categorize",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False, 
            font=dict(size=20, color="black")
        )
        fig.update_layout(
            height=350,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig
    
    # Categorize candidates by score
    excellent = sum(1 for r in results if r.get('score', 0) >= 8)
    good = sum(1 for r in results if 6 <= r.get('score', 0) < 8)
    average = sum(1 for r in results if 4 <= r.get('score', 0) < 6)
    poor = sum(1 for r in results if r.get('score', 0) < 4)
    
    # Create pie chart
    labels = ['Excellent (8-10)', 'Good (6-7)', 'Average (4-5)', 'Poor (0-3)']
    values = [excellent, good, average, poor]
    colors = ['rgb(76, 175, 80)', 'rgb(255, 205, 86)', 'rgb(255, 152, 0)', 'rgb(239, 83, 80)']
    
    # Filter out categories with zero candidates
    non_zero_labels = []
    non_zero_values = []
    non_zero_colors = []
    
    for i, value in enumerate(values):
        if value > 0:
            non_zero_labels.append(labels[i])
            non_zero_values.append(value)
            non_zero_colors.append(colors[i])
    
    # If all categories are zero, add a placeholder
    if not non_zero_values:
        non_zero_labels = ['No candidates']
        non_zero_values = [1]
        non_zero_colors = ['gray']
    
    fig = go.Figure(data=[go.Pie(
        labels=non_zero_labels,
        values=non_zero_values,
        hole=.4,
        marker_colors=non_zero_colors
    )])
    
    fig.update_layout(
        title='Candidates by Category',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': 'black'},  # Changed color to black
        height=350,
        margin=dict(l=20, r=20, t=50, b=20),
        legend={'font': {'color': 'black'}}  # Changed color to black
    )
    
    # Add count annotations
    fig.update_traces(
        textinfo='label+percent+value',
        textposition='inside',
        insidetextorientation='radial'
    )
    
    return fig

def generate_interview_questions(cv_text, job_description, analysis_result, client):
    """Generate relevant interview questions and expected answers based on the CV and job requirements."""
    try:
        # Ensure analysis_result is a dictionary
        if isinstance(analysis_result, str):
            try:
                analysis_result = json.loads(analysis_result)
            except json.JSONDecodeError:
                # If we can't parse it, create a minimal structure
                analysis_result = {
                    "score": 5,
                    "key_skills_matched": [],
                    "missing_skills": []
                }
        
        prompt = f"""
        You are an expert HR interviewer. Based on the CV and job description below, create a set of interview questions
        with expected answers that would help assess this candidate thoroughly.
        
        Job Description:
        {job_description}
        
        Candidate CV:
        {cv_text}
        
        Analysis Results:
        - Match Score: {analysis_result.get('score', 'N/A')}/10
        - Matched Skills: {', '.join(analysis_result.get('key_skills_matched', []))}
        - Missing Skills: {', '.join(analysis_result.get('missing_skills', []))}
        
        Generate 10 interview questions with expected answers across these categories:
        1. Technical Skills Assessment (questions specific to the technical skills in the CV)
        2. Experience Validation (questions about specific projects or roles mentioned in the CV)
        3. Behavioral Questions (relevant to the job requirements)
        4. Problem-Solving (scenario-based questions related to the role)
        5. Cultural Fit & Motivation
        
        For each question:
        - Provide the rationale for asking this question
        - Describe what a strong answer would include
        - Include red flags to watch for
        
        Format your response in clear sections with markdown formatting.
        """
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.5,
            max_tokens=2000
        )
        result = response.choices[0].message.content
        return result
    except Exception as e:
        return f"Error generating interview questions: {str(e)}"

def initialize_session_state():
    """Initialize all session state variables."""
    if 'openai_api_key' not in st.session_state:
        st.session_state.openai_api_key = ""
    if 'client' not in st.session_state:
        st.session_state.client = None
    if 'cv_data' not in st.session_state:
        st.session_state.cv_data = {}
    if 'job_description' not in st.session_state:
        st.session_state.job_description = ""
    if 'results' not in st.session_state:
        st.session_state.results = []
    if 'feedback' not in st.session_state:
        st.session_state.feedback = {}
    if 'generated_feedback' not in st.session_state:
        st.session_state.generated_feedback = {}
    if 'interview_questions' not in st.session_state:
        st.session_state.interview_questions = {}
    if 'error_log' not in st.session_state:
        st.session_state.error_log = []
    # Sample job description for first-time users
    if 'sample_job_description' not in st.session_state:
        st.session_state.sample_job_description = """
        Job Title: Full Stack Developer
        
        About the Role:
        We are looking for a skilled Full Stack Developer to join our innovative team. You will be responsible for developing and maintaining web applications, working on both front-end and back-end code.
        
        Key Responsibilities:
        - Develop front-end website architecture using React.js and Next.js
        - Design and build backend systems using Python/Django
        - Work with databases and integrate with external APIs
        - Ensure cross-platform optimization and responsiveness of applications
        - Implement security and data protection measures
        - Collaborate with other team members and stakeholders
        
        Requirements:
        - 2+ years of experience in full stack development
        - Proficiency in JavaScript, HTML, CSS, and React.js framework
        - Experience with Next.js and server-side rendering
        - Strong knowledge of Python and Django web framework
        - Familiarity with database technologies (SQL, NoSQL)
        - Understanding of server-side CSS preprocessors
        - Knowledge of code versioning tools (Git)
        - Experience with API integration
        - Familiarity with AWS cloud services
        - Understanding of AI tools and integration is a plus
        - Excellent problem-solving and communication skills
        """
def main():
    """Main application function."""
    # Initialize session state
    initialize_session_state()
    
    # Apply custom styling
    set_custom_styling()
    
    # Create header
    st.markdown('<div class="header-container"><h1>CV Analyzer</h1><p>Upload CVs and match them against job descriptions</p></div>', unsafe_allow_html=True)
    
    # API Key input
    with st.expander("API Settings", expanded=not st.session_state.openai_api_key):
        st.markdown('<div class="api-key-container">', unsafe_allow_html=True)
        api_key = st.text_input("Enter your OpenAI API Key:", value=st.session_state.openai_api_key, type="password")
        if api_key:
            st.session_state.openai_api_key = api_key
            try:
                st.session_state.client = OpenAI(api_key=api_key)
                st.success("API key set successfully!")
            except Exception as e:
                st.error(f"Error with API key: {str(e)}")
                st.session_state.client = None
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Main interface with tabs
    tabs = st.tabs(["Analysis", "Dashboard", "Comparison", "Help"])
    
    with tabs[0]:  # Analysis Tab
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Step 1: Enter Job Description")
            
            # Job description input
            job_description = st.text_area(
                "Job Description:", 
                value=st.session_state.job_description if st.session_state.job_description else st.session_state.sample_job_description,
                height=300
            )
            if job_description:
                st.session_state.job_description = job_description
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Step 2: Upload CVs")
            
            # CV upload
            uploaded_files = st.file_uploader("Upload CVs (PDF format)", type="pdf", accept_multiple_files=True)
            
            if uploaded_files:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Process each CV
                for i, file in enumerate(uploaded_files):
                    if not st.session_state.client:
                        st.error("Please enter a valid OpenAI API key first.")
                        break
                        
                    status_text.text(f"Processing {file.name}... ({i+1}/{len(uploaded_files)})")
                    
                    # Extract text from PDF
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                        temp_file.write(file.read())
                        temp_file_path = temp_file.name
                    
                    # Extract and process CV text
                    try:
                        cv_text = extract_text_from_pdf(temp_file_path)
                        os.unlink(temp_file_path)  # Clean up temp file
                        
                        # Store CV text
                        st.session_state.cv_data[file.name] = cv_text
                        
                        # Extract work experience
                        work_experience = extract_work_experience(cv_text, st.session_state.client)
                        
                        # Analyze CV against job description
                        result = analyze_cv(cv_text, job_description, work_experience, st.session_state.client)
                        result['filename'] = file.name
                        
                        # Check if CV is already in results, update if exists
                        existing_index = next((i for i, r in enumerate(st.session_state.results) if r['filename'] == file.name), None)
                        if existing_index is not None:
                            st.session_state.results[existing_index] = result
                        else:
                            st.session_state.results.append(result)
                            
                    except Exception as e:
                        error_msg = f"Error processing {file.name}: {str(e)}"
                        st.error(error_msg)
                        st.session_state.error_log.append(error_msg)
                    
                    # Update progress
                    progress_bar.progress((i + 1) / len(uploaded_files))
                
                status_text.text(f"Processed {len(uploaded_files)} CV(s) successfully!")
                time.sleep(1)
                status_text.empty()
                progress_bar.empty()
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Display results if available
        if st.session_state.results:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Analysis Results")
            
            # Create selectbox for choosing CV
            cv_options = [f"{r['filename']} (Score: {r['score']}/10)" for r in st.session_state.results]
            selected_cv = st.selectbox("Select a CV to view detailed analysis:", cv_options)
            
            if selected_cv:
                # Get the selected CV data
                selected_filename = selected_cv.split(" (Score")[0]
                selected_data = next((r for r in st.session_state.results if r['filename'] == selected_filename), None)
                
                if selected_data:
                    # Display scores and charts
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                        st.plotly_chart(create_gauge_chart(selected_data.get('score', 0), "Overall Match Score"), use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                        st.plotly_chart(create_radar_chart(selected_data), use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Display skills chart
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    matched_skills = selected_data.get('key_skills_matched', [])
                    missing_skills = selected_data.get('missing_skills', [])
                    
                    # Display skills match visualization
                    st.plotly_chart(create_skills_chart(matched_skills, missing_skills), use_container_width=True)
                    
                    # Show matched and missing skills
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("### Skills Matched")
                        if matched_skills:
                            for skill in matched_skills:
                                st.markdown(f"<p class='skills-matched'>✓ {skill}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown("<p>No matched skills identified</p>", unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown("### Skills Missing")
                        if missing_skills:
                            for skill in missing_skills:
                                st.markdown(f"<p class='skills-missing'>✗ {skill}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown("<p>No missing skills identified</p>", unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Display explanation
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Analysis Summary")
                    st.markdown(f"**Overall Score:** {selected_data.get('score', 0)}/10")
                    st.markdown(f"**Skills Match Score:** {selected_data.get('skills_match_score', 0)}/10")
                    st.markdown(f"**Experience Relevance Score:** {selected_data.get('experience_relevance_score', 0)}/10")
                    st.markdown(f"**Explanation:** {selected_data.get('explanation', 'No explanation available.')}")
                    
                    # Display experience summary
                    if 'experience_summary' in selected_data:
                        st.markdown(f"**Experience Summary:** {selected_data['experience_summary']}")
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Generate detailed feedback
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Personalized Feedback")
                    
                    if st.button("Generate Personalized Feedback", key=f"feedback_{selected_filename}"):
                        try:
                            with st.spinner("Generating personalized feedback..."):
                                cv_text = st.session_state.cv_data.get(selected_filename, "")
                                feedback = generate_personalized_feedback(
                                    cv_text, 
                                    st.session_state.job_description, 
                                    selected_data,
                                    st.session_state.client
                                )
                                st.session_state.generated_feedback[selected_filename] = feedback
                        except Exception as e:
                            st.error(f"Error generating feedback: {str(e)}")
                    
                    # Display feedback if available
                    if selected_filename in st.session_state.generated_feedback:
                        st.markdown(st.session_state.generated_feedback[selected_filename])
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Generate interview questions
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Interview Preparation")
                    
                    if st.button("Generate Interview Questions", key=f"questions_{selected_filename}"):
                        try:
                            with st.spinner("Generating interview questions..."):
                                cv_text = st.session_state.cv_data.get(selected_filename, "")
                                questions = generate_interview_questions(
                                    cv_text, 
                                    st.session_state.job_description, 
                                    selected_data,
                                    st.session_state.client
                                )
                                st.session_state.interview_questions[selected_filename] = questions
                        except Exception as e:
                            st.error(f"Error generating interview questions: {str(e)}")
                    
                    # Display interview questions if available
                    if selected_filename in st.session_state.interview_questions:
                        st.markdown(st.session_state.interview_questions[selected_filename])
                    st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[1]:  # Dashboard Tab
        if not st.session_state.results:
            st.info("Upload and analyze CVs to view the dashboard")
        else:
            # Create a dashboard with charts and analytics
            st.markdown('<div class="header-container"><h2>CV Analysis Dashboard</h2></div>', unsafe_allow_html=True)
            
            # Display metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                st.metric("Total CVs Analyzed", len(st.session_state.results))
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                if st.session_state.results:
                    avg_score = sum(r.get('score', 0) for r in st.session_state.results) / len(st.session_state.results)
                    st.metric("Average Match Score", f"{avg_score:.1f}/10")
                else:
                    st.metric("Average Match Score", "N/A")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col3:
                st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                if st.session_state.results:
                    top_score = max(r.get('score', 0) for r in st.session_state.results)
                    st.metric("Top Match Score", f"{top_score:.1f}/10")
                else:
                    st.metric("Top Match Score", "N/A")
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Create charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.plotly_chart(create_candidates_comparison_chart(st.session_state.results), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.plotly_chart(create_top_candidates_pie_chart(st.session_state.results), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Display top skills across all CVs
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Common Skills Across Candidates")
            
            all_matched_skills = []
            for result in st.session_state.results:
                all_matched_skills.extend(result.get('key_skills_matched', []))
            
            # Count frequencies
            skill_counts = {}
            for skill in all_matched_skills:
                if skill in skill_counts:
                    skill_counts[skill] += 1
                else:
                    skill_counts[skill] = 1
            
            # Sort by frequency
            sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
            
            if sorted_skills:
                # Display as a horizontal bar chart
                skills = [s[0] for s in sorted_skills[:10]]  # Top 10 skills
                counts = [s[1] for s in sorted_skills[:10]]
                
                df = pd.DataFrame({
                    'Skill': skills,
                    'Count': counts
                })
                
                fig = px.bar(
                    df, 
                    y='Skill', 
                    x='Count', 
                    orientation='h',
                    title='Top Skills Among Candidates',
                    text='Count'
                )
                
                fig.update_layout(
                    xaxis_title="Number of Candidates",
                    yaxis_title="",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font={'color': 'black'},
                    height=max(250, 40 * len(skills)),
                    margin=dict(l=20, r=20, t=50, b=20)
                )
                
                fig.update_traces(marker_color='#4caf50', textposition='outside')
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No common skills found across candidates")
            st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[2]:  # Comparison Tab
        if len(st.session_state.results) < 2:
            st.info("Upload at least two CVs to compare them")
        else:
            st.markdown('<div class="header-container"><h2>CV Comparison</h2></div>', unsafe_allow_html=True)
            
            # Allow selecting CVs to compare
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Select CVs to Compare")
            
            cv_options = [r['filename'] for r in st.session_state.results]
            
            col1, col2 = st.columns(2)
            with col1:
                cv1 = st.selectbox("First CV:", cv_options, key="cv1_select")
            with col2:
                remaining_options = [cv for cv in cv_options if cv != cv1]
                cv2 = st.selectbox("Second CV:", remaining_options, key="cv2_select")
            
            if cv1 and cv2:
                # Get data for selected CVs
                cv1_data = next((r for r in st.session_state.results if r['filename'] == cv1), None)
                cv2_data = next((r for r in st.session_state.results if r['filename'] == cv2), None)
                
                if cv1_data and cv2_data:
                    # Create comparison charts
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    
                    # Create radar chart for comparison
                    categories = ['Overall Match', 'Skills Match', 'Experience Relevance']
                    
                    fig = go.Figure()
                    
                    # Add first CV
                    fig.add_trace(go.Scatterpolar(
                        r=[
                            cv1_data.get('score', 0),
                            cv1_data.get('skills_match_score', 0),
                            cv1_data.get('experience_relevance_score', 0)
                        ],
                        theta=categories,
                        fill='toself',
                        name=cv1_data['filename'].split('.')[0],
                        line_color='rgb(76, 175, 80)'
                    ))
                    
                    # Add second CV
                    fig.add_trace(go.Scatterpolar(
                        r=[
                            cv2_data.get('score', 0),
                            cv2_data.get('skills_match_score', 0),
                            cv2_data.get('experience_relevance_score', 0)
                        ],
                        theta=categories,
                        fill='toself',
                        name=cv2_data['filename'].split('.')[0],
                        line_color='rgb(33, 150, 243)'
                    ))
                    
                    fig.update_layout(
                        polar=dict(
                            radialaxis=dict(
                                visible=True,
                                range=[0, 10],
                                tickfont=dict(color='black')
                            ),
                            angularaxis=dict(
                                tickfont=dict(color='black')
                            )
                        ),
                        showlegend=True,
                        legend=dict(font=dict(color='black')),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        height=400,
                        margin=dict(l=40, r=40, t=40, b=40)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Compare skills
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Skills Comparison")
                    
                    col1, col2 = st.columns(2)
                    
                    # CV1 skills
                    with col1:
                        st.markdown(f"### {cv1_data['filename'].split('.')[0]}")
                        st.markdown("#### Skills Matched")
                        cv1_matched = cv1_data.get('key_skills_matched', [])
                        if cv1_matched:
                            for skill in cv1_matched:
                                st.markdown(f"<p class='skills-matched'>✓ {skill}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown("<p>No matched skills identified</p>", unsafe_allow_html=True)
                        
                        st.markdown("#### Skills Missing")
                        cv1_missing = cv1_data.get('missing_skills', [])
                        if cv1_missing:
                            for skill in cv1_missing:
                                st.markdown(f"<p class='skills-missing'>✗ {skill}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown("<p>No missing skills identified</p>", unsafe_allow_html=True)
                    
                    # CV2 skills
                    with col2:
                        st.markdown(f"### {cv2_data['filename'].split('.')[0]}")
                        st.markdown("#### Skills Matched")
                        cv2_matched = cv2_data.get('key_skills_matched', [])
                        if cv2_matched:
                            for skill in cv2_matched:
                                st.markdown(f"<p class='skills-matched'>✓ {skill}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown("<p>No matched skills identified</p>", unsafe_allow_html=True)
                        
                        st.markdown("#### Skills Missing")
                        cv2_missing = cv2_data.get('missing_skills', [])
                        if cv2_missing:
                            for skill in cv2_missing:
                                st.markdown(f"<p class='skills-missing'>✗ {skill}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown("<p>No missing skills identified</p>", unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Summary comparison
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Summary Comparison")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"### {cv1_data['filename'].split('.')[0]}")
                        st.markdown(f"**Overall Score:** {cv1_data.get('score', 0)}/10")
                        st.markdown(f"**Skills Match:** {cv1_data.get('skills_match_score', 0)}/10")
                        st.markdown(f"**Experience:** {cv1_data.get('experience_relevance_score', 0)}/10")
                        st.markdown(f"**Summary:** {cv1_data.get('explanation', 'No summary available.')}")
                    
                    with col2:
                        st.markdown(f"### {cv2_data['filename'].split('.')[0]}")
                        st.markdown(f"**Overall Score:** {cv2_data.get('score', 0)}/10")
                        st.markdown(f"**Skills Match:** {cv2_data.get('skills_match_score', 0)}/10")
                        st.markdown(f"**Experience:** {cv2_data.get('experience_relevance_score', 0)}/10")
                        st.markdown(f"**Summary:** {cv2_data.get('explanation', 'No summary available.')}")
                    st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    
    with tabs[3]:  # Help Tab
        st.markdown('<div class="header-container"><h2>Help & Instructions</h2></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("How to Use This App")
        
        st.markdown("""
        ### Getting Started
        1. Enter your OpenAI API key in the API Settings section (necessary for CV analysis)
        2. Enter a job description or use the provided sample
        3. Upload one or more CVs in PDF format
        4. Wait for the analysis to complete
        
        ### Features
        - **Analysis Tab**: View detailed analysis of each CV, including skills match, experience relevance, and personalized feedback
        - **Dashboard Tab**: View aggregate statistics and comparisons across all uploaded CVs
        - **Comparison Tab**: Directly compare two candidates side-by-side
        
        ### Tips for Best Results
        - Provide a detailed job description with clear requirements
        - Use PDF CVs with good text extraction quality
        - For best results, upload CVs in a standard format
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("About")
        
        st.markdown("""
        This CV Analyzer application helps HR professionals and recruiters streamline the candidate screening process.
        
        Features:
        - AI-powered CV analysis based on job requirements
        - Skills matching and experience validation
        - Interview question generation
        - Personalized candidate feedback
        - Visual comparisons and insights
        
        The app uses OpenAI's GPT models to analyze CV content against job descriptions, providing objective scoring and recommendations.
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("FAQ")
        
        expander1 = st.expander("Why do I need an OpenAI API key?")
        expander1.markdown("""
        This application uses OpenAI's GPT models to analyze CV content, extract work experience, and generate personalized feedback.
        The API key is required to access these AI capabilities. Your API key is used only within this application and is not stored permanently.
        """)
        
        expander2 = st.expander("How is the match score calculated?")
        expander2.markdown("""
        The match score is calculated by analyzing several factors:
        - Skills match: How well the candidate's skills align with the job requirements
        - Experience relevance: How relevant the candidate's work experience is to the role
        - Experience duration: Whether the candidate has sufficient experience in relevant areas
        
        The AI considers both explicit skills mentioned and implicit capabilities that can be inferred from the CV.
        """)
        
        expander3 = st.expander("Are my CV files and data secure?")
        expander3.markdown("""
        Yes. Your files are processed temporarily and are not stored permanently after analysis.
        The application runs locally in your browser, and data is sent to OpenAI only for analysis purposes.
        No CV data is retained after you close the application or refresh the browser.
        """)
        
        expander4 = st.expander("Can the app analyze CVs in languages other than English?")
        expander4.markdown("""
        Yes, the application can analyze CVs in multiple languages, though performance may be best with English content.
        The OpenAI models used for analysis have multilingual capabilities, but for optimal results with non-English CVs,
        consider providing the job description in the same language.
        """)
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()