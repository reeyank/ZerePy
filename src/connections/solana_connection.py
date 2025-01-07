import base64
import logging
import os
from typing import Dict, Any, List, Optional
from dotenv import set_key, load_dotenv
import math, json
import aiohttp
import requests
from jupiter_python_sdk.jupiter import Jupiter
import asyncio
# solana
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts

# solders
from solders import message
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.system_program import TransferParams, transfer
from solders.transaction import VersionedTransaction # type: ignore
from solders.hash import Hash  # type: ignore
from solders.message import MessageV0, to_bytes_versioned # type: ignore

# src
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.types import TransferResult, JupiterTokenData, NetworkPerformanceMetrics
from src.constants import LAMPORTS_PER_SOL, DEFAULT_OPTIONS, JUP_API, TOKENS

# spl
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (get_associated_token_address,
                                    transfer_checked)


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
    def _get_connection(self) -> Client:
        conn = Client(self.config['rpc'])
        if not conn.is_connected():
            raise SolanaConnectionError("rpc invalid connection")
        return conn
    def _get_connection_async(self) -> AsyncClient:
        conn = AsyncClient(self.config['rpc'])
        return conn

    def _get_wallet(self):
        creds = self._get_credentials()
        return Keypair.from_base58_string(creds['SOLANA_PRIVATE_KEY'])
    def _get_credentials(self) -> Dict[str, str]:
        """Get Solana credentials from environment with validation"""
        logger.debug("Retrieving Solana Credentials")
        load_dotenv()
        required_vars = {
            "SOLANA_PRIVATE_KEY": "solana wallet private key"
        }
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
        

        
        
        Keypair.from_base58_string(credentials['SOLANA_PRIVATE_KEY'])
        logger.debug("All required credentials found")
        return credentials
    def _get_jupiter(self,private_key,async_client):
        jupiter = Jupiter(
            async_client=async_client,
            keypair=private_key,
            quote_api_url="https://quote-api.jup.ag/v6/quote?",
            swap_api_url="https://quote-api.jup.ag/v6/swap",
            open_order_api_url="https://jup.ag/api/limit/v1/createOrder",
            cancel_orders_api_url="https://jup.ag/api/limit/v1/cancelOrders",
            query_open_orders_api_url="https://jup.ag/api/limit/v1/openOrders?wallet=",
            query_order_history_api_url="https://jup.ag/api/limit/v1/orderHistory",
            query_trade_history_api_url="https://jup.ag/api/limit/v1/tradeHistory"
        )
        return jupiter
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Solana configuration from JSON"""
        required_fields = ["rpc"]
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
            
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
            "request-faucet": Action(
                name="request-faucet",
                parameters=[],
                description="Request funds from faucet for testing"
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
            ),
            "get-token-by-ticker": Action(
                name="get-token-by-ticker",
                parameters=[
                    ActionParameter("ticker", True, str, "Token ticker symbol")
                ],
                description="Get token data by ticker symbol"
            ),
            "get-token-by-address": Action(
                name="get-token-by-address",
                parameters=[
                    ActionParameter("mint", True, str, "Token mint address")
                ],
                description="Get token data by mint address"
            ),
            "launch-pump-token": Action(
                name="launch-pump-token",
                parameters=[
                    ActionParameter("token_name", True, str, "Name of the token"),
                    ActionParameter("token_ticker", True, str, "Token ticker symbol"),
                    ActionParameter("description", True, str, "Token description"),
                    ActionParameter("image_url", True, str, "Token image URL"),
                    ActionParameter("options", False, dict, "Additional token options")
                ],
                description="Launch a Pump & Fun token"
            )
        }
#todo w
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

    def transfer(self, to_address: str, amount: float, token_mint: Optional[str] = None) -> bool:
        logger.info(f"STUB: Transfer {amount} to {to_address}")
        try:
                if token_mint:
                    signature = SolanaTransferHelper.transfer_spl_tokens(self, to_address, amount, token_mint)
                    token_identifier = str(token_mint)
                else:
                    signature = SolanaTransferHelper.transfer_native_sol(self, to_address, amount)
                    token_identifier = "SOL"
                SolanaTransferHelper.confirm_transaction(self, signature)

                
                logger.info(f'\nSuccess!\n\nSignature: {signature}\nFrom Address: {str(self._get_wallet().pubkey())}\nTo Address: {to_address}\nAmount: {amount}\nToken: {token_identifier}')

                return True

        except Exception as error:

            logger.error(f"Transfer failed: {error}")
            raise RuntimeError(f"Transfer operation failed: {error}") from error
            
# todo: test on mainnet
    def trade(self, output_mint: str, input_amount: float, 
             input_mint: Optional[str] = TOKENS['USDC'], slippage_bps: int = 100) -> bool:
        logger.info(f"STUB: Swap {input_amount} for {output_mint}")
        res = TradeManager._trade(self,output_mint,input_amount,input_mint,slippage_bps)
        asyncio.run(res)
        return True

    def get_balance(self, token_address: Optional[str] = None) -> float:
        connection = self._get_connection()
        wallet = self._get_wallet()
        try:
            if not token_address:
                response = connection.get_balance(
                    wallet.pubkey(),
                    commitment=Confirmed
                )
                return response.value / LAMPORTS_PER_SOL

            response = connection.get_token_account_balance(
                token_address,
                commitment=Confirmed
            )

            if response.value is None:
                return None

            return float(response.value.ui_amount)

        except Exception as error:
            raise Exception(f"Failed to get balance: {str(error)}") from error

# todo: test on mainnet
    def stake(self, amount: float) -> bool:
        logger.info(f"STUB: Stake {amount} SOL")
        res = StakeManager.stake_with_jup(self, amount)
        res = asyncio.run(res)
        logger.info(f"Staked {amount} SOL\nTransaction ID: {res}")
        return True

#todo: test on mainnet
    def lend_assets(self, amount: float) -> bool:
        logger.info(f"STUB: Lend {amount}")
        res = AssetLender.lend_asset(self, amount)
        res = asyncio.run(res)
        logger.info(f"Lent {amount} USDC\nTransaction ID: {res}")
        return True

#todo w
    def request_faucet(self) -> bool:
        logger.info("STUB: Requesting faucet funds")
        res = FaucetManager.request_faucet_funds(self)
        res = asyncio.run(res)
        logger.info(f"Requested faucet funds\nTransaction ID: {res}")
        return True
#todo w
    def deploy_token(self, decimals: int = 9) -> str:
        return "STUB_TOKEN_ADDRESS"
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
#todo: test
    def get_tps(self) -> int:
        return SolanaPerformanceTracker.fetch_current_tps(self)

    def get_token_by_ticker(self, ticker: str) -> Dict[str, Any]:
        try:
            response = requests.get(f"https://api.dexscreener.com/latest/dex/search?q={ticker}")
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
            logger.error(f"Error fetching token address from DexScreener: {str(error)}", exc_info=True)
            return None

    def get_token_by_address(self, mint: str) -> Dict[str, Any]:
        try:
            if not mint:
                raise ValueError("Mint address is required")

            response = requests.get("https://tokens.jup.ag/tokens?tags=verified", headers={"Content-Type": "application/json"})
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

#todo w
    def launch_pump_token(self, token_name: str, token_ticker: str, 
                         description: str, image_url: str, 
                         options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "name": token_name,
            "ticker": token_ticker,
            "mint": "STUB_MINT_ADDRESS",
            "decimals": 9,
        }
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
    
class SolanaTransferHelper:

    """Helper class for Solana token and SOL transfers."""

    @staticmethod
    def transfer_native_sol(agent: SolanaConnection, to: Pubkey, amount: float) -> str:
        """
        Transfer native SOL.

        Args:
            agent: SolanaAgentKit instance
            to: Recipient's public key
            amount: Amount of SOL to transfer

        Returns:
            Transaction signature.
        """
        connection = agent._get_connection()
        receiver=Pubkey.from_string(to)
        sender = agent._get_wallet()
        ix = transfer(
            TransferParams(
                from_pubkey=sender.pubkey(),to_pubkey=receiver,lamports=LAMPORTS_PER_SOL
            )
        )
        blockhash=connection.get_latest_blockhash().value.blockhash
        msg = MessageV0.try_compile(
            payer=sender.pubkey(),
            instructions=[ix],
            address_lookup_table_accounts=[],
            recent_blockhash=blockhash
        )
        tx= VersionedTransaction(msg,[sender])

        result = agent._get_connection().send_transaction(
            tx
        )

        return result.value

    @staticmethod
    def transfer_spl_tokens(
        rpc_client: Client,
        agent:SolanaConnection,
        recipient: Pubkey,
        spl_token: Pubkey,
        amount: float,
    ) -> str:
        """
        Transfer SPL tokens from payer to recipient.

        Args:
            rpc_client: Async RPC client instance.
            payer: Payer's public key (wallet address).
            recipient: Recipient's public key.
            spl_token: SPL token mint address.
            amount: Amount of tokens to transfer.

        Returns:
            Transaction signature.
        """
        connection = agent._get_connection()
        sender =agent._get_wallet()
        spl_client = Token(rpc_client, spl_token, TOKEN_PROGRAM_ID, sender.pubkey())
        
        mint = spl_client.get_mint_info()
        if not mint.is_initialized:
            raise ValueError("Token mint is not initialized.")

        token_decimals = mint.decimals
        if amount < 10 ** -token_decimals:
            raise ValueError("Invalid amount of decimals for the token.")

        tokens = math.floor(amount * (10 ** token_decimals))

        payer_ata = get_associated_token_address(sender.pubkey(), spl_token)
        recipient_ata = get_associated_token_address(recipient, spl_token)

        payer_account_info = spl_client.get_account_info(payer_ata)
        if not payer_account_info.is_initialized:
            raise ValueError("Payer's associated token account is not initialized.")
        if tokens > payer_account_info.amount:
            raise ValueError("Insufficient funds in payer's token account.")

        recipient_account_info = spl_client.get_account_info(recipient_ata)
        if not recipient_account_info.is_initialized:
            raise ValueError("Recipient's associated token account is not initialized.")

        transfer_instruction = transfer_checked(
            amount=tokens,
            decimals=token_decimals,
            program_id=TOKEN_PROGRAM_ID,
            owner=sender.pubkey(),
            source=payer_ata,
            dest=recipient_ata,
            mint=spl_token,
        )
        
        blockhash=connection.get_latest_blockhash().value.blockhash
        msg = MessageV0.try_compile(
            payer=sender.pubkey(),
            instructions=[transfer_instruction],
            address_lookup_table_accounts=[],
            recent_blockhash=blockhash
        )
        tx= VersionedTransaction(msg,[sender])

        result = agent._get_connection().send_transaction(
            tx
        )

        return result.value

    @staticmethod
    def confirm_transaction(agent: SolanaConnection, signature: str) -> None:
        """Wait for transaction confirmation."""
        agent._get_connection().confirm_transaction(signature, commitment=Confirmed)

def fetch_performance_samples(
    agent: SolanaConnection, sample_count: int = 1
) -> List[NetworkPerformanceMetrics]:
    """
    Fetch detailed performance metrics for a specified number of samples.

    Args:
        agent: An instance of SolanaAgent providing the RPC connection.
        sample_count: Number of performance samples to retrieve (default: 1).

    Returns:
        A list of NetworkPerformanceMetrics objects.

    Raises:
        ValueError: If performance samples are unavailable or invalid.
    """
    connection = agent._get_connection()
    try:
        performance_samples = connection.get_recent_performance_samples(sample_count)

        if not performance_samples:
            raise ValueError("No performance samples available.")

        return [
            NetworkPerformanceMetrics(
                transactions_per_second=sample["num_transactions"]
                / sample["sample_period_secs"],
                total_transactions=sample["num_transactions"],
                sampling_period_seconds=sample["sample_period_secs"],
                current_slot=sample["slot"],
            )
            for sample in performance_samples
        ]

    except Exception as error:
        raise ValueError(f"Failed to fetch performance samples: {str(error)}") from error
    
class SolanaPerformanceTracker:
    """
    A utility class for tracking and analyzing Solana network performance metrics.
    """

    def __init__(self, agent: SolanaConnection):
        self.agent = agent
        self.metrics_history: List[NetworkPerformanceMetrics] = []

    def record_latest_metrics(self) -> NetworkPerformanceMetrics:
        """
        Fetch the latest performance metrics and add them to the history.

        Returns:
            The most recent NetworkPerformanceMetrics object.
        """
        latest_metrics = fetch_performance_samples(self.agent, 1)
        self.metrics_history.append(latest_metrics[0])
        return latest_metrics[0]

    def calculate_average_tps(self) -> Optional[float]:
        """
        Calculate the average TPS from the recorded performance metrics.

        Returns:
            The average TPS as a float, or None if no metrics are recorded.
        """
        if not self.metrics_history:
            return None
        return sum(
            metric.transactions_per_second for metric in self.metrics_history
        ) / len(self.metrics_history)

    def find_maximum_tps(self) -> Optional[float]:
        """
        Find the maximum TPS from the recorded performance metrics.

        Returns:
            The maximum TPS as a float, or None if no metrics are recorded.
        """
        if not self.metrics_history:
            return None
        return max(metric.transactions_per_second for metric in self.metrics_history)

    def reset_metrics_history(self) -> None:
        """Clear all recorded performance metrics."""
        self.metrics_history.clear()
    
    def fetch_current_tps(agent: SolanaConnection) -> float:
        """
        Fetch the current Transactions Per Second (TPS) on the Solana network.

        Args:
            agent: An instance of SolanaAgent providing the RPC connection.

        Returns:
            Current TPS as a float.

        Raises:
            ValueError: If performance samples are unavailable or invalid.
        """
        connection = agent._get_connection()
        try:
            response =  connection.get_recent_performance_samples(1)

            performance_samples = response.value
            # logger.info("Performance Samples:", performance_samples)

            if not performance_samples:
                raise ValueError("No performance samples available.")

            sample = performance_samples[0]

            if not all(
                hasattr(sample, attr)
                for attr in ["num_transactions", "sample_period_secs"]
            ) or sample.num_transactions <= 0 or sample.sample_period_secs <= 0:
                raise ValueError("Invalid performance sample data.")

            return sample.num_transactions / sample.sample_period_secs

        except Exception as error:
            raise ValueError(f"Failed to fetch TPS: {str(error)}") from error
        
class TradeManager:
    @staticmethod
    async def _trade(
        agent: SolanaConnection,
        output_mint: Pubkey,
        input_amount: float,
        input_mint: Pubkey,
        slippage_bps: int,
    ) -> str:
        """
        Swap tokens using Jupiter Exchange.

        Args:
            agent (SolanaAgentKit): The Solana agent instance.
            output_mint (Pubkey): Target token mint address.
            input_amount (float): Amount to swap (in token decimals).
            input_mint (Pubkey): Source token mint address (default: USDC).
            slippage_bps (int): Slippage tolerance in basis points (default: 300 = 3%).

        Returns:
            str: Transaction signature.

        Raises:
            Exception: If the swap fails.
        """
        wallet = agent._get_wallet()
        async_client = agent._get_connection_async()
        jupiter = agent._get_jupiter(wallet,async_client)
        # convert wallet.secret() from bytes to string
        input_mint = str(input_mint)
        output_mint = str(output_mint)
        input_amount: int = int(input_amount * 10 ** DEFAULT_OPTIONS["TOKEN_DECIMALS"])

        try:
            transaction_data = await jupiter.swap(
                input_mint,
                output_mint,
                input_amount,
                slippage_bps=slippage_bps,
            )
            raw_transaction = VersionedTransaction.from_bytes(base64.b64decode(transaction_data))
            signature = wallet.sign_message(message.to_bytes_versioned(raw_transaction.message))
            signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])
            opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
            result = await async_client.send_raw_transaction(txn=bytes(signed_txn), opts=opts)
            transaction_id = json.loads(result.to_json())['result']
            print(f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}")
            return str(signature)

        except Exception as e:
            raise Exception(f"Swap failed: {str(e)}")
        
class StakeManager:
    @staticmethod
    async def stake_with_jup(agent: SolanaConnection, amount: float) -> str:
        
        connection = agent._get_connection_async()
        wallet = agent._get_wallet()
        try:

            url = f"https://worker.jup.ag/blinks/swap/So11111111111111111111111111111111111111112/jupSoLaHXQiZZTSfEWMTRRgpnyFm8f6sZdosWBjx93v/{amount}"
            payload = {"account": str(wallet.pubkey())}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as res:
                    if res.status != 200:
                        raise Exception(f"Failed to fetch transaction: {res.status}")

                    data = await res.json()

            raw_transaction = VersionedTransaction.from_bytes(base64.b64decode(data["transaction"]))
            signature = wallet.sign_message(message.to_bytes_versioned(raw_transaction.message))
            signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])
            opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
            result = await connection.send_raw_transaction(txn=bytes(signed_txn), opts=opts)
            transaction_id = json.loads(result.to_json())['result']
            print(f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}")
            return str(signature)

        except Exception as e:
            raise Exception(f"jupSOL staking failed: {str(e)}") 
        
class AssetLender:
    @staticmethod
    async def lend_asset(agent: SolanaConnection, amount: float) -> str:
        wallet = agent._get_wallet()
        async_client = agent._get_connection_async()
        try:
            url = f"https://blink.lulo.fi/actions?amount={amount}&symbol=USDC"
            headers = {"Content-Type": "application/json"}
            payload = json.dumps({"account": str(wallet.pubkey())})

            session = aiohttp.ClientSession()

            async with session.post(url, headers=headers, data=payload) as response:
                if response.status != 200:
                    raise Exception(f"Lulo API Error: {response.status}")
                data = await response.json()
                logger.debug(f"Lending data: {data}")
            transaction_data = base64.b64decode(data["transaction"])
            raw_transaction = VersionedTransaction.from_bytes(transaction_data)
            signature = wallet.sign_message(message.to_bytes_versioned(raw_transaction.message))
            signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])
            opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
            result = await async_client.send_raw_transaction(txn=bytes(signed_txn), opts=opts)
            transaction_id = json.loads(result.to_json())['result']
        
            print(f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}")
            return str(signature)

        except Exception as e:
            raise Exception(f"Lending failed: {str(e)}")

class FaucetManager:
    @staticmethod
    async def request_faucet_funds(agent: SolanaConnection) -> str:
        """
        Request SOL from the Solana faucet (devnet/testnet only).

        Args:
            agent: An object with `connection` (AsyncClient) and `wallet_address` (str).

        Returns:
            str: The transaction signature.

        Raises:
            Exception: If the request fails or times out.
        """
        wallet = agent._get_wallet()
        async_client = agent._get_connection_async()
        try:
            print(f"Requesting faucet for wallet: {repr(wallet.pubkey())}")

            response = await async_client.request_airdrop(
                wallet.pubkey(), 5 * LAMPORTS_PER_SOL
            )

            latest_blockhash = await async_client.get_latest_blockhash()
            await async_client.confirm_transaction(
                response.value,
                commitment=Confirmed,
                last_valid_block_height=latest_blockhash.value.last_valid_block_height
            )

            print(f"Airdrop successful, transaction signature: {response.value}")
            return response.value
        except KeyError:
            raise Exception("Airdrop response did not contain a transaction signature.")
        except Exception as e:
            raise Exception(f"An error occurred: {str(e)}")