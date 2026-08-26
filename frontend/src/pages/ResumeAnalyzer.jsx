import { useState } from 'react';
import Markdown from 'react-markdown';
import { analyzeResume, analyzeResumeFile } from '../services/api';

function ResumeAnalyzer() {
    const [resumeText, setResumeText] = useState('');
    const [jobText, setJobText] = useState('');
    const [file, setFile] = useState(null);
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // FastAPI sends validation errors as an array of objects and HTTPException
    // details as a plain string, so handle both before falling back.
    const errorMessage = (err, fallback) => {
        const detail = err.response?.data?.detail;
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
        return fallback;
    };

    const handleAnalyzeText = async (e) => {
        e.preventDefault();
        if (!resumeText.trim() || !jobText.trim()) return;

        setError('');
        setLoading(true);
        setResults(null);

        try {
            const res = await analyzeResume(resumeText, jobText);
            setResults(res.data);
        } catch (err) {
            setError(errorMessage(err, 'Analysis failed. Please try again.'));
        } finally {
            setLoading(false);
        }
    };

    const handleAnalyzeFile = async () => {
        if (!file || !jobText.trim()) {
            setError('Please upload a resume file and enter a job description.');
            return;
        }

        setError('');
        setLoading(true);
        setResults(null);

        try {
            const res = await analyzeResumeFile(file, jobText);
            setResults(res.data);
        } catch (err) {
            setError(errorMessage(err, 'File analysis failed. Please try again.'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="analyzer">
            <h1>🔍 Resume Analyzer</h1>
            <p className="subtitle">
                Get AI-powered suggestions to improve your resume for any job
            </p>

            {error && <div className="error-msg">{error}</div>}

            <form onSubmit={handleAnalyzeText}>
                <div className="analyzer-grid">
                    <div className="form-group">
                        <label>📄 Paste Your Resume</label>
                        <textarea
                            placeholder="Paste your resume text here..."
                            value={resumeText}
                            onChange={(e) => setResumeText(e.target.value)}
                        />
                    </div>
                    <div className="form-group">
                        <label>💼 Job Description</label>
                        <textarea
                            placeholder="Paste the job description here..."
                            value={jobText}
                            onChange={(e) => setJobText(e.target.value)}
                        />
                    </div>
                </div>

                <div className="file-upload-area">
                    <label className="file-upload-label">
                        <input
                            type="file"
                            accept=".pdf,.docx,.txt"
                            onChange={(e) => setFile(e.target.files[0])}
                        />
                        📎 {file ? file.name : 'Or upload resume file (PDF, DOCX, TXT)'}
                    </label>
                </div>

                <div style={{ display: 'flex', gap: '0.8rem' }}>
                    <button
                        className="btn btn-primary"
                        type="submit"
                        disabled={loading || !resumeText.trim() || !jobText.trim()}
                    >
                        {loading ? 'Analyzing...' : '⚡ Analyze Text'}
                    </button>
                    <button
                        className="btn btn-ghost"
                        type="button"
                        onClick={handleAnalyzeFile}
                        disabled={loading || !file || !jobText.trim()}
                    >
                        {loading ? 'Analyzing...' : '📎 Analyze File'}
                    </button>
                </div>
            </form>

            {loading && (
                <div className="loading-spinner">
                    <div className="spinner"></div>
                    <span>Analyzing your resume with AI... This may take a moment.</span>
                </div>
            )}

            {results && (
                <div className="results-section">
                    {/* Match Score — null means the job description had no
                        recognisable skills, which is not the same as 0%. */}
                    <div className="results-card">
                        {results.match_percentage === null ? (
                            <div className="match-score">
                                <div className="score-label">
                                    Couldn't identify any required skills in that job
                                    description, so there's no score to report. Try pasting
                                    the full posting, including its requirements section.
                                </div>
                            </div>
                        ) : (
                            <div className="match-score">
                                <div className="score-number">{results.match_percentage}%</div>
                                <div className="score-label">Match Score</div>
                            </div>
                        )}
                    </div>

                    {/* Skills Breakdown */}
                    <div className="results-card">
                        <h3>🎯 Skills Found in Your Resume</h3>
                        <div className="skills-row">
                            {results.resume_skills?.map((skill) => (
                                <span key={skill} className="skill-tag matched">
                                    {skill}
                                </span>
                            ))}
                        </div>
                    </div>

                    <div className="results-card">
                        <h3>📋 Skills Required by Job</h3>
                        <div className="skills-row">
                            {results.job_skills?.map((skill) => (
                                <span
                                    key={skill}
                                    className={`skill-tag ${results.missing_skills?.includes(skill) ? 'missing' : 'matched'
                                        }`}
                                >
                                    {skill}
                                </span>
                            ))}
                        </div>
                    </div>

                    {results.missing_skills?.length > 0 && (
                        <div className="results-card">
                            <h3>⚠️ Missing Skills</h3>
                            <div className="skills-row">
                                {results.missing_skills.map((skill) => (
                                    <span key={skill} className="skill-tag missing">
                                        {skill}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* AI Recommendation — rendered via react-markdown, which
                        escapes HTML by default. Never use dangerouslySetInnerHTML
                        here: this text comes from an LLM reading an uploaded file,
                        so it is untrusted input. */}
                    {results.ai_recommendation && (
                        <div className="results-card">
                            <h3>🤖 AI Recommendation</h3>
                            <div className="ai-recommendation">
                                <Markdown>{results.ai_recommendation}</Markdown>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default ResumeAnalyzer;
