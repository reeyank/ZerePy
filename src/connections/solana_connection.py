import logging
from typing import Dict, Any, List, Optional
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.solana_connection")

class SolanaConnectionError(Exception):
    """Base exception for Solana connection errors"""
    pass

class SolanaConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Solana connection...")
        super().__init__(config)

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Solana configuration from JSON"""
        return config  # For stub, accept any config

    def register_actions(self) -> None:
        """Register available Solana actions"""
        self.actions = {
            "transfer": Action(
                name="transfer",
                parameters=[
                    ActionParameter("to_address", True, str, "Destination address"),
                    ActionParameter("amount", True, float, "Amount to transfer"),
                    ActionParameter("token_mint", False, str, "Token mint address (optional for SOL)")
                ],
                description="Transfer SOL or SPL tokens"
            ),
            "trade": Action(
                name="trade",
                parameters=[
                    ActionParameter("output_mint", True, str, "Output token mint address"),
                    ActionParameter("input_amount", True, float, "Input amount"),
                    ActionParameter("input_mint", False, str, "Input token mint (optional for SOL)"),
                    ActionParameter("slippage_bps", False, int, "Slippage in basis points")
                ],
                description="Swap tokens using Jupiter"
            ),
            "get-balance": Action(
                name="get-balance",
                parameters=[
                    ActionParameter("token_address", False, str, "Token mint address (optional for SOL)")
                ],
                description="Check SOL or token balance"
            ),
            "stake": Action(
                name="stake",
                parameters=[
                    ActionParameter("amount", True, float, "Amount of SOL to stake")
                ],
                description="Stake SOL"
            ),
            "lend-assets": Action(
                name="lend-assets",
                parameters=[
                    ActionParameter("amount", True, float, "Amount to lend")
                ],
                description="Lend assets"
            ),
            "deploy-token": Action(
                name="deploy-token",
                parameters=[
                    ActionParameter("decimals", False, int, "Token decimals (default 9)")
                ],
                description="Deploy a new token"
            ),
            "fetch-price": Action(
                name="fetch-price",
                parameters=[
                    ActionParameter("token_id", True, str, "Token ID to fetch price for")
                ],
                description="Get token price"
            ),
            "get-tps": Action(
                name="get-tps",
                parameters=[],
                description="Get current Solana TPS"
            )
        }

    def configure(self) -> bool:
        """Stub configuration"""
        return True

    def is_configured(self, verbose: bool = False) -> bool:
        """Stub configuration check"""
        return True

    def transfer(self, to_address: str, amount: float, token_mint: Optional[str] = None) -> bool:
        logger.info(f"STUB: Transfer {amount} to {to_address}")
        return True

    def trade(self, output_mint: str, input_amount: float, 
             input_mint: Optional[str] = None, slippage_bps: int = 100) -> bool:
        logger.info(f"STUB: Swap {input_amount} for {output_mint}")
        return True

    def get_balance(self, token_address: Optional[str] = None) -> float:
        return 100.0

    def stake(self, amount: float) -> bool:
        logger.info(f"STUB: Stake {amount} SOL")
        return True

    def lend_assets(self, amount: float) -> bool:
        logger.info(f"STUB: Lend {amount}")
        return True

    def deploy_token(self, decimals: int = 9) -> str:
        return "STUB_TOKEN_ADDRESS"

    def fetch_price(self, token_id: str) -> float:
        return 1.23

    def get_tps(self) -> int:
        return 5000

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Solana action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)