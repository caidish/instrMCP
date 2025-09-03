"""Context7 MCP Client Wrapper

Thin wrapper for querying Context7 MCP server for QCoDeS documentation and examples.
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

class Context7Client:
    """Client for Context7 MCP server integration."""
    
    def __init__(self, api_key: Optional[str] = None, url: Optional[str] = None):
        """Initialize Context7 client.
        
        Args:
            api_key: Context7 API key (or from CONTEXT7_API_KEY env var)
            url: Context7 MCP server URL (or from CONTEXT7_URL env var)
        """
        self.api_key = api_key or os.getenv("CONTEXT7_API_KEY")
        self.url = url or os.getenv("CONTEXT7_URL", "https://mcp.context7.com/mcp")
        
        if not self.api_key:
            logger.warning("Context7 API key not provided - Context7 features disabled")
    
    async def query_qcodes_docs(self, query: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Query Context7 for QCoDeS documentation.
        
        Args:
            query: Search query for QCoDeS documentation
            context: Additional context for the query
            
        Returns:
            Dictionary containing the response from Context7
        """
        if not self.api_key:
            return {
                "error": "Context7 API key not configured",
                "status": "disabled"
            }
        
        try:
            logger.info(f"Querying Context7 for QCoDeS docs: {query}")
            
            # Prepare the query with QCoDeS context
            full_query = f"QCoDeS: {query}"
            if context:
                full_query += f" Context: {context}"
            
            # Make HTTP request to Context7 MCP server
            headers = {
                "CONTEXT7_API_KEY": self.api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": {
                        "query": full_query,
                        "max_results": 5
                    }
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                
                result = response.json()
                logger.info("Successfully retrieved Context7 documentation")
                
                return {
                    "query": query,
                    "results": result,
                    "status": "success"
                }
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error querying Context7: {e}")
            return {
                "error": f"HTTP error: {e}",
                "query": query,
                "status": "error"
            }
        except Exception as e:
            logger.error(f"Error querying Context7: {e}")
            return {
                "error": str(e),
                "query": query, 
                "status": "error"
            }
    
    async def get_station_examples(self) -> Dict[str, Any]:
        """Get QCoDeS Station configuration examples from Context7."""
        return await self.query_qcodes_docs(
            "Station configuration YAML examples setup instruments",
            "Looking for examples of how to configure QCoDeS Station from YAML files"
        )
    
    async def get_snapshot_docs(self) -> Dict[str, Any]:
        """Get QCoDeS snapshot documentation from Context7."""
        return await self.query_qcodes_docs(
            "snapshot method instrument station update parameter",
            "Need documentation on QCoDeS snapshot methods and update behavior"
        )
    
    async def get_instrument_driver_info(self, driver_name: str) -> Dict[str, Any]:
        """Get information about a specific QCoDeS instrument driver.
        
        Args:
            driver_name: Name of the instrument driver (e.g., 'Keithley2400')
        """
        return await self.query_qcodes_docs(
            f"{driver_name} instrument driver parameters methods",
            f"Looking for documentation and examples for QCoDeS {driver_name} driver"
        )
    
    async def get_error_solutions(self, error_message: str) -> Dict[str, Any]:
        """Get solutions for QCoDeS-related errors.
        
        Args:
            error_message: The error message encountered
        """
        return await self.query_qcodes_docs(
            f"error solution fix: {error_message}",
            "Looking for solutions to this QCoDeS error"
        )

class QCoDesDocHelper:
    """Helper class for QCoDeS-specific documentation queries."""
    
    def __init__(self, context7_client: Optional[Context7Client] = None):
        """Initialize with Context7 client.
        
        Args:
            context7_client: Context7Client instance (creates default if None)
        """
        self.context7 = context7_client or Context7Client()
    
    async def help_with_station_config(self) -> str:
        """Get help with Station configuration."""
        try:
            result = await self.context7.get_station_examples()
            
            if result["status"] == "success":
                # Extract relevant information from Context7 response
                docs = result.get("results", {})
                return self._format_documentation(docs, "Station Configuration")
            else:
                return f"Error getting Station configuration help: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            logger.error(f"Error getting Station config help: {e}")
            return f"Error: {e}"
    
    async def help_with_snapshots(self) -> str:
        """Get help with snapshot methods."""
        try:
            result = await self.context7.get_snapshot_docs()
            
            if result["status"] == "success":
                docs = result.get("results", {})
                return self._format_documentation(docs, "Snapshot Methods")
            else:
                return f"Error getting snapshot help: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            logger.error(f"Error getting snapshot help: {e}")
            return f"Error: {e}"
    
    async def help_with_driver(self, driver_name: str) -> str:
        """Get help with specific instrument driver.
        
        Args:
            driver_name: Name of the driver to get help for
        """
        try:
            result = await self.context7.get_instrument_driver_info(driver_name)
            
            if result["status"] == "success":
                docs = result.get("results", {})
                return self._format_documentation(docs, f"{driver_name} Driver")
            else:
                return f"Error getting {driver_name} driver help: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            logger.error(f"Error getting driver help for {driver_name}: {e}")
            return f"Error: {e}"
    
    def _format_documentation(self, docs: Dict[str, Any], title: str) -> str:
        """Format documentation response for display.
        
        Args:
            docs: Documentation data from Context7
            title: Title for the formatted output
            
        Returns:
            Formatted documentation string
        """
        if not docs:
            return f"No documentation found for {title}"
        
        formatted = f"\n=== {title} Help ===\n\n"
        
        # Try to extract meaningful content from Context7 response
        if isinstance(docs, dict):
            if "content" in docs:
                formatted += docs["content"]
            elif "results" in docs:
                for i, result in enumerate(docs["results"][:3], 1):  # Limit to top 3 results
                    if isinstance(result, dict) and "content" in result:
                        formatted += f"{i}. {result['content']}\n\n"
            else:
                formatted += json.dumps(docs, indent=2)
        else:
            formatted += str(docs)
        
        return formatted

# Global instances
context7_client = Context7Client()
qcodes_doc_helper = QCoDesDocHelper(context7_client)

# Convenience functions
async def get_station_help() -> str:
    """Get help with QCoDeS Station configuration."""
    return await qcodes_doc_helper.help_with_station_config()

async def get_snapshot_help() -> str:
    """Get help with QCoDeS snapshot methods."""
    return await qcodes_doc_helper.help_with_snapshots()

async def get_driver_help(driver_name: str) -> str:
    """Get help with specific QCoDeS instrument driver."""
    return await qcodes_doc_helper.help_with_driver(driver_name)

async def solve_qcodes_error(error_message: str) -> str:
    """Get solutions for QCoDeS errors."""
    result = await context7_client.get_error_solutions(error_message)
    if result["status"] == "success":
        return qcodes_doc_helper._format_documentation(
            result.get("results", {}), 
            "Error Solutions"
        )
    else:
        return f"Error getting solution: {result.get('error', 'Unknown error')}"