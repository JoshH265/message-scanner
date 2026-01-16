import requests
import asyncio
import time
import discord
from typing import List, Dict, Any, Optional
from database import get_all_monitored_tokens, add_claim_event, update_last_checked, get_unnotified_claim_events, mark_claim_event_notified

BAGS_API_KEY = "bags_prod_jdN_JWEQpUZOJVEhgZnhN5zYEQ4ApxUAekQTxLP7P0s"
BAGS_API_BASE_URL = "https://public-api-v2.bags.fm/api/v1"

class BagsAPIService:
    def __init__(self):
        self.api_key = BAGS_API_KEY
        self.base_url = BAGS_API_BASE_URL
        self.headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }
    
    async def get_token_claim_events(self, token_mint: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get claim events for a specific token"""
        url = f"{self.base_url}/fee-share/token/claim-events"
        params = {
            'tokenMint': token_mint,
            'limit': limit,
            'offset': offset
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching claim events for {token_mint}: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_new_claims_for_all_tokens(self) -> List[Dict[str, Any]]:
        """Check for new claim events for all monitored tokens"""
        monitored_tokens = get_all_monitored_tokens()
        new_events = []
        
        for token_mint, added_by, added_at in monitored_tokens:
            try:
                # Get recent claim events
                result = await self.get_token_claim_events(token_mint)
                
                if result.get('success') and 'response' in result:
                    events = result['response'].get('events', [])
                    
                    # Process each event
                    for event in events:
                        signature = event.get('signature')
                        wallet = event.get('wallet')
                        is_creator = event.get('isCreator', False)
                        amount = event.get('amount')
                        timestamp = event.get('timestamp')
                        
                        # Add to database if new
                        if add_claim_event(signature, token_mint, wallet, is_creator, amount, timestamp):
                            new_events.append({
                                'signature': signature,
                                'token_mint': token_mint,
                                'wallet': wallet,
                                'is_creator': is_creator,
                                'amount': amount,
                                'timestamp': timestamp
                            })
                
                # Update last checked time
                update_last_checked(token_mint)
                
                # Rate limit to avoid hitting API limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"Error checking token {token_mint}: {e}")
        
        return new_events

# Global instance
bags_service = BagsAPIService()

async def start_monitoring_loop(bot, notification_channel_id: int):
    """Background task to monitor fee claim events"""
    print("Starting Bags API monitoring loop...")
    
    while True:
        try:
            # Check for new claim events
            new_events = await bags_service.check_new_claims_for_all_tokens()
            
            if new_events:
                print(f"Found {len(new_events)} new claim events")
                
                # Get notification channel
                channel = bot.get_channel(notification_channel_id)
                if not channel:
                    print(f"Could not find notification channel {notification_channel_id}")
                    await asyncio.sleep(60)  # Wait longer if channel not found
                    continue
                
                # Send notifications for each new event
                for event in new_events:
                    await send_claim_notification(channel, event)
                    mark_claim_event_notified(event['signature'])
            
            # Check every 2 minutes to respect rate limits
            await asyncio.sleep(120)
            
        except Exception as e:
            print(f"Error in monitoring loop: {e}")
            await asyncio.sleep(60)  # Wait before retrying

async def send_claim_notification(channel, event: Dict[str, Any]):
    """Send a notification about a new claim event"""
    try:
        embed = {
            "title": "💰 New Fee Claim Detected!",
            "description": f"Someone claimed fees from a monitored token!",
            "color": 0x00ff00,
            "fields": [
                {
                    "name": "Token Mint",
                    "value": f"`{event['token_mint']}`",
                    "inline": False
                },
                {
                    "name": "Claimer Wallet",
                    "value": f"`{event['wallet']}`",
                    "inline": True
                },
                {
                    "name": "Is Creator",
                    "value": "Yes" if event['is_creator'] else "No",
                    "inline": True
                },
                {
                    "name": "Amount Claimed",
                    "value": f"🪙 {event['amount']} SOL",
                    "inline": True
                },
                {
                    "name": "Timestamp",
                    "value": f"<t:{int(time.time())}:R>",  # Discord timestamp
                    "inline": True
                },
                {
                    "name": "Transaction",
                    "value": f"[View on Solana Explorer](https://solscan.io/tx/{event['signature']})",
                    "inline": False
                }
            ],
            "footer": {
                "text": "Bags Fee Claim Monitor"
            }
        }
        
        await channel.send(embed=discord.Embed.from_dict(embed))
        print(f"Sent claim notification for token {event['token_mint']}")
        
    except Exception as e:
        print(f"Error sending claim notification: {e}")