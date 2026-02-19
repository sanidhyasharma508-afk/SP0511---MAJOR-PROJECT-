<?php
// setup_db.php
// Run this script from your browser (http://localhost/campus-automation/attendance/setup_db.php)
// It will execute create_tables.sql and create the `campus_automation` database and tables.

require_once __DIR__ . '/config.php';

// connect without selecting a database, so we can create it
$mysqli = new mysqli(DB_HOST, DB_USER, DB_PASS);
if ($mysqli->connect_errno) {
    die('Connection failed: ' . $mysqli->connect_error);
}
$mysqli->set_charset('utf8mb4');

$sqlFile = __DIR__ . '/create_tables.sql';
if (!file_exists($sqlFile)) {
    die('SQL file not found: ' . e($sqlFile));
}

$sql = file_get_contents($sqlFile);
if ($sql === false) {
    die('Could not read SQL file.');
}

// Execute multi-query
if ($mysqli->multi_query($sql)) {
    $success = true;
    // loop through results to ensure all statements executed
    do {
        if ($res = $mysqli->store_result()) {
            $res->free();
        }
        if ($mysqli->errno) {
            $success = false;
            $error = $mysqli->error;
            break;
        }
    } while ($mysqli->more_results() && $mysqli->next_result());

    if ($success) {
        echo '<h2>Database and tables created successfully.</h2>';
        echo '<p>Database: <strong>' . e(DB_NAME) . '</strong></p>';
        echo '<p><a href="generate_qr.php">Go to Generate QR</a></p>';
    } else {
        echo '<h2>Error executing SQL:</h2>';
        echo '<pre>' . e($error) . '</pre>';
    }
} else {
    echo '<h2>Failed to execute SQL:</h2>';
    echo '<pre>' . e($mysqli->error) . '</pre>';
}

$mysqli->close();

?>