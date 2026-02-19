<?php
// view_attendance.php - Teacher view of sessions and records
require_once __DIR__ . '/config.php';
$mysqli = get_db_connection();

$session_id = isset($_GET['session_id']) ? intval($_GET['session_id']) : 0;

// fetch recent sessions
$stmt = $mysqli->prepare("SELECT id, created_at, expires_at FROM attendance_sessions ORDER BY created_at DESC LIMIT 50");
$stmt->execute();
$res = $stmt->get_result();
$sessions = $res->fetch_all(MYSQLI_ASSOC);
$stmt->close();

$records = [];
if ($session_id) {
    $stmt = $mysqli->prepare("SELECT ar.timestamp, s.name, s.roll_no
                             FROM attendance_records ar
                             JOIN students s ON s.id = ar.student_id
                             WHERE ar.session_id = ?
                             ORDER BY ar.timestamp ASC");
    $stmt->bind_param('i', $session_id);
    $stmt->execute();
    $res = $stmt->get_result();
    $records = $res->fetch_all(MYSQLI_ASSOC);
    $stmt->close();
}

?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>View Attendance</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="container">
    <h1>Attendance Sessions</h1>

    <div class="card">
      <table class="table">
        <thead>
          <tr><th>Session ID</th><th>Created</th><th>Expires</th><th>Actions</th></tr>
        </thead>
        <tbody>
        <?php foreach ($sessions as $s): ?>
          <tr>
            <td><?php echo e($s['id']); ?></td>
            <td><?php echo e($s['created_at']); ?></td>
            <td><?php echo e($s['expires_at']); ?></td>
            <td>
              <a href="view_attendance.php?session_id=<?php echo e($s['id']); ?>">View records</a>
              |
              <a href="generate_qr.php">Generate QR</a>
            </td>
          </tr>
        <?php endforeach; ?>
        </tbody>
      </table>
    </div>

    <?php if ($session_id): ?>
      <h2>Records for session <?php echo e($session_id); ?></h2>
      <div class="card">
        <?php if (empty($records)): ?>
          <p class="muted">No records yet for this session.</p>
        <?php else: ?>
          <table class="table">
            <thead><tr><th>Time</th><th>Name</th><th>Roll No</th></tr></thead>
            <tbody>
            <?php foreach ($records as $r): ?>
              <tr>
                <td><?php echo e($r['timestamp']); ?></td>
                <td><?php echo e($r['name']); ?></td>
                <td><?php echo e($r['roll_no']); ?></td>
              </tr>
            <?php endforeach; ?>
            </tbody>
          </table>
        <?php endif; ?>
      </div>
    <?php endif; ?>

    <p><a href="generate_qr.php">Generate QR</a></p>
  </div>
</body>
</html>
