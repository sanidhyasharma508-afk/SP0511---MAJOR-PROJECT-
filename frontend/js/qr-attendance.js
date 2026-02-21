/**
 * QR Attendance System JavaScript
 * Smart QR-based attendance with geo-fencing, real-time validation, and anti-proxy features
 */

const API_BASE_URL = 'http://localhost:8000';
let currentLocation = null;
let currentSessionId = null;
let qrTimer = null;
let liveUpdateInterval = null;
let qrVideoStream = null;

// Initialize QR Attendance System
document.addEventListener('DOMContentLoaded', () => {
    initializeRoleTabs();
    requestLocationPermission();
    loadStudentDashboard();
});

// ============== Role Tab Switching ==============

function initializeRoleTabs() {
    const roleTabs = document.querySelectorAll('.role-tab');

    roleTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs and panels
            document.querySelectorAll('.role-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.qr-panel').forEach(p => p.classList.remove('active'));

            // Add active class to clicked tab
            tab.classList.add('active');

            // Show corresponding panel
            const role = tab.dataset.role;
            document.getElementById(`${role}-panel`).classList.add('active');

            // Load appropriate data
            if (role === 'student') {
                loadStudentDashboard();
            } else {
                // Faculty panel initialization
            }
        });
    });
}

// ============== Location Services ==============

function requestLocationPermission() {
    if (!navigator.geolocation) {
        showLocationStatus('Geolocation not supported', 'error');
        return;
    }

    showLocationStatus('Requesting location access...', 'loading');

    navigator.geolocation.getCurrentPosition(
        (position) => {
            currentLocation = {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy
            };
            showLocationStatus(`Location acquired (±${Math.round(currentLocation.accuracy)}m)`, 'success');
        },
        (error) => {
            showLocationStatus('Location access denied. Please enable location.', 'error');
            console.error('Location error:', error);
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }
    );
}

function showLocationStatus(message, type) {
    const locationStatus = document.getElementById('location-status');
    const locationText = document.getElementById('location-text');

    locationText.textContent = message;

    locationStatus.className = 'location-status';
    if (type === 'success') {
        locationStatus.style.background = 'linear-gradient(135deg, rgba(67, 233, 123, 0.1) 0%, rgba(56, 249, 215, 0.1) 100%)';
        locationStatus.style.color = '#2d8659';
    } else if (type === 'error') {
        locationStatus.style.background = 'linear-gradient(135deg, rgba(240, 147, 251, 0.1) 0%, rgba(245, 87, 108, 0.1) 100%)';
        locationStatus.style.color = '#c7254e';
    }
}

function getDeviceInfo() {
    const userAgent = navigator.userAgent;
    const platform = navigator.platform;

    // Simple device detection
    let deviceModel = 'Unknown';
    let deviceOS = 'Unknown';

    if (/Android/i.test(userAgent)) {
        deviceOS = 'Android';
        deviceModel = userAgent.match(/Android.*; (.*?) Build/)?.[1] || 'Android Device';
    } else if (/iPhone/i.test(userAgent)) {
        deviceOS = 'iOS';
        deviceModel = userAgent.match(/iPhone\s+OS\s+([\d_]+)/)?.[0] || 'iPhone';
    } else if (/Windows/i.test(userAgent)) {
        deviceOS = 'Windows';
    } else if (/Mac/i.test(userAgent)) {
        deviceOS = 'MacOS';
    } else if (/Linux/i.test(userAgent)) {
        deviceOS = 'Linux';
    }

    // Generate device fingerprint
    const deviceId = generateDeviceFingerprint();

    return {
        device_id: deviceId,
        device_model: deviceModel,
        device_os: deviceOS,
        browser: getBrowserInfo(),
        screen_resolution: `${window.screen.width}x${window.screen.height}`,
        user_agent: userAgent
    };
}

