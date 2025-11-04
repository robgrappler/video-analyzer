# WordPress Landing Page Generator

Automatically create high-converting landing pages on robgrappler.io from video analyzer output.

## Overview

This tool generates professional, conversion-focused landing pages for your wrestling videos by:
- **Pulling video analysis data** from your analyzer output (JSON + sales report)
- **Creating WordPress pages** via REST API
- **Building responsive HTML** with your brand colors
- **Including WatchFighters CTAs** with UTM tracking
- **Saving as drafts** for manual review before publishing

## Prerequisites

- WordPress admin access to robgrappler.io
- Ability to create Application Passwords (requires permalink structure)
- Python 3.10+
- Completed video analysis (gemini_sales_report.py output)

## Quick Start

### 1. Install Dependencies

```bash
cd /Users/ppt04/Github/video-analyzer

# Install WordPress-specific requirements
pip install -r wordpress_requirements.txt
```

### 2. Run Setup Wizard

```bash
python wordpress_setup.py
```

The wizard will guide you through:
1. Creating a WordPress Application Password
2. Testing your connection
3. Saving configuration

**Application Password Creation:**
1. Go to https://robgrappler.io/wp-admin
2. Navigate to: Users → Profile
3. Scroll to "Application Passwords"
4. Name: "Landing Page Generator"
5. Click "Add New Application Password"
6. **COPY the password immediately** (format: `xxxx xxxx xxxx xxxx xxxx xxxx`)

### 3. Generate Your First Landing Page

```bash
# Dry run (preview only)
python wordpress_landing_page_generator.py \
  --video-name Match3Nocturmex25K \
  --watchfighters-url https://www.watchfighters.com/watch/12345 \
  --dry-run

# Create draft page
python wordpress_landing_page_generator.py \
  --video-name Match3Nocturmex25K \
  --watchfighters-url https://www.watchfighters.com/watch/12345
```

### 4. Review & Publish

1. Open the edit URL provided by the generator
2. Review the content in WordPress
3. Click "Publish" when ready

## Usage

### Command-Line Options

```bash
python wordpress_landing_page_generator.py \
  --video-name <VIDEO_NAME> \           # Required: e.g., Match3Nocturmex25K
  --watchfighters-url <URL> \            # Required: WatchFighters video URL
  [--path <PATH>] \                      # Optional: explicit analyzer folder path
  [--template <NAME>] \                  # Optional: custom template name
  [--publish] \                          # Optional: publish immediately (default: draft)
  [--dry-run] \                          # Optional: preview without creating
  [--update] \                           # Optional: update existing page
  [--verbose]                            # Optional: extra logging
```

### Examples

**Basic Usage:**
```bash
python wordpress_landing_page_generator.py \
  --video-name "Rob vs Dexter" \
  --watchfighters-url https://www.watchfighters.com/watch/abc123
```

**Dry Run (Preview):**
```bash
python wordpress_landing_page_generator.py \
  --video-name "Rob vs Dexter" \
  --watchfighters-url https://www.watchfighters.com/watch/abc123 \
  --dry-run
```

**Update Existing Page:**
```bash
python wordpress_landing_page_generator.py \
  --video-name "Rob vs Dexter" \
  --watchfighters-url https://www.watchfighters.com/watch/abc123 \
  --update
```

**Custom Analyzer Path:**
```bash
python wordpress_landing_page_generator.py \
  --video-name "Match Video" \
  --watchfighters-url https://www.watchfighters.com/watch/xyz789 \
  --path /path/to/custom/analysis/folder
```

## How It Works

### Data Flow

```
Video Analyzer Output
    ↓
{video_name}/analysis/
  ├── {video_name}_analysis.json      ← Sales metrics, techniques, moments
  └── {video_name}_sales_report.txt   ← Human-readable report
    ↓
WordPress Landing Page Generator
    ↓
WordPress REST API
    ↓
robgrappler.io (Draft Page)
```

### Content Mapping

The generator maps analyzer data to page sections:

#### Hero Section
- **Heading:** `titles[0]` from analysis
- **Subheading:** `descriptions[0]` from analysis
- **Badges:** Heat, Intensity, Technical ratings
- **CTA Button:** "Watch on WatchFighters"

#### Sales Highlights
- **Bullets:** First 6 items from `bullets[]`
- **Emojis:** ⭐, 💥, 🎯 for visual appeal

#### Match Details
- **Style:** `style` (e.g., "Mixed", "Submission Grappling")
- **Competitiveness:** `competitiveness_10`
- **Momentum Shifts:** Count of major turning points
- **Featured Techniques:** First 8 from `techniques[]` with difficulty ratings

