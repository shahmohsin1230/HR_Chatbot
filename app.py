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
import matplotlib.pyplot as plt
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
    .api-key-container {
        background-color: #1a62c5;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
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
    """Extract work experience durations from the CV text."""
    # Use GPT-4o to extract work experience
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
            max_tokens=1000
        )
        result = response.choices[0].message.content
        experience_data = json.loads(result)
        return experience_data
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
    """Use GPT-4o to analyze a CV against a job description, including work experience consideration."""
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
            max_tokens=1000
        )
        result = response.choices[0].message.content
        return result
    except Exception as e:
        return f"Error analyzing CV: {str(e)}"

def generate_personalized_feedback(cv_text, job_description, analysis_result, client):
    """Generate detailed personalized feedback for a specific CV."""
    try:
        # Parse the analysis result if it's a string
        if isinstance(analysis_result, str):
            analysis_result = json.loads(analysis_result)
        
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

def generate_interview_questions(cv_text, job_description, analysis_result, client):
    """Generate relevant interview questions and expected answers based on the CV and job requirements."""
    try:
        # Parse the analysis result if it's a string
        if isinstance(analysis_result, str):
            analysis_result = json.loads(analysis_result)
        
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

def create_gauge_chart(value, title, max_value=10):
    """Create a gauge chart for displaying scores."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'color': 'white', 'size': 16}},
        gauge={
            'axis': {'range': [0, max_value], 'tickcolor': 'white'},
            'bar': {'color': get_score_color(value)},
            'steps': [
                {'range': [0, 4], 'color': 'rgba(239, 83, 80, 0.2)'},
                {'range': [4, 7], 'color': 'rgba(255, 205, 86, 0.2)'},
                {'range': [7, 10], 'color': 'rgba(76, 175, 80, 0.2)'}
            ],
            'threshold': {
                'line': {'color': 'white', 'width': 4},
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    
    fig.update_layout(
        height=250, 
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': 'white'},
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
        line_color='rgba(255, 255, 255, 0.5)',
        fillcolor='rgba(255, 255, 255, 0.1)'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                tickfont=dict(color='white')
            ),
            angularaxis=dict(
                tickfont=dict(color='white')
            )
        ),
        showlegend=True,
        legend=dict(font=dict(color='white')),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=350,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    return fig

def create_skills_chart(matched_skills, missing_skills):
    """Create a horizontal bar chart showing matched vs missing skills."""
    all_skills = matched_skills + missing_skills
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
        font={'color': 'white'},
        height=max(250, 50 * len(all_skills)),  # Dynamic height based on number of skills
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    fig.update_traces(textposition='inside', textfont_color='white')
    
    return fig

def create_candidates_comparison_chart(results):
    """Create a horizontal bar chart comparing candidates by overall score."""
    # Sort results by score
    sorted_results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)
    
    # Extract names and scores
    names = [f"#{i+1}: {r['filename'].split('.')[0]}" for i, r in enumerate(sorted_results)]
    scores = [r.get('score', 0) for r in sorted_results]
    skills_scores = [r.get('skills_match_score', 0) for r in sorted_results]
    exp_scores = [r.get('experience_relevance_score', 0) for r in sorted_results]
    
    # Create a color scale - CHANGE THIS PART
    # Instead of using dynamic colors based on scores, use fixed colors for each category
    
    fig = go.Figure()
    
    # Add overall score bars with CONSISTENT COLOR
    fig.add_trace(go.Bar(
        y=names,
        x=scores,
        orientation='h',
        name='Overall Match',
        marker_color='rgb(76, 175, 80)',  # Fixed green color for all Overall Match bars
        text=[f"{s}/10" for s in scores],
        textposition='auto',
    ))
    
    # Add skills score bars
    fig.add_trace(go.Bar(
        y=names,
        x=skills_scores,
        orientation='h',
        name='Skills Match',
        marker_color='rgba(33, 150, 243, 0.8)',  # Blue color for Skills Match
        text=[f"{s}/10" for s in skills_scores],
        textposition='auto',
    ))
    
    # Add experience score bars
    fig.add_trace(go.Bar(
        y=names,
        x=exp_scores,
        orientation='h',
        name='Experience',
        marker_color='rgba(255, 152, 0, 0.8)',  # Orange color for Experience
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
        font={'color': 'white'},
        legend={'font': {'color': 'white'}},
        height=max(350, 60 * len(names)),  # Dynamic height based on number of candidates
        margin=dict(l=20, r=20, t=50, b=20),
        xaxis=dict(range=[0, 10])
    )
    
    return fig

def create_top_candidates_pie_chart(results):
    """Create a pie chart showing top candidates distribution by category."""
    # Categorize candidates by score
    excellent = sum(1 for r in results if r.get('score', 0) >= 8)
    good = sum(1 for r in results if 6 <= r.get('score', 0) < 8)
    average = sum(1 for r in results if 4 <= r.get('score', 0) < 6)
    poor = sum(1 for r in results if r.get('score', 0) < 4)
    
    # Create pie chart
    labels = ['Excellent (8-10)', 'Good (6-7)', 'Average (4-5)', 'Poor (0-3)']
    values = [excellent, good, average, poor]
    colors = ['rgb(76, 175, 80)', 'rgb(255, 205, 86)', 'rgb(255, 152, 0)', 'rgb(239, 83, 80)']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=.4,
        marker_colors=colors
    )])
    
    fig.update_layout(
        title='Candidates by Category',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': 'white'},
        height=350,
        margin=dict(l=20, r=20, t=50, b=20),
        legend={'font': {'color': 'white'}}
    )
    
    # Add count annotations
    fig.update_traces(
        textinfo='label+percent+value',
        textposition='inside',
        insidetextorientation='radial'
    )
    
    return fig

def main():
    set_custom_styling()
    
    # Initialize session states
    if 'api_key' not in st.session_state:
        st.session_state.api_key = ""
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
    
    st.markdown(
        """
        <div class="header-container">
            <h1>HR CV Ranking Bot</h1>
            <p>Upload job description and candidate CVs to rank them automatically</p>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    # API Key input section
    st.markdown('<div class="api-key-container">', unsafe_allow_html=True)
    api_key = st.text_input(
        "Enter your OpenAI API Key", 
        value=st.session_state.api_key,
        type="password",
        help="Your API key is stored only in your browser's session and is not saved on any server."
    )
    
    if api_key:
        st.session_state.api_key = api_key
        
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Check if API key is provided
    if not st.session_state.api_key:
        st.warning("Please enter your OpenAI API key to use this application.")
        st.info("Your API key will be used to analyze CVs using GPT-4o. It is stored only in your browser session.")
        return
    
    # Initialize OpenAI client
    try:
        client = OpenAI(api_key=st.session_state.api_key)
    except Exception as e:
        st.error(f"Error initializing OpenAI client: {str(e)}")
        return
    
    # Create tabs for main workflow
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload & Analyze", "📊 Rankings", "📝 Feedback", "🎯 Interview Questions"])
    
    # Tab 1: Upload & Analyze
    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        with st.form("cv_ranking_form"):
            job_description = st.text_area("Enter Job Description", height=200, 
                                         value=st.session_state.job_description)
            uploaded_files = st.file_uploader("Upload Candidate CVs (PDF format)", 
                                             type="pdf", accept_multiple_files=True)
            submit_button = st.form_submit_button("Analyze CVs")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
        if submit_button and job_description and uploaded_files:
            st.session_state.job_description = job_description
            
            with st.spinner("Analyzing CVs... This may take a few minutes depending on the number of files."):
                results = []
                cv_texts = {}
                
                # Progress bar
                progress_bar = st.progress(0)
                
                # Process each CV
                for i, uploaded_file in enumerate(uploaded_files):
                    progress_text = f"Processing CV {i+1}/{len(uploaded_files)}: {uploaded_file.name}"
                    st.write(progress_text)
                    progress_bar.progress((i + 0.5) / len(uploaded_files))
                    
                    # Create a temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                        temp_file.write(uploaded_file.getvalue())
                        temp_path = temp_file.name
                    
                    # Extract text from PDF
                    cv_text = extract_text_from_pdf(temp_path)
                    cv_texts[uploaded_file.name] = cv_text
                    
                    # Extract work experience
                    work_experience_data = extract_work_experience(cv_text, client)
                    
                    # Calculate total experience
                    experience_data = calculate_total_experience(work_experience_data)
                    
                    # Analyze CV
                    analysis_result = analyze_cv(cv_text, job_description, work_experience_data, client)
                    
                    # Try to parse the JSON response
                    try:
                        result_dict = json.loads(analysis_result)
                        result_dict["filename"] = uploaded_file.name
                        result_dict["total_experience"] = experience_data["formatted"]
                        result_dict["experience_months"] = experience_data["total_months"]
                        results.append(result_dict)
                    except json.JSONDecodeError:
                        st.error(f"Failed to parse analysis for {uploaded_file.name}: {analysis_result}")
                        results.append({
                            "filename": uploaded_file.name,
                            "score": 0,
                            "explanation": "Error analyzing this CV",
                            "key_skills_matched": [],
                            "missing_skills": [],
                            "total_experience": "Unknown",
                            "experience_months": 0
                        })
                    
                    # Clean up temporary file
                    os.unlink(temp_path)
                    
                    # Add a small delay to avoid rate limits
                    time.sleep(1)
                    
                    # Update progress
                    progress_bar.progress((i + 1) / len(uploaded_files))
                
                # Sort results by score in descending order
                results.sort(key=lambda x: x.get("score", 0), reverse=True)
                
                # Store results and CV texts in session state
                st.session_state.results = results
                st.session_state.cv_data = cv_texts
                
                # Complete progress
                progress_bar.progress(1.0)
                
                # Success message
                st.success(f"✅ Analysis complete! Analyzed {len(results)} CVs.")
                st.balloons()
    
    # Tab 2: Rankings
    with tab2:
        if st.session_state.results:
            # Summary metrics at the top
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📊 Summary Dashboard")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Display pie chart for candidate distribution
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                pie_fig = create_top_candidates_pie_chart(st.session_state.results)
                st.plotly_chart(pie_fig, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with col2:
                # Key metrics
                st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                st.metric("Total Candidates", len(st.session_state.results))
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                top_candidate = st.session_state.results[0] if st.session_state.results else {}
                st.metric("Top Candidate Score", f"{top_candidate.get('score', 'N/A')}/10")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                avg_score = sum(r.get('score', 0) for r in st.session_state.results) / len(st.session_state.results) if st.session_state.results else 0
                st.metric("Average Score", f"{avg_score:.1f}/10")
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Candidate comparison chart
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("🔍 Candidate Comparison")
            comparison_fig = create_candidates_comparison_chart(st.session_state.results)
            st.plotly_chart(comparison_fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Individual candidate details
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("👤 Individual Candidate Details")
            
            # Create a selectbox for choosing candidates
            candidate_names = [f"#{i+1}: {r['filename']} (Score: {r['score']}/10)" 
                              for i, r in enumerate(st.session_state.results)]
            selected_candidate = st.selectbox("Select a candidate to view details", candidate_names)
            
            if selected_candidate:
                # Get the index of the selected candidate
                candidate_index = candidate_names.index(selected_candidate)
                candidate_data = st.session_state.results[candidate_index]
                
                # Display candidate details
                st.markdown(f"### {candidate_data['filename']}")
                
                # Create three columns for scores
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Overall score gauge
                    overall_gauge = create_gauge_chart(candidate_data.get('score', 0), 'Overall Match')
                    st.plotly_chart(overall_gauge, use_container_width=True)
                
                with col2:
                    # Skills match gauge
                    skills_gauge = create_gauge_chart(candidate_data.get('skills_match_score', 0), 'Skills Match')
                    st.plotly_chart(skills_gauge, use_container_width=True)
                
                with col3:
                    # Experience relevance gauge
                    exp_gauge = create_gauge_chart(candidate_data.get('experience_relevance_score', 0), 'Exp. Relevance')
                    st.plotly_chart(exp_gauge, use_container_width=True)
                
                # Display the radar chart
                radar_fig = create_radar_chart(candidate_data)
                st.plotly_chart(radar_fig, use_container_width=True)
                
                # Display matched and missing skills
                skills_fig = create_skills_chart(
                    candidate_data.get('key_skills_matched', []),
                    candidate_data.get('missing_skills', [])
                )
                st.plotly_chart(skills_fig, use_container_width=True)
                
                # Display explanation and experience summary
                st.markdown("### Analysis")
                st.markdown(f"**Explanation:** {candidate_data.get('explanation', 'N/A')}")
                st.markdown(f"**Work Experience:** {candidate_data.get('total_experience', 'N/A')}")
                st.markdown(f"**Experience Summary:** {candidate_data.get('experience_summary', 'N/A')}")
                
                # Add buttons for generating feedback and interview questions
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button(f"Generate Feedback for {candidate_data['filename'].split('.')[0]}", key=f"feedback_{candidate_index}"):
                        with st.spinner("Generating personalized feedback..."):
                            # Get CV text
                            cv_text = st.session_state.cv_data.get(candidate_data['filename'], "")
                            
                            # Generate feedback
                            try:
                                client = OpenAI(api_key=st.session_state.api_key)
                                feedback = generate_personalized_feedback(
                                    cv_text, 
                                    st.session_state.job_description, 
                                    candidate_data,
                                    client
                                )
                                st.session_state.generated_feedback[candidate_data['filename']] = feedback
                                st.success("Feedback generated! Go to the Feedback tab to view.")
                            except Exception as e:
                                st.error(f"Error generating feedback: {str(e)}")
                
                with col2:
                    if st.button(f"Generate Interview Questions for {candidate_data['filename'].split('.')[0]}", key=f"questions_{candidate_index}"):
                        with st.spinner("Generating interview questions..."):
                            # Get CV text
                            cv_text = st.session_state.cv_data.get(candidate_data['filename'], "")
                            
                            # Generate interview questions
                            try:
                                client = OpenAI(api_key=st.session_state.api_key)
                                questions = generate_interview_questions(
                                    cv_text, 
                                    st.session_state.job_description, 
                                    candidate_data,
                                    client
                                )
                                st.session_state.interview_questions[candidate_data['filename']] = questions
                                st.success("Interview questions generated! Go to the Interview Questions tab to view.")
                            except Exception as e:
                                st.error(f"Error generating interview questions: {str(e)}")
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No analysis results yet. Please upload CVs and job description on the Upload & Analyze tab.")
    
    # Tab 3: Feedback
    with tab3:
        if st.session_state.generated_feedback:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📝 Personalized Candidate Feedback")
            
            # Create a selectbox for choosing candidates
            candidate_options = list(st.session_state.generated_feedback.keys())
            selected_feedback_candidate = st.selectbox(
                "Select a candidate to view feedback", 
                candidate_options,
                key="feedback_candidate_select"
            )
            
            if selected_feedback_candidate and selected_feedback_candidate in st.session_state.generated_feedback:
                # Display the feedback
                st.markdown("### Feedback for: " + selected_feedback_candidate.split('.')[0])
                st.markdown(st.session_state.generated_feedback[selected_feedback_candidate])
                
                # Add an option to download the feedback
                feedback_text = st.session_state.generated_feedback[selected_feedback_candidate]
                st.download_button(
                    label="Download Feedback as Text",
                    data=feedback_text,
                    file_name=f"feedback_{selected_feedback_candidate.split('.')[0]}.txt",
                    mime="text/plain"
                )
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No feedback generated yet. Generate feedback for candidates on the Rankings tab.")
    
    # Tab 4: Interview Questions
    with tab4:
        if st.session_state.interview_questions:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("🎯 Interview Questions")
            
            # Create a selectbox for choosing candidates
            candidate_options = list(st.session_state.interview_questions.keys())
            selected_questions_candidate = st.selectbox(
                "Select a candidate to view interview questions", 
                candidate_options,
                key="questions_candidate_select"
            )
            
            if selected_questions_candidate and selected_questions_candidate in st.session_state.interview_questions:
                # Display the interview questions
                st.markdown("### Interview Questions for: " + selected_questions_candidate.split('.')[0])
                st.markdown(st.session_state.interview_questions[selected_questions_candidate])
                
                # Add an option to download the interview questions
                questions_text = st.session_state.interview_questions[selected_questions_candidate]
                st.download_button(
                    label="Download Interview Questions as Text",
                    data=questions_text,
                    file_name=f"questions_{selected_questions_candidate.split('.')[0]}.txt",
                    mime="text/plain"
                )
            
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No interview questions generated yet. Generate questions for candidates on the Rankings tab.")
    
    # Footer
    st.markdown("""
    <div style="text-align: center; margin-top: 30px; padding: 20px; color: #ccc;">
        <p>HR CV Ranking Bot - Powered by OpenAI GPT-4o</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()