function generateDeviceFingerprint() {
    // Simple fingerprinting based on screen, browser, and platform
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillText('fingerprint', 2, 2);

    const fingerprint = `${navigator.userAgent}${window.screen.width}${window.screen.height}${canvas.toDataURL()}`;

    // Simple hash function
    let hash = 0;
    for (let i = 0; i < fingerprint.length; i++) {
        const char = fingerprint.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }

    return 'device_' + Math.abs(hash).toString(16);
}

function getBrowserInfo() {
    const userAgent = navigator.userAgent;

    if (userAgent.includes('Chrome')) return 'Chrome';
    if (userAgent.includes('Firefox')) return 'Firefox';
    if (userAgent.includes('Safari')) return 'Safari';
    if (userAgent.includes('Edge')) return 'Edge';
    if (userAgent.includes('Opera')) return 'Opera';

    return 'Unknown';
}

// ============== Student Panel ==============

async function loadStudentDashboard() {
    try {
        // Mock student ID - in production, get from session
        const studentId = 'student_123';

        const response = await fetch(`${API_BASE_URL}/qr-attendance/student/dashboard/${studentId}`);

        if (response.ok) {
            const data = await response.json();
            updateStudentDashboard(data);
        } else {
            console.error('Failed to load student dashboard');
        }
    } catch (error) {
        console.error('Error loading student dashboard:', error);
    }
}

function updateStudentDashboard(data) {
    document.getElementById('student-today-attended').textContent = data.today_attended || 0;
    document.getElementById('student-overall-percentage').textContent =
        `${Math.round(data.overall_attendance_percentage || 0)}%`;

    // Count late entries from recent attendance (respecting grace period)
    const lateCount = data.recent_attendance?.filter(r => r.attendance_status === 'late').length || 0;
    document.getElementById('student-late-count').textContent = lateCount;

    // Update recent attendance list if data available
    if (data.recent_attendance && data.recent_attendance.length > 0) {
        updateRecentAttendanceList(data.recent_attendance);
    }
}

function updateRecentAttendanceList(attendanceList) {
    const listContainer = document.getElementById('student-recent-list');

    listContainer.innerHTML = attendanceList.map(record => `
        <div class="attendance-item">
            <div class="attendance-item-info">
                <h4>${record.subject_name || 'Subject'}</h4>
                <p>
                    <i class="fas fa-clock"></i> 
                    ${formatDateTime(record.marked_at)} • Faculty Name
                </p>
            </div>
            <span class="attendance-badge ${record.attendance_status === 'late' ? 'warning' : 'success'}">
                ${record.attendance_status === 'late' ? `Late (${record.late_by_minutes} min)` : 'Present'}
            </span>
        </div>
    `).join('');
}

function formatDateTime(dateString) {
    let dateStr = dateString;
    if (typeof dateString === 'string' && !dateString.includes('Z') && !dateString.includes('+')) {
        dateStr += 'Z';
    }
    const date = new Date(dateStr);
    const today = new Date();

    const isToday = date.toDateString() === today.toDateString();

    const timeStr = date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });

    if (isToday) {
        return `Today, ${timeStr}`;
    } else {
        return `${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${timeStr}`;
    }
}

// ============== QR Scanner ==============

async function startQRScanner() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' }
        });

        qrVideoStream = stream;

        const videoElement = document.getElementById('qr-video');
        videoElement.srcObject = stream;

        document.getElementById('camera-preview').style.display = 'block';
        document.getElementById('manual-entry').style.display = 'none';
        document.getElementById('start-camera-btn').style.display = 'none';
        document.getElementById('stop-camera-btn').style.display = 'inline-flex';

        // In production, integrate QR scanning library like jsQR or QuaggaJS
        // For now, show instructions
        showScanResult('Camera started. Point at QR code to scan.', 'info');

    } catch (error) {
        console.error('Camera error:', error);
        showScanResult('Failed to access camera. Please check permissions.', 'error');
    }
}

