#!/usr/bin/env python3
"""
Notification system for contractor environment management.
Uses Slack webhooks (no expiration, no tokens needed).
"""

import json
import logging
import requests
import yaml
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class NotificationManager:
    """Manages notifications for contractor environment events"""
    
    def __init__(self, config_path: str = "config/master_config.yaml"):
        """Initialize notification manager with configuration"""
        self.config = self._load_config(config_path)
        self.notifications_config = self.config.get('notifications', {})
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return {}
    
    def send_environment_created_notification(self, 
                                            contractor_name: str,
                                            project_id: str,
                                            github_repo_url: str,
                                            service_account_email: str,
                                            tables_copied: list) -> bool:
        """Send notification when a new contractor environment is created"""
        
        if not self._should_send_slack():
            logger.info("Slack notifications not configured, skipping")
            return True
        
        message = self._format_environment_created_message(
            contractor_name, project_id, github_repo_url, 
            service_account_email, tables_copied
        )
        
        return self._send_slack_notification(message)
    
    def send_environment_cleanup_notification(self,
                                            contractor_name: str,
                                            project_id: str,
                                            cleanup_results: Dict[str, Any]) -> bool:
        """Send notification when a contractor environment is cleaned up"""
        
        if not self._should_send_slack():
            logger.info("Slack notifications not configured, skipping")
            return True
        
        message = self._format_cleanup_message(contractor_name, project_id, cleanup_results)
        return self._send_slack_notification(message)
    
    def _should_send_slack(self) -> bool:
        """Check if Slack notifications are configured and enabled"""
        webhook_url = self.notifications_config.get('slack_webhook', '')
        return (webhook_url and 
                webhook_url != '' and 
                webhook_url.startswith('https://hooks.slack.com/services/'))
    
    def _send_slack_notification(self, message: Dict[str, Any]) -> bool:
        """Send notification to Slack webhook (no tokens needed!)"""
        webhook_url = self.notifications_config.get('slack_webhook')
        
        if not webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False
            
        try:
            response = requests.post(
                webhook_url,
                json=message,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info("✅ Slack notification sent successfully")
                return True
            else:
                logger.error(f"❌ Slack notification failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to send Slack notification: {e}")
            return False
    
    def _format_environment_created_message(self,
                                          contractor_name: str,
                                          project_id: str,
                                          github_repo_url: str,
                                          service_account_email: str,
                                          tables_copied: list) -> Dict[str, Any]:
        """Format Slack message for environment creation"""
        
        contact_info = self.config.get('contact_info', {})
        
        return {
            "text": f"🚀 New Contractor Environment Created: {contractor_name}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚀 New Contractor Environment Created"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Contractor:*\n{contractor_name}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Project ID:*\n`{project_id}`"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Service Account:*\n`{service_account_email}`"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Created:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*GitHub Repository:*\n<{github_repo_url}|{github_repo_url}>"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Tables Copied:*\n• " + "\n• ".join(tables_copied)
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Contact: {contact_info.get('email', 'N/A')} | {contact_info.get('slack', 'N/A')}"
                        }
                    ]
                }
            ]
        }
    
    def _format_cleanup_message(self,
                              contractor_name: str,
                              project_id: str,
                              cleanup_results: Dict[str, Any]) -> Dict[str, Any]:
        """Format Slack message for environment cleanup"""
        
        status_emoji = "✅" if cleanup_results.get('status') == 'completed' else "❌"
        
        fields = [
            {
                "type": "mrkdwn",
                "text": f"*Contractor:*\n{contractor_name}"
            },
            {
                "type": "mrkdwn",
                "text": f"*Project ID:*\n`{project_id}`"
            },
            {
                "type": "mrkdwn",
                "text": f"*Status:*\n{status_emoji} {cleanup_results.get('status', 'unknown')}"
            },
            {
                "type": "mrkdwn",
                "text": f"*Cleaned up:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        ]
        
        # Add cleanup details
        if cleanup_results.get('project_deleted'):
            fields.append({
                "type": "mrkdwn",
                "text": "*GCP Project:*\n✅ Deleted"
            })
        
        if cleanup_results.get('repo_archived'):
            fields.append({
                "type": "mrkdwn",
                "text": "*GitHub Repo:*\n✅ Archived"
            })
        
        return {
            "text": f"{status_emoji} Contractor Environment Cleanup: {contractor_name}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{status_emoji} Contractor Environment Cleanup"
                    }
                },
                {
                    "type": "section",
                    "fields": fields
                }
            ]
        }

def test_slack_webhook(config_path: str = "config/master_config.yaml") -> bool:
    """Test Slack webhook configuration"""
    
    print("🧪 Testing Slack webhook configuration...")
    
    notification_manager = NotificationManager(config_path)
    
    if not notification_manager._should_send_slack():
        print("❌ Slack webhook not configured properly")
        print("Please update the slack_webhook in your master_config.yaml with a valid webhook URL")
        print("Get one from: https://api.slack.com/apps → Your App → Incoming Webhooks")
        return False
    
    # Send test message
    test_message = {
        "text": "🧪 Test Notification from Dev Environment System",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🧪 *Test Notification*\n\nThis is a test message from your contractor environment management system.\n\nIf you see this, your Slack webhook is working correctly! ✅\n\n*No tokens needed - webhooks never expire!*"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                ]
            }
        ]
    }
    
    success = notification_manager._send_slack_notification(test_message)
    
    if success:
        print("✅ Slack webhook test successful!")
        print("Check your Slack channel for the test message.")
        print("💡 Webhooks never expire - set once and forget!")
    else:
        print("❌ Slack webhook test failed!")
        print("Check your webhook URL and network connection.")
    
    return success

if __name__ == "__main__":
    # Test the webhook when run directly
    test_slack_webhook() 