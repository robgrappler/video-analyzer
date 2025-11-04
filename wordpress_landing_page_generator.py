#!/usr/bin/env python3
"""
WordPress Landing Page Generator
Creates conversion-focused landing pages from video analyzer output.
"""

import os
import sys
import json
import yaml
import argparse
import time
import re
import requests
from pathlib import Path
from base64 import b64encode
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv


# ==================== DATA MODELS ====================

@dataclass
class VideoModel:
    """Normalized video analysis data model."""
    video_name: str
    
    # Core metrics
    intensity_10: int = 7
    competitiveness_10: int = 7
    technical_rating_10: int = 7
    heat_factor_5: int = 4
    rewatch_value_10: int = 7
    capture_rating_10: int = 7
    
    # Style & structure
    style: str = "mixed"
    momentum_shifts: List[Dict] = field(default_factory=list)
    techniques: List[Dict] = field(default_factory=list)
    physiques: List[Dict] = field(default_factory=list)
    highlight_moments: List[Dict] = field(default_factory=list)
    
    # Copy kit
    titles: List[str] = field(default_factory=list)
    descriptions: List[str] = field(default_factory=list)
    bullets: List[str] = field(default_factory=list)
    buyer_tags: List[str] = field(default_factory=list)
    cta: str = ""
    
    # Raw text
    sales_report_snippet: str = ""
    
    # Pacing
    pacing_curve: Dict = field(default_factory=dict)


# ==================== UTILITIES ====================

def load_config() -> Dict[str, Any]:
    """Load configuration from wordpress_config.yaml and .env."""
    config_path = Path("wordpress_config.yaml")
    
    if not config_path.exists():
        print("❌ Configuration not found!")
        print("   Run: python wordpress_setup.py")
        sys.exit(1)
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Load secrets from .env
    load_dotenv()
    app_password = os.getenv("WP_APP_PASSWORD")
    
    if not app_password:
        print("❌ WP_APP_PASSWORD not found in .env!")
        print("   Run: python wordpress_setup.py")
        sys.exit(1)
    
    config['wordpress']['app_password'] = app_password
    
    return config


def kebab_case(text: str) -> str:
    """Convert text to kebab-case slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text.strip('-')


def format_timestamp(seconds: int) -> str:
    """Convert seconds to MM:SS format."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def add_utm_params(url: str, slug: str) -> str:
    """Add UTM parameters to URL."""
    separator = '&' if '?' in url else '?'
    return f"{url}{separator}utm_source=robgrappler.io&utm_medium=landing&utm_campaign={slug}"


# ==================== ANALYZER DATA INGESTION ====================

def load_analyzer_data(video_name: str, analysis_path: Optional[Path] = None) -> VideoModel:
    """Load and validate analyzer output data."""
    
    if analysis_path:
        base_dir = analysis_path
    else:
        base_dir = Path(f"{video_name}/analysis")
    
    if not base_dir.exists():
        print(f"❌ Analysis directory not found: {base_dir}")
        print(f"   Expected structure: {video_name}/analysis/")
        sys.exit(1)
    
    # Find files (handle various naming patterns)
    json_files = list(base_dir.glob("*_analysis.json")) + list(base_dir.glob("*.json"))
    txt_files = list(base_dir.glob("*_sales_report.txt")) + list(base_dir.glob("*_analysis.txt"))
    
    if not json_files:
        print(f"❌ No analysis JSON found in {base_dir}")
        sys.exit(1)
    
    json_path = json_files[0]
    
    # Load JSON
    with open(json_path) as f:
        data = json.load(f)
    
    # Load sales report snippet if available
    sales_snippet = ""
    if txt_files:
        with open(txt_files[0]) as f:
            sales_snippet = f.read()[:500]
    
    # Build model with defaults
    model = VideoModel(
        video_name=video_name,
        intensity_10=data.get('intensity_10', 7),
        competitiveness_10=data.get('competitiveness_10', 7),
        technical_rating_10=data.get('technical_rating_10', 7),
        heat_factor_5=data.get('heat_factor_5', 4),
        rewatch_value_10=data.get('rewatch_value_10', 7),
        capture_rating_10=data.get('capture_rating_10', 7),
        style=data.get('style', 'mixed'),
        momentum_shifts=data.get('momentum_shifts', []),
        techniques=data.get('techniques', []),
        physiques=data.get('physiques', []),
        highlight_moments=data.get('highlight_moments', []),
        titles=data.get('titles', [f"{video_name} | RobGrappler"]),
        descriptions=data.get('descriptions', []),
        bullets=data.get('bullets', []),
        buyer_tags=data.get('buyer_tags', []),
        cta=data.get('cta', ''),
        pacing_curve=data.get('pacing_curve', {}),
        sales_report_snippet=sales_snippet
    )
    
    return model


