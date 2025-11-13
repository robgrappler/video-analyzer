#!/usr/bin/env python3
"""
WordPress Landing Page Generator - Theme-Independent Version
Creates self-contained landing pages that override theme styles completely.
"""

from wordpress_landing_page_generator import (
    VideoModel, format_timestamp, load_analyzer_data, 
    kebab_case, add_utm_params
)
from typing import Dict, List


def build_html_content(model: VideoModel, cta_url: str, branding: Dict, hero_image_url: str = None, gallery_images: list = None, video_url: str = None) -> str:
    """Build self-contained HTML with aggressive theme style overrides."""
    
    primary = branding.get('primary_color', '#E91E63')
    secondary = branding.get('secondary_color', '#000000')
    
    title = model.titles[0] if model.titles else f"{model.video_name} | RobGrappler"
    subtitle = model.descriptions[0] if model.descriptions else model.sales_report_snippet[:200]
    
    gallery_images = gallery_images or []
    
    html = f"""
<style>
/* Complete CSS Reset and Isolation */
#rg-lp, #rg-lp * {{
    all: unset;
    display: revert;
}}

#rg-lp {{
    display: block !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    background: #ffffff !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    line-height: 1.6 !important;
    color: #333333 !important;
    box-sizing: border-box !important;
}}

#rg-lp *, #rg-lp *::before, #rg-lp *::after {{
    box-sizing: border-box !important;
}}

/* Hero Section */
#rg-lp .rg-hero {{
    position: relative !important;
    background: linear-gradient(135deg, {primary}44 0%, {secondary} 100%) !important;
    color: white !important;
    padding: 80px 20px !important;
    text-align: center !important;
    overflow: hidden !important;
    width: 100% !important;
    display: block !important;
}}

#rg-lp .rg-hero-content {{
    position: relative !important;
    z-index: 2 !important;
    max-width: 1200px !important;
    margin: 0 auto !important;
    padding: 0 20px !important;
}}

#rg-lp .rg-hero h1 {{
    font-size: 3rem !important;
    font-weight: 800 !important;
    margin-bottom: 20px !important;
    line-height: 1.2 !important;
    color: white !important;
    text-shadow: 0 2px 20px rgba(0,0,0,0.5) !important;
}}

#rg-lp .rg-hero p {{
    font-size: 1.25rem !important;
    margin: 20px auto 30px !important;
    color: rgba(255,255,255,0.95) !important;
    max-width: 700px !important;
    line-height: 1.6 !important;
}}

/* Hero Image/Video */
#rg-lp .rg-hero-image {{
    max-width: 900px !important;
    width: 100% !important;
    height: auto !important;
    border-radius: 16px !important;
    margin: 30px auto !important;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5) !important;
    display: block !important;
}}

#rg-lp .rg-video-container {{
    position: relative !important;
    max-width: 900px !important;
    margin: 30px auto !important;
    border-radius: 16px !important;
    overflow: hidden !important;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5) !important;
}}

#rg-lp .rg-video-container video,
#rg-lp .rg-video-container iframe {{
    width: 100% !important;
    height: auto !important;
    min-height: 400px !important;
    display: block !important;
    border: none !important;
}}

/* Badges */
#rg-lp .rg-badges {{
    display: flex !important;
    justify-content: center !important;
    gap: 15px !important;
    flex-wrap: wrap !important;
    margin: 30px 0 !important;
}}

#rg-lp .rg-badge {{
    background: rgba(255,255,255,0.2) !important;
    backdrop-filter: blur(10px) !important;
    padding: 12px 24px !important;
    border-radius: 30px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
    color: white !important;
    display: inline-block !important;
}}

/* CTA Buttons */
#rg-lp .rg-cta {{
    display: inline-block !important;
    background: {primary} !important;
    color: white !important;
    padding: 18px 48px !important;
    text-decoration: none !important;
    border-radius: 50px !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    margin: 20px 10px !important;
    box-shadow: 0 8px 30px rgba(233, 30, 99, 0.4) !important;
    transition: all 0.3s ease !important;
    cursor: pointer !important;
}}

#rg-lp .rg-cta:hover {{
    transform: translateY(-3px) !important;
    box-shadow: 0 12px 40px rgba(233, 30, 99, 0.6) !important;
}}

/* Content Sections */
#rg-lp .rg-section {{
    max-width: 1200px !important;
    margin: 60px auto !important;
    padding: 0 20px !important;
}}

#rg-lp .rg-section h2 {{
    color: {primary} !important;
    font-size: 2.5rem !important;
    font-weight: 800 !important;
    margin-bottom: 30px !important;
    position: relative !important;
    padding-bottom: 15px !important;
}}

#rg-lp .rg-section h2::after {{
    content: '' !important;
    position: absolute !important;
    bottom: 0 !important;
    left: 0 !important;
    width: 60px !important;
    height: 4px !important;
    background: {primary} !important;
    border-radius: 2px !important;
}}

#rg-lp .rg-section h3 {{
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    margin: 30px 0 20px !important;
    color: #333 !important;
}}

/* Highlights Grid */
#rg-lp .rg-highlights {{
    display: grid !important;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)) !important;
    gap: 25px !important;
    margin-top: 30px !important;
}}

#rg-lp .rg-highlight {{
    background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%) !important;
    border-left: 5px solid {primary} !important;
    padding: 20px !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 15px rgba(0,0,0,0.1) !important;
    transition: all 0.3s ease !important;
}}

#rg-lp .rg-highlight:hover {{
    transform: translateX(5px) !important;
    box-shadow: 0 8px 25px rgba(0,0,0,0.15) !important;
}}

/* Details Cards */
#rg-lp .rg-details-grid {{
    display: grid !important;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)) !important;
    gap: 20px !important;
    margin: 30px 0 !important;
}}

#rg-lp .rg-detail-card {{
    background: white !important;
    padding: 25px !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 15px rgba(0,0,0,0.1) !important;
    border-top: 4px solid {primary} !important;
    transition: all 0.3s ease !important;
}}

#rg-lp .rg-detail-card:hover {{
    transform: translateY(-5px) !important;
    box-shadow: 0 8px 25px rgba(0,0,0,0.2) !important;
}}

#rg-lp .rg-detail-card strong {{
    color: {primary} !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    display: block !important;
    margin-bottom: 8px !important;
}}

/* Timeline */
#rg-lp .rg-timeline {{
    position: relative !important;
    padding-left: 30px !important;
    margin: 30px 0 !important;
}}

#rg-lp .rg-timeline::before {{
    content: '' !important;
    position: absolute !important;
    left: 0 !important;
    top: 0 !important;
    bottom: 0 !important;
    width: 3px !important;
    background: linear-gradient(to bottom, {primary}, {secondary}) !important;
    border-radius: 2px !important;
}}

#rg-lp .rg-timeline-item {{
    position: relative !important;
    padding: 20px !important;
    margin-bottom: 20px !important;
    background: white !important;
    border-radius: 8px !important;
    box-shadow: 0 3px 12px rgba(0,0,0,0.1) !important;
    transition: all 0.3s ease !important;
}}

#rg-lp .rg-timeline-item::before {{
    content: '' !important;
    position: absolute !important;
    left: -37px !important;
    top: 25px !important;
    width: 12px !important;
    height: 12px !important;
    border-radius: 50% !important;
    background: {primary} !important;
    border: 3px solid white !important;
    box-shadow: 0 0 0 2px {primary} !important;
}}

#rg-lp .rg-timeline-item:hover {{
    transform: translateX(5px) !important;
    box-shadow: 0 6px 20px rgba(0,0,0,0.15) !important;
}}

#rg-lp .rg-timestamp {{
    display: inline-block !important;
    background: {primary} !important;
    color: white !important;
    padding: 4px 12px !important;
    border-radius: 15px !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    margin-bottom: 8px !important;
}}

/* Gallery */
#rg-lp .rg-gallery {{
    display: grid !important;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)) !important;
    gap: 20px !important;
    margin: 30px 0 !important;
}}

#rg-lp .rg-gallery img {{
    width: 100% !important;
    height: 220px !important;
    object-fit: cover !important;
    border-radius: 12px !important;
    cursor: pointer !important;
    transition: all 0.4s ease !important;
    box-shadow: 0 4px 15px rgba(0,0,0,0.15) !important;
    display: block !important;
}}

#rg-lp .rg-gallery img:hover {{
    transform: scale(1.05) translateY(-5px) !important;
    box-shadow: 0 12px 30px rgba(0,0,0,0.25) !important;
}}

/* Tags */
#rg-lp .rg-tags {{
    display: flex !important;
    gap: 12px !important;
    flex-wrap: wrap !important;
}}

#rg-lp .rg-tag {{
    background: linear-gradient(135deg, {primary} 0%, {secondary} 100%) !important;
    color: white !important;
    padding: 8px 20px !important;
    border-radius: 25px !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    box-shadow: 0 3px 10px rgba(0,0,0,0.2) !important;
    transition: all 0.3s ease !important;
    display: inline-block !important;
}}

#rg-lp .rg-tag:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 15px rgba(0,0,0,0.25) !important;
}}

/* Responsive */
@media (max-width: 768px) {{
    #rg-lp .rg-hero {{
        padding: 60px 20px !important;
    }}
    
    #rg-lp .rg-hero h1 {{
        font-size: 2rem !important;
    }}
    
    #rg-lp .rg-hero p {{
        font-size: 1rem !important;
    }}
    
    #rg-lp .rg-cta {{
        padding: 15px 35px !important;
        font-size: 1rem !important;
    }}
    
    #rg-lp .rg-section h2 {{
        font-size: 1.8rem !important;
    }}
}}
</style>

<div id="rg-lp">
<!-- Hero Section -->
<div class="rg-hero">
    <div class="rg-hero-content">
        <h1>{title}</h1>
        <p>{subtitle}</p>
        """
    
    # Add video or image
    if video_url:
        if 'youtube.com' in video_url or 'vimeo.com' in video_url or 'watchfighters.com' in video_url:
            html += f"""<div class="rg-video-container">
            <iframe src="{video_url}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
        </div>"""
        else:
            html += f"""<div class="rg-video-container">
            <video controls preload="metadata" poster="{hero_image_url if hero_image_url else ''}">
                <source src="{video_url}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>"""
    elif hero_image_url:
        html += f'<img src="{hero_image_url}" alt="{title}" class="rg-hero-image">'
    
    html += f"""
        
        <div class="rg-badges">
            <div class="rg-badge">🔥 Heat: {model.heat_factor_5}/5</div>
            <div class="rg-badge">⚔️ Intensity: {model.intensity_10}/10</div>
            <div class="rg-badge">🧠 Technical: {model.technical_rating_10}/10</div>
        </div>
        <a href="{cta_url}" class="rg-cta" target="_blank" rel="noopener">▶ Watch Full Match Now</a>
    </div>
</div>

<!-- Sales Highlights -->
<div class="rg-section">
    <h2>What You'll Experience</h2>
    <div class="rg-highlights">
"""
    
    for bullet in model.bullets[:6]:
        html += f'        <div class="rg-highlight">⭐ {bullet}</div>\n'
    
    html += """    </div>
</div>

<!-- Match Details -->
<div class="rg-section">
    <h2>Match Details</h2>
    <div class="rg-details-grid">
"""
    
    html += f"""        <div class="rg-detail-card">
            <strong>Style</strong>
            {model.style.title()}
        </div>
        <div class="rg-detail-card">
            <strong>Competitiveness</strong>
            {model.competitiveness_10}/10
        </div>
        <div class="rg-detail-card">
            <strong>Momentum Shifts</strong>
            {len(model.momentum_shifts)} major turns
        </div>
        <div class="rg-detail-card">
            <strong>Rewatch Value</strong>
            {model.rewatch_value_10}/10
        </div>
    </div>
"""
    
    # Techniques
    if model.techniques:
        html += """    <h3>Featured Techniques</h3>
    <div class="rg-highlights">
"""
        for tech in model.techniques[:8]:
            html += f"""        <div class="rg-highlight">
            <strong>{tech.get('name', 'Unknown')}</strong><br>
            {tech.get('type', 'technique')} • Difficulty: {tech.get('difficulty_5', 3)}/5
        </div>
"""
        html += "    </div>\n"
    
    html += "</div>\n\n"
    
    # Timeline
    if model.highlight_moments:
        html += """<div class="rg-section">
    <h2>Key Moments Timeline</h2>
    <div class="rg-timeline">
"""
        for moment in model.highlight_moments[:10]:
            timestamp = format_timestamp(moment.get('time_s', 0))
            moment_type = moment.get('type', 'moment').replace('_', ' ').title()
            description = moment.get('why_it_hooks', 'Intense action')
            html += f"""        <div class="rg-timeline-item">
            <span class="rg-timestamp">{timestamp}</span>
            <div><strong>{moment_type}</strong></div>
            <div>{description}</div>
        </div>
"""
        html += """    </div>
"""
        html += f'    <a href="{cta_url}" class="rg-cta" target="_blank" rel="noopener">🎬 Watch Full Match</a>\n'
        html += """</div>

"""
    
    # Gallery
    if gallery_images:
        html += """<div class="rg-section">
    <h2>Action Highlights</h2>
    <div class="rg-gallery">
"""
        for img in gallery_images[:9]:
            html += f"""        <img src="{img['url']}" alt="{img.get('caption', 'Match highlight')}" loading="lazy">
"""
        html += """    </div>
</div>

"""
    
    # Entertainment Value
    html += f"""<div class="rg-section">
    <h2>Entertainment Metrics</h2>
    <div class="rg-details-grid">
        <div class="rg-detail-card">
            <strong>Rewatch Value</strong>
            {model.rewatch_value_10}/10
        </div>
        <div class="rg-detail-card">
            <strong>Production Quality</strong>
            {model.capture_rating_10}/10
        </div>
"""
    
    if model.pacing_curve:
        html += f"""        <div class="rg-detail-card">
            <strong>Early Pacing</strong>
            {model.pacing_curve.get('early_10', 7)}/10
        </div>
        <div class="rg-detail-card">
            <strong>Mid Pacing</strong>
            {model.pacing_curve.get('mid_10', 7)}/10
        </div>
        <div class="rg-detail-card">
            <strong>Late Pacing</strong>
            {model.pacing_curve.get('late_10', 8)}/10
        </div>
"""
    
    html += """    </div>
</div>

"""
    
    # Tags
    if model.buyer_tags:
        html += """<div class="rg-section">
    <h2>Perfect For Fans Of</h2>
    <div class="rg-tags">
"""
        for tag in model.buyer_tags:
            html += f'        <span class="rg-tag">{tag}</span>\n'
        html += """    </div>
</div>

"""
    
    # Final CTA
    html += f"""<div class="rg-hero">
    <div class="rg-hero-content">
        <h2>Ready to Watch This Epic Match?</h2>
        <p>Get instant access on WatchFighters and experience every moment</p>
        <a href="{cta_url}" class="rg-cta" target="_blank" rel="noopener">🔥 Watch Now on WatchFighters</a>
    </div>
</div>
</div>
"""
    
    return html
