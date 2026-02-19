function sendMessage() {
    let input = document.getElementById("userInput").value;
    if (input === "") return;

    let chatBox = document.getElementById("chat-box");
    chatBox.innerHTML += `<div class="user">${input}</div>`;

    fetch("chat.php", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: "message=" + encodeURIComponent(input)
    })
    .then(res => res.text())
    .then(reply => {
        chatBox.innerHTML += `<div class="bot">${reply}</div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
    });

    document.getElementById("userInput").value = "";
}