# ==================== WORDPRESS REST CLIENT ====================

class WordPressClient:
    """WordPress REST API client with Application Password auth."""
    
    def __init__(self, site_url: str, username: str, app_password: str):
        self.site_url = site_url.rstrip('/')
        self.username = username
        self.app_password = app_password
        self.session = requests.Session()
        
        # Setup auth header
        auth_string = f"{username}:{app_password}"
        encoded_auth = b64encode(auth_string.encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/json'
        })
    
    def test_auth(self) -> tuple:
        """Test authentication."""
        try:
            resp = self.session.get(f"{self.site_url}/wp-json/wp/v2/users/me", timeout=10)
            if resp.status_code == 200:
                return True, resp.json()
            return False, f"Auth failed: {resp.status_code}"
        except Exception as e:
            return False, str(e)
    
    def get_page_by_slug(self, slug: str) -> Optional[Dict]:
        """Get page by slug."""
        try:
            resp = self.session.get(
                f"{self.site_url}/wp-json/wp/v2/pages",
                params={'slug': slug},
                timeout=10
            )
            if resp.status_code == 200:
                pages = resp.json()
                return pages[0] if pages else None
            return None
        except Exception:
            return None
    
    def create_page(self, title: str, slug: str, content: str, status: str = 'draft',
                    meta: Optional[Dict] = None, template: str = '') -> Dict:
        """Create a new page."""
        payload = {
            'title': title,
            'slug': slug,
            'content': content,
            'status': status,
            'template': template
        }
        
        if meta:
            payload['meta'] = meta
        
        try:
            resp = self.session.post(
                f"{self.site_url}/wp-json/wp/v2/pages",
                json=payload,
                timeout=30
            )
            
            if resp.status_code in [200, 201]:
                return resp.json()
            else:
                raise Exception(f"Create failed: {resp.status_code} - {resp.text[:300]}")
        except Exception as e:
            raise Exception(f"Failed to create page: {str(e)}")
    
    def update_page(self, page_id: int, **kwargs) -> Dict:
        """Update an existing page."""
        try:
            resp = self.session.post(
                f"{self.site_url}/wp-json/wp/v2/pages/{page_id}",
                json=kwargs,
                timeout=30
            )
            
            if resp.status_code == 200:
                return resp.json()
            else:
                raise Exception(f"Update failed: {resp.status_code} - {resp.text[:300]}")
        except Exception as e:
            raise Exception(f"Failed to update page: {str(e)}")


# ==================== CONTENT BUILDERS ====================

