<?php
// mark_attendance.php
// Student opens this by scanning the QR. Verifies session and token, then marks attendance.

require_once __DIR__ . '/config.php';
$mysqli = get_db_connection();

$session_id = isset($_REQUEST['session']) ? intval($_REQUEST['session']) : 0;
$token = isset($_REQUEST['token']) ? $_REQUEST['token'] : '';

$valid_session = false;
$session_row = null;
$message = '';

if ($session_id && $token) {
    // verify session and token with prepared statement
    $stmt = $mysqli->prepare("SELECT id, token, expires_at FROM attendance_sessions WHERE id = ? LIMIT 1");
    if (!$stmt) die('Prepare failed: ' . $mysqli->error);
    $stmt->bind_param('i', $session_id);
    $stmt->execute();
    $res = $stmt->get_result();
    $session_row = $res->fetch_assoc();
    $stmt->close();

    if (!$session_row) {
        $message = 'Invalid session.';
    } elseif (!hash_equals($session_row['token'], $token)) {
        $message = 'Token mismatch.';
    } elseif (strtotime($session_row['expires_at']) < time()) {
        $message = 'Session has expired.';
    } else {
        $valid_session = true;
    }
} else {
    $message = 'Missing session or token.';
}

// Handle submission to mark attendance
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $valid_session) {
    $roll_no = isset($_POST['roll_no']) ? trim($_POST['roll_no']) : '';
    $name = isset($_POST['name']) ? trim($_POST['name']) : '';

    if ($roll_no === '') {
        $message = 'Please provide your roll number.';
    } else {
        // find student by roll_no
        $stmt = $mysqli->prepare("SELECT id, name FROM students WHERE roll_no = ? LIMIT 1");
        $stmt->bind_param('s', $roll_no);
        $stmt->execute();
        $res = $stmt->get_result();
        $student = $res->fetch_assoc();
        $stmt->close();

        if (!$student) {
            // optional: auto-register the student
            $student_name = $name !== '' ? $name : 'Unknown';
            $stmt = $mysqli->prepare("INSERT INTO students (name, roll_no) VALUES (?, ?)");
            $stmt->bind_param('ss', $student_name, $roll_no);
            if (!$stmt->execute()) {
                $message = 'Failed to register student: ' . $mysqli->error;
                $stmt->close();
            } else {
                $student_id = $stmt->insert_id;
                $stmt->close();
                $student = ['id' => $student_id, 'name' => $student_name];
            }
        }

        if ($student) {
            $student_id = (int)$student['id'];

            // prevent duplicate attendance for same session
            $stmt = $mysqli->prepare("SELECT id FROM attendance_records WHERE student_id = ? AND session_id = ? LIMIT 1");
            $stmt->bind_param('ii', $student_id, $session_id);
            $stmt->execute();
            $res = $stmt->get_result();
            $exists = $res->fetch_assoc();
            $stmt->close();

            if ($exists) {
                $message = 'Attendance already recorded.';
            } else {
                // insert attendance record
                $stmt = $mysqli->prepare("INSERT INTO attendance_records (student_id, session_id) VALUES (?, ?)");
                if (!$stmt) die('Prepare failed: ' . $mysqli->error);
                $stmt->bind_param('ii', $student_id, $session_id);
                if ($stmt->execute()) {
                    $message = 'Attendance recorded. Thank you, ' . e($student['name']) . '!';
                } else {
                    // handle unique constraint failures
                    if ($mysqli->errno === 1062) {
                        $message = 'Attendance already recorded (race condition prevented duplicate).';
                    } else {
                        $message = 'Failed to record attendance: ' . $mysqli->error;
                    }
                }
                $stmt->close();
            }
        }
    }
}

?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Mark Attendance</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="container">
    <h1>Mark Attendance</h1>

    <?php if (!$valid_session): ?>
      <div class="card error"><?php echo e($message); ?></div>
    <?php else: ?>
      <?php if ($message): ?>
        <div class="card info"><?php echo e($message); ?></div>
      <?php endif; ?>

      <div class="card">
        <p>Session ID: <strong><?php echo e($session_id); ?></strong></p>
        <p>Expires at: <strong><?php echo e($session_row['expires_at']); ?></strong></p>

        <form method="post">
          <input type="hidden" name="session" value="<?php echo e($session_id); ?>">
          <input type="hidden" name="token" value="<?php echo e($token); ?>">

          <label>Roll Number
            <input type="text" name="roll_no" required placeholder="Enter your roll number">
          </label>

          <label>Your Name (optional)
            <input type="text" name="name" placeholder="First Last">
          </label>

          <button type="submit" class="btn">Mark Attendance</button>
        </form>

        <p class="muted">If you already registered in the student list, just enter your roll number.</p>
      </div>
    <?php endif; ?>

    <p><a href="../index.php">Back</a> | <a href="generate_qr.php">Generate new QR</a></p>
  </div>
</body>
</html>
