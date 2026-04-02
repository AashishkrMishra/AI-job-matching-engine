import axios from 'axios';

const API = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000',
});

// Attach JWT token to every request
API.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Auth
export const registerUser = (email, password) =>
    API.post('/register', { email, password });

export const loginUser = (email, password) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);
    return API.post('/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
};

export const getMe = () => API.get('/me');

// Jobs
export const getJobs = () => API.get('/jobs');
export const createJob = (company, role) =>
    API.post('/jobs', { company, role });
export const updateJob = (jobId, status) =>
    API.patch(`/jobs/${jobId}`, { status });
export const deleteJob = (jobId) => API.delete(`/jobs/${jobId}`);

// Resume Analysis
export const analyzeResume = (resume, job) =>
    API.post('/analyze-resume', { resume, job });

export const analyzeResumeFile = (file, jobDescription) => {
    const formData = new FormData();
    formData.append('resume', file);
    formData.append('job_description', jobDescription);
    return API.post('/analyze-resume-file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
    });
};

export default API;