function stopQRScanner() {
    if (qrVideoStream) {
        qrVideoStream.getTracks().forEach(track => track.stop());
        qrVideoStream = null;
    }

    document.getElementById('camera-preview').style.display = 'none';
    document.getElementById('manual-entry').style.display = 'block';
    document.getElementById('start-camera-btn').style.display = 'inline-flex';
    document.getElementById('stop-camera-btn').style.display = 'none';

    clearScanResult();
}

async function markAttendanceManually() {
    const sessionIdInput = document.getElementById('session-id-input');
    const sessionData = sessionIdInput.value.trim();

    if (!sessionData) {
        showScanResult('Please enter a session ID', 'error');
        return;
    }

    // Try to parse as JSON (QR code data) or use as session ID
    let sessionId = sessionData;
    let qrHash = null;
    try {
        const parsed = JSON.parse(sessionData);
        sessionId = parsed.session_id;
        qrHash = parsed.hash;
    } catch {
        // Not JSON, use as-is
    }

    await markAttendance(sessionId, qrHash);
}

async function markAttendance(sessionId, qrHash = null) {
    if (!currentLocation) {
        showScanResult('Location not available. Please enable location services.', 'error');
        return;
    }

    showScanResult('Validating attendance...', 'info');

    const requestData = {
        session_id: sessionId,
        student_id: 'student_123', // Mock - get from session in production
        roll_number: '2021BCS001',
        student_name: 'Alex Johnson',
        student_email: 'alex@student.edu',
        branch: 'CS',
        semester: 4,
        section: 'A',
        qr_code_hash: qrHash || '0000000000000000000000000000000000000000000000000000000000000000', // Use provided hash or dummy
        location: {
            latitude: currentLocation.latitude,
            longitude: currentLocation.longitude,
            accuracy: currentLocation.accuracy
        },
        device: getDeviceInfo(),
        scan_timestamp: new Date().toISOString(),
        scan_duration_ms: 1500
    };

    try {
        const response = await fetch(`${API_BASE_URL}/qr-attendance/student/scan-qr`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        const result = await response.json();

        if (result.success) {
            showScanResult(
                `✓ ${result.message}`,
                'success',
                result.session_info ?
                    `${result.session_info.subject} • ${result.session_info.faculty}` :
                    null
            );

            // Reload dashboard after 2 seconds
            setTimeout(() => {
                loadStudentDashboard();
            }, 2000);
        } else {
            const errorMessages = result.errors?.join(', ') || 'Attendance marking failed';
            showScanResult(
                `✗ ${result.message}`,
                'error',
                errorMessages
            );
        }

    } catch (error) {
        console.error('Attendance marking error:', error);
        showScanResult('Network error. Please try again.', 'error');
    }
}

function showScanResult(message, type, details = null) {
    const scanResult = document.getElementById('scan-result');
    scanResult.style.display = 'block';
    scanResult.className = `scan-result ${type}`;

    let icon = '';
    if (type === 'success') icon = '✓';
    else if (type === 'error') icon = '✗';
    else if (type === 'warning') icon = '⚠';
    else icon = 'ℹ';

    scanResult.innerHTML = `
        <div class="scan-result-icon">${icon}</div>
        <div class="scan-result-message">${message}</div>
        ${details ? `<div class="scan-result-details">${details}</div>` : ''}
    `;
}

function clearScanResult() {
    const scanResult = document.getElementById('scan-result');
    scanResult.style.display = 'none';
}

// ============== Faculty Panel ==============

document.getElementById('qr-generation-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    await generateQRSession();
});