#### Key Moments
- **8-12 highlights** from `highlight_moments[]`
- **Timestamps:** Converted to MM:SS format
- **Type & Hook:** Why each moment matters
- **Mid-page CTA:** Encourages action after reading highlights

#### Entertainment Value
- **Rewatch Value:** `rewatch_value_10`
- **Production Quality:** `capture_rating_10`
- **Pacing Breakdown:** Early/Mid/Late ratings

#### Buyer Tags
- **Tags:** All items from `buyer_tags[]`
- **Styled Pills:** Inline, easy-to-scan format

#### Final CTA
- **Call to Action:** "Get Access on WatchFighters"
- **UTM Tracking:** Automatic campaign tracking

### UTM Parameters

All CTAs automatically include:
```
?utm_source=robgrappler.io
&utm_medium=landing
&utm_campaign={page-slug}
```

This helps track conversions from landing pages in WatchFighters analytics.

## Configuration

### wordpress_config.yaml

```yaml
wordpress:
  site_url: "https://robgrappler.io"
  username: "YOUR_USERNAME"
  app_password: ""  # Stored in .env

branding:
  primary_color: "#E91E63"      # Pink accent
  secondary_color: "#000000"     # Black
  font_family: "Arial, Helvetica, sans-serif"

watchfighters:
  profile_url: "https://www.watchfighters.com/channels/Robgrappler"
  video_url_template: "https://www.watchfighters.com/watch/{video_id}"

page_settings:
  default_status: "draft"
  page_template: "elementor_header_footer"
  category: "Wrestling Videos"
  use_categories_for_pages: false

templates:
  default: "default_conversion"
  custom_path: "templates/elementor/"
```

**Customization:**
- **Branding colors:** Update `primary_color` and `secondary_color`
- **Page template:** Change `page_template` if using a custom WordPress template
- **Default status:** Set to `"publish"` to auto-publish (not recommended)

### .env

```bash
WP_APP_PASSWORD=xxxxxxxxxxxxxxxxxxxx
```

**Security:**
- This file is `.gitignore`d by default
- Never commit to version control
- Permissions set to `600` (owner read/write only)

## Elementor Support

### Current Implementation

The generator creates **HTML content** that:
- Works immediately without Elementor
- Uses responsive CSS grid layouts
- Can be converted to Elementor later

### Future: Custom Templates

To use custom Elementor templates:

1. **Create template in Elementor:**
   - Design your landing page in Elementor
   - Export as JSON (if using Elementor Pro)

2. **Save template:**
   ```bash
   templates/elementor/my_custom_template.json
   ```

3. **Use template:**
   ```bash
   python wordpress_landing_page_generator.py \
     --video-name VideoName \
     --watchfighters-url URL \
     --template my_custom_template
   ```

**Placeholder Support (Planned):**
- `{{hero_title}}` - Page title
- `{{hero_sub}}` - Subtitle/description
- `{{cta_url}}` - WatchFighters URL with UTM
- `{{badges}}` - Heat/Intensity/Technical badges
- `{{highlights}}` - Sales highlights list
- `{{techniques}}` - Technique list
- `{{moments}}` - Key moments with timestamps
- `{{buyer_tags}}` - Tag pills

## Troubleshooting

### Authentication Errors

**Problem:** `❌ WordPress authentication failed`

**Solutions:**
1. **Verify Application Password:**
   - Re-run `python wordpress_setup.py`
   - Create a fresh Application Password
   - Ensure no extra spaces in password

2. **Check Permalinks:**
   - Go to WordPress → Settings → Permalinks
   - Must be set to "Post name" or custom structure
   - Save changes (this flushes rewrite rules)

3. **Security Plugins:**
   - Some plugins block REST API access
   - Check: Wordfence, iThemes Security, All In One WP Security
   - Add exception for REST API routes

4. **Test manually:**
   ```bash
   curl -u "username:password" \
     https://robgrappler.io/wp-json/wp/v2/users/me
   ```

### Analysis Not Found

**Problem:** `❌ Analysis directory not found`

**Solutions:**
1. **Check video name:**
   - Use exact folder name (case-sensitive)
   - Example: `Match3Nocturmex25K` not `match3nocturmex25k`

2. **Verify folder structure:**
   ```
   Match3Nocturmex25K/
     └── analysis/
         ├── Match3Nocturmex25K_analysis.json  ← Required
         └── Match3Nocturmex25K_sales_report.txt
   ```

