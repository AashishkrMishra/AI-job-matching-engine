import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getJobs, createJob, updateJob, deleteJob } from '../services/api';

const STATUS_OPTIONS = ['applied', 'interview', 'offered', 'rejected'];

function Dashboard() {
    const [jobs, setJobs] = useState([]);
    const [company, setCompany] = useState('');
    const [role, setRole] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    useEffect(() => {
        fetchJobs();
    }, []);

    const fetchJobs = async () => {
        try {
            const res = await getJobs();
            setJobs(res.data);
        } catch (err) {
            if (err.response?.status === 401) {
                localStorage.removeItem('token');
                navigate('/login');
            }
            setError('Failed to load jobs');
        } finally {
            setLoading(false);
        }
    };

    const handleAdd = async (e) => {
        e.preventDefault();
        if (!company.trim() || !role.trim()) return;

        try {
            const res = await createJob(company.trim(), role.trim());
            setJobs([res.data, ...jobs]);
            setCompany('');
            setRole('');
        } catch (err) {
            setError('Failed to add job');
        }
    };

    const handleStatusChange = async (jobId, newStatus) => {
        try {
            await updateJob(jobId, newStatus);
            setJobs(jobs.map((j) => (j.id === jobId ? { ...j, status: newStatus } : j)));
        } catch (err) {
            setError('Failed to update status');
        }
    };

    const handleDelete = async (jobId) => {
        try {
            await deleteJob(jobId);
            setJobs(jobs.filter((j) => j.id !== jobId));
        } catch (err) {
            setError('Failed to delete job');
        }
    };

    return (
        <div className="dashboard">
            <h1>📋 Your Applications</h1>
            <p className="subtitle">Track and manage your job applications</p>

            {error && <div className="error-msg">{error}</div>}

            <form className="add-job-form" onSubmit={handleAdd}>
                <input
                    placeholder="Company name"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    required
                />
                <input
                    placeholder="Role / Position"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    required
                />
                <button className="btn btn-primary" type="submit">
                    + Add Job
                </button>
            </form>

            {loading ? (
                <div className="loading-spinner">
                    <div className="spinner"></div>
                    <span>Loading your jobs...</span>
                </div>
            ) : jobs.length === 0 ? (
                <div className="empty-state">
                    <div className="emoji">🎯</div>
                    <p>No applications yet. Add your first job above!</p>
                </div>
            ) : (
                <div className="job-list">
                    {jobs.map((job) => (
                        <div className="job-card" key={job.id}>
                            <div className="job-info">
                                <h3>{job.role}</h3>
                                <span className="company">{job.company}</span>
                            </div>
                            <div className="job-actions">
                                <span className={`status-badge status-${job.status}`}>
                                    {job.status}
                                </span>
                                <select
                                    className="status-select"
                                    value={job.status}
                                    onChange={(e) => handleStatusChange(job.id, e.target.value)}
                                >
                                    {STATUS_OPTIONS.map((s) => (
                                        <option key={s} value={s}>
                                            {s}
                                        </option>
                                    ))}
                                </select>
                                <button
                                    className="btn btn-danger btn-sm"
                                    onClick={() => handleDelete(job.id)}
                                >
                                    ✕
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default Dashboard;
