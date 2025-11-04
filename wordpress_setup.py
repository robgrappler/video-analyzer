#!/usr/bin/env python3
"""
WordPress Landing Page Generator - Interactive Setup Wizard
Guides user through WordPress authentication and configuration.
"""

import os
import sys
import yaml
import requests
from pathlib import Path
from base64 import b64encode


def print_header(text):
    """Print a styled header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_step(step_num, text):
    """Print a step indicator."""
    print(f"\n📋 Step {step_num}: {text}\n")


def test_wordpress_auth(site_url, username, app_password):
    """Test WordPress REST API authentication."""
    try:
        # Clean up site URL
        site_url = site_url.rstrip('/')
        
        # Create basic auth header
        auth_string = f"{username}:{app_password}"
        encoded_auth = b64encode(auth_string.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/json'
        }
        
        # Test with /users/me endpoint
        response = requests.get(
            f"{site_url}/wp-json/wp/v2/users/me",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            user_data = response.json()
            return True, user_data
        elif response.status_code == 401:
            return False, "Authentication failed. Please check your username and Application Password."
        elif response.status_code == 403:
            return False, "Access forbidden. Your user account may not have sufficient permissions."
        elif response.status_code == 404:
            return False, "WordPress REST API not found. Check your site URL and permalink settings."
        else:
            return False, f"Unexpected response: {response.status_code} - {response.text[:200]}"
            
    except requests.exceptions.Timeout:
        return False, "Connection timeout. Check your site URL and internet connection."
    except requests.exceptions.ConnectionError:
        return False, "Connection error. Is your WordPress site accessible?"
    except Exception as e:
        return False, f"Error: {str(e)}"


def guide_application_password():
    """Guide user through creating an Application Password."""
    print_step(1, "Create WordPress Application Password")
    
    print("📝 Follow these steps to create an Application Password:\n")
    print("1. Log in to your WordPress admin dashboard")
    print("   URL: https://robgrappler.io/wp-admin")
    print()
    print("2. Navigate to: Users → Profile (or Users → Your Profile)")
    print()
    print("3. Scroll down to the \"Application Passwords\" section")
    print("   (If you don't see this, permalinks must be set to 'Post name')")
    print()
    print("4. Enter a name: \"Landing Page Generator\"")
    print()
    print("5. Click \"Add New Application Password\"")
    print()
    print("6. COPY the generated password immediately")
    print("   ⚠️  It looks like: xxxx xxxx xxxx xxxx xxxx xxxx")
    print("   ⚠️  You'll only see it once!")
    print()
    
    input("Press ENTER when you're ready to continue...")


def main():
    """Main setup wizard flow."""
    print_header("WordPress Landing Page Generator - Setup Wizard")
    
    print("👋 Welcome! This wizard will help you set up WordPress integration.\n")
    print("You'll need:")
    print("  • WordPress admin access to robgrappler.io")
    print("  • Ability to create Application Passwords")
    print()
    
    # Check if already configured
    config_path = Path("wordpress_config.yaml")
    env_path = Path(".env")
    
    if config_path.exists() and env_path.exists():
        print("⚠️  Configuration files already exist.")
        reconfigure = input("Do you want to reconfigure? (y/N): ").strip().lower()
        if reconfigure != 'y':
            print("\n✅ Setup cancelled. Using existing configuration.")
            sys.exit(0)
    
    # Guide through Application Password creation
    guide_application_password()
    
    # Collect configuration
    print_step(2, "Enter WordPress Details")
    
    site_url = input("WordPress Site URL [https://robgrappler.io]: ").strip()
    if not site_url:
        site_url = "https://robgrappler.io"
    
    site_url = site_url.rstrip('/')
    
    username = input("WordPress Username: ").strip()
    if not username:
        print("❌ Username is required!")
        sys.exit(1)
    
    print("\n📋 Paste your Application Password:")
    print("   (Spaces are OK - they'll be removed automatically)")
    app_password = input("Application Password: ").strip()
    
    if not app_password:
        print("❌ Application Password is required!")
        sys.exit(1)
    
    # Remove spaces from password
    app_password = app_password.replace(' ', '')
    
    # Test authentication
    print_step(3, "Testing WordPress Connection")
    print("🔄 Connecting to WordPress...")
    
    success, result = test_wordpress_auth(site_url, username, app_password)
    
    if success:
        print(f"✅ Authentication successful!")
        print(f"   Connected as: {result.get('name', 'Unknown')}")
        print(f"   User ID: {result.get('id', 'Unknown')}")
        print(f"   Email: {result.get('email', 'Not provided')}")
    else:
        print(f"❌ Authentication failed!")
        print(f"   Error: {result}\n")
        print("💡 Troubleshooting tips:")
        print("   • Verify your username and Application Password")
        print("   • Check WordPress → Settings → Permalinks (should be 'Post name')")
        print("   • Ensure no security plugins are blocking REST API")
        print("   • Try accessing: {}/wp-json/wp/v2/users/me in your browser".format(site_url))
        sys.exit(1)
    
    # Create configuration
    print_step(4, "Saving Configuration")
    
    config = {
        'wordpress': {
            'site_url': site_url,
            'username': username,
            'app_password': ''  # Stored in .env
        },
        'branding': {
            'primary_color': '#E91E63',
            'secondary_color': '#000000',
            'font_family': 'Arial, Helvetica, sans-serif'
        },
        'watchfighters': {
            'profile_url': 'https://www.watchfighters.com/channels/Robgrappler',
            'video_url_template': 'https://www.watchfighters.com/watch/{video_id}'
        },
        'page_settings': {
            'default_status': 'draft',
            'page_template': 'elementor_header_footer',
            'category': 'Wrestling Videos',
            'use_categories_for_pages': False
        },
        'templates': {
            'default': 'default_conversion',
            'custom_path': 'templates/elementor/'
        }
    }
    
    # Write config.yaml
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Config saved to: {config_path}")
    
    # Write .env
    env_content = f"""# WordPress Landing Page Generator - Environment Variables
