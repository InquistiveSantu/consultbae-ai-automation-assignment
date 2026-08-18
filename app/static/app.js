// ConsultBae Audio Collection App JavaScript Logic

let candidateMap = {};
let selectedPersonId = null;
let currentMethod = 'mic'; // 'mic' or 'file'

// Recording state
let mediaRecorder = null;
let audioChunks = [];
let recordedBlob = null;
let recordingTimer = null;
let startTime = 0;

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    fetchCandidates();
    fetchSubmissions();
});

// Switch Views / Tabs
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active-view'));

    if (tab === 'collect') {
        document.getElementById('tab-collect').classList.add('active');
        document.getElementById('view-collect').classList.add('active-view');
    } else {
        document.getElementById('tab-submissions').classList.add('active');
        document.getElementById('view-submissions').classList.add('active-view');
        fetchSubmissions(); // Refresh table
    }
}

// Fetch Candidates (60 Golden Persons)
async function fetchCandidates() {
    try {
        const res = await fetch('/api/candidates');
        if (!res.ok) throw new Error('Failed to load candidates');
        const candidates = await res.json();

        const select = document.getElementById('candidate-select');
        select.innerHTML = '<option value="">-- Select Candidate (60 Golden Persons) --</option>';

        candidateMap = {};
        candidates.forEach(c => {
            candidateMap[c.id] = c;
            const opt = document.createElement('option');
            opt.value = c.id;
            opt.textContent = `${c.canonical_name} (${c.primary_phone || 'No Phone'}) — ${c.canonical_city || 'India'}`;
            select.appendChild(opt);
        });
    } catch (err) {
        showAlert(`Error loading candidates: ${err.message}`, 'error');
    }
}

// Candidate Select Handler
function onCandidateSelect(personId) {
    const infoCard = document.getElementById('candidate-info');
    if (!personId || !candidateMap[personId]) {
        selectedPersonId = null;
        infoCard.classList.add('hidden');
        validateSubmitButton();
        return;
    }

    const c = candidateMap[personId];
    selectedPersonId = c.id;

    document.getElementById('info-name').textContent = c.canonical_name;
    document.getElementById('info-phone').textContent = c.primary_phone || 'N/A';
    document.getElementById('info-city').textContent = c.canonical_city || 'N/A';
    infoCard.classList.remove('hidden');

    validateSubmitButton();
}

// Toggle Input Method (Mic vs File)
function setMethod(method) {
    currentMethod = method;
    document.getElementById('method-mic').classList.toggle('active', method === 'mic');
    document.getElementById('method-file').classList.toggle('active', method === 'file');

    document.getElementById('section-mic').classList.toggle('hidden', method !== 'mic');
    document.getElementById('section-file').classList.toggle('hidden', method !== 'file');

    validateSubmitButton();
}

// MediaRecorder Logic
async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = event => {
            if (event.data.size > 0) audioChunks.push(event.data);
        };

        mediaRecorder.onstop = () => {
            recordedBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
            setupPreview(recordedBlob);
            validateSubmitButton();
        };

        mediaRecorder.start();
        startTime = Date.now();
        
        document.getElementById('btn-start-rec').classList.add('hidden');
        document.getElementById('btn-stop-rec').classList.remove('hidden');
        document.getElementById('pulse-ring').style.display = 'block';

        recordingTimer = setInterval(updateTimer, 1000);
    } catch (err) {
        showAlert(`Microphone permission denied or unavailable: ${err.message}`, 'error');
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }

    clearInterval(recordingTimer);
    document.getElementById('btn-start-rec').classList.remove('hidden');
    document.getElementById('btn-stop-rec').classList.add('hidden');
    document.getElementById('pulse-ring').style.display = 'none';
}

function updateTimer() {
    const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
    const m = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
    const s = String(elapsedSec % 60).padStart(2, '0');
    document.getElementById('timer-display').textContent = `${m}:${s}`;
}

// File Selection Handler
function onFileSelected(input) {
    const file = input.files[0];
    if (file) {
        document.getElementById('selected-filename').textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        document.getElementById('selected-filename').classList.remove('hidden');
        setupPreview(file);
        validateSubmitButton();
    }
}

// Setup Audio Preview Player
function setupPreview(source) {
    const previewContainer = document.getElementById('preview-container');
    const audioPlayer = document.getElementById('audio-preview');
    
    const audioUrl = URL.createObjectURL(source);
    audioPlayer.src = audioUrl;
    previewContainer.classList.remove('hidden');
}

// Validate Submit Button State
function validateSubmitButton() {
    const btn = document.getElementById('btn-submit');
    const hasCandidate = !!selectedPersonId;
    let hasAudio = false;

    if (currentMethod === 'mic') {
        hasAudio = !!recordedBlob;
    } else {
        const fileInput = document.getElementById('audio-file-input');
        hasAudio = fileInput.files && fileInput.files.length > 0;
    }

    btn.disabled = !(hasCandidate && hasAudio);
}

