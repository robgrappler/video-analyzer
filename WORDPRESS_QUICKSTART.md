# WordPress Landing Page Generator - Quick Start

## 🚀 Get Started in 5 Minutes

### Step 1: Install Dependencies (2 min)

```bash
cd /Users/ppt04/Github/video-analyzer
pip install -r wordpress_requirements.txt
```

### Step 2: Run Setup Wizard (3 min)

```bash
python wordpress_setup.py
```

**You'll need:**
- WordPress admin access
- Application Password (wizard guides you through creation)

### Step 3: Generate Landing Page (30 sec)

```bash
python wordpress_landing_page_generator.py \
  --video-name Match3Nocturmex25K \
  --watchfighters-url https://www.watchfighters.com/watch/VIDEO_ID
```

**Done!** Open the edit URL to review your draft page.

---

## 📋 What You Get

Each landing page includes:

✅ **Hero section** with video title and ratings  
✅ **Sales highlights** (6 key selling points)  
✅ **Match details** (style, techniques, competitiveness)  
✅ **Key moments** with timestamps  
✅ **Entertainment value** ratings  
✅ **Buyer tags** (target audience)  
✅ **3 CTA buttons** to WatchFighters with UTM tracking  

---

## 🔑 Common Commands

### Preview Before Creating
```bash
python wordpress_landing_page_generator.py \
  --video-name VideoName \
  --watchfighters-url URL \
  --dry-run
```

### Update Existing Page
```bash
python wordpress_landing_page_generator.py \
  --video-name VideoName \
  --watchfighters-url URL \
  --update
```

### Publish Immediately (Skip Draft)
```bash
python wordpress_landing_page_generator.py \
  --video-name VideoName \
  --watchfighters-url URL \
  --publish
```
⚠️ **Not recommended** - always review drafts first!

---

## 🛠 Troubleshooting

### "Configuration not found"
→ Run `python wordpress_setup.py`

### "Authentication failed"
→ Check WordPress → Settings → Permalinks (must be "Post name")  
→ Verify Application Password in .env

### "Analysis directory not found"
→ Use exact video name (case-sensitive)  
→ Or use `--path /full/path/to/analysis/folder`

---

## 📖 Full Documentation

For detailed information, see [README_WORDPRESS.md](README_WORDPRESS.md)

Topics covered:
- Content mapping (analyzer → page sections)
- Configuration options
- Elementor support
- Security best practices
- Batch processing
- FAQ

---

## 🎯 Recommended Workflow

1. **Analyze video** with `gemini_sales_report.py`
2. **Generate landing page** (this tool)
3. **Review draft** in WordPress admin
4. **Publish** when ready
5. **Share** landing page URL

---

**Need help?** Check README_WORDPRESS.md or run `python wordpress_setup.py` to reconfigure.
