# CV Analyzer

An AI-powered web application that helps HR professionals and recruiters streamline the candidate screening process by automatically analyzing CVs against job descriptions using OpenAI's GPT models.

## Features

- **AI-Powered CV Analysis**: Automatically analyze CVs against job descriptions with detailed scoring
- **Skills Matching**: Identify matched and missing skills for each candidate
- **Experience Validation**: Assess work experience relevance and duration
- **Visual Dashboard**: Interactive charts and comparisons across all candidates
- **Personalized Feedback**: Generate detailed feedback for candidates
- **Interview Questions**: Create tailored interview questions based on CV analysis
- **Side-by-Side Comparison**: Compare multiple candidates directly
- **Responsive UI**: Modern, blue-themed interface with interactive visualizations

## Screenshots

The application features:
- Clean, professional blue-themed interface
- Interactive charts and visualizations using Plotly
- Comprehensive scoring with gauge charts and radar plots
- Skills assessment with color-coded matching
- Candidate comparison tools

## Installation

### Prerequisites

- Python 3.7 or higher
- OpenAI API key

### Setup

1. **Clone or download the application files**
   ```bash
   # If using git
   git clone <repository-url>
   cd cv-analyzer
   
   # Or download the files directly
   ```

2. **Install required dependencies**
   ```bash
   pip install streamlit pandas PyPDF2 python-dateutil plotly openai
   ```

3. **Run the application**
   ```bash
   streamlit run app.py
   ```

4. **Open your browser**
   - The application will automatically open at `http://localhost:8501`
   - If it doesn't open automatically, navigate to the URL shown in your terminal

## Usage

### Getting Started

1. **API Setup**
   - Click on "API Settings" section
   - Enter your OpenAI API key
   - The key is used only for this session and not stored permanently

2. **Job Description**
   - Enter your job description in the text area
   - A sample job description is provided for testing
   - Be specific about requirements for better matching results

3. **Upload CVs**
   - Upload one or more PDF files containing candidate CVs
   - The application will process each CV automatically
   - Progress is shown during processing

### Analysis Features

#### Analysis Tab
- View detailed analysis for each CV
- See overall match scores, skills match, and experience relevance
- Generate personalized feedback for candidates
- Create tailored interview questions
- Visual representations with gauge charts and radar plots

#### Dashboard Tab
- Overview of all analyzed CVs
- Average scores and top performers
- Candidate categorization (Excellent, Good, Average, Poor)
- Common skills analysis across all candidates

#### Comparison Tab
- Side-by-side comparison of any two candidates
- Radar chart comparisons
- Skills matching comparison
- Summary comparison with scores and explanations

## Scoring System

The application uses a 10-point scoring system across three dimensions:

- **Overall Match Score**: Comprehensive assessment of candidate fit
- **Skills Match Score**: How well candidate skills align with job requirements
- **Experience Relevance Score**: Relevance and duration of work experience

### Score Interpretation
- **8-10**: Excellent match - Strong candidate
- **6-7**: Good match - Suitable candidate with minor gaps
- **4-5**: Average match - Some relevant skills/experience
- **0-3**: Poor match - Significant gaps in requirements

## Dependencies

The application requires the following Python packages:

```
streamlit>=1.28.0
pandas>=1.5.0
PyPDF2>=3.0.0
python-dateutil>=2.8.0
plotly>=5.15.0
openai>=1.0.0
```

## Configuration

### OpenAI API Key
- Required for CV analysis functionality
- Can be obtained from [OpenAI's website](https://platform.openai.com/api-keys)
- Used only during your session, not stored permanently
- Supports all OpenAI models (application uses GPT-4)

### Supported File Formats
- **Input**: PDF files only
- **Output**: Interactive web interface with downloadable insights

## Troubleshooting

### Common Issues

1. **"Error with API key"**
   - Verify your OpenAI API key is valid
   - Ensure you have sufficient API credits
   - Check your internet connection

2. **"Error extracting PDF content"**
   - Ensure PDF files are not password-protected
   - Try with different PDF files to isolate the issue
   - Some scanned PDFs may not extract text properly

3. **Application won't start**
   - Verify all dependencies are installed: `pip list`
   - Check Python version: `python --version`
   - Try reinstalling Streamlit: `pip install --upgrade streamlit`

4. **Slow analysis**
   - Analysis speed depends on OpenAI API response times
   - Large CVs or many files will take longer to process
   - Consider processing files in smaller batches

### Error Logs
The application maintains internal error logs accessible through the session state for debugging purposes.

## Security & Privacy

- **Data Privacy**: CV content is processed temporarily and not stored permanently
- **API Security**: OpenAI API key is used only within the application session
- **Local Processing**: Application runs locally in your browser
- **No Data Retention**: All data is cleared when you close or refresh the application

## Limitations

- **PDF Quality**: Text extraction quality depends on PDF format and quality
- **Language Support**: Optimized for English content, though multilingual support is available
- **API Dependency**: Requires active OpenAI API access for analysis features
- **File Size**: Very large PDF files may take longer to process

## Technical Details

### Architecture
- **Frontend**: Streamlit web application
- **AI Processing**: OpenAI GPT-4 models
- **Visualizations**: Plotly for interactive charts
- **PDF Processing**: PyPDF2 for text extraction
- **Date Processing**: python-dateutil for experience calculation

### Performance
- Processes multiple CVs in parallel where possible
- Progress tracking for long operations
- Optimized API calls to minimize latency
- Efficient caching of processed results during session

## Contributing

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is provided as-is for educational and professional use. Please ensure compliance with OpenAI's usage policies when using their API.

## Support

For issues or questions:
1. Check the FAQ section in the Help tab of the application
2. Review the troubleshooting section above
3. Ensure all dependencies are properly installed
4. Verify your OpenAI API key is valid and has sufficient credits


---

**Note**: This application requires an active OpenAI API key to function. API usage charges apply according to OpenAI's pricing structure.
