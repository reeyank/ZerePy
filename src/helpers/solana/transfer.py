import math
from venv import logger
from src.constants import LAMPORTS_PER_SOL

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.system_program import TransferParams, transfer
from solders.transaction import VersionedTransaction  # type: ignore
from solders.message import MessageV0  # type: ignore

from spl.token.async_client import AsyncToken
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address, transfer_checked
from spl.token.instructions import TransferCheckedParams
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from spl.token.instructions import (
    get_associated_token_address,
    transfer_checked,
    TransferCheckedParams,
)
from spl.token.constants import TOKEN_PROGRAM_ID
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price  # type: ignore
import asyncio


class SolanaTransferHelper:
    """Helper class for Solana token and SOL transfers."""

    @staticmethod
    async def transfer(
        async_client: AsyncClient,
        wallet: Keypair,
        to: str,
        amount: float,
        spl_token: str = None,
    ) -> str:
        """
        Transfer SOL or SPL tokens.

        Args:
            async_client: Async RPC client instance.
            wallet: Sender's wallet keypair.
            to: Recipient's public key.
            amount: Amount of tokens to transfer.
            spl_token: SPL token mint address (default: None).

        Returns:
            Transaction signature.
        """
        to = Pubkey.from_string(to)
        try:
            if spl_token:
                signature = await SolanaTransferHelper._transfer_spl_tokens(
                    async_client,
                    wallet,
                    to,
                    Pubkey.from_string(spl_token),
                    amount,
                )
                token_identifier = str(spl_token)
            else:
                signature = await SolanaTransferHelper._transfer_native_sol(
                    async_client, wallet, to, amount
                )
                token_identifier = "SOL"
            await SolanaTransferHelper._confirm_transaction(async_client, signature)

            logger.debug(
                f"\nSuccess!\n\nSignature: {signature}\nFrom Address: {str(wallet.pubkey())}\nTo Address: {to}\nAmount: {amount}\nToken: {token_identifier}"
            )

            return signature

        except Exception as error:

            logger.error(f"Transfer failed: {error}")
            raise RuntimeError(f"Transfer operation failed: {error}") from error

    @staticmethod
    async def _transfer_native_sol(
        async_client: AsyncClient, wallet: Keypair, to: Pubkey, amount: float
    ) -> str:
        """
        Transfer native SOL.

        Args:
            agent: SolanaAgentKit instance
            to: Recipient's public key
            amount: Amount of SOL to transfer

        Returns:
            Transaction signature.
        """
        sender = wallet
        receiver = Pubkey.from_string(to)
        ix = transfer(
            TransferParams(
                from_pubkey=sender.pubkey(),
                to_pubkey=receiver,
                lamports=LAMPORTS_PER_SOL,
            )
        )
        blockhash = (await async_client.get_latest_blockhash()).value.blockhash
        msg = MessageV0.try_compile(
            payer=sender.pubkey(),
            instructions=[ix],
            address_lookup_table_accounts=[],
            recent_blockhash=blockhash,
        )
        tx = VersionedTransaction(msg, [sender])

        result = await async_client.send_transaction(tx)

        return result.value

    @staticmethod
    async def _transfer_spl_tokens(
        async_client: AsyncClient,
        wallet: Keypair,
        recipient: Pubkey,
        spl_token: Pubkey,
        amount: float,
    ) -> str:
        """
        Transfer SPL tokens from payer to recipient.

        Args:
            async_client: Async RPC client instance.
            payer: Payer's public key (wallet address).
            recipient: Recipient's public key.
            spl_token: SPL token mint address.
            amount: Amount of tokens to transfer.

        Returns:
            Transaction signature.
        """

        compute_unit_limit = 10_000
        compute_unit_price = 1_000_000
        connection = async_client
        keypair = wallet
        token_mint = spl_token
        spl_client = AsyncToken(
            connection, spl_token, TOKEN_PROGRAM_ID, keypair.pubkey()
        )
        mint = await spl_client.get_mint_info()
        decimals = mint.decimals
        amount = math.floor(amount * 10**decimals)
        sender_token_address = get_associated_token_address(keypair.pubkey(), spl_token)
        recipient_token_address = get_associated_token_address(recipient, spl_token)
        blockhash_resp = await connection.get_latest_blockhash()
        recent_blockhash = blockhash_resp.value.blockhash

        ixs = []
        # if compute_unit_limit > 0:
        #    ixs.append(set_compute_unit_limit(compute_unit_limit))
        # if compute_unit_price > 0:
        #    ixs.append(set_compute_unit_price(compute_unit_price))
        # log all transfer params
        logger.debug(f"\nAmount: {amount}")
        logger.debug(f"\nSender Token Address: {sender_token_address}")
        logger.debug(f"\nRecipient Token Address: {recipient_token_address}")
        logger.debug(f"\nOwner: {keypair.pubkey()}")
        logger.debug(f"\nMint: {token_mint}")
        logger.debug(f"\nDecimals: {decimals}")
        logger.debug(f"\nProgram ID: {TOKEN_PROGRAM_ID}")

        ixs.append(
            transfer_checked(
                TransferCheckedParams(
                    source=sender_token_address,
                    dest=recipient_token_address,
                    owner=keypair.pubkey(),
                    mint=token_mint,
                    amount=amount,
                    decimals=decimals,
                    program_id=TOKEN_PROGRAM_ID,
                )
            )
        )
        blockhash = (await async_client.get_latest_blockhash()).value.blockhash
        msg = MessageV0.try_compile(
            payer=wallet.pubkey(),
            instructions=ixs,
            address_lookup_table_accounts=[],
            recent_blockhash=blockhash,
        )
        tx = VersionedTransaction(msg, [wallet])

        result = await async_client.send_transaction(tx)

        return result.value

    @staticmethod
    async def _confirm_transaction(async_client: AsyncClient, signature: str) -> None:
        """Wait for transaction confirmation."""
        async_client.confirm_transaction(signature, commitment=Confirmed)
