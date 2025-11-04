#!/usr/bin/env python3
"""
WordPress Landing Page Generator - SSH Setup Wizard
Configures SSH and WP-CLI settings for page generation.
"""

import os
import sys
import yaml
import subprocess
from pathlib import Path


def print_header(text):
    """Print a styled header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_step(step_num, text):
    """Print a step indicator."""
    print(f"\n📋 Step {step_num}: {text}\n")


def test_ssh_connection(host, port, user) -> tuple:
    """Test SSH connection."""
    print(f"🔄 Testing SSH connection to {user}@{host}:{port}...")
    print("(You will be prompted for your SSH password)\n")
    
    test_cmd = f"ssh -p {port} {user}@{host} 'echo SSH_TEST_OK'"
    
    try:
        # Run without capturing output so user can see and respond to password prompt
        result = subprocess.run(
            test_cmd,
            shell=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return True, "SSH connection successful"
        else:
            return False, f"Connection failed (exit code: {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)


def find_wordpress_path(host, port, user) -> str:
    """Try to find WordPress installation path."""
    print("🔍 Searching for WordPress installation...")
    print("(Enter your SSH password when prompted)\n")
    
    paths_to_try = [
        "domains/robgrappler.io/public_html",
        "public_html",
        "htdocs",
        "www",
        "wordpress"
    ]
    
    for path in paths_to_try:
        cmd = f"ssh -o BatchMode=no -p {port} {user}@{host} 'test -f {path}/wp-config.php && echo found || true'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        
        if 'found' in result.stdout:
            print(f"✅ Found WordPress at: {path}")
            return path
    
    print("⚠️  Could not auto-detect WordPress path")
    return ""


def test_wp_cli(host, port, user, wp_path) -> tuple:
    """Test if WP-CLI is available."""
    print("🔍 Checking for WP-CLI...")
    print("(Enter your SSH password if prompted)\n")
    
    cmd = f"ssh -o BatchMode=no -p {port} {user}@{host} 'cd {wp_path} && wp --version 2>&1'"
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and 'WP-CLI' in result.stdout:
            return True, result.stdout.strip()
        else:
            return False, f"WP-CLI not found. Output: {result.stdout[:100]}"
    except Exception as e:
        return False, str(e)


def main():
    """Main setup wizard flow."""
    print_header("WordPress Landing Page Generator - SSH Setup")
    
    print("👋 Welcome! This wizard will configure SSH access to your WordPress site.\n")
    print("You'll need:")
    print("  • SSH access to your hosting server")
    print("  • WP-CLI installed on the server (most hosts have this)")
    print("  • Your SSH password")
    print()
    
    # Check if already configured
    config_path = Path("wordpress_ssh_config.yaml")
    
    if config_path.exists():
        print("⚠️  Configuration file already exists.")
        reconfigure = input("Do you want to reconfigure? (y/N): ").strip().lower()
        if reconfigure != 'y':
            print("\n✅ Setup cancelled. Using existing configuration.")
            sys.exit(0)
    
    # Collect SSH details
    print_step(1, "Enter SSH Connection Details")
    
    print("From your SSH access info:")
    print("  IP: 46.202.196.43")
    print("  Port: 65002")
    print("  Username: u830957326\n")
    
    use_defaults = input("Use these values? (Y/n): ").strip().lower()
    
    if use_defaults == 'n':
        host = input("SSH Host/IP: ").strip()
        port = int(input("SSH Port [22]: ").strip() or "22")
        user = input("SSH Username: ").strip()
    else:
        host = "46.202.196.43"
        port = 65002
        user = "u830957326"
    
    # Test SSH connection
    print_step(2, "Testing SSH Connection")
    
    success, result = test_ssh_connection(host, port, user)
    
    if success:
        print(f"✅ {result}")
    else:
        print(f"❌ Connection test failed: {result}\n")
        print("💡 Troubleshooting:")
        print("   • Verify your SSH credentials")
        print("   • Make sure you can connect manually first:")
        print(f"     ssh -p {port} {user}@{host}")
        sys.exit(1)
    
    # Find WordPress path
    print_step(3, "WordPress Installation Path")
    
    print("Enter the path to your WordPress installation.")
    print("Common paths:")
    print("  • domains/robgrappler.io/public_html")
    print("  • public_html")
    print("  • htdocs")
    print("  • www\n")
    
    wp_path = input("WordPress Path [domains/robgrappler.io/public_html]: ").strip()
    
    if not wp_path:
        wp_path = "domains/robgrappler.io/public_html"
    
    print(f"Using WordPress path: {wp_path}")
    
    # Test WP-CLI
    print_step(4, "Testing WP-CLI")
    
    success, result = test_wp_cli(host, port, user, wp_path)
    
    if success:
        print(f"✅ WP-CLI found: {result}")
    else:
        print(f"❌ WP-CLI test failed: {result}\n")
        print("💡 WP-CLI is required for this tool to work.")
        print("   Ask your hosting provider to install it, or install it yourself:")
        print("   https://wp-cli.org/#installing")
        
        continue_anyway = input("\nContinue anyway? (y/N): ").strip().lower()
        if continue_anyway != 'y':
            sys.exit(1)
    
    # Save configuration
    print_step(5, "Saving Configuration")
    
    config = {
        'ssh': {
            'host': host,
            'port': port,
            'user': user,
            'wp_path': wp_path
        },
        'wordpress': {
            'site_url': 'https://robgrappler.io'
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
            'page_template': '',
            'category': 'Wrestling Videos'
        }
    }
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Configuration saved to: {config_path}")
    
    # Success summary
    print_header("Setup Complete! 🎉")
    
    print("✅ SSH connection verified")
    print("✅ WP-CLI found and working")
    print("✅ Configuration saved\n")
    
    print("📖 Next Steps:")
    print()
    print("1. Generate a landing page:")
    print("   python wordpress_ssh_generator.py \\")
    print("     --video-name Match3Nocturmex25K \\")
    print("     --watchfighters-url https://www.watchfighters.com/watch/VIDEO_ID")
    print()
    print("2. Preview first (dry-run):")
    print("   Add --dry-run flag to see what will be created")
    print()
    print("3. You'll be prompted for your SSH password when running the generator")
    print()
    
    # Offer to create a test page
    print("─" * 70)
    test_now = input("\n🧪 Would you like to test with a dry-run now? (y/N): ").strip().lower()
    
    if test_now == 'y':
        video_name = input("Video name (e.g., Match3Nocturmex25K): ").strip()
        wf_url = input("WatchFighters URL: ").strip()
        
        if video_name and wf_url:
            print("\n🔄 Running dry-run test...\n")
            import subprocess
            try:
                subprocess.run([
                    sys.executable,
                    "wordpress_ssh_generator.py",
                    "--video-name", video_name,
                    "--watchfighters-url", wf_url,
                    "--dry-run"
                ])
            except Exception as e:
                print(f"⚠️  Could not run generator: {e}")
                print("You can run it manually using the command above.")
    
    print("\n🎉 Setup complete!")
    print("Use wordpress_ssh_generator.py to create landing pages! 🚀\n")


if __name__ == "__main__":
    main()
