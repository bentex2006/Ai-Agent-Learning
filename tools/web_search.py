import asyncio
import json
import os
import sys
from typing import Dict, Any, List, Optional
import requests
from urllib.parse import quote_plus

from config import settings


class WebSearchTool:
    """Tool for performing web searches using DuckDuckGo Instant Answer API"""
    
    def __init__(self):
        self.name = "web_search"
        self.description = "Search the web for information, news, and current data"
        self.keywords = ["search", "find", "web", "internet", "current", "news", "information"]
        
        # DuckDuckGo Instant Answer API (no API key required)
        self.search_url = "https://api.duckduckgo.com/"
        self.html_search_url = "https://html.duckduckgo.com/html/"
        
        # Backup search engines (if available)
        self.serpapi_key = os.getenv("SERPAPI_KEY")
        self.bing_key = os.getenv("BING_SEARCH_KEY")
    
    async def execute(self, query: str, max_results: int = 5, 
                     search_type: str = "general") -> Dict[str, Any]:
        """
        Execute web search
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            search_type: Type of search (general, news, images)
            
        Returns:
            Dictionary with search results
        """
        
        try:
            # Sanitize query
            query = query.strip()
            if not query:
                return {"error": "Empty search query provided"}
            
            if len(query) > 500:
                query = query[:500]  # Limit query length
            
            # Try different search methods in order of preference
            if self.serpapi_key:
                return await self._search_with_serpapi(query, max_results, search_type)
            elif self.bing_key:
                return await self._search_with_bing(query, max_results, search_type)
            else:
                return await self._search_with_duckduckgo(query, max_results, search_type)
                
        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}
    
    async def _search_with_duckduckgo(self, query: str, max_results: int, 
                                     search_type: str) -> Dict[str, Any]:
        """Search using DuckDuckGo Instant Answer API"""
        
        try:
            # DuckDuckGo Instant Answer API
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            response = requests.get(self.search_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            results = []
            
            # Extract instant answer if available
            if data.get('AbstractText'):
                results.append({
                    'title': 'Instant Answer',
                    'snippet': data['AbstractText'],
                    'url': data.get('AbstractURL', ''),
                    'source': 'DuckDuckGo Instant Answer'
                })
            
            # Extract related topics
            for topic in data.get('RelatedTopics', [])[:max_results-len(results)]:
                if isinstance(topic, dict) and topic.get('Text'):
                    results.append({
                        'title': topic.get('Text', '').split(' - ')[0],
                        'snippet': topic.get('Text', ''),
                        'url': topic.get('FirstURL', ''),
                        'source': 'DuckDuckGo Related Topic'
                    })
            
            # If no good results, try a simple web search simulation
            if not results:
                results = await self._fallback_search(query, max_results)
            
            return {
                'query': query,
                'results': results[:max_results],
                'total_results': len(results),
                'search_engine': 'DuckDuckGo'
            }
            
        except Exception as e:
            return await self._fallback_search(query, max_results)
    
    async def _search_with_serpapi(self, query: str, max_results: int, 
                                  search_type: str) -> Dict[str, Any]:
        """Search using SerpAPI (Google Search API)"""
        
        try:
            import requests
            
            url = "https://serpapi.com/search"
            params = {
                'q': query,
                'api_key': self.serpapi_key,
                'engine': 'google',
                'num': max_results
            }
            
            if search_type == "news":
                params['tbm'] = 'nws'
            elif search_type == "images":
                params['tbm'] = 'isch'
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            results = []
            
            # Extract organic results
            for result in data.get('organic_results', [])[:max_results]:
                results.append({
                    'title': result.get('title', ''),
                    'snippet': result.get('snippet', ''),
                    'url': result.get('link', ''),
                    'source': 'Google Search'
                })
            
            # Extract news results if available
            for result in data.get('news_results', [])[:max_results-len(results)]:
                results.append({
                    'title': result.get('title', ''),
                    'snippet': result.get('snippet', ''),
                    'url': result.get('link', ''),
                    'source': 'Google News'
                })
            
            return {
                'query': query,
                'results': results[:max_results],
                'total_results': len(results),
                'search_engine': 'Google (SerpAPI)'
            }
            
        except Exception as e:
            return {"error": f"SerpAPI search failed: {str(e)}"}
    
    async def _search_with_bing(self, query: str, max_results: int, 
                               search_type: str) -> Dict[str, Any]:
        """Search using Bing Search API"""
        
        try:
            url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {'Ocp-Apim-Subscription-Key': self.bing_key}
            params = {
                'q': query,
                'count': max_results,
                'responseFilter': 'Webpages'
            }
            
            if search_type == "news":
                url = "https://api.bing.microsoft.com/v7.0/news/search"
                params['responseFilter'] = 'News'
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            results = []
            
            # Extract web results
            for result in data.get('webPages', {}).get('value', [])[:max_results]:
                results.append({
                    'title': result.get('name', ''),
                    'snippet': result.get('snippet', ''),
                    'url': result.get('url', ''),
                    'source': 'Bing Search'
                })
            
            # Extract news results
            for result in data.get('value', [])[:max_results-len(results)]:
                results.append({
                    'title': result.get('name', ''),
                    'snippet': result.get('description', ''),
                    'url': result.get('url', ''),
                    'source': 'Bing News'
                })
            
            return {
                'query': query,
                'results': results[:max_results],
                'total_results': len(results),
                'search_engine': 'Bing'
            }
            
        except Exception as e:
            return {"error": f"Bing search failed: {str(e)}"}
    
    async def _fallback_search(self, query: str, max_results: int) -> Dict[str, Any]:
        """Fallback search method when APIs are not available"""
        
        # This provides a basic search simulation for demo purposes
        # In a production system, you'd want to implement a proper fallback
        
        fallback_results = [
            {
                'title': f"Search results for: {query}",
                'snippet': f"I apologize, but I'm currently unable to perform live web searches. "
                          f"To get current information about '{query}', I recommend checking "
                          f"reliable sources like Wikipedia, official websites, or recent news outlets.",
                'url': f"https://www.google.com/search?q={quote_plus(query)}",
                'source': 'Search Unavailable'
            }
        ]
        
        return {
            'query': query,
            'results': fallback_results,
            'total_results': 1,
            'search_engine': 'Fallback',
            'note': 'Live search unavailable - please verify information from reliable sources'
        }
    
    async def search_news(self, query: str, max_results: int = 3) -> Dict[str, Any]:
        """Search for news articles specifically"""
        return await self.execute(query, max_results, "news")
    
    async def search_recent(self, query: str, days: int = 7, max_results: int = 5) -> Dict[str, Any]:
        """Search for recent content (last N days)"""
        # Modify query to include recency indicators
        recent_query = f"{query} recent {days} days"
        return await self.execute(recent_query, max_results, "general")
    
    def get_search_suggestions(self, query: str) -> List[str]:
        """Get search suggestions for a query"""
        # Basic search suggestions based on common patterns
        suggestions = [
            f"{query} definition",
            f"{query} examples",
            f"{query} tutorial",
            f"{query} vs alternatives",
            f"{query} best practices"
        ]
        
        return suggestions[:3]
    
    def is_search_query(self, text: str) -> bool:
        """Determine if text looks like a search query"""
        search_indicators = [
            "what is", "who is", "when did", "where is", "how to",
            "find", "search", "look up", "information about"
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in search_indicators)
    
    def extract_search_terms(self, text: str) -> str:
        """Extract search terms from natural language text"""
        # Simple extraction - remove common words and focus on key terms
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "is", "are", "was", "were", "what", "who", "when",
            "where", "why", "how", "can", "could", "would", "should", "find",
            "search", "look", "tell", "me", "about", "information"
        }
        
        words = text.lower().split()
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        
        return " ".join(filtered_words[:5])  # Limit to 5 key terms