async function generateQRSession() {
    if (!currentLocation) {
        alert('Location not available. Please enable location services.');
        return;
    }

    const formData = {
        faculty_id: 'faculty_001', // Mock - get from session
        faculty_name: 'Dr. Sharma',
        faculty_email: 'sharma@faculty.edu',
        subject_code: document.getElementById('subject-code').value,
        subject_name: document.getElementById('subject-name').value,
        branch: document.getElementById('branch').value,
        semester: parseInt(document.getElementById('semester').value),
        section: document.getElementById('section').value || null,
        lecture_date: new Date().toISOString().split('T')[0],
        lecture_start_time: new Date().toISOString(),
        lecture_duration_minutes: parseInt(document.getElementById('lecture-duration').value),
        qr_validity_minutes: parseInt(document.getElementById('qr-validity').value),
        center_latitude: currentLocation.latitude,
        center_longitude: currentLocation.longitude,
        geo_fence_radius_meters: parseInt(document.getElementById('geofence-radius').value),
        location_name: document.getElementById('location-name').value || 'Classroom',
        total_students_expected: parseInt(document.getElementById('total-students').value),
        allow_screenshot_scan: document.getElementById('allow-screenshot').checked,
        require_device_verification: document.getElementById('require-device-check').checked
    };

    try {
        const response = await fetch(`${API_BASE_URL}/qr-attendance/faculty/generate-qr`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            const session = await response.json();
            currentSessionId = session.session_id;

            // Hide form, show QR display
            document.querySelector('.qr-generation-card').style.display = 'none';
            document.getElementById('qr-display-card').style.display = 'block';
            document.getElementById('live-dashboard').style.display = 'block';

            // Display QR code
            await displayQRCode(session);

            // Start live updates
            startLiveUpdates(session.id);

            // Start timer
            startQRTimer(session.qr_expires_at);

        } else {
            alert('Failed to generate QR session');
        }

    } catch (error) {
        console.error('QR generation error:', error);
        alert('Network error. Please try again.');
    }
}

async function displayQRCode(session) {
    // Fetch QR code image
    try {
        const response = await fetch(`${API_BASE_URL}/qr-attendance/faculty/qr-image/${session.session_id}`);

        if (response.ok) {
            const data = await response.json();

            document.getElementById('qr-code-img').src = `data:image/png;base64,${data.qr_code_base64}`;
            document.getElementById('qr-subject-display').textContent = session.subject_name;
            document.getElementById('qr-class-details').textContent =
                `${session.branch} • Semester ${session.semester} • ${session.location_name}`;
            document.getElementById('session-id-display').textContent = session.session_id;

            // Reset timer UI to active state
            const timerText = document.getElementById('qr-timer-text');
            if (timerText) {
                timerText.parentElement.style.background = 'linear-gradient(135deg, rgba(67, 233, 123, 0.1) 0%, rgba(56, 249, 215, 0.1) 100%)';
                timerText.style.color = '#2d8659';
            }
        }

    } catch (error) {
        console.error('QR display error:', error);
    }
}

function startQRTimer(expiresAt) {
    // Force UTC interpretation by ensuring 'Z' suffix if no timezone offset present
    let expiryStr = expiresAt;
    if (typeof expiresAt === 'string' && !expiresAt.includes('Z') && !expiresAt.includes('+')) {
        expiryStr += 'Z';
    }
    const expiryTime = new Date(expiryStr);

    qrTimer = setInterval(() => {
        const now = new Date();
        const remaining = expiryTime - now;

        if (remaining <= 0) {
            clearInterval(qrTimer);
            document.getElementById('qr-timer-text').textContent = 'Expired';
            document.getElementById('qr-timer-text').parentElement.style.background =
                'linear-gradient(135deg, #F093FB 0%, #F5576C 100%)';
            return;
        }

        const minutes = Math.floor(remaining / 60000);
        const seconds = Math.floor((remaining % 60000) / 1000);

        document.getElementById('qr-timer-text').textContent =
            `Expires in ${minutes}:${seconds.toString().padStart(2, '0')}`;

    }, 1000);
}

function startLiveUpdates(sessionId) {
    // Initial load
    updateLiveAttendance(sessionId);

    // Update every 5 seconds
    liveUpdateInterval = setInterval(() => {
        updateLiveAttendance(sessionId);
    }, 5000);
}