3. **Use explicit path:**
   ```bash
   --path /full/path/to/Match3Nocturmex25K/analysis
   ```

### Page Creation Fails

**Problem:** `Failed to create page: 403` or `500`

**Solutions:**
1. **403 Forbidden:**
   - Your user lacks page creation permissions
   - Grant "Editor" or "Administrator" role

2. **500 Server Error:**
   - Check WordPress error logs
   - May be theme/plugin conflict
   - Try disabling plugins temporarily

3. **Template not found:**
   - Check `page_template` value in config
   - Try setting to empty string: `page_template: ""`

### Elementor Meta Save Blocked

**Note:** Some WordPress setups restrict Elementor meta updates via REST API.

**Current Behavior:**
- Generator uses HTML content (always works)
- You can "Convert to Elementor" manually in WordPress
- HTML content remains as fallback

**Future Enhancement:**
- Detect Elementor meta capabilities
- Auto-switch to direct Elementor JSON if supported

## Workflow Integration

### Recommended Process

1. **Analyze video:**
   ```bash
   cd /Users/ppt04/Github/video-analyzer
   ./gemini_sales_report.py video.mp4 \
     --cta-url "https://www.watchfighters.com/watch/VIDEO_ID"
   ```

2. **Generate landing page:**
   ```bash
   cd /Users/ppt04/Github/video-analyzer
   python wordpress_landing_page_generator.py \
     --video-name VideoName \
     --watchfighters-url https://www.watchfighters.com/watch/VIDEO_ID
   ```

3. **Review draft:**
   - Open edit URL from generator output
   - Adjust content if needed
   - Add custom images/embeds

4. **Publish:**
   - Click "Publish" in WordPress
   - Share landing page URL

### Batch Processing

To generate pages for multiple videos:

```bash
# Create a simple script
for video in "Match1" "Match2" "Match3"; do
  python wordpress_landing_page_generator.py \
    --video-name "$video" \
    --watchfighters-url "https://www.watchfighters.com/watch/${video}"
done
```

## Security Best Practices

1. **Never commit `.env`:**
   - Already in `.gitignore`
   - Contains your Application Password

2. **Rotate passwords:**
   - Delete old Application Passwords in WordPress
   - Create new ones periodically

3. **Use least privilege:**
   - Application Passwords only need "Editor" role
   - Don't use Administrator if not needed

4. **Monitor usage:**
   - Check WordPress user logs
   - Revoke compromised passwords immediately

## FAQ

### Can I automate this completely?

Yes, but **manual review is recommended**. Reasons:
- Catch analyzer edge cases
- Add custom touches
- Verify WatchFighters URL is correct
- Check for typos or formatting issues

For full automation, use `--publish` flag (at your own risk).

### Do I need Elementor Pro?

No. The generator works with:
- **Free Elementor:** Can manually edit with Elementor later
- **Elementor Pro:** Future template import support
- **No Elementor:** HTML content works standalone

### Can I customize the HTML template?

Yes! Edit `build_html_content()` function in `wordpress_landing_page_generator.py`:
- Change layout structure
- Adjust CSS styles
- Add new sections
- Reorder content

### How do I track conversions?

UTM parameters are automatically added to all CTAs:
```
utm_source=robgrappler.io
utm_medium=landing
utm_campaign={video-slug}
```

View in:
- WatchFighters analytics (if supported)
- Google Analytics (if installed on WF)
- Your own tracking pixel

### Can I use this for other platforms?

The generator is designed for WordPress REST API. To adapt:
- Implement a different client class
- Keep the analyzer data ingestion
- Change content builders as needed

## Support

### Issues

If you encounter problems:

1. **Run in verbose mode:**
   ```bash
   python wordpress_landing_page_generator.py \
     --video-name VideoName \
     --watchfighters-url URL \
     --verbose
   ```

2. **Check configuration:**
   ```bash
   cat wordpress_config.yaml
   ```

3. **Test authentication:**
   ```bash
   python wordpress_setup.py
   ```

4. **Dry run to debug:**
   ```bash
   python wordpress_landing_page_generator.py \
     --video-name VideoName \
     --watchfighters-url URL \
     --dry-run
   ```

### Future Enhancements

Planned features:
- Full Elementor template support
- Automatic thumbnail upload
- A/B testing variations
- Bulk update tool
- Analytics integration
- Video embed support
- Social sharing meta tags
- Schema.org markup for SEO

## License

Private tool for personal content creation workflow.

---

**Built for:** Automating landing page creation for robgrappler.io wrestling content library.
