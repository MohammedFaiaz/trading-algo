# How to Upload This Project to GitHub

This guide provides step-by-step instructions for uploading the trading bot code to your own GitHub repository.

### Where to Run These Commands

You need to run these commands on your **local computer**, not in the chat window.

1.  First, download all the project files to a folder on your computer.
2.  Open a **terminal** (on macOS/Linux) or a **Command Prompt/PowerShell** (on Windows).
3.  Use the `cd` command to navigate into the project folder you just downloaded. For example: `cd C:\Users\YourUser\Downloads\trading-bot-project`

Once you are inside the project folder in your terminal, you can run the following commands.

---

### Step 1: Initialize Git

This command sets up a new Git repository in your project folder. It only needs to be run once per project.

```bash
git init
```

---

### Step 2: Add Files to be Saved

This command prepares all the project files to be saved. The `.gitignore` file we created will automatically prevent your secret `.env` file from being added.

```bash
git add .
```

---

### Step 3: Save the Files (Commit)

This command saves the files to the repository's local history with a descriptive message.

```bash
git commit -m "Initial commit: Add trading bot application files"
```

---

### Step 4: Connect to Your GitHub Repository

1.  Go to [GitHub.com](https://github.com) and create a **new, empty repository**.
2.  **Important:** Do **not** initialize the new repository with a `README`, `license`, or `.gitignore` file on the website.
3.  After you create it, GitHub will give you a URL. It will look like `https://github.com/YourUsername/YourRepoName.git`.

Copy that URL and use it in the following command to link your local folder to your GitHub repository. **Remember to replace the example URL with your own.**

```bash
git remote add origin https://github.com/YourUsername/YourRepoName.git
```

---

### Step 5: Upload (Push) Your Code to GitHub

This final command sends all your saved files from your local computer to your GitHub repository.

*(Note: Your default branch might be named `master` or `main`. If the first command doesn't work, try the second one.)*

```bash
git push -u origin master
```
or
```bash
git push -u origin main
```

---

After these steps are complete, you can refresh your GitHub page, and you will see all your project files there, safely and without your secret keys.