def build_html_content(model: VideoModel, cta_url: str, branding: Dict, hero_image_url: str = None, gallery_images: list = None) -> str:
    """Build HTML fallback content."""
    
    primary = branding.get('primary_color', '#E91E63')
    secondary = branding.get('secondary_color', '#000000')
    
    title = model.titles[0] if model.titles else f"{model.video_name} | RobGrappler"
    subtitle = model.descriptions[0] if model.descriptions else model.sales_report_snippet[:200]
    
    # Default to empty lists if not provided
    gallery_images = gallery_images or []
    
    html = f"""
<style>
.lp-hero {{ background: linear-gradient(135deg, {primary}, {secondary}); color: white; padding: 60px 20px; text-align: center; }}
.lp-hero h1 {{ font-size: 2.5em; margin-bottom: 20px; }}
.lp-hero p {{ font-size: 1.2em; margin-bottom: 30px; }}
.lp-badges {{ display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin: 20px 0; }}
.lp-badge {{ background: rgba(255,255,255,0.2); padding: 10px 20px; border-radius: 25px; }}
.lp-cta {{ display: inline-block; background: {primary}; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; font-size: 1.2em; margin: 20px 0; }}
.lp-section {{ max-width: 1200px; margin: 40px auto; padding: 0 20px; }}
.lp-section h2 {{ color: {primary}; font-size: 2em; margin-bottom: 20px; }}
.lp-highlights {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
.lp-highlight {{ border-left: 4px solid {primary}; padding-left: 15px; }}
.lp-tags {{ display: flex; gap: 10px; flex-wrap: wrap; }}
.lp-tag {{ background: {secondary}; color: white; padding: 5px 15px; border-radius: 15px; font-size: 0.9em; }}
.lp-hero-image {{ max-width: 100%; height: auto; border-radius: 10px; margin: 20px 0; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }}
.lp-gallery {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 30px 0; }}
.lp-gallery img {{ width: 100%; height: 200px; object-fit: cover; border-radius: 8px; cursor: pointer; transition: transform 0.2s; }}
.lp-gallery img:hover {{ transform: scale(1.05); }}
</style>

<!-- Hero Section -->
<div class="lp-hero">
    <h1>{title}</h1>
    <p>{subtitle}</p>
    {f'<img src="{hero_image_url}" alt="{title}" class="lp-hero-image">' if hero_image_url else ''}
    <div class="lp-badges">
        <div class="lp-badge">🔥 Heat: {model.heat_factor_5}/5</div>
        <div class="lp-badge">⚔️ Intensity: {model.intensity_10}/10</div>
        <div class="lp-badge">🧠 Technical: {model.technical_rating_10}/10</div>
    </div>
    <a href="{cta_url}" class="lp-cta" target="_blank">Watch on WatchFighters</a>
</div>

<!-- Sales Highlights -->
<div class="lp-section">
    <h2>What You'll See</h2>
    <div class="lp-highlights">
"""
    
    # Add bullets
    for bullet in model.bullets[:6]:
        html += f'        <div class="lp-highlight">⭐ {bullet}</div>\n'
    
    html += """    </div>
</div>

<!-- Match Details -->
<div class="lp-section">
    <h2>Match Details</h2>
"""
    
    html += f"""    <p><strong>Style:</strong> {model.style.title()}</p>
    <p><strong>Competitiveness:</strong> {model.competitiveness_10}/10</p>
    <p><strong>Momentum Shifts:</strong> {len(model.momentum_shifts)} major turning points</p>
"""
    
    # Add techniques
    if model.techniques:
        html += "    <h3>Featured Techniques</h3>\n    <ul>\n"
        for tech in model.techniques[:8]:
            html += f"        <li><strong>{tech.get('name', 'Unknown')}</strong> - {tech.get('type', 'technique')} (Difficulty: {tech.get('difficulty_5', 3)}/5)</li>\n"
        html += "    </ul>\n"
    
    html += "</div>\n\n"
    
    # Highlight Moments
    if model.highlight_moments:
        html += """<div class="lp-section">
    <h2>Key Moments</h2>
"""
        for moment in model.highlight_moments[:10]:
            timestamp = format_timestamp(moment.get('time_s', 0))
            html += f"""    <div class="lp-highlight">
        <strong>{timestamp}</strong> - {moment.get('type', 'moment').replace('_', ' ').title()}<br>
        {moment.get('why_it_hooks', 'Intense action')}
    </div>
"""
        html += "    <a href=\"" + cta_url + "\" class=\"lp-cta\" target=\"_blank\">Watch Full Match</a>\n"
        
        # Add image gallery if available
        if gallery_images:
            html += "    <h3 style='margin-top: 30px;'>Action Highlights</h3>\n"
            html += "    <div class=\"lp-gallery\">\n"
            for img in gallery_images[:8]:  # Show max 8 images
                html += f"        <img src=\"{img['url']}\" alt=\"{img.get('caption', 'Match highlight')}\" loading=\"lazy\">\n"
            html += "    </div>\n"
        
        html += "</div>\n\n"
    
    # Entertainment Value
    html += f"""<div class="lp-section">
    <h2>Entertainment Value</h2>
    <p><strong>Rewatch Value:</strong> {model.rewatch_value_10}/10</p>
    <p><strong>Production Quality:</strong> {model.capture_rating_10}/10</p>
"""
    
    if model.pacing_curve:
        html += f"""    <p><strong>Pacing:</strong> Early {model.pacing_curve.get('early_10', 7)}/10, Mid {model.pacing_curve.get('mid_10', 7)}/10, Late {model.pacing_curve.get('late_10', 8)}/10</p>
"""
    
    html += "</div>\n\n"
    
    # Buyer Tags
    if model.buyer_tags:
        html += """<div class="lp-section">
    <h2>Perfect For Fans Of</h2>
    <div class="lp-tags">
"""
        for tag in model.buyer_tags:
            html += f'        <span class="lp-tag">{tag}</span>\n'
        html += """    </div>
</div>

"""
    
    # Final CTA
    html += f"""<div class="lp-hero">
    <h2>Ready to Watch?</h2>
    <a href="{cta_url}" class="lp-cta" target="_blank">Get Access on WatchFighters</a>
</div>
"""
    
    return html


