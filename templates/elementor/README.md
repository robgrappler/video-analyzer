# Elementor Templates

This directory stores custom Elementor template JSON files.

## Usage

### Option 1: Use Default Template (HTML)

The generator creates responsive HTML by default. No template needed.

```bash
python wordpress_landing_page_generator.py \
  --video-name VideoName \
  --watchfighters-url URL
```

### Option 2: Custom Template (Future)

1. Design your landing page in Elementor
2. Export as JSON
3. Save here as `my_template.json`
4. Use with `--template my_template`

```bash
python wordpress_landing_page_generator.py \
  --video-name VideoName \
  --watchfighters-url URL \
  --template my_template
```

## Template Placeholders

When creating custom templates, use these placeholders:

- `{{hero_title}}` - Video title
- `{{hero_sub}}` - Subtitle/description
- `{{cta_url}}` - WatchFighters URL (with UTM)
- `{{intensity}}` - Intensity rating (1-10)
- `{{heat}}` - Heat factor (1-5)
- `{{technical}}` - Technical rating (1-10)
- `{{style}}` - Wrestling style
- `{{highlights}}` - Sales highlights list
- `{{techniques}}` - Technique list
- `{{moments}}` - Key moments with timestamps
- `{{tags}}` - Buyer tags

## Notes

- Template support is planned for future releases
- Current version uses HTML with embedded CSS
- HTML output can be manually edited with Elementor

## Example Structure

```json
{
  "version": "1.0",
  "name": "conversion_template",
  "sections": [
    {
      "type": "hero",
      "title": "{{hero_title}}",
      "subtitle": "{{hero_sub}}",
      "cta_url": "{{cta_url}}"
    }
  ]
}
```

(This is a conceptual example - actual Elementor JSON structure is more complex)
