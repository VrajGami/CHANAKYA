"""
FILE: src/mcp_server.py
DESCRIPTION: Simulates a Model Context Protocol (MCP) server for Risk Governance.
This isolates the deterministic risk math from the LLM execution logic.
Agents must formally request approval through this interface.
"""
from src.risk_manager import RiskGuardian
import json

class MCPRiskServer:
    def __init__(self, initial_capital: float = 1000.0):
        self.fortress = RiskGuardian(total_capital=initial_capital)
        self.tools = [
            {
                "name": "get_position_size",
                "description": "Calculates the Kelly-criterion safe number of shares.",
                "parameters": ["price", "stop_loss", "confidence"]
            },
            {
                "name": "validate_trade",
                "description": "Final deterministic gate to prevent over-leverage.",
                "parameters": ["symbol", "total_cost"]
            }
        ]

    def execute_tool(self, tool_name: str, parameters: dict) -> str:
        """
        Standardized MCP JSON execution protocol.
        """
        try:
            if tool_name == "get_position_size":
                price = float(parameters.get("price", 0))
                stop_loss = float(parameters.get("stop_loss", 0))
                confidence = float(parameters.get("confidence", 0))
                size = self.fortress.get_safe_position_size(price, stop_loss, confidence)
                return json.dumps({"status": "success", "recommended_shares": size})

            elif tool_name == "validate_trade":
                symbol = str(parameters.get("symbol", ""))
                total_cost = float(parameters.get("total_cost", 0))
                is_valid = self.fortress.validate_trade(symbol, total_cost)
                return json.dumps({"status": "success", "is_valid": is_valid})
                
            else:
                 return json.dumps({"status": "error", "message": f"Unknown tool: {tool_name}"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def update_capital(self, new_capital: float):
        self.fortress.total_capital = new_capital
