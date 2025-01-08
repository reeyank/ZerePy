import math

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


class SolanaTransferHelper:
    """Helper class for Solana token and SOL transfers."""

    @staticmethod
    async def transfer_native_sol(
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
        blockhash = await async_client.get_latest_blockhash().value.blockhash
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
    async def transfer_spl_tokens(
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
        sender = wallet
        spl_client = AsyncToken(
            async_client, spl_token, TOKEN_PROGRAM_ID, sender.pubkey()
        )

        mint = await spl_client.get_mint_info()
        if not mint.is_initialized:
            raise ValueError("Token mint is not initialized.")

        token_decimals = mint.decimals
        if amount < 10**-token_decimals:
            raise ValueError("Invalid amount of decimals for the token.")

        tokens = math.floor(amount * (10**token_decimals))

        payer_ata = get_associated_token_address(sender.pubkey(), spl_token)
        recipient_ata = get_associated_token_address(recipient, spl_token)

        payer_account_info = await spl_client.get_account_info(payer_ata)
        if not payer_account_info.is_initialized:
            raise ValueError("Payer's associated token account is not initialized.")
        if tokens > payer_account_info.amount:
            raise ValueError("Insufficient funds in payer's token account.")

        recipient_account_info = await spl_client.get_account_info(recipient_ata)
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

        blockhash = (await async_client.get_latest_blockhash()).value.blockhash
        msg = MessageV0.try_compile(
            payer=sender.pubkey(),
            instructions=[transfer_instruction],
            address_lookup_table_accounts=[],
            recent_blockhash=blockhash,
        )
        tx = VersionedTransaction(msg, [sender])

        result = await async_client.send_transaction(tx)

        return result.value

    @staticmethod
    async def confirm_transaction(async_client: AsyncClient, signature: str) -> None:
        """Wait for transaction confirmation."""
        async_client.confirm_transaction(signature, commitment=Confirmed)