async function updateLiveAttendance(sessionId) {
    try {
        const response = await fetch(`${API_BASE_URL}/qr-attendance/faculty/live-attendance/${currentSessionId}`);

        if (response.ok) {
            const data = await response.json();

            document.getElementById('live-present-count').textContent = data.total_present;
            document.getElementById('live-absent-count').textContent = data.total_absent;
            document.getElementById('live-late-count').textContent = data.total_late;
            document.getElementById('live-percentage').textContent = `${Math.round(data.attendance_percentage)}%`;

            // Load attendance records
            await loadAttendanceRecords(sessionId);
        }

    } catch (error) {
        console.error('Live update error:', error);
    }
}

async function loadAttendanceRecords(sessionId) {
    try {
        const response = await fetch(`${API_BASE_URL}/qr-attendance/faculty/attendance-records/${currentSessionId}`);

        if (response.ok) {
            const records = await response.json();

            const tbody = document.getElementById('live-attendance-tbody');
            tbody.innerHTML = records.map(record => `
                <tr>
                    <td>${record.roll_number}</td>
                    <td>${record.student_name}</td>
                    <td>${formatDateTime(record.marked_at)}</td>
                    <td>${Math.round(record.distance_from_center)}m</td>
                    <td>
                        <span class="attendance-badge ${record.attendance_status === 'late' ? 'warning' : 'success'}">
                            ${record.attendance_status === 'late' ? 'Late' : 'Present'}
                        </span>
                    </td>
                </tr>
            `).join('');
        }

    } catch (error) {
        console.error('Records load error:', error);
    }
}

function closeQRSession() {
    if (confirm('Are you sure you want to close this attendance session?')) {
        // Clear intervals
        if (qrTimer) clearInterval(qrTimer);
        if (liveUpdateInterval) clearInterval(liveUpdateInterval);

        // Reset display
        document.querySelector('.qr-generation-card').style.display = 'block';
        document.getElementById('qr-display-card').style.display = 'none';
        document.getElementById('live-dashboard').style.display = 'none';

        // Reset form
        document.getElementById('qr-generation-form').reset();

        currentSessionId = null;
    }
}

async function refreshQRCode() {
    if (currentSessionId) {
        try {
            const response = await fetch(`${API_BASE_URL}/qr-attendance/faculty/regenerate-qr/${currentSessionId}`, {
                method: 'POST'
            });

            if (response.ok) {
                const session = await response.json();

                // Update display
                await displayQRCode(session);

                // Restart timer
                if (qrTimer) clearInterval(qrTimer);
                startQRTimer(session.qr_expires_at);

                // Update status UI
                const timerText = document.getElementById('qr-timer-text');
                if (timerText) {
                    timerText.parentElement.style.background = 'linear-gradient(135deg, rgba(67, 233, 123, 0.1) 0%, rgba(56, 249, 215, 0.1) 100%)';
                    timerText.style.color = '#2d8659';
                }

                // Update Badge if it exists
                const expiredBadge = document.querySelector('.expired-badge');
                if (expiredBadge) {
                    expiredBadge.className = 'active-badge';
                    expiredBadge.textContent = 'Active';
                }

                alert('QR Code regenerated successfully!');
            } else {
                alert('Failed to regenerate QR session');
            }
        } catch (error) {
            console.error('QR regeneration error:', error);
            alert('Network error. Please try again.');
        }
    }
}

function copySessionId() {
    const sessionId = document.getElementById('session-id-display').textContent;
    navigator.clipboard.writeText(sessionId).then(() => {
        const btn = event.target.closest('.btn-copy');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check"></i>';
        setTimeout(() => {
            btn.innerHTML = originalHTML;
        }, 2000);
    });
}

async function downloadAttendance() {
    alert('Attendance export will be implemented');
}

// Export functions to window for inline onclick handlers
window.startQRScanner = startQRScanner;
window.stopQRScanner = stopQRScanner;
window.markAttendanceManually = markAttendanceManually;
window.closeQRSession = closeQRSession;
window.refreshQRCode = refreshQRCode;
window.copySessionId = copySessionId;
window.downloadAttendance = downloadAttendance;
