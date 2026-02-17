from flask import Flask, render_template, request, redirect
import sqlite3
import qrcode
import time
import os

app = Flask(__name__)

@app.route("/")
def login():
    return render_template("login.html")

@app.route("/teacher")
def teacher():
    return render_template("teacher.html")

@app.route("/student")
def student():
    return render_template("student.html")

@app.route("/generate_qr")
def generate_qr():
    data = f"SESSION-{int(time.time())}"
    img = qrcode.make(data)

    path = "static/qr/qr.png"
    img.save(path)

    return f"QR Generated <br><img src='/{path}'>"

if __name__ == "__main__":
    app.run(debug=True)