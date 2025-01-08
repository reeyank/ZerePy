import logging
import os
import requests
import asyncio
from typing import Dict, Any, Optional

from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.types import JupiterTokenData
from src.constants import LAMPORTS_PER_SOL, TOKENS
from src.helpers.solana.pumpfun import PumpfunTokenManager
from src.helpers.solana.faucet import FaucetManager
from src.helpers.solana.lend import AssetLender
from src.helpers.solana.stake import StakeManager
from src.helpers.solana.trade import TradeManager
from src.helpers.solana.token_deploy import TokenDeploymentManager
from src.helpers.solana.performance import SolanaPerformanceTracker
from src.helpers.solana.transfer import SolanaTransferHelper


from dotenv import load_dotenv

from jupiter_python_sdk.jupiter import Jupiter

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from solders.keypair import Keypair  # type: ignore


logger = logging.getLogger("connections.solana_connection")


class SolanaConnectionError(Exception):
    """Base exception for Solana connection errors"""

    pass


class SolanaConfigurationError(SolanaConnectionError):
    """Raised when there are configuration/credential issues"""

    pass


class SolanaConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Solana connection...")
        super().__init__(config)

    @property
    def is_llm_provider(self) -> bool:
        return False

    def _get_connection_async(self) -> AsyncClient:
        conn = AsyncClient(self.config["rpc"])
        return conn

    def _get_wallet(self):
        creds = self._get_credentials()
        return Keypair.from_base58_string(creds["SOLANA_PRIVATE_KEY"])

    def _get_credentials(self) -> Dict[str, str]:
        """Get Solana credentials from environment with validation"""
        logger.debug("Retrieving Solana Credentials")
        load_dotenv()
        required_vars = {"SOLANA_PRIVATE_KEY": "solana wallet private key"}
        credentials = {}
        missing = []

        for env_var, description in required_vars.items():
            value = os.getenv(env_var)
            if not value:
                missing.append(description)
            credentials[env_var] = value

        if missing:
            error_msg = f"Missing Solana credentials: {', '.join(missing)}"
            raise SolanaConfigurationError(error_msg)

        Keypair.from_base58_string(credentials["SOLANA_PRIVATE_KEY"])
        logger.debug("All required credentials found")
        return credentials

    def _get_jupiter(self, private_key, async_client):
        jupiter = Jupiter(
            async_client=async_client,
            keypair=private_key,
            quote_api_url="https://quote-api.jup.ag/v6/quote?",
            swap_api_url="https://quote-api.jup.ag/v6/swap",
            open_order_api_url="https://jup.ag/api/limit/v1/createOrder",
            cancel_orders_api_url="https://jup.ag/api/limit/v1/cancelOrders",
            query_open_orders_api_url="https://jup.ag/api/limit/v1/openOrders?wallet=",
            query_order_history_api_url="https://jup.ag/api/limit/v1/orderHistory",
            query_trade_history_api_url="https://jup.ag/api/limit/v1/tradeHistory",
        )
        return jupiter

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Solana configuration from JSON"""
        required_fields = ["rpc"]
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise ValueError(
                f"Missing required configuration fields: {', '.join(missing_fields)}"
            )

        if not isinstance(config["rpc"], str):
            raise ValueError("rpc must be a positive integer")

        return config  # For stub, accept any config

    def register_actions(self) -> None:
        """Register available Solana actions"""
        self.actions = {
            "transfer": Action(
                name="transfer",
                parameters=[
                    ActionParameter("to_address", True, str, "Destination address"),
                    ActionParameter("amount", True, float, "Amount to transfer"),
                    ActionParameter(
                        "token_mint",
                        False,
                        str,
                        "Token mint address (optional for SOL)",
                    ),
                ],
                description="Transfer SOL or SPL tokens",
            ),
            "trade": Action(
                name="trade",
                parameters=[
                    ActionParameter(
                        "output_mint", True, str, "Output token mint address"
                    ),
                    ActionParameter("input_amount", True, float, "Input amount"),
                    ActionParameter(
                        "input_mint", False, str, "Input token mint (optional for SOL)"
                    ),
                    ActionParameter(
                        "slippage_bps", False, int, "Slippage in basis points"
                    ),
                ],
                description="Swap tokens using Jupiter",
            ),
            "get-balance": Action(
                name="get-balance",
                parameters=[
                    ActionParameter(
                        "token_address",
                        False,
                        str,
                        "Token mint address (optional for SOL)",
                    )
                ],
                description="Check SOL or token balance",
            ),
            "stake": Action(
                name="stake",
                parameters=[
                    ActionParameter("amount", True, float, "Amount of SOL to stake")
                ],
                description="Stake SOL",
            ),
            "lend-assets": Action(
                name="lend-assets",
                parameters=[ActionParameter("amount", True, float, "Amount to lend")],
                description="Lend assets",
            ),
            "request-faucet": Action(
                name="request-faucet",
                parameters=[],
                description="Request funds from faucet for testing",
            ),
            "deploy-token": Action(
                name="deploy-token",
                parameters=[
                    ActionParameter(
                        "decimals", False, int, "Token decimals (default 9)"
                    )
                ],
                description="Deploy a new token",
            ),
            "fetch-price": Action(
                name="fetch-price",
                parameters=[
                    ActionParameter(
                        "token_id", True, str, "Token ID to fetch price for"
                    )
                ],
                description="Get token price",
            ),
            "get-tps": Action(
                name="get-tps", parameters=[], description="Get current Solana TPS"
            ),
            "get-token-by-ticker": Action(
                name="get-token-by-ticker",
                parameters=[
                    ActionParameter("ticker", True, str, "Token ticker symbol")
                ],
                description="Get token data by ticker symbol",
            ),
            "get-token-by-address": Action(
                name="get-token-by-address",
                parameters=[ActionParameter("mint", True, str, "Token mint address")],
                description="Get token data by mint address",
            ),
            "launch-pump-token": Action(
                name="launch-pump-token",
                parameters=[
                    ActionParameter("token_name", True, str, "Name of the token"),
                    ActionParameter("token_ticker", True, str, "Token ticker symbol"),
                    ActionParameter("description", True, str, "Token description"),
                    ActionParameter("image_url", True, str, "Token image URL"),
                    ActionParameter("options", False, dict, "Additional token options"),
                ],
                description="Launch a Pump & Fun token",
            ),
        }

    # todo w
    def configure(self) -> bool:
        """Stub configuration"""
        return True

    def is_configured(self, verbose: bool = True) -> bool:
        """Stub configuration check"""
        try:

            credentials = self._get_credentials()
            logger.debug("Solana configuration is valid")
            return True

        except Exception as e:
            if verbose:
                error_msg = str(e)
                if isinstance(e, SolanaConfigurationError):
                    error_msg = f"Configuration error: {error_msg}"
                elif isinstance(e, SolanaConnectionError):
                    error_msg = f"API validation error: {error_msg}"
                logger.debug(f"Solana Configuration validation failed: {error_msg}")
            return False
        return True

    def transfer(
        self, to_address: str, amount: float, token_mint: Optional[str] = None
    ) -> bool:
        logger.info(f"STUB: Transfer {amount} to {to_address}")
        try:
            if token_mint:
                signature = SolanaTransferHelper.transfer_spl_tokens(
                    self._get_connection_async(),
                    self._get_wallet(),
                    to_address,
                    amount,
                    token_mint,
                )
                token_identifier = str(token_mint)
            else:
                signature = SolanaTransferHelper.transfer_native_sol(
                    self._get_connection_async(), self._get_wallet(), to_address, amount
                )
                token_identifier = "SOL"
            SolanaTransferHelper.confirm_transaction(
                self._get_connection_async(), signature
            )

            logger.info(
                f"\nSuccess!\n\nSignature: {signature}\nFrom Address: {str(self._get_wallet().pubkey())}\nTo Address: {to_address}\nAmount: {amount}\nToken: {token_identifier}"
            )

            return True

        except Exception as error:

            logger.error(f"Transfer failed: {error}")
            raise RuntimeError(f"Transfer operation failed: {error}") from error

    # todo: test on mainnet
    def trade(
        self,
        output_mint: str,
        input_amount: float,
        input_mint: Optional[str] = TOKENS["USDC"],
        slippage_bps: int = 100,
    ) -> bool:
        logger.info(f"STUB: Swap {input_amount} for {output_mint}")
        res = TradeManager.trade(
            self._get_connection_async(),
            self._get_wallet(),
            output_mint,
            input_amount,
            input_mint,
            slippage_bps,
        )
        asyncio.run(res)
        return True

    def get_balance(self, token_address: Optional[str] = None) -> float:
        connection = self._get_connection()
        wallet = self._get_wallet()
        try:
            if not token_address:
                response = connection.get_balance(wallet.pubkey(), commitment=Confirmed)
                return response.value / LAMPORTS_PER_SOL

            response = connection.get_token_account_balance(
                token_address, commitment=Confirmed
            )

            if response.value is None:
                return None

            return float(response.value.ui_amount)

        except Exception as error:
            raise Exception(f"Failed to get balance: {str(error)}") from error

    # todo: test on mainnet
    def stake(self, amount: float) -> bool:
        logger.info(f"STUB: Stake {amount} SOL")
        res = StakeManager.stake_with_jup(
            self._get_connection_async(), self._get_wallet(), amount
        )
        res = asyncio.run(res)
        logger.info(f"Staked {amount} SOL\nTransaction ID: {res}")
        return True

    # todo: test on mainnet
    def lend_assets(self, amount: float) -> bool:
        logger.info(f"STUB: Lend {amount}")
        res = AssetLender.lend_asset(
            self._get_connection_async(), self._get_wallet(), amount
        )
        res = asyncio.run(res)
        logger.info(f"Lent {amount} USDC\nTransaction ID: {res}")
        return True

    def request_faucet(self) -> bool:
        logger.info("STUB: Requesting faucet funds")
        res = FaucetManager.request_faucet_funds(self)
        res = asyncio.run(res)
        logger.info(f"Requested faucet funds\nTransaction ID: {res}")
        return True

    def deploy_token(self, decimals: int = 9) -> str:
        logger.info(f"STUB: Deploy token with {decimals} decimals")
        res = TokenDeploymentManager.deploy_token(
            self._get_connection_async(), self._get_wallet(), decimals
        )
        res = asyncio.run(res)
        logger.info(
            f"Deployed token with {decimals} decimals\nToken Mint: {res['mint']}"
        )
        return res["mint"]

    def fetch_price(self, token_id: str) -> float:
        url = f"https://api.jup.ag/price/v2?ids={token_id}"

        try:
            with requests.get(url) as response:
                response.raise_for_status()
                data = response.json()
                price = data.get("data", {}).get(token_id, {}).get("price")

                if not price:
                    raise Exception("Price data not available for the given token.")

                return str(price)
        except Exception as e:
            raise Exception(f"Price fetch failed: {str(e)}")
        return 1.23

    # todo: test on mainnet
    def get_tps(self) -> int:
        return SolanaPerformanceTracker.fetch_current_tps(self)

    def get_token_by_ticker(self, ticker: str) -> Dict[str, Any]:
        try:
            response = requests.get(
                f"https://api.dexscreener.com/latest/dex/search?q={ticker}"
            )
            response.raise_for_status()

            data = response.json()
            if not data.get("pairs"):
                return None

            solana_pairs = [
                pair for pair in data["pairs"] if pair.get("chainId") == "solana"
            ]
            solana_pairs.sort(key=lambda x: x.get("fdv", 0), reverse=True)

            solana_pairs = [
                pair
                for pair in solana_pairs
                if pair.get("baseToken", {}).get("symbol", "").lower() == ticker.lower()
            ]

            if solana_pairs:
                return solana_pairs[0].get("baseToken", {}).get("address")
            return None
        except Exception as error:
            logger.error(
                f"Error fetching token address from DexScreener: {str(error)}",
                exc_info=True,
            )
            return None

    def get_token_by_address(self, mint: str) -> Dict[str, Any]:
        try:
            if not mint:
                raise ValueError("Mint address is required")

            response = requests.get(
                "https://tokens.jup.ag/tokens?tags=verified",
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            data = response.json()
            for token in data:
                if token.get("address") == str(mint):
                    return JupiterTokenData(
                        address=token.get("address"),
                        symbol=token.get("symbol"),
                        name=token.get("name"),
                    )
            return None
        except Exception as error:
            raise Exception(f"Error fetching token data: {str(error)}")

    # todo: test on mainnet
    def launch_pump_token(
        self,
        token_name: str,
        token_ticker: str,
        description: str,
        image_url: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info(f"STUB: Launch Pump & Fun token {token_ticker}")
        res = PumpfunTokenManager.launch_pumpfun_token(
            self._get_connection_async(),
            self._get_wallet(),
            token_name,
            token_ticker,
            description,
            image_url,
            options,
        )
        res = asyncio.run(res)
        logger.info(
            f"Launched Pump & Fun token {token_ticker}\nToken Mint: {res['mint']}"
        )
        return res

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Solana action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        method_name = action_name.replace("-", "_")
        method = getattr(self, method_name)
        return method(**kwargs)
