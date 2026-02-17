<?php
// config.php - MySQL connection and helper functions
// Update DB credentials as needed for your XAMPP/localhost setup

error_reporting(E_ALL);
ini_set('display_errors', 1);
date_default_timezone_set('Asia/Kolkata'); // adjust as needed

define('DB_HOST', '127.0.0.1');
define('DB_USER', 'root');
define('DB_PASS', '');
define('DB_NAME', 'campus_automation');

function get_db_connection() {
    $mysqli = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    if ($mysqli->connect_errno) {
        http_response_code(500);
        die('Database connection failed: ' . $mysqli->connect_error);
    }
    $mysqli->set_charset('utf8mb4');
    return $mysqli;
}

// Helper: safe output
function e($str) {
    return htmlspecialchars($str, ENT_QUOTES, 'UTF-8');
}

?>