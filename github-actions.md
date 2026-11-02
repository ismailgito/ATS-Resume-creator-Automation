  ## Step 1 — Host Your CSV at a Public URL
  
  You have 3 options. GitHub Gist is easiest:
  
  1. Go to https://gist.github.com                                                                                                                      
  2. Create a file named jobs.csv with this format:                                                                                                     
    title,company,location,url,description                                                                                                              
    Senior Performance Marketer,Zalando,Berlin,https://...,Full job description text here...                                                            
    Growth Marketing Lead,Delivery Hero,Remote,https://...,Another job description here...                                                              
  
  3. Click "Create secret gist"
  4. Open the raw file → copy the URL (it looks like https://gist.githubusercontent.com/yourname/abc123/raw/jobs.csv)                                   
  ──────
  ## Step 2 — Add 4 GitHub Secrets
  
  Go to your repo → Settings → Secrets and variables → Actions → New repository secret
  
   Secret Name                                                               │ Where to Get It
  ───────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────
   TELEGRAM_CHAT_ID                                                          │ Message @userinfobot on Telegram
                                                              
  [1]: aistudio.google.com https://aistudio.google.com/apikey
  ──────
  ## Step 3 — Commit the New Workflow
    
    cd C:\Users\Lenovo\Documents\ATS-Resume-creator-Automation
    git add .github/workflows/daily-automation.yml
    git commit -m "Add daily CSV automation workflow with Telegram notifications"
    git push
  ──────                                          
  ## How It Runs                                                                 
    
    Daily 1:30 PM IST (automatic)     
        ↓ Downloads your CSV from Gist   
        ↓ Scores each job vs your profile
        ↓ Generates PDF + DOCX + cover note for qualifying jobs (score ≥ 75)
        ↓ Uploads all packages as a downloadable artifact (kept 30 days)           
        ↓ Sends Telegram: "OK: ATS Daily CSV Run | Jobs: 12 | Packages: 5 | <link>"
  
  You can also trigger it manually any time from Actions tab with optional overrides (different CSV URL, score threshold, or force-generate all rows).
  ──────
  ### Update Your CSV Any Time
  
  Just edit the Gist online — no git push required. The next run automatically picks up the new jobs.