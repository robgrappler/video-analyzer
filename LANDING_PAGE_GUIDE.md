# Landing Page Generator - Quick Guide

## ✅ Setup Complete

Your WordPress landing page generator is configured and ready to use!

### Configuration
- **Method:** SSH + WP-CLI (no REST API needed)
- **Template:** Elementor Canvas (full-width, no header/footer)
- **Default Status:** Draft (for manual review)
- **Site:** https://robgrappler.io

## 🚀 Creating Landing Pages

### Basic Usage

```bash
cd /Users/ppt04/Github/video-analyzer
source venv/bin/activate

python wordpress_ssh_generator.py \
  --video-name YOUR_VIDEO_NAME \
  --watchfighters-url YOUR_WATCHFIGHTERS_URL
```

### Example

```bash
python wordpress_ssh_generator.py \
  --video-name Match3Nocturmex25K-2.5pro \
  --watchfighters-url https://view.wf/v/mxxpfcbp
```

### Dry Run (Preview First)

```bash
python wordpress_ssh_generator.py \
  --video-name Match3Nocturmex25K-2.5pro \
  --watchfighters-url https://view.wf/v/mxxpfcbp \
  --dry-run
```

## 📋 Workflow

1. **Analyze video** (if not done already):
   ```bash
   ./gemini_sales_report.py video.mp4 --cta-url "https://view.wf/v/VIDEO_ID"
   ```

2. **Generate landing page**:
   ```bash
   python wordpress_ssh_generator.py \
     --video-name VideoName \
     --watchfighters-url https://view.wf/v/VIDEO_ID
   ```
   
   *Note: You'll be prompted for your SSH password 3-4 times during creation*

3. **Review in WordPress**:
   - Open the edit URL provided by the generator
   - Page will be in Elementor Canvas format
   - Click "Edit with Elementor" to customize if needed

4. **Publish**:
   - Click "Publish" button when satisfied

## 🎨 Elementor Canvas Features

All landing pages are created with:
- ✅ **Elementor Canvas template** (full control, no theme restrictions)
- ✅ **Elementor edit mode enabled** (can edit with Elementor immediately)
- ✅ **Responsive HTML content** (works great as-is, or customize with Elementor)

## 📊 What's Included in Each Page

From your video analysis, each landing page includes:

- **Hero Section**
  - Video title
  - Compelling description
  - Heat/Intensity/Technical ratings
  - Primary CTA button

- **Sales Highlights**
  - 6 key selling points with emojis

- **Match Details**
  - Wrestling style
  - Competitiveness level
  - Featured techniques (with difficulty ratings)

- **Key Moments**
  - 8-12 highlights with timestamps
  - Why each moment hooks viewers

- **Entertainment Value**
  - Rewatch rating
  - Production quality
  - Pacing breakdown

- **Buyer Tags**
  - Target audience tags

- **CTAs**
  - 3 strategically placed "Watch on WatchFighters" buttons
  - Automatic UTM tracking (utm_source, utm_medium, utm_campaign)

## 🔧 Configuration

Edit `wordpress_ssh_config.yaml` to customize:

```yaml
branding:
  primary_color: "#E91E63"      # Your brand color
  secondary_color: "#000000"     # Accent color

page_settings:
  default_status: draft          # or "publish" for auto-publish
  page_template: elementor_canvas # Elementor full-width template
```

## 🎯 Tips

### For New Videos

1. Run analyzer first: `./gemini_sales_report.py`
2. Generate landing page immediately after analysis
3. Video name should match analyzer folder name

### Updating Existing Pages

```bash
python wordpress_ssh_generator.py \
  --video-name VideoName \
  --watchfighters-url URL \
  --update
```

### Preview Before Creating

Always run with `--dry-run` first to see what will be created

### Editing in Elementor

1. Open the page in WordPress admin
2. Click "Edit with Elementor"
3. Customize the design, colors, layout as needed
4. The content structure is already there - just style it!

## 🐛 Troubleshooting

### SSH Password Prompts

You'll be asked for your SSH password 3-4 times:
- Once for content transfer
- 2-3 times for WP-CLI commands
- This is normal and secure

### Connection Issues

If SSH fails, verify:
```bash
ssh -p 65002 u830957326@46.202.196.43
```

### Re-run Setup

If you need to reconfigure:
```bash
python wordpress_ssh_setup.py
```

## 📁 Files

- `wordpress_ssh_generator.py` - Main generator script
- `wordpress_ssh_setup.py` - Setup wizard
- `wordpress_ssh_config.yaml` - Configuration (safe to commit)
- `.env` - NOT USED (SSH uses password auth)

## 🎉 Success Indicators

When a page is created successfully, you'll see:
```
✅ Page created successfully with Elementor Canvas

Page ID: XXXX
Title: Your Video Title
Slug: your-video-slug
Status: draft

🔗 Edit URL: https://robgrappler.io/wp-admin/post.php?post=XXXX&action=edit
🔗 View URL: https://robgrappler.io/?page_id=XXXX
```

## 📊 Your First Landing Page

- **Page ID:** 4737
- **Title:** "Tattooed Muscle vs. Bearded Bear: A Grueling Submission War"
- **Status:** Draft
- **Edit:** https://robgrappler.io/wp-admin/post.php?post=4737&action=edit
- **Template:** Elementor Canvas ✅

---

**Need help?** Check README_WORDPRESS.md for detailed documentation.
