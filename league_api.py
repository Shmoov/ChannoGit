from riotwatcher import LolWatcher
import os
from typing import Optional, Tuple

class LeagueAPI:
    def __init__(self, api_key: str):
        self.watcher = LolWatcher(api_key)
        self.region = "na1"  # Default region
        
    def set_region(self, region: str):
        """Set the region for API calls"""
        self.region = region.lower()
        
    def get_summoner_by_name(self, summoner_name: str):
        """Get summoner info by name"""
        try:
            return self.watcher.summoner.by_name(self.region, summoner_name)
        except Exception as e:
            print(f"Error getting summoner: {e}")
            return None
            
    def get_match_history(self, puuid: str, count: int = 20) -> list:
        """Get recent matches for a summoner"""
        try:
            # Match v5 API uses different region format
            region = "americas" if self.region in ["na1", "br1", "la1", "la2"] else "europe" if self.region in ["euw1", "eun1", "tr1", "ru"] else "asia"
            return self.watcher.match.matchlist_by_puuid(region, puuid, count=count)
        except Exception as e:
            print(f"Error getting match history: {e}")
            return []
            
    def get_match_details(self, match_id: str) -> Optional[dict]:
        """Get details for a specific match"""
        try:
            # Match v5 API uses different region format
            region = "americas" if self.region in ["na1", "br1", "la1", "la2"] else "europe" if self.region in ["euw1", "eun1", "tr1", "ru"] else "asia"
            return self.watcher.match.by_id(region, match_id)
        except Exception as e:
            print(f"Error getting match details: {e}")
            return None
            
    def verify_match_result(self, match_id: str, summoner_name: str) -> Optional[bool]:
        """Verify if a summoner won a specific match
        Returns:
            bool: True if won, False if lost, None if error or match not found
        """
        try:
            # Get match details
            match_details = self.get_match_details(match_id)
            if not match_details:
                return None
                
            # Find the participant info for the summoner
            summoner = self.get_summoner_by_name(summoner_name)
            if not summoner:
                return None
                
            # Find participant in match
            for participant in match_details["info"]["participants"]:
                if participant["summonerId"] == summoner["id"]:
                    return participant["win"]
                    
            return None
        except Exception as e:
            print(f"Error verifying match result: {e}")
            return None
            
    def verify_recent_match_between_players(self, summoner1: str, summoner2: str, max_matches_to_check: int = 20) -> Tuple[Optional[str], Optional[bool]]:
        """Find and verify the most recent match between two players
        Returns:
            Tuple[str, bool]: (match_id, summoner1_won) or (None, None) if no match found
        """
        try:
            # Get summoner info
            summoner1_info = self.get_summoner_by_name(summoner1)
            summoner2_info = self.get_summoner_by_name(summoner2)
            if not summoner1_info or not summoner2_info:
                return None, None
                
            # Get recent matches for summoner1
            matches = self.get_match_history(summoner1_info["puuid"], count=max_matches_to_check)
            
            # Check each match for both players
            for match_id in matches:
                match_detail = self.get_match_details(match_id)
                if not match_detail:
                    continue
                    
                summoner1_result = None
                summoner2_found = False
                
                # Look for both players in the match
                for participant in match_detail["info"]["participants"]:
                    if participant["summonerId"] == summoner1_info["id"]:
                        summoner1_result = participant["win"]
                    elif participant["summonerId"] == summoner2_info["id"]:
                        summoner2_found = True
                        
                    if summoner1_result is not None and summoner2_found:
                        return match_id, summoner1_result
                        
            return None, None
        except Exception as e:
            print(f"Error verifying match between players: {e}")
            return None, None 