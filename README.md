# 🚀 Server Control Panel & Instructions

This guide provides step-by-step instructions on how to start, monitor, and stop the servers in your development environment.

---

## 1. Job Hunter Server (Flask / Python)
* **Default Port:** `5001`
* **Directory:** `/Users/kiranlalk/Desktop/job hunter`

### 🔼 How to Start
Activate the Python virtual environment and run the Flask application:
```bash
# 1. Navigate to the project directory
cd "/Users/kiranlalk/Desktop/job hunter"

# 2. Activate the virtual environment
source venv/bin/activate

# 3. Run the application
python app.py
```
The server will start running at **`http://localhost:5001`**.

### 🔽 How to Stop
* **Standard Way:** Press `Ctrl + C` in the terminal window where the server is running.
* **Force Kill (if running in background/hung):**
  Run the following commands in any terminal:
  ```bash
  # Find the Process ID (PID) running on port 5001
  lsof -i :5001

  # Kill the process (replace <PID> with the actual number from the command above)
  kill -9 <PID>
  
  # Or kill it directly in one command:
  kill -9 $(lsof -t -i:5001)
  ```

---

## 2. Portfolio Server (Vite / Node.js)
* **Default Port:** `5173`
* **Directory:** `/Users/kiranlalk/Desktop/kiran-portfolio`

### 🔼 How to Start
Run the Vite development command:
```bash
# 1. Navigate to the portfolio directory
cd "/Users/kiranlalk/Desktop/kiran-portfolio"

# 2. Start the dev server
npm run dev
```
The server will start running at **`http://localhost:5173`**.

### 🔽 How to Stop
* **Standard Way:** Press `Ctrl + C` in the terminal window where the server is running.
* **Force Kill (if running in background/hung):**
  Run the following commands in any terminal:
  ```bash
  # Find the Process ID (PID) running on port 5173
  lsof -i :5173

  # Kill the process
  kill -9 $(lsof -t -i:5173)
  ```

---

## 🔍 Useful Diagnostic Commands

* **Check all listening TCP ports:**
  ```bash
  lsof -iTCP -sTCP:LISTEN
  ```
* **Check if a specific port is in use:**
  ```bash
  lsof -i :5001
  lsof -i :5173
  ```
# JOB-HUNTER
