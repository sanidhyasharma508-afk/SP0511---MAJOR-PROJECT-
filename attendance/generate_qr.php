<?php
// generate_qr.php
// Teacher clicks "Generate QR" to create a short-lived session and display a QR code

require_once __DIR__ . '/config.php';
$mysqli = get_db_connection();

$message = '';
$qrImageUrl = '';
$expires_at = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // generate secure random token
    try {
        $token = bin2hex(random_bytes(16));
    } catch (Exception $e) {
        die('Could not generate secure token');
    }

    // expiry: 3 minutes from now
    $expires_at = date('Y-m-d H:i:s', time() + 180);

    // insert session into DB using prepared statement
    $stmt = $mysqli->prepare("INSERT INTO attendance_sessions (token, expires_at) VALUES (?, ?)");
    if (!$stmt) die('Prepare failed: ' . $mysqli->error);
    $stmt->bind_param('ss', $token, $expires_at);

    if ($stmt->execute()) {
        $session_id = $stmt->insert_id;
        $stmt->close();

        // Build URL that student will open when scanning the QR
        // Adjust the base URL if your htdocs path is different
        $base = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on' ? 'https' : 'http') . '://' . 
                $_SERVER['HTTP_HOST'] . '/campus-automation/attendance/mark_attendance.php';
        $url = $base . '?session=' . urlencode($session_id) . '&token=' . urlencode($token);

        // Generate QR image locally using phpqrcode library
        $qrcodeDir = __DIR__ . '/qrcodes';
        if (!is_dir($qrcodeDir)) {
          @mkdir($qrcodeDir, 0755, true);
        }
        $localPng = $qrcodeDir . '/session_' . $session_id . '.png';

        // use bundled phpqrcode library
        $libFile = __DIR__ . '/phpqrcode/qrlib.php';
        if (file_exists($libFile)) {
          require_once $libFile;
          // generate PNG locally
          // size recommended: 6, margin: 2
          $res = QRcode::png($url, $localPng, QR_ECLEVEL_L, 6, 2);
          if ($res !== false) {
            $qrImageUrl = 'qrcodes/' . basename($localPng);
            $message = 'QR generated for session ID ' . e($session_id) . ' (offline)';
          } else {
            // fallback to external Google Chart if something goes wrong
            $qrImageUrl = 'https://chart.googleapis.com/chart?cht=qr&chs=350x350&chl=' . urlencode($url);
            $message = 'QR generated for session ID ' . e($session_id) . ' (fallback online)';
          }
        } else {
          // library missing, fallback to Google Chart
          $qrImageUrl = 'https://chart.googleapis.com/chart?cht=qr&chs=350x350&chl=' . urlencode($url);
          $message = 'QR generated for session ID ' . e($session_id) . ' (online fallback - phpqrcode missing)';
        }

        // cleanup: remove qrcodes older than 1 hour to avoid buildup
        if (is_dir($qrcodeDir)) {
          foreach (glob($qrcodeDir . '/*.png') as $f) {
            if (filemtime($f) < time() - 3600) {
              @unlink($f);
            }
          }
        }
    } else {
        $message = 'Failed to create session: ' . $mysqli->error;
    }
}

?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Generate QR - Attendance</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="container">
    <h1>Generate QR for Attendance</h1>
    <form method="post">
      <button type="submit" class="btn">Generate QR (3 minutes)</button>
    </form>

    <?php if ($message): ?>
      <p class="info"><?php echo e($message); ?></p>
    <?php endif; ?>

    <?php if ($qrImageUrl): ?>
      <div class="qr-card">
        <p>Session expires at: <strong><?php echo e($expires_at); ?></strong></p>
        <img src="<?php echo e($qrImageUrl); ?>" alt="QR code">
        <p class="muted">Students should scan this QR with their phone camera or open the URL.</p>
        <p><a href="view_attendance.php">View attendance</a></p>
      </div>
    <?php endif; ?>

    <p class="foot">Note: QR encodes a URL like: <code>mark_attendance.php?session=ID&token=...</code></p>
  </div>
</body>
</html>
