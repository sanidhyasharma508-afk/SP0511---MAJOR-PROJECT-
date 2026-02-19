<?php

$API_KEY = "AIzaSyAnpGp65vf9qcX7lI3NGgMYbSYKI6ZWzQI";

$userMessage = $_POST['message'];

$prompt = "You are a campus assistant. Answer politely.\n\n" . $userMessage;

$url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=$API_KEY";

$data = [
    "contents" => [[
        "parts" => [["text" => $prompt]]
    ]]
];

$options = [
    "http" => [
        "header" => "Content-Type: application/json",
        "method" => "POST",
        "content" => json_encode($data)
    ]
];

$context = stream_context_create($options);
$response = file_get_contents($url, false, $context);
$result = json_decode($response, true);

echo $result['candidates'][0]['content']['parts'][0]['text'];

?>