// Form Submit Handler
async function handleFormSubmit(e) {
    e.preventDefault();
    if (!selectedPersonId) {
        showAlert('Please select an existing candidate from the Golden Persons list.', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('person_id', selectedPersonId);

    if (currentMethod === 'mic') {
        if (!recordedBlob) {
            showAlert('No audio recorded. Please record audio first.', 'error');
            return;
        }
        const ext = recordedBlob.type.includes('webm') ? 'webm' : 'wav';
        formData.append('file', recordedBlob, `recording_${Date.now()}.${ext}`);
    } else {
        const fileInput = document.getElementById('audio-file-input');
        if (!fileInput.files || fileInput.files.length === 0) {
            showAlert('Please select an audio file to upload.', 'error');
            return;
        }
        formData.append('file', fileInput.files[0]);
    }

    const submitBtn = document.getElementById('btn-submit');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Processing Audio & LUFS Metadata...';

    try {
        const res = await fetch('/api/audio/upload', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Upload failed');
        }

        showAlert(data.message, 'success');
        resetForm();
        switchTab('submissions'); // Jump to submissions list view
    } catch (err) {
        showAlert(`Submission Error: ${err.message}`, 'error');
    } finally {
        submitBtn.textContent = '⚡ Submit Audio & Extract Metadata';
        validateSubmitButton();
    }
}

// Reset Form
function resetForm() {
    document.getElementById('audio-form').reset();
    document.getElementById('candidate-info').classList.add('hidden');
    document.getElementById('preview-container').classList.add('hidden');
    document.getElementById('selected-filename').classList.add('hidden');
    document.getElementById('timer-display').textContent = '00:00';
    selectedPersonId = null;
    recordedBlob = null;
    audioChunks = [];
}

// Fetch Submissions List (View 2)
async function fetchSubmissions() {
    try {
        const res = await fetch('/api/audio/submissions');
        if (!res.ok) throw new Error('Failed to fetch submissions');
        const submissions = await res.json();

        document.getElementById('sub-count-badge').textContent = submissions.length;
        renderSubmissionsTable(submissions);
        renderAnalytics(submissions);
    } catch (err) {
        console.error('Error fetching submissions:', err);
    }
}

// Render Submissions Table
function renderSubmissionsTable(subs) {
    const tbody = document.getElementById('submissions-tbody');
    if (!subs || subs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty-table">No audio submissions recorded yet.</td></tr>';
        return;
    }

    tbody.innerHTML = '';
    subs.forEach(s => {
        const tr = document.createElement('tr');
        const durFormatted = `${Math.floor(s.duration_seconds / 60)}:${String(Math.floor(s.duration_seconds % 60)).padStart(2, '0')}`;
        const srKHz = (s.sample_rate_hz / 1000).toFixed(1);
        const dateStr = new Date(s.created_at).toLocaleString();

        tr.innerHTML = `
            <td><strong>${s.canonical_name}</strong></td>
            <td>${s.primary_phone || 'N/A'}</td>
            <td>${s.canonical_city || 'N/A'}</td>
            <td>
                <audio controls src="/${s.file_path}" style="height: 36px; max-width: 180px;"></audio>
            </td>
            <td>${durFormatted} (${s.duration_seconds}s)</td>
            <td>${srKHz} kHz</td>
            <td>${s.bitrate_kbps} kbps</td>
            <td><strong>${s.loudness_lufs} LUFS</strong></td>
            <td>${dateStr}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Render Analytics Summary Cards
function renderAnalytics(subs) {
    document.getElementById('stat-total').textContent = subs.length;

    if (subs.length === 0) {
        document.getElementById('stat-duration').textContent = '0.0s';
        document.getElementById('stat-loudness').textContent = '- LUFS';
        return;
    }

    const totalDur = subs.reduce((acc, curr) => acc + curr.duration_seconds, 0);
    const avgDur = (totalDur / subs.length).toFixed(1);
    document.getElementById('stat-duration').textContent = `${avgDur}s`;

    const totalLoudness = subs.reduce((acc, curr) => acc + curr.loudness_lufs, 0);
    const avgLoudness = (totalLoudness / subs.length).toFixed(1);
    document.getElementById('stat-loudness').textContent = `${avgLoudness} LUFS`;
}

// Show Alert Banner Toast
function showAlert(message, type = 'success') {
    const banner = document.getElementById('alert-banner');
    banner.textContent = message;
    banner.className = `alert-banner ${type === 'success' ? 'alert-success' : 'alert-error'}`;
    banner.classList.remove('hidden');

    setTimeout(() => {
        banner.classList.add('hidden');
    }, 6000);
}