# DO NOT COMMIT THIS FILE TO GIT!

WP_APP_PASSWORD={app_password}
"""
    
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    # Set secure permissions
    os.chmod(env_path, 0o600)
    
    print(f"✅ Secrets saved to: {env_path} (permissions: 600)")
    
    # Success summary
    print_header("Setup Complete! 🎉")
    
    print("✅ WordPress connection verified")
    print("✅ Configuration files created")
    print("✅ Ready to generate landing pages\n")
    
    print("📖 Next Steps:")
    print()
    print("1. Generate a landing page:")
    print("   python wordpress_landing_page_generator.py \\")
    print("     --video-name Match3Nocturmex25K \\")
    print("     --watchfighters-url https://www.watchfighters.com/watch/VIDEO_ID")
    print()
    print("2. Preview first (dry-run):")
    print("   Add --dry-run flag to see what will be created")
    print()
    print("3. Check the documentation:")
    print("   cat README_WORDPRESS.md")
    print()
    
    # Offer to create a test page
    print("─" * 70)
    test_now = input("\n🧪 Would you like to create a test landing page now? (y/N): ").strip().lower()
    
    if test_now == 'y':
        print("\n📋 To create a test page, you'll need:")
        video_name = input("Video name (e.g., Match3Nocturmex25K): ").strip()
        wf_url = input("WatchFighters URL: ").strip()
        
        if video_name and wf_url:
            print("\n🔄 Creating test page in dry-run mode...")
            print(f"\nRun this command to preview:\n")
            print(f"  python wordpress_landing_page_generator.py \\")
            print(f"    --video-name \"{video_name}\" \\")
            print(f"    --watchfighters-url \"{wf_url}\" \\")
            print(f"    --dry-run")
            print()
            
            proceed = input("Run this now? (y/N): ").strip().lower()
            if proceed == 'y':
                import subprocess
                try:
                    subprocess.run([
                        sys.executable,
                        "wordpress_landing_page_generator.py",
                        "--video-name", video_name,
                        "--watchfighters-url", wf_url,
                        "--dry-run"
                    ])
                except Exception as e:
                    print(f"⚠️  Could not run generator: {e}")
                    print("You can run it manually using the command above.")
    
    print("\n🎉 Setup wizard complete!")
    print("Happy landing page generating! 🚀\n")


if __name__ == "__main__":
    main()