def build_elementor_json(model: VideoModel, cta_url: str, branding: Dict) -> List[Dict]:
    """Build Elementor page structure (simplified for MVP)."""
    # Note: Full Elementor JSON structure is complex. 
    # This is a simplified version. Real implementation would be more detailed.
    
    primary = branding.get('primary_color', '#E91E63')
    title = model.titles[0] if model.titles else f"{model.video_name} | RobGrappler"
    subtitle = model.descriptions[0] if model.descriptions else ""
    
    structure = [
        {
            "id": generate_id(),
            "elType": "section",
            "settings": {"background_color": primary},
            "elements": [
                {
                    "id": generate_id(),
                    "elType": "column",
                    "elements": [
                        {
                            "id": generate_id(),
                            "elType": "widget",
                            "widgetType": "heading",
                            "settings": {
                                "title": title,
                                "title_color": "#FFFFFF"
                            }
                        },
                        {
                            "id": generate_id(),
                            "elType": "widget",
                            "widgetType": "text-editor",
                            "settings": {
                                "editor": subtitle,
                                "text_color": "#FFFFFF"
                            }
                        },
                        {
                            "id": generate_id(),
                            "elType": "widget",
                            "widgetType": "button",
                            "settings": {
                                "text": "Watch on WatchFighters",
                                "link": {"url": cta_url, "is_external": True},
                                "button_background_color": "#FFFFFF",
                                "button_text_color": primary
                            }
                        }
                    ]
                }
            ]
        }
    ]
    
    return structure


def generate_id() -> str:
    """Generate Elementor-style element ID."""
    import hashlib
    import time
    return hashlib.md5(str(time.time()).encode()).hexdigest()[:7]


# ==================== MAIN WORKFLOW ====================

