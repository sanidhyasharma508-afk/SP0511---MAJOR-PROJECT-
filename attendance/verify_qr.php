<?php
// verify_qr.php - Returns JSON status for a given session + token
header('Content-Type: application/json; charset=utf-8');
require_once __DIR__ . '/config.php';
$mysqli = get_db_connection();

$session_id = isset($_GET['session']) ? intval($_GET['session']) : 0;
$token = isset($_GET['token']) ? $_GET['token'] : '';

if (!$session_id || $token === '') {
    echo json_encode(['ok' => false, 'error' => 'Missing session or token']);
    exit;
}

$stmt = $mysqli->prepare("SELECT id, token, expires_at FROM attendance_sessions WHERE id = ? LIMIT 1");
$stmt->bind_param('i', $session_id);
$stmt->execute();
$res = $stmt->get_result();
$session = $res->fetch_assoc();
$stmt->close();

if (!$session) {
    echo json_encode(['ok' => false, 'error' => 'Invalid session']);
    exit;
}

if (!hash_equals($session['token'], $token)) {
    echo json_encode(['ok' => false, 'error' => 'Token mismatch']);
    exit;
}

if (strtotime($session['expires_at']) < time()) {
    echo json_encode(['ok' => false, 'error' => 'Session expired']);
    exit;
}

echo json_encode(['ok' => true, 'session_id' => (int)$session['id'], 'expires_at' => $session['expires_at']]);
exit;
?>