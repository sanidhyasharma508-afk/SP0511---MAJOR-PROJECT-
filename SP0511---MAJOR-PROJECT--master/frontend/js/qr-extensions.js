/* QR extensions: store attendance details locally (student, section, branch, roll, datetime, event/club)
   This wraps the existing markAttendance function without modifying original file.
*/
(function(){
  const STORAGE_KEY = 'qrAttendanceRecords';

  function getStudentInfo() {
    return {
      studentName: document.getElementById('student-name')?.textContent || 'Unknown',
      rollNumber: document.getElementById('student-roll')?.textContent || '',
      branch: document.getElementById('student-branch')?.textContent || '',
      section: (document.querySelector('.user-info-mini span')?.textContent || '').split('•')?.[1]?.trim() || ''
    };
  }

  function getSessionInfo() {
    return {
      eventName: document.getElementById('qr-subject-display')?.textContent || document.getElementById('session-id-display')?.textContent || 'Unknown'
    };
  }

  // wrap existing markAttendance if present
  const original = window.markAttendance;
  if (typeof original === 'function') {
    window.markAttendance = async function(sessionId) {
      let result;
      try { result = await original(sessionId); } catch (e) { result = null; }

      // store record locally for admin/demo purposes
      try {
        const s = getStudentInfo();
        const sess = getSessionInfo();
        const rec = {
          student_name: s.studentName,
          roll_number: s.rollNumber,
          branch: s.branch,
          section: s.section,
          datetime: new Date().toISOString(),
          event_name: sess.eventName,
          session_id: sessionId || null
        };
        const arr = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        arr.push(rec);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(arr));
      } catch(e) { console.error('qr-extensions save error', e); }

      return result;
    };
  }

  // expose a helper to view stored QR attendance (dev/demo)
  window.getStoredQRAttendance = function() { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); };
})();