def main():
    parser = argparse.ArgumentParser(
        description="Generate WordPress landing pages from video analyzer output"
    )
    parser.add_argument('--video-name', required=True, help='Video name (e.g., Match3Nocturmex25K)')
    parser.add_argument('--watchfighters-url', required=True, help='WatchFighters video URL')
    parser.add_argument('--path', help='Explicit path to analyzer folder')
    parser.add_argument('--template', help='Elementor template name (optional)')
    parser.add_argument('--publish', action='store_true', help='Publish immediately (default: draft)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without creating')
    parser.add_argument('--update', action='store_true', help='Update existing page')
    parser.add_argument('--verbose', action='store_true', help='Extra logging')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("  WordPress Landing Page Generator")
    print("="*70 + "\n")
    
    # Load configuration
    print("📋 Loading configuration...")
    config = load_config()
    branding = config['branding']
    wp_config = config['wordpress']
    
    # Load analyzer data
    print(f"📊 Loading analysis for: {args.video_name}")
    analysis_path = Path(args.path) if args.path else None
    model = load_analyzer_data(args.video_name, analysis_path)
    print(f"✅ Analysis loaded: {len(model.techniques)} techniques, {len(model.highlight_moments)} moments")
    
    # Build content
    print("🎨 Building landing page content...")
    slug = kebab_case(args.video_name)
    title = model.titles[0] if model.titles else f"{model.video_name} | RobGrappler"
    cta_url = add_utm_params(args.watchfighters_url, slug)
    
    html_content = build_html_content(model, cta_url, branding)
    
    # Dry run
    if args.dry_run:
        print("\n" + "─"*70)
        print("DRY RUN - Preview Only")
        print("─"*70)
        print(f"\nTitle: {title}")
        print(f"Slug: {slug}")
        print(f"Status: {'publish' if args.publish else 'draft'}")
        print(f"CTA URL: {cta_url}")
        print(f"\nFirst 30 lines of HTML:\n")
        print('\n'.join(html_content.split('\n')[:30]))
        print("\n[... content truncated ...]")
        
        # Save preview
        preview_path = f"/tmp/{slug}_content.html"
        with open(preview_path, 'w') as f:
            f.write(html_content)
        print(f"\n✅ Full preview saved to: {preview_path}")
        return
    
    # Create/Update page
    print("🔗 Connecting to WordPress...")
    client = WordPressClient(wp_config['site_url'], wp_config['username'], wp_config['app_password'])
    
    success, result = client.test_auth()
    if not success:
        print(f"❌ WordPress authentication failed: {result}")
        print("   Run: python wordpress_setup.py")
        sys.exit(1)
    
    print(f"✅ Connected as: {result.get('name', 'Unknown')}")
    
    status = 'publish' if args.publish else config['page_settings']['default_status']
    template = config['page_settings'].get('page_template', '')
    
    if args.update:
        existing = client.get_page_by_slug(slug)
        if existing:
            print(f"📝 Updating existing page (ID: {existing['id']})...")
            page = client.update_page(existing['id'], content=html_content, title=title, status=status)
        else:
            print(f"⚠️  No existing page found with slug '{slug}', creating new...")
            page = client.create_page(title, slug, html_content, status, template=template)
    else:
        print(f"📝 Creating new landing page...")
        page = client.create_page(title, slug, html_content, status, template=template)
    
    # Success!
    print("\n" + "="*70)
    print("  ✅ Landing Page Created!")
    print("="*70 + "\n")
    
    print(f"Page ID: {page['id']}")
    print(f"Title: {page['title']['rendered']}")
    print(f"Slug: {page['slug']}")
    print(f"Status: {page['status']}")
    print(f"\n🔗 Edit URL: {wp_config['site_url']}/wp-admin/post.php?post={page['id']}&action=edit")
    
    if page.get('link'):
        print(f"🔗 View URL: {page['link']}")
    
    print(f"\n📊 Content Summary:")
    print(f"  • {len(model.techniques)} techniques featured")
    print(f"  • {len(model.highlight_moments)} key moments")
    print(f"  • {len(model.bullets)} selling points")
    print(f"  • {len(model.buyer_tags)} buyer tags")
    print(f"  • 3 CTA buttons included")
    
    print("\n🎉 Done! Review the draft in WordPress before publishing.\n")


if __name__ == "__main__":
    main()
