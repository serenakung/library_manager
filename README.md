# 📚 Personal Library Manager

A simple web app for tracking books I’ve been gifted or bought for my baby.  
It began as a practical way to catalogue our growing library — and evolved into a small experiment in building a Python-based app from scratch.

---

## 💡 Overview
The goal of this project was to create a **personal book-tracking system** that records each title and whether it’s been read.  
The app allows me to **add books by scanning ISBNs or entering details manually**, displaying them in a searchable list.  

In the future, I plan to extend it to analyse book **themes, genres, and seasonal relevance**, helping me rotate our reading selection throughout the year.

This was my first project using **Python, Flask, and HTML templates**, and it taught me how a back-end app connects to a front-end interface.

---

## 🧠 What I Learned
- How to **set up and run a Flask app locally** using Homebrew and Python3.  
- How to troubleshoot **port conflicts** (moving from port 5000 to 8080).  
- How to **connect HTML templates** with Flask routes to render dynamic content.  
- How to **collect metadata** (title, author, ISBN) from both manual input and barcode scans.  
- How to **git commit and manage changes** properly through Terminal.  
- How to collaborate with **ChatGPT (vibe-coding)** to iterate and debug efficiently.  
- How to think about **data flow** between user inputs, Python logic, and the displayed list.

---

## 🧩 Features
- 📖 Add books manually or by scanning an ISBN barcode.  
- 🧾 Store key metadata: title, author, ISBN, and read status.  
- ✅ “Mark as read” functionality to update book status directly.  
- 🪄 Streamlined interface that avoids repetitive scrolling by combining actions under one button.  
- 🧠 Uses HTML templates for clean separation of structure and logic.  
- 🧩 Runs locally for personal use (not yet deployed online).  

---

## 🚀 Future Improvements
- Add **persistent storage** (e.g. SQLite database) to save data beyond sessions.  
- Implement **search, sort, and filter** features for title, author, and theme.  
- Add a **delete / edit** function for existing entries.  
- Integrate a **theme analysis feature** to categorise books by topic or mood.  
- Introduce **seasonal rotation** logic to suggest books relevant to holidays or developmental stages.  
- Deploy the app for web or mobile access.  

---

## 🛠️ Tech Stack
| Area | Tools |
|------|--------|
| Back-end | Python, Flask |
| Front-end | HTML, CSS, JavaScript |
| Version Control | Git, GitHub |
| Environment | macOS Terminal, Homebrew |
| Editor | VS Code |
| Deployment | Localhost (port 8080) |

---

## 🧩 Reflection
I built this app with support from ChatGPT, which helped me write and debug much of the code.  
I don’t yet understand every part of the codebase in detail, but I’m proud that I was able to guide the process, troubleshoot issues, and get the app working.  
Each time I revisit it, I understand a little more about how the pieces fit together.

This project was also a major milestone in my journey — the first time I used **Flask and back-end logic** to build something meaningful from scratch.  
I learned to troubleshoot environment issues, commit confidently with Git, and think through how data moves between user input, Python logic, and the interface.  

Most importantly, I built something that feels personal and useful — a tool that can grow with my family, and a stepping stone toward building more sophisticated, data-driven apps.

---
