#!/usr/bin/env python3
"""
WordPress Landing Page Generator (SSH/WP-CLI Version)
Creates landing pages using SSH and WP-CLI (more reliable than REST API)
"""

import os
import sys
import json
import yaml
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

# Import the data model and utilities from the REST version
from wordpress_landing_page_generator import (
    VideoModel, load_analyzer_data, kebab_case, 
    format_timestamp, add_utm_params, build_html_content
)


def load_ssh_config() -> Dict[str, Any]:
    """Load SSH configuration."""
    config_path = Path("wordpress_ssh_config.yaml")
    
    if not config_path.exists():
        print("❌ SSH configuration not found!")
        print("   Run: python wordpress_ssh_setup.py")
        sys.exit(1)
    
    with open(config_path) as f:
        return yaml.safe_load(f)


class WordPressSSHClient:
    """WordPress client using SSH and WP-CLI."""
    
    def __init__(self, ssh_host: str, ssh_port: int, ssh_user: str, wp_path: str):
        self.ssh_host = ssh_host
        self.ssh_port = ssh_port
        self.ssh_user = ssh_user
        self.wp_path = wp_path
        self.ssh_base = f"ssh -p {ssh_port} {ssh_user}@{ssh_host}"
    
    def _run_wp_cli(self, command: str) -> tuple:
        """Run a WP-CLI command via SSH."""
        full_cmd = f"{self.ssh_base} 'cd {self.wp_path} && wp {command}'"
        
        try:
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def test_connection(self) -> tuple:
        """Test SSH and WP-CLI availability."""
        # Test SSH connection (run without capture for interactive password)
        test_cmd = f"{self.ssh_base} 'echo SSH_CONNECTION_OK'"
        result = subprocess.run(test_cmd, shell=True, timeout=30)
        
        if result.returncode != 0:
            return False, "SSH connection failed"
        
        # Test WP-CLI (also without capture)
        wp_cmd = f"{self.ssh_base} 'cd {self.wp_path} && wp --version'"
        result = subprocess.run(wp_cmd, shell=True, timeout=30)
        
        if result.returncode != 0:
            return False, "WP-CLI not found or not working"
        
        return True, "Connected. SSH and WP-CLI verified"
    
    def get_page_by_slug(self, slug: str) -> Optional[int]:
        """Get page ID by slug."""
        success, stdout, _ = self._run_wp_cli(f"post list --post_type=page --name={slug} --format=ids")
        if success and stdout.strip():
            return int(stdout.strip().split()[0])
        return None
    
    def create_page(self, title: str, slug: str, content: str, status: str = 'draft') -> tuple:
        """Create a new page using WP-CLI."""
        
        # Write content to a temporary local file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(content)
            temp_file = f.name
        
        # Transfer via SSH redirect instead of SCP (works better with password auth)
        remote_temp = f"/tmp/wp_page_{slug}.html"
        transfer_cmd = f"cat {temp_file} | {self.ssh_base} 'cat > {remote_temp}'"
        
        result = subprocess.run(transfer_cmd, shell=True, timeout=60)
        os.unlink(temp_file)
        
        if result.returncode != 0:
            return False, None, f"Failed to transfer content (exit code: {result.returncode})"
        
        # Create page with WP-CLI (use double quotes and escape them)
        escaped_title = title.replace('"', '\\"')
        wp_cmd = f'post create {remote_temp} --post_type=page --post_title="{escaped_title}" --post_name={slug} --post_status={status} --porcelain'
        success, stdout, stderr = self._run_wp_cli(wp_cmd)
        
        # Cleanup remote temp file
        self._run_wp_cli(f"! rm {remote_temp}")
        
        if success and stdout.strip():
            page_id = int(stdout.strip())
            # Set page template to Elementor Canvas
            self._run_wp_cli(f'post meta update {page_id} _wp_page_template elementor_canvas')
            # Enable Elementor edit mode
            self._run_wp_cli(f'post meta update {page_id} _elementor_edit_mode builder')
            return True, page_id, "Page created successfully with Elementor Canvas"
        else:
            return False, None, f"Failed to create page: {stderr}"
    def update_page(self, page_id: int, content: str, title: str = None, status: str = None) -> tuple:
        """Update an existing page."""
        
        # Write content to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(content)
            temp_file = f.name
        
        # Transfer via SSH redirect
        remote_temp = f"/tmp/wp_page_update_{page_id}.html"
        transfer_cmd = f"cat {temp_file} | {self.ssh_base} 'cat > {remote_temp}'"
        
        result = subprocess.run(transfer_cmd, shell=True, timeout=60)
        os.unlink(temp_file)
        
        if result.returncode != 0:
            return False, f"Failed to transfer content (exit code: {result.returncode})"
        
        # Build update command
        wp_cmd = f"post update {page_id} {remote_temp}"
        if title:
            escaped_title = title.replace('"', '\\"')
            wp_cmd += f' --post_title="{escaped_title}"'
        if status:
            wp_cmd += f" --post_status={status}"
        
        success, stdout, stderr = self._run_wp_cli(wp_cmd)
        
        # Cleanup
        self._run_wp_cli(f"! rm {remote_temp}")
        
        if success:
            return True, "Page updated successfully"
        else:
            return False, f"Failed to update page: {stderr}"
    
    def get_page_url(self, page_id: int) -> Optional[str]:
        """Get page URL."""
        success, stdout, _ = self._run_wp_cli(f"post url {page_id}")
        if success:
            return stdout.strip()
        return None
    
    def upload_media(self, local_file: Path, title: str = "", post_id: int = None) -> Optional[int]:
        """Upload media file to WordPress."""
        if not local_file.exists():
            print(f"    ⚠️  File not found: {local_file}")
            return None
        
        # Transfer file to server via SSH
        remote_temp = f"/tmp/wp_upload_{local_file.name}"
        transfer_cmd = f"cat {local_file} | {self.ssh_base} 'cat > {remote_temp}'"
        
        result = subprocess.run(transfer_cmd, shell=True, timeout=120)
        if result.returncode != 0:
            print(f"    ⚠️  Transfer failed for {local_file.name}")
            return None
        
        # Import to WordPress media library (use direct command for better output)
        wp_import_cmd = f"cd {self.wp_path} && wp media import {remote_temp} --porcelain"
        if title:
            escaped_title = title.replace('"', '\\"').replace("'", "'\\''")
            wp_import_cmd = f'cd {self.wp_path} && wp media import {remote_temp} --title="{escaped_title}" --porcelain'
        if post_id:
            wp_import_cmd += f" --post_id={post_id}"
        
        wp_cmd = f"{self.ssh_base} '{wp_import_cmd}'"
        
        try:
            result = subprocess.run(wp_cmd, shell=True, capture_output=True, text=True, timeout=60)
            
            # Cleanup remote file
            subprocess.run(f"{self.ssh_base} 'rm {remote_temp}'", shell=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                media_id = int(result.stdout.strip())
                return media_id
            else:
                print(f"    ⚠️  Import failed: {result.stderr[:100] if result.stderr else 'Unknown error'}")
                return None
        except Exception as e:
            print(f"    ⚠️  Upload error: {str(e)[:100]}")
            return None


def main():
    parser = argparse.ArgumentParser(
        description="Generate WordPress landing pages via SSH/WP-CLI (more reliable than REST API)"
    )
    parser.add_argument('--video-name', required=True, help='Video name (e.g., Match3Nocturmex25K)')
    parser.add_argument('--watchfighters-url', required=True, help='WatchFighters video URL')
    parser.add_argument('--video-snippet-url', help='Optional: URL to video snippet for hero section (mp4, YouTube, Vimeo embed)')
    parser.add_argument('--path', help='Explicit path to analyzer folder')
    parser.add_argument('--publish', action='store_true', help='Publish immediately (default: draft)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without creating')
    parser.add_argument('--update', action='store_true', help='Update existing page')
    parser.add_argument('--verbose', action='store_true', help='Extra logging')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("  WordPress Landing Page Generator (SSH/WP-CLI)")
    print("="*70 + "\n")
    
    # Load SSH configuration
    print("📋 Loading SSH configuration...")
    config = load_ssh_config()
    ssh_config = config['ssh']
    branding = config.get('branding', {
        'primary_color': '#E91E63',
        'secondary_color': '#000000'
    })
    
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
    
    # Check for thumbnails - prefer optimized versions
    thumbnails_dir = analysis_path / "../thumbnails" if analysis_path else Path(f"{args.video_name}/thumbnails")
    thumbnail_files = []
    
    if thumbnails_dir.exists():
        # Check for optimized folder first
        optimized_dir = thumbnails_dir / "optimized"
        if optimized_dir.exists():
            thumbnail_files = sorted(optimized_dir.glob("thumb_*.jpg"))[:10]
            if thumbnail_files:
                print(f"🖼️ Found {len(thumbnail_files)} optimized thumbnail images")
        
        # Fallback to original thumbnails
        if not thumbnail_files:
            thumbnail_files = sorted(thumbnails_dir.glob("thumb_*.jpg"))[:10]
            if thumbnail_files:
                print(f"🖼️ Found {len(thumbnail_files)} thumbnail images")
    
    # Build HTML without images first (for dry-run)
    html_content = build_html_content(model, cta_url, branding, video_url=args.video_snippet_url)
    
    # Dry run
    if args.dry_run:
        print("\n" + "─"*70)
        print("DRY RUN - Preview Only")
        print("─"*70)
        print(f"\nTitle: {title}")
        print(f"Slug: {slug}")
        print(f"Status: {'publish' if args.publish else 'draft'}")
        print(f"CTA URL: {cta_url}")
        print(f"\nSSH Connection: {ssh_config['user']}@{ssh_config['host']}:{ssh_config['port']}")
        print(f"WordPress Path: {ssh_config['wp_path']}")
        print(f"\nFirst 30 lines of HTML:\n")
        print('\n'.join(html_content.split('\n')[:30]))
        print("\n[... content truncated ...]")
        
        # Save preview
        preview_path = f"/tmp/{slug}_content.html"
        with open(preview_path, 'w') as f:
            f.write(html_content)
        print(f"\n✅ Full preview saved to: {preview_path}")
        return
    
    # Create client
    print("🔗 Preparing to connect via SSH...")
    print(f"   Host: {ssh_config['host']}:{ssh_config['port']}")
    print(f"   User: {ssh_config['user']}")
    print(f"   WordPress: {ssh_config['wp_path']}")
    print(f"\n💡 Note: You'll be prompted for your SSH password multiple times during page creation.\n")
    
    client = WordPressSSHClient(
        ssh_config['host'],
        ssh_config['port'],
        ssh_config['user'],
        ssh_config['wp_path']
    )
    
    status = 'publish' if args.publish else config['page_settings'].get('default_status', 'draft')
    
    # Create or update page
    if args.update:
        existing_id = client.get_page_by_slug(slug)
        if existing_id:
            print(f"📝 Updating existing page (ID: {existing_id})...")
            success, result = client.update_page(existing_id, html_content, title, status)
            if success:
                page_id = existing_id
                print(f"✅ {result}")
            else:
                print(f"❌ {result}")
                sys.exit(1)
        else:
            print(f"⚠️  No existing page found with slug '{slug}', creating new...")
            success, page_id, result = client.create_page(title, slug, html_content, status)
            if not success:
                print(f"❌ {result}")
                sys.exit(1)
    else:
        print(f"📝 Creating new landing page...")
        success, page_id, result = client.create_page(title, slug, html_content, status)
        if not success:
            print(f"❌ {result}")
            sys.exit(1)
        print(f"✅ {result}")
    
    # Upload media if thumbnails exist
    hero_image_url = None
    gallery_images = []
    
    if thumbnail_files and page_id:
        print(f"\n💾 Uploading {len(thumbnail_files)} images...")
        uploaded_count = 0
        
        for i, thumb_file in enumerate(thumbnail_files):
            img_title = f"{title} - Moment {i+1}"
            media_id = client.upload_media(thumb_file, title=img_title, post_id=page_id)
            
            if media_id:
                uploaded_count += 1
                # Get image URL
                success, img_url, _ = client._run_wp_cli(f"post get {media_id} --field=guid")
                
                if success and img_url.strip():
                    img_data = {'url': img_url.strip(), 'caption': img_title}
                    
                    # First image becomes hero
                    if i == 0:
                        hero_image_url = img_url.strip()
                    else:
                        gallery_images.append(img_data)
                        
                print(f"  ✅ Uploaded image {uploaded_count}/{len(thumbnail_files)}")
        
        print(f"✅ Uploaded {uploaded_count} images successfully")
        
        # Rebuild HTML with images and update page
        if hero_image_url or gallery_images:
            print("\n🔄 Updating page with images...")
            html_content_with_images = build_html_content(
                model, cta_url, branding, 
                hero_image_url=hero_image_url, 
                gallery_images=gallery_images,
                video_url=args.video_snippet_url
            )
            
            success, update_result = client.update_page(page_id, html_content_with_images)
            if success:
                print("✅ Page updated with images")
            else:
                print(f"⚠️ Warning: Could not update page with images: {update_result}")
    
    # Get page URL
    page_url = client.get_page_url(page_id)
    
    # Success!
    print("\n" + "="*70)
    print("  ✅ Landing Page Created!")
    print("="*70 + "\n")
    
    print(f"Page ID: {page_id}")
    print(f"Title: {title}")
    print(f"Slug: {slug}")
    print(f"Status: {status}")
    
    site_url = config.get('wordpress', {}).get('site_url', 'https://robgrappler.io')
    print(f"\n🔗 Edit URL: {site_url}/wp-admin/post.php?post={page_id}&action=edit")
    
    if page_url:
        print(f"🔗 View URL: {page_url}")
    
    print(f"\n📊 Content Summary:")
    print(f"  • {len(model.techniques)} techniques featured")
    print(f"  • {len(model.highlight_moments)} key moments")
    print(f"  • {len(model.bullets)} selling points")
    print(f"  • {len(model.buyer_tags)} buyer tags")
    print(f"  • 3 CTA buttons included")
    
    print("\n🎉 Done! Review the draft in WordPress before publishing.\n")


if __name__ == "__main__":
    main()
